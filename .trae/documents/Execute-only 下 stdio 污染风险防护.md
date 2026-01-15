## 目标
- 在 **adapter 层**从机制上避免算法 `stdout` 污染协议帧导致解析失败。
- 在 **CLI validate** 中加入“可验证的约束”：能在开发期明确发现并拦截 stdout 污染（失败即提示修复）。

## 背景与问题
- 当前 Runner/CLI 与算法通过 stdio 帧协议交互：协议帧必须严格、连续写入 `stdout`。
- 算法或三方库若 `print()`/进度条/banner/底层 C 库写 stdout，会插入到协议流中，导致握手失败/解析失败/卡死。
- 仅靠文档提醒不足，需要 SDK/adapter 层提供“硬隔离”与“可检测验证”。

## 方案（优先级：Adapter 侧硬隔离 + Validate 严格检测）

### 1) Adapter：协议输出与 stdout 日志彻底隔离（默认开启）
- **核心思路**：
  1) 启动时先 `dup(1)` 得到一份“原始 stdout pipe”的副本 `protocol_fd`；
  2) 协议帧写入永远走 `protocol_fd`（不再依赖 `sys.stdout`）。
  3) 再把进程的 `fd=1`（stdout）重定向到 `fd=2`（stderr），确保算法侧任何 stdout 写入都进入 stderr，不会污染协议。
- 这样即便算法调用 `print()` 或底层库 `os.write(1, ...)`，也只会出现在 stderr，协议仍然可解析。

### 2) Adapter：严格模式（用于 validate 可验证）——检测到 stdout 写入则返回错误
- 需求：你提到“能否在 cli validate 中验证这个逻辑”。答案是 **可以**，做法如下：
- 在 adapter 增加一个 **严格模式开关**（建议用环境变量）：`PROC_STRICT_STDIO=1`。
- 严格模式下，不是简单 `dup2(2,1)`，而是：
  - `os.pipe()` 创建一对管道 `(r_fd, w_fd)`；
  - `dup2(w_fd, 1)` 把 stdout 指向 pipe；
  - 启动一个后台线程持续读取 `r_fd`：
    - 读取到任何字节 ⇒ 计数 `stdout_bytes += len(chunk)`；
    - 同时把这些字节转发到 stderr（作为日志留痕），可做截断预览（比如最多 4KB）。
  - 协议帧仍写入 `protocol_fd`（不受影响）。
- 当一次 `call/execute` 完成后：
  - 若 `stdout_bytes > 0`：adapter 对该 `request_id` 返回 `error` 帧（比如 `error_code="1010"`, message: "stdout 污染：禁止向 stdout 输出"），并在 stderr 输出“捕获到的 stdout 片段”。
  - 若为 0：正常返回 `result`。

### 3) CLI：在 validate --full 内默认启用严格模式
- 在 `procvision-cli validate --full` 启动 adapter 子进程时：
  - 注入 `PROC_STRICT_STDIO=1`。
- 这样 validate 会**硬性保证**：
  - 只要算法污染 stdout（无论 Python print 还是底层 C stdout），validate 必定失败，并给出清晰提示。
- `procvision-cli run`：建议默认不开严格（避免运行时因第三方库输出而中断），但可以加 `--strict-stdio` 选项或同样用环境变量开关。

## 文档与团队规范补充（同步）
- 在 quickstart/README/tutorial 的 stdio 风险段落补充：
  - SDK 已做隔离：stdout 默认重定向到 stderr；
  - `validate --full` 会严格检测 stdout 污染并失败；
  - 推荐实践：所有日志只写 stderr（StructuredLogger）。

## 测试与验收
- 新增/调整单测覆盖：
  1) 一个算法在 `execute` 内 `print("hello")`：
     - 严格模式下：adapter 返回 `error`，CLI validate --full 失败。
  2) 同样算法在非严格模式：
     - adapter 仍应返回 `result`，且协议解析正常；stdout 内容应出现在 stderr（可选断言）。
- 验收标准：
  - `validate --full` 可稳定复现并拦截 stdout 污染；
  - 不影响正常算法的执行与协议握手；
  - 兼容 Windows（os.dup/os.dup2/os.pipe 可用）。

## 影响面
- 代码：`procvision_algorithm_sdk/adapter/__main__.py`、`procvision_algorithm_sdk/cli.py`（validate_adapter 子进程 env + 可选新增参数）。
- 文档：quickstart/README/tutorial 增加“validate 可检测”说明。

## 交付方式
- 先实现 adapter 侧隔离与严格检测 + CLI validate 注入严格模式。
- 然后补测试与文档，最后跑全量单测验证。