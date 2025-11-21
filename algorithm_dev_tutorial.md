# 算法开发教程（ProcVision SDK）

本文提供规范化的算法项目开发与交付流程，面向工程实践。内容涵盖环境准备、项目初始化、接口实现、校验运行、依赖管理、离线打包与交付验收。

## 快速路径与顺序

- 环境准备 → 项目初始化（CLI） → 编辑 manifest → 接口实现（get_info/pre_execute/execute）
- 校验与运行（CLI） → 依赖管理与 wheels 下载 → 离线打包 → 交付前核对 → 交付与验收
- 附录：参数修改指南、CLI 命令清单与帮助、常见问题与处理建议

## 一、环境准备

- 安装 Python 3.10 及以上版本。
- 创建并激活虚拟环境：
  - Windows：`python -m venv .venv`，`.\.venv\Scripts\activate`
  - Linux/Mac：`python -m venv .venv`，`source .venv/bin/activate`
- 安装 SDK 与常用依赖：
  - `pip install procvision_algorithm_sdk`

## 二、项目初始化（CLI）

- 执行：`procvision-cli init product_a_screw_check --pids A01,A02 -v 1.2.1 -d ./product_a_screw_check`
- 目录结构：
  - `product_a_screw_check/manifest.json`
  - `product_a_screw_check/product_a_screw_check/__init__.py`
  - `product_a_screw_check/product_a_screw_check/main.py`
- 更新 `main.py` 中 `self._supported_pids` 与 `get_info()` 返回的 `name/version/supported_pids`，保持与 `manifest.json` 一致（不在 manifest 中添加 `steps`）。

## 三、编辑 manifest.json

- 必填字段：`name`、`version`、`entry_point`、`supported_pids`。
- 推荐字段：`description`（用于 UI 展示）。
- 示例：

```
{
  "name": "product_a_screw_check",
  "version": "1.2.1",
  "entry_point": "product_a_screw_check.main:ProductAScrewCheckAlgorithm",
  "description": "A产品螺丝检测",
  "supported_pids": ["A01", "A02"]
}
```

- 约束：`supported_pids` 必须与 `get_info()` 完全一致。

## 四、参数修改指南（必读）

- 目标：明确算法团队需要自行配置/维护的参数项、修改位置、取值约束与常见问题。

—

**A. manifest.json（项目根）**

- `name`
  - 作用：算法唯一标识（与包目录/入口类保持一致）。
  - 约束：小写字母、数字、下划线组合，避免空格与特殊字符。
  - 常见问题：与 `get_info().name` 不一致导致校验失败。
- `version`
  - 作用：算法版本（语义化版本）。
  - 约束：`major.minor.patch`；与 `get_info().version` 一致。
- `entry_point`
  - 作用：平台加载入口，格式 `模块路径:类名`。
  - 约束：类必须继承 `BaseAlgorithm`。示例：`product_a_screw_check.main:ProductAScrewCheckAlgorithm`。
- `description`
  - 作用：算法简要说明，UI中展示。
  - 约束：简洁明确，建议 < 80 字符。
- `supported_pids`
  - 作用：支持的产品型号列表。
  - 约束：与 `get_info().supported_pids` 完全一致；建议 ≤ 20 个。
  - 常见问题：列表不一致，或包含无效 PID 编码。

**B. 算法源码（main.py）**

- `self._supported_pids`
  - 位置：入口类构造函数。
  - 约束：必须与 `manifest.json.supported_pids` 一致。
  - 参考：`algorithm-example/algorithm_example/main.py:9`。
- `get_info()` 返回值
  - 必填：`name/version/description/supported_pids/steps`。
  - 约束：`name/version/supported_pids` 与 `manifest.json` 一致；`steps` 参数类型合法。
  - 参考：`algorithm-example/algorithm_example/main.py:11-26`。
- `pre_execute(step_index, pid, session, user_params, shared_mem_id, image_meta)`
  - 作用：条件检查/参考信息产出。
  - 约束：`status` 仅取 `OK/ERROR`；不返回 `result_status`；`message` 简洁明确。
  - 参考签名：`procvision_algorithm_sdk/base.py:37-45`。
- `execute(step_index, pid, session, user_params, shared_mem_id, image_meta)`
  - 作用：核心检测与业务判定。
  - 约束：`status` 仅取 `OK/ERROR`；业务判定在 `data.result_status`（`OK/NG`）；NG 时提供 `ng_reason/defect_rects`（≤ 20）。
  - 参考签名：`procvision_algorithm_sdk/base.py:48-57`。

—

**C. 步骤参数 schema 说明（get_info().steps[].params）**

- `int`
  - 字段：`default/min/max/unit`
  - 规则：`min ≤ default ≤ max`；`unit` 可选（如 `ms`）。
- `float`
  - 字段：`default/min/max/unit`
  - 规则：建议提供单位（如 `lux`、`ms`）。
- `rect`
  - 字段：`required/description`
  - 规则：格式为 `x,y,width,height`；坐标与尺寸均在图像范围内。
- `enum`
  - 字段：`choices/default`
  - 规则：`default ∈ choices`；用于运行模式等离散值。
- `bool`
  - 字段：`default`
  - 规则：布尔开关；默认 `false/true`。
- `string`
  - 字段：`description/min_length/max_length/pattern`
  - 规则：文本长度与正则约束（如路径、ID）。

示例：

```
{
  "index": 0,
  "name": "主板定位",
  "params": [
    {"key": "roi", "type": "rect", "required": true, "description": "定位区域"},
    {"key": "threshold", "type": "float", "default": 0.7, "min": 0.3, "max": 0.9, "unit": "score"},
    {"key": "mode", "type": "enum", "choices": ["fast", "accurate"], "default": "fast"}
  ]
}
```

—

**D. 运行时入参说明（平台传入）**

- `step_index`
  - 作用：当前步骤索引（从 1 开始）。
- `pid`
  - 作用：产品型号编码（匹配 `supported_pids`）。
  - 约束：不在支持列表时返回 `status=ERROR`，`error_code=1001`。
- `session`
  - 作用：单次检测流程的上下文与状态存储；`get/set/delete/exists`。
- `user_params`
  - 作用：平台根据 `steps.params` 注入的用户配置；需按 schema 校验。
- `shared_mem_id`
  - 作用：共享内存标识，用于读取图像数据。
- `image_meta`
  - 作用：图像最小必要元信息。
  - 约束：包含 `width/height/timestamp_ms/camera_id`；尺寸在合理范围。

—

**E. 约束与数量限制**

- `supported_pids`：建议 ≤ 20（最大 50）。
- `defect_rects`：最大 20；超出应截断并记录。
- `position_rects`：建议 ≤ 20。
- `message`：建议 < 100 字符；`ng_reason` 建议 < 50 字符。

—

**F. 常见错误与修正**

- 不一致：`manifest.json.supported_pids` ≠ `get_info().supported_pids` → 统一两处值。
- 参数越界：`threshold` 超出 `min/max` → 调整默认值或限制 UI 范围。
- 坐标越界：`rect` 超出图像范围 → 入口校验并返回 `status=ERROR, error_code=1007`。
- 结构错误：`pre_execute` 返回 `result_status` → 移除，仅在 `execute.data` 判定。

## 五、接口实现（最小示例）

在 `main.py` 实现 `get_info / pre_execute / execute`：

```
class ProductAScrewCheckAlgorithm(BaseAlgorithm):
    def __init__(self) -> None:
        super().__init__()
        self._supported_pids = ["A01", "A02"]

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": "product_a_screw_check",
            "version": "1.2.1",
            "description": "A产品螺丝检测",
            "supported_pids": self._supported_pids,
            "steps": [{"index": 0, "name": "主板定位", "params": [{"key": "threshold", "type": "float", "default": 0.7, "min": 0.3, "max": 0.9}]}],
        }

    def pre_execute(self, step_index, pid, session, user_params, shared_mem_id, image_meta):
        if pid not in self._supported_pids:
            return {"status": "ERROR", "message": f"不支持的产品型号: {pid}", "error_code": "1001"}
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        if img is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}
        return {"status": "OK", "message": "准备就绪", "debug": {"latency_ms": 0.0}}

    def execute(self, step_index, pid, session, user_params, shared_mem_id, image_meta):
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        if img is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}
        return {"status": "OK", "data": {"result_status": "OK", "defect_rects": [], "debug": {"latency_ms": 0.0}}}
```

要点：

- `pre_execute` 进行条件确认与提示，不返回实际检测结果。
- `execute` 返回业务结果；NG 时提供 `ng_reason` 与 `defect_rects`（≤20）。
- `message` 建议控制在 100 字以内。

补充：`pre_execute` 可返回参考信息（可选）
- 字段：`data.calibration_rects`（一个或多个标定框，包含坐标与 `label`）。
- 结构示例：
```
{
  "status": "OK",
  "message": "标定完成",
  "data": {
    "calibration_rects": [
      {"x": 100, "y": 120, "width": 200, "height": 250, "label": "roi-1"},
      {"x": 400, "y": 300, "width": 150, "height": 180, "label": "roi-2"}
    ]
  }
}
```
- 说明：用于平台在执行前展示或记录标定区域；数量可为 1 个或多个，未设定上限，坐标需在图像范围内。

## 六、测试资源

- 准备一张 `JPEG/PNG` 测试图片（例如 `./test.jpg`）。

## 七、校验与运行（CLI）

- 结构校验：`procvision-cli validate ./product_a_screw_check`
- 本地运行：`procvision-cli run ./product_a_screw_check --pid A01 --image ./test.jpg --json`
- 结果包含 `pre_execute.status`、`execute.status` 与 `data.result_status`。

## 八、依赖管理与 wheels 下载

- 锁定依赖：`pip freeze > requirements.txt`
- 下载 wheels（根据目标环境）：

```
pip download -r requirements.txt -d ./product_a_screw_check/wheels \
  --platform win_amd64 --python-version 3.10 --implementation cp --abi cp310
```

## 九、离线打包

- 使用 CLI（默认参数）：

```
procvision-cli package ./product_a_screw_check
```
- 默认参数：
  - `--output`：按 `name/version` 生成 `<name>-v<version>-offline.zip`
  - `--auto-freeze`：开启，缺失 `requirements.txt` 时自动生成
  - `--wheels-platform`：`win_amd64`
  - `--python-version`：`3.10`
  - `--implementation`：`cp`
  - `--abi`：`cp310`

- 产物包含：源码目录、`manifest.json`、`requirements.txt`、`wheels/`、可选 `assets/`。

## 十、交付前核对

- `supported_pids` 与 `get_info()` 完全一致。
- `pre_execute` 返回 `status: OK/ERROR`，包含 `message`。
- `execute` 返回 `status: OK/ERROR`；OK 时 `data.result_status: OK/NG`。
- NG 时包含 `ng_reason` 与 `defect_rects`（≤20）。
- `image_meta` 含 `width/height/timestamp_ms/camera_id`。
- `requirements.txt` 锁版本，wheels 与目标环境匹配。
- zip 结构正确，`procvision-cli validate` 通过。

## 十一、常见问题与处理建议

- PID 不一致：检查 `manifest.json` 与 `get_info()` 的 `supported_pids`。
- 返回结构错误：`pre_execute` 不包含 `result_status`；业务判定位于 `execute.data.result_status`。
- UI 性能压力：限制 `defect_rects` 数量 ≤ 20，必要时截断。
- 图像尺寸异常：确保 `image_meta.width/height` 合理（例如 100–8000）。

## 十二、交付与验收

- 提交离线 zip 至平台；平台侧 Runner 已实现心跳与协议处理。
- 如需诊断，使用 `debug` 字段并通过 `StructuredLogger` 输出结构化日志（stderr）。

本教程旨在确保算法项目在标准化流程下快速上线，并在后续迭代中保持接口与交付的一致性。

## 十三、CLI 命令清单与帮助

- 程序名：`procvision-cli`
- validate

  - 用法：`procvision-cli validate [project] [--manifest <path>] [--zip <path>] [--json]`
  - 说明：校验 `manifest`、入口导入、`supported_pids` 一致性与返回结构；可选检查离线包结构。
  - 参数：
    - `project`：算法项目根目录（默认 `.`）
    - `--manifest`：指定 `manifest.json` 路径
    - `--zip`：离线包路径（检查内部是否包含 `manifest/requirements/wheels`）
    - `--json`：以 JSON 输出结果（默认人类可读）
  - 退出码：校验通过返回 0，否则返回非 0。
- run

  - 用法：`procvision-cli run <project> --pid <pid> --image <path> [--params <json>] [--json]`
  - 说明：模拟平台调用，写入共享内存并依次调用 `pre_execute/execute`；输出摘要或 JSON 结构。
  - 参数：
    - `project`：算法项目根目录（包含 `manifest.json` 与源码）
    - `--pid`：产品型号编码（需在 `supported_pids` 内）
    - `--image`：本地图片路径（JPEG/PNG）
    - `--params`：JSON 字符串的用户参数（例如 `{"threshold":0.8}`）
    - `--json`：以 JSON 输出结果
  - 退出码：`execute.status == "OK"` 返回 0，否则返回非 0。
- package

  - 用法：`procvision-cli package <project> [--output <zip>] [--requirements <path>] [--auto-freeze] [--wheels-platform <p>] [--python-version <v>] [--implementation <impl>] [--abi <abi>] [--skip-download]`
  - 说明：下载 wheels 并打包源码、`manifest`、`requirements` 与可选 `assets` 为离线 zip。
  - 参数：
    - `--output/-o`：输出 zip 路径，默认按 `name/version` 生成
    - `--requirements/-r`：`requirements.txt` 路径；缺失时可配 `--auto-freeze`
    - `--auto-freeze/-a`：自动生成 `requirements.txt`（`pip freeze`）
    - `--wheels-platform/-w`：目标平台（默认 `win_amd64`）
    - `--python-version/-p`：目标 Python 版本（默认 `3.10`）
    - `--implementation/-i`：Python 实现标识（如 `cp`）
    - `--abi/-b`：ABI（如 `cp310`）
    - `--skip-download/-s`：跳过依赖下载，仅打包现有内容
  - 退出码：成功返回 0，失败返回非 0。
- init

  - 用法：`procvision-cli init <name> [-d|--dir <dir>] [--pids <p1,p2>] [-v|--version <ver>] [-e|--desc <text>]`
  - 说明：生成脚手架与 `manifest.json`；在 `main.py` 注释给出需更新项（PID、接口实现）。
  - 参数：
    - `name`：算法名（用于模块与入口类）
    - `-d/--dir`：目标目录（默认在当前目录下生成）
    - `--pids`：支持的 PID 列表（默认 `p001,p002`）
    - `-v/--version`：算法版本（默认 `1.0.0`）
    - `-e/--desc`：算法描述（可选）

## 十四、SDK API 参考
本节以“模块 → 类/函数 → 语义 → 参数 → 返回 → 示例”的格式提供完整参考。

—

### 包导出（procvision_algorithm_sdk）
- 导出名称：`BaseAlgorithm`、`Session`、`read_image_from_shared_memory`、`StructuredLogger`、`Diagnostics`、`RecoverableError`、`FatalError`、`GPUOutOfMemoryError`、`ProgramError`
- 用法示例：
```
from procvision_algorithm_sdk import BaseAlgorithm, Session, read_image_from_shared_memory
```

—

### BaseAlgorithm（抽象基类）
- 语义：定义算法的标准接口与生命周期钩子。
- 属性：`logger: StructuredLogger`、`diagnostics: Diagnostics`、`_resources_loaded: bool`、`_model_version: Optional[str]`、`_supported_pids: List[str]`

- 方法列表：
```
__init__(self) -> None
setup(self) -> None
teardown(self) -> None
on_step_start(self, step_index: int, session: Session, context: Dict[str, Any]) -> None
on_step_finish(self, step_index: int, session: Session, result: Dict[str, Any]) -> None
reset(self, session: Session) -> None
get_info(self) -> Dict[str, Any]
pre_execute(self, step_index: int, pid: str, session: Session, user_params: Dict[str, Any], shared_mem_id: str, image_meta: Dict[str, Any]) -> Dict[str, Any]
execute(self, step_index: int, pid: str, session: Session, user_params: Dict[str, Any], shared_mem_id: str, image_meta: Dict[str, Any]) -> Dict[str, Any]
```

- 参数约束：
  - `step_index`：从 1 开始的整数。
  - `pid`：必须在 `self._supported_pids` 内；否则返回 `status="ERROR"` 与 `error_code="1001"`。
  - `user_params`：遵循 `get_info().steps[].params`（如使用）；建议按类型/范围校验。
  - `shared_mem_id`：平台传入的共享内存 ID。
  - `image_meta`：最小集合 `width/height/timestamp_ms/camera_id`。

- 返回约束：
  - `pre_execute`：
    - 必含：`status: "OK" | "ERROR"`
    - 可选：`message: str`、`debug: Dict`、`data.calibration_rects: List[RectWithLabel]`
  - `execute`：
    - 必含：`status: "OK" | "ERROR"`
    - 当 `status="OK"` 时：`data.result_status: "OK" | "NG"`
    - NG 时：`data.ng_reason: str`、`data.defect_rects: List[RectWithScore] (≤20)`

- 返回结构示例：
```
# pre_execute (返回标定框)
{
  "status": "OK",
  "message": "标定完成",
  "data": {
    "calibration_rects": [
      {"x": 100, "y": 120, "width": 200, "height": 250, "label": "roi-1"}
    ]
  },
  "debug": {"latency_ms": 25.3}
}

# execute (NG 示例)
{
  "status": "OK",
  "data": {
    "result_status": "NG",
    "ng_reason": "检测到3处划痕",
    "defect_rects": [
      {"x": 150, "y": 200, "width": 60, "height": 20, "label": "scratch", "score": 0.85}
    ],
    "debug": {"latency_ms": 48.7, "model_version": "yolov5s_20240101"}
  }
}
```

—

### Session（会话上下文）
- 语义：提供单次检测流程内的 KV 状态存储与只读上下文。
- 构造：`Session(id: str, context: Optional[Dict[str, Any]] = None)`
- 属性：
```
id -> str
context -> Dict[str, Any]  # 返回只读副本
```
- 方法：
```
get(key: str, default: Any = None) -> Any
set(key: str, value: Any) -> None  # value 必须可 JSON 序列化
delete(key: str) -> bool
exists(key: str) -> bool
```
- 示例：
```
session.set("template", {...})
alignment = session.get("alignment")
if session.exists("retry_count"):
    session.delete("retry_count")
```

—

### StructuredLogger（结构化日志）
- 语义：将结构化 JSON 日志写入 `stderr`。
- 方法：
```
info(message: str, **fields: Any) -> None
debug(message: str, **fields: Any) -> None
error(message: str, **fields: Any) -> None
```
- 日志格式示例：
```
{"level":"info","timestamp_ms":1714032000123,"message":"步骤完成","step_index":1,"latency_ms":25.3}
```

—

### Diagnostics（诊断数据聚合）
- 语义：在单次调用中聚合诊断指标，便于 UI/远程排查。
- 方法：
```
publish(key: str, value: Any) -> None
get() -> Dict[str, Any]
```
- 示例：
```
self.diagnostics.publish("brightness", 115.5)
self.diagnostics.publish("confidence", 0.82)
```

—

### 共享内存图像读入
- 函数：`read_image_from_shared_memory(shared_mem_id: str, image_meta: Dict[str, Any]) -> Any`
- 语义：从共享内存读取 JPEG/PNG 并返回 `numpy.ndarray (H x W x 3)`；失败回退为零矩阵。
- 参数：
  - `shared_mem_id`：共享内存标识；由平台/Dev Runner 提供。
  - `image_meta`：`{"width": int, "height": int, "timestamp_ms": int, "camera_id": str}`。
- 示例：
```
img = read_image_from_shared_memory(shared_mem_id, {"width":1920,"height":1200,"timestamp_ms":1714032000123,"camera_id":"cam-01"})
```
- 开发辅助（Dev Runner 内部使用）：`dev_write_image_to_shared_memory(shared_mem_id, image_bytes)`、`dev_clear_shared_memory(shared_mem_id)`。

—

### 异常类型
- 语义：用于内部分类与日志记录；对平台返回错误时优先使用返回值的 `status="ERROR"` 与 `message/error_code`。
- 列表：
```
RecoverableError
FatalError
GPUOutOfMemoryError
ProgramError
```

—

### 关键约束与约定
- `supported_pids` 在 `get_info()` 与 `manifest.json` 完全一致（建议 ≤ 20）。
- `step_index` 从 1 开始。
- `pre_execute` 不返回检测结论；`execute` 的业务判定使用 `data.result_status`。
- `defect_rects` 最大 20；坐标需在图像范围内；`message` 建议 < 100 字，`ng_reason` 建议 < 50 字。
