# ProcVision 适配器协议规范（Execute-only）

## 通道约定
- `stdout`：仅输出协议帧（hello/pong/result/error/shutdown）。
- `stderr`：算法日志输出（文本或 JSON 行）。

## 帧格式
每一帧为：
- `[4字节 big-endian 长度][UTF-8 JSON bytes]`

## 消息类型

### hello（适配器 → Runner）
```json
{
  "type": "hello",
  "sdk_version": "0.3.0",
  "timestamp_ms": 1714032000123,
  "capabilities": ["ping","call","shutdown","shared_memory:v1","execute"]
}
```

### hello（Runner → 适配器）
```json
{
  "type": "hello",
  "runner_version": "desktop-runner",
  "heartbeat_interval_ms": 5000,
  "heartbeat_grace_ms": 2000
}
```

### ping / pong
- Runner 周期性发送 `ping`：
```json
{"type":"ping","request_id":"..."}
```
- 适配器回复 `pong`：
```json
{"type":"pong","request_id":"...","timestamp_ms":1714032000123,"status":"OK"}
```

### call（Runner → 适配器）
适配器仅支持一次性 execute 调用，`call.data` 字段如下：
```json
{
  "type": "call",
  "request_id": "rid-123",
  "data": {
    "step_index": 1,
    "step_desc": "步骤描述（中英文）",
    "guide_info": [
      {"label": "1", "posList": [{"x": 94, "y": 269, "width": 319, "height": 398}]},
      {"label": "2", "posList": [{"x": 797, "y": 242, "width": 250, "height": 283}]}
    ],
    "cur_image_shm_id": "dev-shm:sid-123:cur",
    "cur_image_meta": {"width": 1920, "height": 1200, "timestamp_ms": 1714032000123, "camera_id": "cur-01", "color_space": "RGB"},
    "guide_image_shm_id": "dev-shm:sid-123:guide",
    "guide_image_meta": {"width": 1920, "height": 1200, "timestamp_ms": 1714032000123, "camera_id": "cam-01", "color_space": "RGB"}
  }
}
```

### result（适配器 → Runner）
`result` 透传算法 `execute` 的 `status/message/data`，并额外包含 `step_index`：
```json
{
  "type": "result",
  "request_id": "rid-123",
  "timestamp_ms": 1714032000456,
  "status": "OK",
  "message": "",
  "data": {
    "step_index": 1,
    "result_status": "OK",
    "defect_rects": [],
    "debug": {"latency_ms": 25.3}
  }
}
```

字段类型说明：
- `status: "OK" | "ERROR"`（对应算法 `execute.status`，当为 `ERROR` 时 `data` 可为空或缺失）
- `message: str`（可选）
- `data.step_index: int`
- `data.result_status: "OK" | "NG"`（当 `status=="OK"` 时才有业务意义）
- `data.defect_rects: List[Rect]`（当 `data.result_status=="NG"` 必填，且 ≤20）
- `data.ng_reason: str`（当 `data.result_status=="NG"` 必填）
- `data.position_rects: List[Rect]`（可选）
- `data.debug: Dict[str, Any]`（可选）

### error（适配器 → Runner）
```json
{
  "type": "error",
  "request_id": "rid-123",
  "timestamp_ms": 1714032000456,
  "status": "ERROR",
  "message": "invalid execute return",
  "error_code": "1000"
}
```

### shutdown
- Runner → 适配器：
```json
{"type":"shutdown"}
```
- 适配器 → Runner：
```json
{"type":"shutdown","timestamp_ms":1714032000999,"status":"OK"}
```
