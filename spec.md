# ProcVision Algorithm SDK 规范（Execute-only）

## 目标
- 将算法接口精简为单函数 `execute`，算法实现无状态、无生命周期钩子。
- Runner 以子进程方式启动算法适配器，通过帧协议发起一次 `execute` 调用并获取结果。

## 算法接口（唯一必实现）

算法入口类必须继承 `procvision_algorithm_sdk.BaseAlgorithm`，并实现：

```python
from typing import Any, Dict
from procvision_algorithm_sdk import BaseAlgorithm


class Algorithm(BaseAlgorithm):
    def execute(
        self,
        step_index: int,
        step_desc: str,
        cur_image: Any,
        guide_image: Any,
        guide_info: Any,
    ) -> Dict[str, Any]:
        if cur_image is None or guide_image is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}
        return {"status": "OK", "data": {"result_status": "OK", "defect_rects": []}}
```

## 入参定义
- `step_index`：步骤索引（平台从 1 开始）。
- `step_desc`：步骤描述文本（中英文均可）。
- `cur_image`：当前步骤引导图（ndarray，推荐 `H×W×3 uint8`，RGB）。
- `guide_image`：当前步骤相机采集图（ndarray，推荐 `H×W×3 uint8`，RGB）。
- `guide_info`：引导信息（JSON 对象/数组），推荐结构：

```json
[
  {"label":"1","posList":[{"x":94,"y":269,"width":319,"height":398}]},
  {"label":"2","posList":[{"x":797,"y":242,"width":250,"height":283}]}
]
```

说明：
- `label`：标签标识（字符串）
- `posList`：矩形列表；坐标以图像左上为原点，单位像素

## Runner→adapter 的图像传递（共享内存）
算法 `execute` 不直接接收共享内存 ID；共享内存由 Runner/CLI 写入，adapter 负责读取并解码成 ndarray 再调用 `execute`。

call.data 需要提供两套共享内存引用（详见 `protocol_adapter_spec.md`）：
- `cur_image_shm_id` + `cur_image_meta`
- `guide_image_shm_id` + `guide_image_meta`

## 返回结构（execute）

### 顶层
- 类型：`Dict[str, Any]`
- `status: Literal["OK","ERROR"]`
- `message: str`（可选，建议 < 100）
- `error_code: str`（可选）
- `data: Dict[str, Any]`（当 `status="OK"` 时必填）

### data（OK）
- `result_status: Literal["OK","NG"]`
- `defect_rects: List[Rect]`：当 `result_status="NG"` 时必填，且 `len(defect_rects) ≤ 20`
- `ng_reason: str`：当 `result_status="NG"` 时必填（建议 < 50）
- `position_rects: List[Rect]`（可选，位置/引导框）
- `debug: Dict[str, Any]`（可选，调试信息）

## 算法侧返回格式要求（开发团队必须遵守）
- 必须返回 JSON 可序列化的 `Dict[str, Any]`（不要返回自定义对象/ndarray/bytes）。
- `status=="ERROR"` 时：\n
  - 必须提供 `message`（用于定位问题）\n
  - 建议提供 `error_code`（便于平台侧分类/统计）\n
  - 不要求提供 `data`（可省略或置空）
- `status=="OK"` 时：\n
  - 必须提供 `data.result_status in {"OK","NG"}`\n
  - 若 `result_status=="NG"`：必须提供 `ng_reason` 与 `defect_rects`，且 `defect_rects ≤ 20`\n
  - 若 `result_status=="OK"`：建议显式返回 `defect_rects: []`（便于平台侧统一解析）
- `Rect` 坐标使用像素整数，原点为图像左上角（x 向右、y 向下），建议保证 `width/height > 0`。\n

## 返回示例

### 1) OK（无缺陷）
```json
{
  "status": "OK",
  "message": "",
  "data": {
    "result_status": "OK",
    "defect_rects": [],
    "debug": {"latency_ms": 12.3}
  }
}
```

### 2) NG（有缺陷）
```json
{
  "status": "OK",
  "data": {
    "result_status": "NG",
    "ng_reason": "检测到划伤",
    "defect_rects": [
      {"x": 94, "y": 269, "width": 319, "height": 398, "label": "scratch", "score": 0.87}
    ],
    "debug": {"latency_ms": 15.8}
  }
}
```

### 3) ERROR（执行失败）
```json
{
  "status": "ERROR",
  "message": "模型加载失败",
  "error_code": "2001"
}
```

### rect 结构
类型（建议）：
- `x: int` / `y: int` / `width: int` / `height: int`
- `label: str`（可选）
- `score: float`（可选，0~1）

```json
{"x": 10, "y": 20, "width": 50, "height": 30, "label": "defect", "score": 0.85}
```

## manifest.json（最小要求）
- 必填：`name`、`version`、`entry_point`
- `entry_point` 格式：`模块路径:类名`

示例：
```json
{
  "name": "algorithm-example",
  "version": "1.0.0",
  "entry_point": "algorithm_example.main:AlgorithmExample",
  "description": "示例算法"
}
```
