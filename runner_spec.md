# ProcVision 平台侧 SDK Runtime（Runner）规范

目标：定义平台侧 Runner 与算法包之间的运行协议、生命周期管理、数据通道、错误与重试策略，确保与当前算法 SDK 完全对齐并可生产落地。

## 总览
- 职责：
  - 进程管理：按 `manifest.entry_point` 启动算法子进程，维护生命周期（setup/teardown/重启）。
  - 通信协议：通过 `stdin/stdout` 进行 JSON 帧通信，长度前缀封包，`stderr` 用于结构化日志。
  - 资源分配：共享内存写入图像，分配 `shared_mem_id` 与注入 `image_meta`。
  - 调度执行：按工艺步骤触发 `pre_execute` 与 `execute` 调用，`step_index` 从 1 开始。
  - 状态与会话：创建并注入 `Session`（`id/context`），在单次检测流程内维持 KV 状态。
  - 健壮性：心跳保活、超时与重试、异常分类处理、错误码对齐。

## 启动与握手
- 启动：按 `manifest.entry_point` 生成 Python 命令行：`python -m <module>` 或 `python <file>`。
- 环境：工作目录为算法包根；注入必要的环境变量（如 `PROC_ENV=prod`）。
- 握手：
  - 算法启动后在 `stdout` 输出：`{"type":"hello","sdk_version":"1.0"}`。
  - Runner 接收后在 2s 内回复：`{"type":"hello","runner_version":"1.0"}`，完成握手。

## 通信协议
- 帧格式：`[4字节大端长度][UTF-8 JSON]`。
- 通道：
  - `stdout`：算法结果与协议消息（hello/pong/result）。
  - `stdin`：Runner 指令（hello/ping/call/stop）。
  - `stderr`：结构化日志（JSON 行或文本）。
- 心跳：
  - Runner 每 5s 发送：`{"type":"ping"}`。
  - 算法需在 2s 内回复：`{"type":"pong"}`；超时累计达阈值后执行重启策略。

## 调用模型
- 指令：`call`
```
{
  "type": "call",
  "step_index": 1,
  "pid": "A01",
  "session": {"id": "sid-123", "context": {"product_code": "A01", "trace_id": "..."}},
  "user_params": {"threshold": 0.7},
  "shared_mem_id": "dev-shm:sid-123",
  "image_meta": {"width": 1920, "height": 1200, "timestamp_ms": 1714032000123, "camera_id": "cam-01"},
  "phase": "pre" | "execute"
}
```
- 响应：`result`
```
{
  "type": "result",
  "phase": "pre" | "execute",
  "status": "OK" | "ERROR",
  "message": "...",
  "error_code": "1001" | "...",
  "data": {
    "result_status": "OK" | "NG",
    "ng_reason": "...",
    "defect_rects": [{"x":...,"y":...,"width":...,"height":...,"label":"...","score":0.85}],
    "position_rects": [{"x":...,"y":...,"width":...,"height":...,"label":"..."}],
    "calibration_rects": [{"x":...,"y":...,"width":...,"height":...,"label":"..."}],
    "debug": {"latency_ms": 25.3, "model_version": "..."}
  }
}
```
- 约束：
  - `pre` 阶段不返回业务判定；可返回 `calibration_rects` 与提示信息。
  - `execute` 阶段业务判定在 `data.result_status`；NG 时需提供 `ng_reason/defect_rects`。
  - `step_index` 从 1 开始。

## 包扫描与部署流程（与 PID 无关）
- 目标：Runner 在不依赖 PID 的前提下完成算法包的发现、校验、部署与运行态准备。
- 扫描：周期性或按请求扫描 `algorithms/zips/` 目录，识别新增离线包。
- 校验：对未部署的 zip 执行结构校验与入口校验（等价 `validate`）；不通过的标记为 `invalid` 并记录原因。
- 部署：将校验通过的 zip 解压到 `algorithms/deployed/<name>/<version>/`，创建隔离 `venv/` 并仅使用 `wheels/` 安装依赖。
- 预热：完成部署后可按前端请求或策略预启动子进程并完成握手，进入 `running` 态（可接受后续 `pre/execute` 调用）。

## 运行态与执行态
- 运行态（running）：包已部署并进程握手完成，具备心跳与日志输出；尚未绑定具体 PID。
- 执行态（executing）：前端或上层流程传入 `pid` 与图像等上下文，Runner 进入具体一步的 `pre/execute` 调用；算法侧在收到 `pid` 后自行校验是否包含于 `supported_pids`。
- 流程：
  - 前端启动包 → Runner 预热并进入 `running` 态。
  - 前端触发检测 → Runner 注入 `pid/session/user_params/shared_mem_id/image_meta/step_index` 并执行 `pre/execute`。
  - 执行完成 → 返回 `result` 帧；保持进程常驻以复用。

## 前端交互（包管理与运行）
- 列表：枚举 `algorithms/zips` 与 `algorithms/deployed`，提供包信息（name/version/state）。
- 启动：请求指定包 `name/version` → Runner 部署并预热，进入 `running` 态。
- 停止：停止指定包的进程，保持已部署状态；可重新启动。
- 执行：针对已启动的包，传入 `pid` 与输入，进入 `pre/execute` 调用链并返回结果。

## 钩子执行语义（Runner 责任）
- setup/teardown：由算法侧在进程生命周期内自行调用；Runner 保障进程常驻与优雅关闭。
- on_step_start/on_step_finish：Runner 在每次调用 `pre/execute` 的步骤边界触发（内部事件），用于统计与日志。
- reset：在需要重置流程时触发（如人工重试或流程重置），由 Runner 发送 `call` 指令类型 `reset` 或在下一次 `pre` 前置标记，算法侧执行清理。

## 状态机（文件系统驱动）
- discovered → validated → deployed → running → executing → running
- invalid：校验失败（不可部署）；记录原因并待人工处理。
- stopped：进程停止（仍已部署）；可恢复到 `running`。

## 共享内存
- 写入：平台侧将输入图像编码为 JPEG/PNG，并写入共享内存；生成 `shared_mem_id`。
- 元信息：注入最小集合 `width/height/timestamp_ms/camera_id`；尺寸需与实际一致。
- 读入：算法使用 SDK 的 `read_image_from_shared_memory(shared_mem_id, image_meta)` 获取 `numpy.ndarray (H x W x 3)`。

## 会话与状态
- Runner 负责生成 `Session`（`id/context`），并在一次检测流程内保存 KV（由算法侧调用 `session.get/set/delete/exists`）。
- 会话生命周期：
  - 绑定一次检测流程；流程结束后销毁或归档（根据业务需要）。

## 生命周期管理
- 钩子支持：算法内部 `setup/teardown/on_step_start/on_step_finish/reset`，Runner 不直接调用，但以步骤边界事件驱动（如在 `pre` 前后触发 `on_step_start/on_step_finish`）。
- 超时：
  - `pre_execute_timeout_ms`、`execute_timeout_ms` 可配置；超时后标记调用失败并执行重试或终止。
- 重试策略：
  - 可配置最大重试次数（如 2）；在 `RecoverableError/timeout/ping超时` 情况下重试；`FatalError` 直接终止并重启进程。
- 进程管理：
  - 心跳丢失或错误累计超阈值时，优雅终止并重启算法进程；保留最近 N 次日志。

## 错误码与处理
- 标准错误码（与 SDK 对齐）：
  - `1001` invalid_pid
  - `1002` image_load_failed
  - `1003` model_not_found
  - `1004` gpu_oom
  - `1005` timeout
  - `1006` invalid_params
  - `1007` coordinate_invalid
  - `9999` unknown_error
- 处理策略：
  - UI 提示与运维记录：展示 `message/error_code`。
  - 可重试错误（如 `1005/部分 1006`）：按策略重试。
  - 不可重试错误（如 `1003/1004/FatalError`）：标记流程失败，允许人工干预。

## 日志与诊断
- `stderr`：算法输出结构化日志（建议 JSON 行），字段包含 `timestamp_ms/level/message/step_index/...`。
- 采集：Runner 聚合 `stderr` 与 `debug` 字段信息，按检测流程归档。

## 安全与资源
- 访问边界：算法运行在受限环境，无外网访问；Runner 不向算法下发机密信息。
- 资源限制：为算法进程设置 CPU/GPU/内存限制（可选，用于容器化部署）。

## 配置项（示例）
```
runner_config.json
{
  "pre_execute_timeout_ms": 3000,
  "execute_timeout_ms": 5000,
  "heartbeat_interval_ms": 5000,
  "heartbeat_grace_ms": 2000,
  "max_retries": 2,
  "log_level": "info",
  "save_debug_fields": ["latency_ms","model_version"],
  "shared_memory_backend": "native",
  "image_encoding": "jpeg",
  "max_defects": 20
}
```

## 验收标准
- 协议一致：hello/ping/pong/call/result 行为与字段严格符合规范。
- 索引与判定：`step_index` 从 1；`pre_execute` 不返回判定；`execute` 的业务判定在 `data.result_status`。
- 共享内存：图像读写稳定且与 `image_meta` 一致；越界与数量约束（如 `defect_rects<=20`）被严格校验。
- 超时与重试：在配置范围内工作，错误码处理一致。
- 日志采集：结构化日志与 `debug` 字段可被聚合并检索。
- 健壮性：在进程异常与心跳丢失场景下可自动重启并恢复服务。

## 参考实现建议
- 语言：Python/C++/Go 皆可；建议 Python 首版以降低集成成本。
- 模块化：通信、心跳、共享内存、调度、日志分别为独立模块；可替换共享内存后端。
- 测试：
  - 单元测试：帧协议编解码、心跳与超时、错误码映射。
  - 集成测试：与示例算法包端到端跑通两步骤，覆盖 OK/NG/ERROR。

---

以上为 Runner 规范草案，已对齐 SDK 当前接口与约束，满足生产落地的稳定性与可维护性。建议先按该规范完成架构设计与 PoC，实现通信/心跳/调用与错误处理四大模块的核心功能后，再完善共享内存与日志采集细节。

## 算法包管理（新增）
- 目标：提供离线算法包的安装、校验、激活、切换与回滚能力，确保与生产环境版本一致性与可控性。

**包格式与来源**
- 输入为离线 zip 包（由 `procvision-cli package` 生成）：包含源码目录、`manifest.json`、`requirements.txt`、`wheels/` 与可选 `assets/`。
- 禁止在线拉取依赖；仅使用包内 `wheels/`。

**安装流程**
1. 校验：
   - 打开 zip 并检查必须文件是否存在（`manifest.json`、`requirements.txt`、`wheels/`）。
   - 运行 SDK 校验（等价 `validate`）：入口导入、`supported_pids` 一致性、`get_info` 返回结构等。
2. 展开：
   - 解压到 Runner 的 `runtime_store/algorithms/<name>/<version>/`。
3. 环境构建：
   - 创建隔离虚拟环境 `venv/`；仅使用 `wheels/` 安装（`pip install --no-index --find-links ./wheels -r requirements.txt`）。
   - 兼容性检查：确保 `python_version` 与 `abi` 与包内 wheels 一致（建议读取 `.procvision_env.json` 如存在，或根据 wheels 文件名推断）。
4. 注册：
   - 写入注册表 `runtime_store/registry.json`：`{ name, version, supported_pids, state: installed, created_at }`。

**激活/切换**
- 激活：将 `algorithms/<name>/<version>` 绑定到指定 `pid` 或工位范围：
  - 写入 `runtime_store/active/<pid>.json`：`{ name, version, activated_at }`。
  - 校验：目标包的 `supported_pids` 必须包含该 `pid`。
- 切换：
  - 支持零停机切换：预启动新版本进程，完成握手后在下一个检测周期切换映射；旧进程完成在途任务后结束。
- 回滚：
  - 选择历史版本重新激活；保留最近 N 个版本（可配置，如 3）。

**卸载**
- 前置：若包处于激活状态需先解除绑定，或执行“安全卸载”（等待当前进程任务完成后卸载）。
- 操作：删除 `algorithms/<name>/<version>` 目录与注册记录；保留日志与审计信息。

**注册表与存储布局**
```
runtime_store/
  algorithms/
    zips/                 # 原始离线包存储（只读归档）
      <name>-v<version>-offline.zip
    deployed/             # 解压后的可运行包
      <name>/
        <version>/
          src/...         # 源码（保持原目录结构）
          manifest.json
          requirements.txt
          wheels/
          assets/
          venv/           # 该包的隔离环境（--no-index 仅用 wheels 安装）
  active/
    <pid>.json            # 当前激活的包映射
  registry.json           # 所有包的安装记录与元信息
  logs/
    package_install.log
    package_activate.log
```

**文件系统管理约定**
- 根路径：默认为 Runner 运行路径下 `algorithms/`，可配置。
- 归档：所有离线 zip 放置于 `algorithms/zips/`；安装流程从该目录选取包源。
- 部署：解压到 `algorithms/deployed/<name>/<version>/`；虚拟环境位于该版本目录下 `venv/`。
- 激活：`active/<pid>.json` 指向 `name/version`；动态加载按该映射寻找进程与包目录。
- 回滚：保留最近 N 个版本（可配置）；直接切换 `active` 映射并预热新版本。
- 清理：可配置保留策略，对 `zips` 与 `deployed` 超出阈值的旧版本进行归档/删除。
- 并发：安装/卸载/激活操作使用锁文件 `algorithms/.lock` 或版本级锁 `algorithms/deployed/<name>/<version>/.lock` 避免竞争。

**文件系统驱动的安装流程**
- 放置：将 zip 文件复制到 `algorithms/zips/`。
- 校验：Runner 扫描 `zips/` 目录或按用户请求定位 zip，执行离线包结构与入口校验（等价 `validate`）。
- 展开：解压到 `deployed/<name>/<version>/`；创建 `venv/` 并安装依赖（仅使用 `wheels/`）。
- 注册：更新 `registry.json` 记录安装状态与元信息。
- 激活：写入 `active/<pid>.json`；预热进程并完成握手。

**动态加载与路由（文件系统版）**
- 路由查找：收到请求后读取 `active/<pid>.json` → `name/version` → `deployed/<name>/<version>/`。
- 进程启动：使用对应版本目录下 `venv/python` 与 `manifest.entry_point` 启动算法进程。
- 复用与切换：常驻进程复用；切换版本时先预热新版本，再在下一周期路由到新版本，旧版优雅退出。

**API/CLI（平台侧与运维用）**
- 安装：`POST /algorithms/install`（body: zip 路径或上传流）
- 激活：`POST /algorithms/activate`（name, version, pid[]）
- 切换：`POST /algorithms/switch`（name, version, pid[]）
- 卸载：`DELETE /algorithms/{name}/{version}`（若激活则拒绝或要求 `force=true`）
- 查询：`GET /algorithms`（支持过滤 `state`、`name`）、`GET /algorithms/active`（pid→包映射）
- 校验：`POST /algorithms/validate`（name, version）—触发 SDK 校验并返回报告

**错误码（包管理专用 2xxx）**
- 2001 invalid_zip（zip 文件损坏或缺失必要文件）
- 2002 manifest_missing（缺少 manifest.json）
- 2003 incompatible_python（Python/ABI 与 wheels 不匹配）
- 2004 wheels_missing（缺少 wheels 目录或关键依赖）
- 2005 install_failed（安装失败，见 message）
- 2006 activation_conflict（PID 已绑定其他包或不在 supported_pids 中）
- 2007 unsafe_uninstall（包处于激活或正在使用）

**安全与审计**
- 可选签名校验：若 zip 包附带 `SIGNATURE` 与公钥，Runner 在安装前进行签名验证。
- 可选哈希校验：对 `wheels/` 与 `requirements.txt` 中声明的哈希进行一致性检查；策略可配置（strict/lenient）。
- 审计日志：安装/激活/切换/卸载均记录操作者与时间戳，便于追溯。

**兼容与策略**
- Python 与 ABI：Runner 在部署时固定目标版本（如 Python 3.10 / cp310）；包安装时必须与目标一致。
- 多版本保留：每个算法保留最近 N 个版本；超过阈值自动归档或提示清理。
- 并发与锁：包管理操作加互斥锁；安装/卸载与运行互斥或使用“安全卸载”策略。

**验收补充（包管理）**
- 离线包安装成功并可在注册表中查询；激活后 PID 映射正确、进程可用。
- 切换与回滚在生产环境中无中断（或在可接受窗口内切换），日志完整可查。
- 安全策略生效：签名/哈希策略按配置执行；操作审计可检索。