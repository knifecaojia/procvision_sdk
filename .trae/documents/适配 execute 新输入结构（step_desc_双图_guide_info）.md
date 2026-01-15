## 目标（硬切）
- 直接将算法侧 `execute` 入参硬切为你给定的新结构：
  - `step_index`（从 1 开始）
  - `step_desc`（步骤描述，中英文文本）
  - `cur_image`（引导图）
  - `guide_image`（相机采集图）
  - `guide_info`（标签对象数组：`[{label,posList:[{x,y,width,height}]}]`）
- 同步改造 SDK：BaseAlgorithm、adapter 协议、CLI run/validate/init、示例、测试、文档。

## 设计选择
### 1) 图像传递方式（保持共享内存机制，不在协议里塞大对象）
- Runner/CLI 仍把两张图写入共享内存。
- call.data 中携带两套 shm+meta：
  - `cur_image_shm_id` + `cur_image_meta`
  - `guide_image_shm_id` + `guide_image_meta`
- adapter 收到 call 后用 `read_image_from_shared_memory(...)` 解码为 ndarray，并把 `cur_image/guide_image` 作为 **实际数组** 传给算法 `execute`。

### 2) `step_desc/guide_info` 直接作为 call.data 字段
- 这两项属于“执行输入语义”，不放到 user_params。

## 需要修改的代码点（硬切清单）
### 1) BaseAlgorithm（破坏性变更）
- 将 `BaseAlgorithm.execute` 签名改为：
  - `execute(step_index: int, step_desc: str, cur_image: Any, guide_image: Any, guide_info: Any) -> Dict[str,Any]`
- 同步更新导出的 typing（必要时新增 guide_info 的 TypedDict/类型别名）。

### 2) adapter 协议与调用
- 修改 adapter 的 call 解析：读取 `step_desc/guide_info/cur_image_shm_id/cur_image_meta/guide_image_shm_id/guide_image_meta`。
- adapter 内部读取两张图并调用新签名 execute。
- 对缺失字段：
  - `step_desc` 缺省为 ""（或直接报错 1000）
  - 任一图像 shm/meta 缺失则报错（明确 message）

### 3) CLI
- `run`：新增参数并构造新 call.data
  - `--cur-image <path>`
  - `--guide-image <path>`（保留 `--image` 作为 guide-image 的别名，或直接替换为 guide-image）
  - `--step-desc <text>`
  - `--guide-info <json>`（支持 `@file.json`）
- `validate --full`：发送一条带新字段的 call（用内置 dummy 图/空 guide_info）。
- `init`：脚手架模板生成的新 `main.py` 使用新签名。

### 4) 规范文档与开发文档
- 更新：`spec.md`、`protocol_adapter_spec.md`、`runner_spec.md`
  - 明确新 call.data 字段与示例
  - 明确 guide_info 数据结构与坐标约束
- 更新：`README.md`、`algorithm_dev_quickstart.md`、`algorithm_dev_tutorial.md`
  - 增加“硬切说明：旧接口不再兼容”
  - 给出 run/validate 的新参数示例

### 5) 示例与单测
- 更新 `algorithm-example`：execute 改为新签名，并演示读取 guide_info。
- 更新/新增 tests：
  - adapter 能正确走新 call 并返回 result
  - CLI run/validate --full 使用新参数与新协议

### 6) 版本号与迁移提示
- 将 SDK 版本提升到下一个 breaking 版本（例如 `0.3.0`），并在 release-notes / migration guide 中写清楚：
  - execute 入参硬切
  - call.data 字段硬切
  - CLI 参数硬切

## 验证
- 跑全量单测
- 手工验证：
  - `procvision-cli init ...`
  - `procvision-cli run ... --cur-image ... --guide-image ... --guide-info @x.json`
  - `procvision-cli validate ... --full --tail-logs`

## 交付结果
- SDK/adapter/CLI/示例/测试/文档全部对齐新输入结构，旧接口不再支持。