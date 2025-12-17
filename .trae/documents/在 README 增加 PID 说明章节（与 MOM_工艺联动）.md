# 增加“PID 说明”章节到 4 份文档（README、runner_spec、algorithm_dev_quickstart、algorithm_dev_tutorial）

## 背景
- 平台与 MOM 联动：工艺（process_no）→ 工序（operation_no）→ 工步；算法包对象是“工序”。
- 算法包唯一性 = `PID + version`；PID 由 `process_no` 与 `operation_no` 组成。

## PID 定义（统一规范）
- 语义：`PID = <process_no> + <operation_no>`。
- 分隔符：使用冒号 `:`，不得使用下划线 `_` 或连字符 `-` 作为分隔符；分隔符不可出现在组件内部。
- 格式：`<process_no>:<operation_no>`。
- 示例：
  - `process_no = "JZ2.940.10287GY-TX02"`
  - `operation_no = "30"`
  - `PID = "JZ2.940.10287GY-TX02:30"`
- 约束：
  - 组件允许字母/数字/已有字符（如 `.`、`-` 等），但不得包含 `:`；若必须含 `:`, 建议组件内做 `%3A` 转义并在源侧统一（推荐由 MOM 保证不含 `:`）。
  - 建议长度：总长度 ≤ 64，各组件 ≤ 32。
- 正则：`^[^:]+:[^:]+$`。

## 清单与代码约定
- manifest.json：`supported_pids` 必须与 `get_info().supported_pids` 一致。
- 入口实现：在 `pre_execute/execute` 校验 PID 是否受支持；不支持时返回 `status="ERROR"`、`error_code="1001"`、`message` 明确说明。
- CLI validate：检查 `supported_pids` 一致与返回结构；非法 PID 提示修复。

## 运行与路由
- Runner 注入 `pid` 并以 `PID+version` 唯一定位算法包；以 PID 为键管理激活版本与切换。
- 适配器：`call.data.pid` 传递 PID；算法侧不可改写结构与分隔符。

## 错误处理与提示
- Runner：拒绝无分隔符或包含非法分隔符的 PID，记录原因。
- 算法：返回 `1001` 与清晰 `message`（如“无效 PID 或不支持的工序”）。

## 文档插入位置（四处）
- README.md：位于“CLI（Dev Runner）”与“离线交付”之间，新增“PID 说明”小节。
- runner_spec.md：在“运行与路由/运行态与执行态”之后新增“PID 说明与约束”。
- algorithm_dev_quickstart.md：在“初始化与清单”之后新增“PID 说明与示例”，示例 manifest 片段使用 `process_no:operation_no`。
- algorithm_dev_tutorial.md：在“清单规范（manifest.json）”附近新增“PID 说明与校验”。

## 兼容与迁移
- 历史自由分隔符 PID：统一迁移到 `process_no:operation_no` 格式，并同步 manifest 与入口类。
- validate 将提示不一致或非法 PID 并指导修复。

## 交付
- 本次仅新增文档章节，不修改代码；章节内容在四份文档一致（示例与正则复用）。