# 协议适配器设计与开发规范（SDK内置，Runner 集成版）

## 1. 目标与范围
- 目标：提供统一的“协议适配器（launcher/server）”在算法子进程中运行，负责协议通信、心跳保活、消息路由、状态管理与资源管控；算法包仅实现业务方法。
- 范围：适配器运行在算法包的专属 `venv` 解释器下，通过 `stdin/stdout/stderr` 与 Python 桌面程序的 Runner 模块通信，严格对齐 SDK 与 Runner 规范。

## 2. 术语与角色
- 工作站桌面程序（主进程）：Python 应用的整体进程，包含 Runner 模块。
- Runner（主进程模块）：管理算法包生命周期（部署、启动、停止、重启），与适配器通信，负责心跳与超时、共享内存写入、日志聚合与结果展示。
- 协议适配器（子进程，SDK内置）：加载 `manifest.entry_point` 指定算法类，完成握手、心跳响应、帧编解码、消息路由与状态机执行，调用 `get_info/pre_execute/execute` 并返回 `result` 帧。
- 算法包（业务层）：实现 `BaseAlgorithm` 三大方法与可选钩子（`setup/teardown/on_step_start/on_step_finish/reset`）。

## 3. 进程与环境隔离
- 独立 `venv`：按版本部署到 `algorithms/deployed/<name>/<version>/venv/`。
- 启动命令：在该 `venv` 下运行适配器。
  - Windows：`<deployed_dir>\venv\Scripts\python.exe -m procvision_algorithm_sdk.adapter --entry "<module:Class>"`
  - Linux：`<deployed_dir>/venv/bin/python -m procvision_algorithm_sdk.adapter --entry "<module:Class>"`
- 简化启动命令：适配器支持自动发现 `manifest.entry_point`，可省略 `--entry`。
  - Windows：`<deployed_dir>\venv\Scripts\python.exe -m procvision_algorithm_sdk.adapter`
  - Linux：`<deployed_dir>/venv/bin/python -m procvision_algorithm_sdk.adapter`
- 工作目录：设为算法包根目录，确保相对路径与资源可用。
- 常用环境变量：`PROC_ENV=prod`、`PROC_ALGO_ROOT=<deployed_dir>`、`PROC_SESSION_ID=<id>`。

## 4. 通信通道与帧协议
- 通道职责：
  - `stdin`：Runner → 适配器（`hello/ping/call/shutdown`）。
  - `stdout`：适配器 → Runner（`hello/pong/result/shutdown/error`）。
  - `stderr`：结构化日志（JSON Lines 或文本，不混入协议帧）。
- 帧格式：`[4字节大端长度][UTF-8 JSON]`，长度为 JSON 字节长度，禁止分片或多条拼接。
- 编码约束：JSON 遵循 RFC 8259；时间统一用毫秒 `timestamp_ms`；所有字符串为 UTF-8。
- 统一消息字段：
  ```json
  {
    "type": "hello|call|result|ping|pong|error|shutdown",
    "request_id": "uuid-1234",
    "timestamp_ms": 1714032000123,
    "status": "OK|ERROR",
    "message": "...",
    "data": { }
  }
  ```
- 关联规则：`result.request_id == call.request_id`；`phase` 在 `call.data.phase` 中指定，`result.data.phase` 原样回传。
- 建议最大帧大小：≤ 2 MiB；超限由 Runner 记录并返回错误。

## 5. 握手与版本协商
- 适配器启动后立即输出：
  ```json
  {"type":"hello","sdk_version":"1.0","capabilities":["ping","call","shutdown","shared_memory:v1"]}
  ```
- Runner 回应：
  ```json
  {"type":"hello","runner_version":"1.0","heartbeat_interval_ms":5000,"heartbeat_grace_ms":2000}
  ```
- 版本与能力协商：若能力不匹配，Runner 发送 `error` 并优雅关闭；适配器记录并退出。

## 6. 心跳与保活
- 策略：Runner 定期发送 `ping`，适配器在超时前回复 `pong`。
- 推荐参数：`heartbeat_interval_ms=5000`、`heartbeat_grace_ms=2000`、`max_retries=2`。
- 自适应：高频业务调用期间可以降低心跳频率；空闲时恢复。
- 超时：连续丢失心跳达到重试上限时，Runner 负责重启子进程；适配器保持幂等清理。

## 7. 调用模型与状态机
- `call` 示例：
  ```json
  {
    "type": "call",
    "request_id": "uuid-req-1",
    "data": {
      "phase": "pre|execute",
      "step_index": 1,
      "pid": "A01",
      "session": {"id":"sid-123","context":{"product_code":"A01","trace_id":"..."}},
      "user_params": {"threshold":0.7},
      "shared_mem_id": "shm:sid-123",
      "image_meta": {"width":1920,"height":1200,"timestamp_ms":1714032000123,"camera_id":"cam-01","color_space":"RGB"}
    }
  }
  ```
- 适配器路由：
  - `phase=pre` → `pre_execute(...)`，用于前置准备与参数校验，不返回业务判定。
  - `phase=execute` → `execute(...)`，返回业务判定与输出。
- 状态机（串行单并发）：`Idle → RunningPre → Idle → RunningExec → Idle → ShuttingDown`。
- 并发规则：默认 `max_inflight=1`，收到并发 `call` 时后续请求按到达顺序排队或返回错误（由 Runner 配置策略）。

## 8. 共享内存约定
- Runner 写入：
  - 压缩字节：JPEG/PNG（零拷贝，节省内存）。
  - 数组：`numpy.ndarray (H×W×3, uint8)`，默认 `RGB`；`Mono8` 扩展为 3 通道。
- 元信息最小集：`width`、`height`、`timestamp_ms`、`camera_id`；可选 `color_space: RGB|BGR`（默认 `RGB`）。
- 读取（算法侧）：`read_image_from_shared_memory(shared_mem_id, image_meta)` 同时兼容字节与数组；当 `color_space=BGR` 自动转换为 `RGB`。
- 写入（算法侧）：`write_image_array_to_shared_memory(shared_mem_id, array)` 用于调试回写或中间结果。

## 9. 结果与错误
- `result` 示例（执行阶段）：
  ```json
  {
    "type": "result",
    "request_id": "uuid-req-1",
    "status": "OK",
    "message": "",
    "data": {
      "phase": "execute",
      "step_index": 1,
      "latency_ms": 32,
      "result_status": "OK|NG|ERROR",
      "outputs": {"bbox":[],"score":0.91},
      "debug": {"heatmap_id":"shm:sid-123:hm1"}
    }
  }
  ```
- 错误码（建议集合）：
  - `1000 unknown_error`
  - `1001 invalid_pid`
  - `1002 image_load_failed`
  - `1003 invalid_params`
  - `1004 not_initialized`
  - `1005 timeout`
  - `1006 heartbeat_lost`
  - `1007 shared_memory_not_found`
  - `1008 unsupported_color_space`
  - `1009 execute_exception`
- 错误帧返回：`status="ERROR"`，必须包含 `message` 与 `error_code`，必要时附带 `data` 说明。

## 10. 结构化日志与诊断
- 输出到 `stderr`，采用 JSON Lines：每行一个完整 JSON，不与协议帧混合。
- 推荐字段：`level|timestamp_ms|message|step_index|pid|session_id|latency_ms|model_version|extra`。
- 示例：
  ```json
  {"level":"INFO","timestamp_ms":1714032000123,"message":"execute start","step_index":1,"pid":"A01","session_id":"sid-123"}
  ```
- 业务调试：随 `result.data.debug` 返回，供 UI 展示与远程排查。

## 11. 关闭与恢复
- 正常关闭：Runner 发送 `{"type":"shutdown"}`，适配器调用算法 `teardown()` 并回传确认后退出。
- 异常恢复：心跳丢失、超时或崩溃由 Runner 负责重试与重启；适配器确保幂等清理（释放句柄、共享内存引用、线程/异步任务）。

## 12. 配置与启动参数
- 命令行参数（建议）：
  - `--entry <module:Class>` 指定算法入口类。
  - `--log-level <debug|info|warn|error>` 控制日志粒度。
  - `--heartbeat-interval-ms <int>` 与 `--heartbeat-grace-ms <int>` 心跳配置。
  - `--color-space-default <RGB|BGR>` 默认颜色空间。
- 平台差异：见第 3 节 Windows/Linux 启动命令。

- 入口自动发现规则（优先级从高到低）：
  - 命令行：`--entry <module:Class>` 显式指定。
  - 环境变量：`PROC_ENTRY_POINT=<module:Class>`。
  - `manifest.json` 或 `manifest.yaml`：键 `entry_point`，文件位于工作目录或 `PROC_ALGO_ROOT`。
  - `pyproject.toml`：段 `[tool.procvision.algorithm] entry_point = "<module:Class>"`。
  - 默认值：`algorithm.main:Algorithm`（若模块与类存在）。

- 路径解析与错误处理：
  - 工作目录应为算法包根；如非根目录，需设置 `PROC_ALGO_ROOT` 指向算法包根。
  - 未找到入口时，适配器输出 `error` 帧并退出，`error_code=1004 not_initialized`，`message="entry_point not found"`。

## 13. 安全与资源
- 无外网访问；不下发机密信息；避免将敏感数据写入日志与调试输出。
- 资源限制（可选）：CPU/GPU/内存由容器或操作系统层实现；适配器避免创建无界线程与缓冲队列。

## 14. 测试与验收
- 单元测试：帧编解码、握手与版本协商、心跳、路由与状态机、错误码映射。
- 集成测试：端到端跑通两步骤，覆盖 `OK/NG/ERROR` 与超时重试；验证共享内存 `BGR→RGB` 转换一致性。
- 验收标准：
  - 协议一致：`hello/ping/pong/call/result/shutdown/error` 行为与字段正确。
  - 步骤索引从 1 开始；`pre_execute` 不返回业务判定；`execute.data.result_status` 为业务判定。
  - 共享内存读写稳定、尺寸与 `image_meta` 一致；颜色空间转换正确。
  - 日志与协议严格隔离；错误码与策略一致；心跳在负载下稳定。

## 15. Runner 集成要点
- 使用算法包 `venv` 的解释器启动适配器，进程隔离且路径可控。
- 在后台线程/异步任务处理协议通道与心跳，避免阻塞 UI 主线程。
- 相机帧写入共享内存并构造 `call` 输入；在每步执行前后触发 `on_step_start/on_step_finish` 钩子。
- 并发与背压：默认串行；如需并发，Runner 必须与算法包约定 `max_inflight` 并实现排队或拒绝策略。
- 异常处理：超时后重试至上限仍失败时优雅重启子进程，确保资源清理与状态重置。

## 16. 兼容性与演进
- 版本策略：协议适配器随 SDK 版本发布；Runner 与算法包统一升级路径，遵循语义化版本。
- 能力标记：通过 `hello.capabilities` 宣告支持的扩展（如 `shared_memory:v1`）。
- 变更示例：支持 `image_encoding: "jpeg|array"`、`color_space_default`、自适应心跳策略与配置化开关。

---

以上规范用于在生产与开发环境下统一协议适配器的行为与边界，确保 Runner 与算法包之间的通信稳定、可诊断、可演进。
