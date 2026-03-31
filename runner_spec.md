# ProcVision 平台侧 SDK Runtime（Runner）规范（Execute-only）

## 总览
- Runner 负责：
  - 进程管理：启动/停止算法子进程（适配器）。
  - 通信：通过 `stdin/stdout` 帧协议发送 `call` 并接收 `result/error`。
  - 数据通道：写入共享内存并注入双图引用（`*_image_shm_id` + `*_image_meta`）。
  - 健壮性：心跳、超时、重启与日志采集。

## 启动与握手
- 启动命令：`<venv_python> -m procvision_algorithm_sdk.adapter [--entry "<module:Class>"]`
- 工作目录：算法包根目录（包含 `manifest.json`）
- 适配器启动后在 `stdout` 输出 `hello`，Runner 回复 `hello`（带心跳参数）。

## 部署与目录约束（必须遵守）

### 解压目录命名
- 算法包部署到部署文件夹时，必须按 `算法包名-版本` 的方式解压缩为独立目录：
  - `<deploy_root>/<algo_name>-<version>/`
- Runner 启动适配器时必须将工作目录（cwd）设置为该目录，确保目录内包含 `manifest.json`。

### 目录唯一性
- 部署文件夹中不得存在同名目录（同 `algo_name-version`）。
- 若目标目录已存在，部署必须失败并给出明确提示，禁止覆盖或混用旧文件。

### 原子部署建议
- 建议先解压到临时目录（例如 `<algo_name>-<version>.tmp`），完成基础校验后再重命名为最终目录名，以避免半部署状态。

### 线上数据为准
- 算法管理页面展示的算法包必须严格以线上数据为准（发布记录/注册中心），不得以本地文件夹扫描结果作为算法清单来源。
- 本地部署目录仅作为线上某条算法记录在本机的落地副本，用于显示部署状态/路径/健康检查等，不得反向推导线上清单。

## 调用模型（单函数）
Runner 发起一次检测时仅调用一次 `execute`：

### call
```json
{
  "type": "call",
  "request_id": "rid-123",
  "data": {
    "step_index": 1,
    "step_desc": "步骤描述（中英文）",
    "guide_info": [
      {"label": "1", "posList": [{"x": 94, "y": 269, "width": 319, "height": 398}]}
    ],
    "cur_image_shm_id": "dev-shm:sid-123:cur",
    "cur_image_meta": {"width": 1920, "height": 1200, "timestamp_ms": 1714032000123, "camera_id": "cur-01"},
    "guide_image_shm_id": "dev-shm:sid-123:guide",
    "guide_image_meta": {"width": 1920, "height": 1200, "timestamp_ms": 1714032000123, "camera_id": "cam-01"}
  }
}
```

### result
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
    "defect_rects": []
  }
}
```

## 返回数据类型（Runner/Engine 必须实现的解析规则）
- 若收到 `type="result"`：
  - `status=="OK"`：按 `data.result_status` 做业务判断（`OK/NG`）
  - `status=="ERROR"`：视为算法执行失败（可记录 message/error_code 并按策略重试/告警）
- 若收到 `type="error"`：视为协议/入参/运行时异常（不可直接按业务 OK/NG 解释）

字段类型约束（推荐按此做反序列化/校验）：
- `type: "result" | "error" | "pong" | "hello" | "shutdown"`
- `request_id: str`（result/error/pong 必有；shutdown 可无）
- `timestamp_ms: int`
- `status: "OK" | "ERROR"`
- `message: str`（可选）
- `error_code: str`（error 必有；result 可选或无）
- `data: Dict[str, Any]`（result 在 `status=="OK"` 时应存在）
- `data.step_index: int`
- `data.result_status: "OK" | "NG"`
- `data.defect_rects: List[Rect]`（NG 必填，≤20）
- `data.ng_reason: str`（NG 必填）

## 共享内存
- Runner 写入两张图像到共享内存，并生成：`cur_image_shm_id`、`guide_image_shm_id`。
- 对应 meta：`cur_image_meta`、`guide_image_meta` 至少包含：`width/height/timestamp_ms/camera_id`。

## 日志
- 协议在 `stdout`，日志在 `stderr`。
- Runner 聚合 `stderr`，按 `session.id` 或 `trace_id` 归档。

## 错误与超时
- `execute_timeout_ms` 超时后可重试或重启进程。
- 返回 `error` 帧时，Runner 根据 `error_code` 分类处理（可重试/不可重试）。
