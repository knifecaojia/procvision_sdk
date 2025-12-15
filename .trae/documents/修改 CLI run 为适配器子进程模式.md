## 目标
- 将 `procvision-cli run` 从直接导入算法类的本地执行，改为通过启动 `procvision_algorithm_sdk.adapter` 子进程以帧协议通信的 Runner 行为。
- 对齐规范的 `hello/ping/pong/call/result/shutdown/error` 流程，提升与桌面 Runner 一致性与可诊断性。

## 行为变化
- 启动适配器子进程后进行握手；CLI 作为 Runner 端发送 `hello`、构造并发送 `call` 帧、读取 `result`、发送 `shutdown`。
- 共享内存仍使用现有 `dev_write_image_to_shared_memory` 写入本地图片供算法读取。
- 支持 `--entry` 透传给适配器；若未指定则走自动发现（通过设置 `PROC_ALGO_ROOT` 并解析 `manifest.json`）。

## 技术实现
- 子进程启动：`subprocess.Popen([sys.executable, '-m', 'procvision_algorithm_sdk.adapter', *(--entry?)] , stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=project, env={PROC_ALGO_ROOT=project})`。
- 帧编解码：在 CLI 中实现 `_write_frame(fp, obj)` 与 `_read_frame(fp)`（4字节大端长度 + UTF-8 JSON）。
- 握手流程：
  - 读取适配器 `hello`；
  - 发送 Runner `hello`：`{"type":"hello","runner_version":"dev","heartbeat_interval_ms":5000,"heartbeat_grace_ms":2000}`。
- 共享内存：将图片写入 `shared_mem_id = f"dev-shm:{session.id}"`，并构造 `image_meta`（从图片读尺寸或默认 640×480）。
- 发送调用：构建 `call` 帧（按规范字段在 `data` 中携带 `phase/step_index/pid/session/user_params/shared_mem_id/image_meta`）。
- 读取结果：阻塞读取一个 `result` 或 `error` 帧；如 5s 超时返回错误并尝试优雅关闭。
- 优雅关停：发送 `{"type":"shutdown"}`，读取确认后结束子进程；必要时 `terminate()`。
- 错误处理：对 `busy/invalid return/entry not found` 等 `error_code` 打印人类提示并以非零退出码返回。

## 代码改动点
- `procvision_algorithm_sdk/cli.py`：
  - 新增 `_write_frame`、`_read_frame` 辅助函数（CLI 侧）。
  - 新增 `run_adapter(project, pid, image_path, params_json, step_index, entry)` 实现子进程通信逻辑。
  - `run` 子命令改为调用 `run_adapter`；保留旧实现为 `--legacy-run` 后门（默认关闭）。
  - 输出行为：若使用 `--json`，返回完整 `result` 帧；否则打印关键字段（status/result_status/ng_reason/defect_rects 数量）。

## 参数与环境
- 透传 `--entry`（可选）；未提供时自动发现通过适配器完成，CLI 设置 `PROC_ALGO_ROOT=project`。
- 保留现有 `--pid --image --step --params --json` 参数语义不变。

## 验证计划
- 正常案例：存在 `manifest.json` 且入口可导入，返回 `OK` 的 `result`。
- 异常案例：
  - 缺少 `manifest.json` → 适配器返回 `error 1004`；
  - 图片不存在 → CLI 前置校验失败；
  - 并发调用（不在 CLI 测试范围）→ 适配器会返回 `busy`；
  - 非法返回结构 → 适配器返回 `error 1000`。

## 兼容性
- 不破坏原有 CLI 命令集；`run` 默认走适配器模式，保留 `--legacy-run` 兼容旧路径（仅开发排障用）。

## 文档与发布
- 更新 `docs/release-notes/v0.0.6.md` 补充 CLI `run` 的子进程模式说明与使用示例。
- 在 `README.md` 增加简化启动命令与 `run` 的新工作流描述。

## 回滚策略
- 若发现适配器模式在某环境不稳定，可通过 `--legacy-run` 临时回退至旧的直接导入执行路径；后续修复后再切换回默认模式。
