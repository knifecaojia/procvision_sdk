# **工业视觉平台ProcVision算法开发规范**

## 版本变更说明

**当前版本：v0.2.0** (2025-11-20)
**关键更新：支持单个算法包对应多个产品型号（PID），指示runner 对算法包的生命周期管理**

### v0.1.0 → v0.2.0 核心变更

1. **`__init__`签名调整**：移除 `pid: str`参数，算法实例不绑定特定PID
2. **`execute/pre_execute`新增 `pid`参数**：每次调用时动态传递当前产品型号
3. **`manifest.json`增强**：新增 `required_assets`字段，声明每个PID的资源配置【删除】
4. **设计哲学转变**：从"一对一实例-PID"到"一对多实例-PID"，减少内存占用，提升初始化效率

**问题背景**：v0.1.0规范要求算法实例在初始化时绑定单个PID，导致支持多个产品时需要创建多个算法包或多个实例，造成代码冗余、内存浪费和管理复杂。v0.2.0通过将PID从实例属性改为调用参数，实现单个算法实例支持多个PID，通过配置差异化适配不同产品。

详细设计原理参见第3.2节。

## 1. 概述

### 1.1. 目的

本文档旨在为工业视觉平台的算法开发团队提供一套清晰、标准化的开发与交付规范。通过遵循本规范，算法团队开发的算法模块将能够与主平台无缝集成，实现动态热加载、环境隔离和稳定的离线部署，从而确保整个系统的灵活性、稳定性和可维护性。

### 1.2. 核心思想

平台与算法是解耦的。平台方提供一个标准的Python SDK (procvision_algorithm_sdk)，算法团队通过实现SDK定义的接口来完成算法逻辑。最终，算法团队需要交付一个自包含的、可在目标环境离线安装的算法包。平台方不负责处理任何算法的第三方库依赖。

## 2. 核心要求与限制条件

* **完全离线部署**: 生产环境的工作站(C端)和服务器(S端) **均无外网访问能力**。因此，算法交付包必须包含其运行所需的所有依赖项。
* **标准化交付物**: 算法的最终交付物**必须**是一个 **.zip** **格式的压缩包，其内部结构需严格遵循本文档第四节的规定。**
* **目标运行环境**: 所有算法的最终运行环境是固定的。用户方将提供工作站的精确环境规格，算法团队必须基于此规格构建交付包。
* **操作系统**: **[例如: Windows 10 x64 / Ubuntu 20.04 x86_64]**
* **Python版本**: **[例如: Python 3.8.10]**
* **核心硬件**: **[例如: Intel Core i5-9400F, NVIDIA GeForce RTX 4060 with CUDA 12.6]**

---

## 3. 算法SDK (**procvision_algorithm_sdk**)

### 3.1. SDK获取与安装

**平台方已将SDK发布至内部PyPI源或直接提供wheel文件。算法开发团队通过以下方式安装：**

```bash
# 假设sdk文件为 procvision_algorithm_sdk-1.0.0-py3-none-any.whl
pip install procvision_algorithm_sdk-1.0.0-py3-none-any.whl
```

### 3.2. SDK核心接口定义

```python
from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseAlgorithm(ABC):
    """
    算法SDK接口基类。平台会为同一算法包创建单个实例，处理supported_pids中的所有PID。
    在execute/pre_execute调用时通过pid参数传递当前产品型号，算法根据pid动态加载配置。
    """

    def __init__(self):
        """
        构造函数。在算法实例创建时调用，可用于轻量初始化。
        注意：算法实例不绑定具体PID，需支持所有supported_pids中的型号。
        """
        pass

    # 生命周期钩子（可选实现）
    def setup(self) -> None:
        """算法实例启动时调用一次，用于加载模型、建立共享内存/显存池等重量级初始化。"""
        return None

    def teardown(self) -> None:
        """算法实例销毁前调用一次，用于释放模型、显存、共享内存、后台线程/连接。"""
        return None

    def on_step_start(self, step_index: int, session: "Session", context: Dict[str, Any]) -> None:
        """每步执行前调用，可清理临时缓存、记录时间戳、校验输入 meta。"""
        return None

    def on_step_finish(self, step_index: int, session: "Session", result: Dict[str, Any]) -> None:
        """每步执行后调用，可写日志、统计耗时、清理缓存或写回状态。"""
        return None

    def reset(self, session: "Session") -> None:
        """当平台触发重新检测/中断时调用，清理本次检测相关临时资源，避免脏数据。"""
        return None

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """
        返回算法元信息与步骤配置（含可配置参数 schema）。

        **重要要求**：返回的 `supported_pids` 必须与 `manifest.json` 中的 `supported_pids` 字段完全一致。
        平台在加载算法时会验证两者的一致性。
        """
        raise NotImplementedError

    @abstractmethod
    def pre_execute(
        self,
        step_index: int,
        pid: str,
        session: "Session",
        shared_mem_id: str,
        image_meta: Dict[str, Any],
        user_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        执行前调用，用于产出参考信息（模板、ROI等）。

        :param step_index: 当前步骤索引（从0开始）
        :param pid: 产品型号编码（平台传递）
        :param session: 平台为本次工艺提供的 Session 对象（含 state_store/context）
        :param shared_mem_id: 平台提供的共享内存ID，图像数据存放其中
        :param image_meta: 图像元信息（分辨率、格式、时间戳等）
        :param user_params: UI/配置下发的可调参数（按步骤 schema 校验）
        :return: 参考信息字典
        """
        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        step_index: int,
        pid: str,
        session: "Session",
        shared_mem_id: str,
        image_meta: Dict[str, Any],
        user_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        执行核心检测/引导逻辑。

        :param step_index: 当前步骤索引（从0开始）
        :param pid: 产品型号编码（平台传递）
        :param session: 平台为本次工艺提供的 Session 对象（含 state_store/context）
        :param shared_mem_id: 平台提供的共享内存ID，图像数据存放其中
        :param image_meta: 图像元信息（分辨率、格式、时间戳等）
        :param user_params: UI/配置下发的可调参数（按步骤 schema 校验）
        :return: 检测结果字典
        """
        raise NotImplementedError
```

**接口详解:**

* **get_info()**

  * **返回值结构**:

    ```json
    {
      "name": "universal_screw_detection",
      "version": "2.0.0",
      "description": "通用螺丝检测算法（支持A/B/C系列产品）",
      "supported_pids": ["A01", "A02", "A03", "B01", "B02", "C01"],
      "steps": [
        {
          "index": 0,
          "name": "定位主板",
          "params": [
            {"key": "roi", "type": "rect", "required": true, "description": "定位区域"},
            {"key": "exposure", "type": "float", "default": 12.5, "min": 8.0, "max": 16.0, "unit": "ms"}
          ]
        },
        {
          "index": 1,
          "name": "检测左上角螺丝",
          "params": [
            {"key": "threshold", "type": "float", "default": 0.7, "min": 0.5, "max": 0.9, "description": "置信度阈值"},
            {"key": "mode", "type": "enum", "choices": ["fast", "accurate"], "default": "fast"}
          ]
        }
      ]
    }
    ```

  * **字段说明**:
    - `name`: 算法唯一标识（必须与 `manifest.json` 中的 `name` 一致）
    - `version`: 语义化版本（必须与 `manifest.json` 中的 `version` 一致）
    - `description`: 算法描述
    - `supported_pids`: **关键字段** - 此算法包支持的所有产品型号列表。**必须与 `manifest.json` 中的 `supported_pids` 完全一致**，平台会验证两者的一致性。通常一个算法包支持 1-20 个 PID（建议不超过 20 个以便管理）
    - `steps`: 算法步骤列表，定义每步的可配置参数 schema
* **pre_execute(step_index, session, shared_mem_id, image_meta, user_params)**

  * **返回值结构**:

    ```json
    {
      "status": "OK" | "ERROR",
      "suggest_action": "retry" | "skip" | "abort",
      "error_type": "recoverable" | "fatal" | null,
      "message": "光源初始化完成",
      "overlay": {
        "roi_rects": [{"x": 100, "y": 120, "width": 200, "height": 250, "label": "roi"}],
        "template_id": "shared_mem_template_001"
      },
      "debug": {"latency_ms": 25.3}
    }
    ```
* **execute(step_index, session, shared_mem_id, image_meta, user_params)**

  * **返回值结构**:

    ```json
    {
      "status": "OK" | "NG" | "ERROR",
      "ng_reason": "右下角螺丝缺失",
      "suggest_action": "retry" | "skip" | "abort",
      "error_type": "recoverable" | "fatal" | null,
      "defect_rects": [
        {"x": 550, "y": 600, "width": 50, "height": 50, "label": "missing_screw", "score": 0.82}
      ],
      "position_rects": [
        {"x": 100, "y": 120, "width": 200, "height": 250, "label": "screw_position"}
      ],
      "diagnostics": {
        "confidence": 0.82,
        "brightness": 115.5,
        "attachments": [{"type": "image", "shared_mem_id": "diag_overlay_001"}]
      },
      "debug": {"latency_ms": 48.7, "model_version": "yolov5s_20240101"}
    }
    ```

### 3.3. Session 与状态共享

* SDK在每次工艺流程开始时创建 `Session` 对象，并在整个流程中透传给 `pre_execute` / `execute` / 生命周期钩子。
* `Session` 字段示例：

```

  {
    "id": "session-20240425-000123",
    "state_store": {},              // SDK托管的KV存储，可放置JSON可序列化数据
    "context": {
      "product_code": "A01",
      "operator": "user001",
      "trace_id": "..."
    }
  }

```

* 算法可通过 `session.get(key)` / `session.set(key, value)` / `session.delete(key)` 等API共享定位结果、临时模板等数据。SDK保证同一Session在结束或 `reset()` 时自动清理，并与其他Session隔离。

### 3.4. 图像传输（共享内存）

* 平台将相机采集的图像写入共享内存，并把 `shared_mem_id` + `image_meta`（宽高、格式、时间戳、相机ID等）传给算法。
* 算法必须通过SDK提供的 `read_image_from_shared_memory(shared_mem_id, image_meta)` 工具函数获取 `numpy.ndarray` 或其他格式。禁止在JSON中传输Base64图像，也不再支持临时落盘文件。
* 若需要输出模板/调试图，算法同样应调用SDK工具写入共享内存，并在返回值的 `overlay` / `diagnostics.attachments` 中携带共享内存ID。

#### 3.4.1. image_meta 数据结构

**用途**: 描述共享内存中图像的尺寸、像素格式与采集信息，供 `read_image_from_shared_memory(shared_mem_id, image_meta)` 正确解析。

**必需字段**:

```json
{
  "width": 1280,                // 像素宽 (int, >0)
  "height": 1024,               // 像素高 (int, >0)
  "pixel_format": "GRAY8",     // 像素格式 (见下方枚举)
  "dtype": "uint8",            // 数据类型映射 (uint8|uint16|float32)
  "timestamp_ms": 1714032000123,// 采集时间戳 (毫秒, Unix epoch)
  "camera_id": "cam-01"        // 相机/通道标识 (string)
}
```

**推荐字段**（可选，但强烈建议提供，提升解析与追溯能力）:

```json
{
  "channels": 1,                         // 通道数 (GRAY=1, RGB/BGR=3, RGBA=4)
  "bit_depth": 8,                        // 每通道位深 (8|16|32)
  "row_stride_bytes": 1280,              // 每行字节步长 (如紧凑存储=width*channels*dtype_bytes)
  "frame_id": "cam-01-000123",         // 帧ID/序号
  "exposure_ms": 12.5,                   // 曝光时间
  "gain_db": 6.0,                        // 增益
  "white_balance": {"r":1.8,"g":1.0,"b":1.7}, // 白平衡系数
  "color_space": "sRGB",                // 颜色空间 (sRGB|AdobeRGB|linear)
  "rotation_deg": 0,                     // 采集或平台旋转角 (0|90|180|270)
  "flip": {"horizontal": false, "vertical": false}, // 翻转标记
  "trigger_id": "trig-000045"          // 触发源ID/序号
}
```

**格式特定字段**（按需提供）:

```json
{
  // YUV/NV12/NV21/YUV420P 等半/平面格式
  "yuv_planes": {
    "layout": "semi-planar",           // planar|semi-planar
    "y_stride": 1280,                   // Y 平面步长 (bytes)
    "uv_stride": 1280                    // UV 平面步长 (bytes, semi-planar 情况)
  },

  // Bayer 原始格式 (8/16bit)
  "bayer_pattern": "RGGB"               // RGGB|BGGR|GBRG|GRBG
}
```

**pixel_format 枚举**（常用值）:

- `GRAY8` / `MONO16`
- `RGB8` / `BGR8` / `RGBA8` / `RGB16`
- `NV12` / `NV21` / `YUV420P`
- `BayerRG8` / `BayerBG8` / `BayerGB8` / `BayerGR8` / 对应 16bit 变体

**形状与 dtype 映射**（SDK还原为 `numpy.ndarray`）：

- `GRAY8` → 形状 `(H, W)`, `dtype=uint8`
- `MONO16` → 形状 `(H, W)`, `dtype=uint16`
- `RGB8` / `BGR8` → 形状 `(H, W, 3)`, `dtype=uint8`
- `RGBA8` → 形状 `(H, W, 4)`, `dtype=uint8`
- `RGB16` → 形状 `(H, W, 3)`, `dtype=uint16`
- `NV12` / `NV21` / `YUV420P` → 默认转换为三通道 `BGR8`（除非 SDK 配置为保留原始平面）
- `Bayer*` → 依据 `bayer_pattern` 与 `bit_depth` 去马赛克，默认输出 `BGR8`

**校验规则**：

- `width`、`height` 必须为正整数；`row_stride_bytes` ≥ `width*channels*dtype_bytes`
- `pixel_format` 与 `dtype` 必须自洽（如 `GRAY8`→`uint8`，`MONO16`→`uint16`）
- 若提供 `rotation_deg`/`flip`，SDK将按该信息做几何矫正后再返回数组
- YUV/Bayer 原始格式需提供对应 `yuv_planes`/`bayer_pattern` 以确保正确解析

**示例1: 工业黑白相机 (GRAY8)**

```json
{
  "width": 1920,
  "height": 1200,
  "pixel_format": "GRAY8",
  "dtype": "uint8",
  "timestamp_ms": 1714032000456,
  "camera_id": "line1-camA",
  "channels": 1,
  "bit_depth": 8,
  "row_stride_bytes": 1920,
  "exposure_ms": 8.0,
  "gain_db": 4.0
}
```

**示例2: 彩色相机 (NV12 输入，SDK 转 BGR8)**

```json
{
  "width": 1280,
  "height": 720,
  "pixel_format": "NV12",
  "dtype": "uint8",
  "timestamp_ms": 1714032000789,
  "camera_id": "line2-camB",
  "channels": 3,
  "bit_depth": 8,
  "yuv_planes": {"layout": "semi-planar", "y_stride": 1280, "uv_stride": 1280},
  "color_space": "sRGB"
}
```

### 3.5. 错误、日志与诊断

* **异常分类**：SDK内置 `RecoverableError` 与 `FatalError`。算法可以抛出这些异常或在返回值中设置 `status="ERROR"`、`error_type="recoverable|fatal"`、`suggest_action="retry|skip|abort"`。平台根据该信息决定是否提示用户重新检测或人工跳过。
* **日志API**：SDK提供结构化日志器 `logger`，输出JSON格式字段（`timestamp`, `session_id`, `step_index`, `status`, `latency_ms`, `trace_id` 等）。禁止直接 `print`，所有日志需通过API写入stderr或独立文件，便于平台采集。
* **诊断数据**：算法可通过 `diagnostics.publish(key, value)` 或返回值中的 `diagnostics` 字段上报置信度、亮度、调试图等信息。平台将这些指标用于UI展示与远程排查。
* **超时与心跳**：SDK runner 在每次 `pre_execute` / `execute` 调用期间监控超时并与算法进程维持心跳。若在配置时间内未响应，将抛出 `TimeoutError`、杀掉子进程并记录日志。

### 3.6. SDK Runner 与算法进程通信

* **通信方式**：runner 通过启动算法可执行入口（`python main.py serve` 等）并使用 `stdin/stdout` 双向管道通信。协议采用“4字节大端长度 + UTF-8 JSON”帧格式，确保无粘包。
* **消息字段**：
  ```
  {
    "type": "hello|call|result|ping|pong|error|shutdown",
    "request_id": "uuid-1234",        // call/result/error 对必需
    "method": "pre_execute|execute",  // 仅 call
    "payload": {...},                 // 调用入参/返回值
    "timestamp": 1714032000,
    "status": "OK|NG|ERROR"           // result/error
  }
  ```
* **握手流程**：算法启动后立即输出 `{"type":"hello","sdk_version":"1.0"}`，runner 返回 `{"type":"hello","runner_version":"1.0"}`。握手完成前不得发送业务消息。
* **调用流程**：runner 发送 `call` 帧，`payload` 中包含 `step_index`, `session`, `shared_mem_id`, `image_meta`, `user_params` 等；算法处理后回 `result` 帧。若发生异常，可发送 `error` 帧，字段与 `execute` 返回值保持一致。
* **心跳/超时**：runner 定期发送 `ping`，算法需在指定超时时间（默认 1s）内回复 `pong`。若超时，runner 记录日志并尝试优雅 shutdown；多次失败后强制终止子进程。
* **日志与协议隔离**：算法必须仅在 stdout 输出协议帧，所有日志写入 stderr（由 `logger` 统一管理），避免协议流被污染。
* **关闭流程**：runner 发送 `{"type":"shutdown"}`，算法应调用 `teardown()` 并返回 `{"type":"shutdown","status":"OK"}` 后退出进程。

### 3.7. SDK开发工具 (Dev Runner)

为了确保算法交付质量，SDK 内置了轻量级开发运行器 (Dev Runner)，模拟主平台的调用行为。算法团队**必须**在交付前使用此工具进行自测。

#### 3.7.1. 命令行工具 (CLI)

SDK 提供 `procvision-cli` 命令行工具：

```bash
# 1. 验证算法包结构与 manifest.json
procvision-cli validate ./my_algorithm_project/

# 2. 模拟运行算法 (Dev Runner)
procvision-cli run ./my_algorithm_project/ \
    --pid A01 \
    --image ./test_images/sample.jpg \
    --params '{"threshold": 0.8}'
```

#### 3.7.2. Dev Runner 行为

Dev Runner 运行在开发者本地环境，主要职责如下：
1.  **环境模拟**: 启动算法子进程，建立 Stdin/Stdout 管道。
2.  **协议校验**: 验证算法发出的 JSON 消息是否符合 3.6 节定义的协议格式。
3.  **Schema 校验**: 根据 `get_info()` 返回的 schema，验证 `user_params` 和返回值的字段类型。
4.  **资源模拟**:
    *   **共享内存**: 使用本地临时文件或 System V 共享内存模拟，将本地图片加载并传递给算法。
    *   **Session**: 创建虚拟 Session 对象，模拟状态存储。
5.  **报告生成**: 运行结束后生成简单的 HTML/JSON 报告，展示耗时、返回值和潜在错误。

---

## 3.8. 返回值详解与使用指南

本节详细解释 `pre_execute` 和 `execute` 方法的返回值结构，防止开发团队因理解偏差导致实现错误。

### 3.8.1. 返回值设计哲学

**核心原则**：
1. **明确的状态机**：平台根据 `status` 字段决定下一步动作
2. **人机分离**：`status`/`suggest_action`/`error_type` 供平台逻辑使用，`message` 供操作员阅读
3. **无副作用**：`pre_execute` 不返回真实检测结果，只返回参考信息
4. **内存只读**：算法不创建/写入共享内存，只读取平台提供的图像

**状态流转图**:
```
┌─────────────┐
│ pre_execute │
└──────┬──────┘
       │
       ├─► status: OK ──► continue to execute
       │
       └─► status: ERROR ──► handle error (retry/skip/abort)

┌──────────┐
│ execute  │
└─────┬────┘
      │
      ├─► status: OK ──► next product (检测通过)
      │
      ├─► status: NG ──► show defects + wait user (人工判断)
      │
      └─► status: ERROR ──► handle error (recoverable/fatal)
```

---

### 3.8.2. pre_execute 返回值详解

**适用场景**：
- 光照检查（验证检测条件）
- ROI/检测区域可视化
- 相机标定验证
- 模板匹配预览
- **任何不需要真实检测结果但需要参考信息的场景**

**完整结构**：
```json
{
  "status": "OK" | "ERROR",
  "suggest_action": "retry" | "skip" | "abort",
  "error_type": "recoverable" | "fatal" | null,
  "message": "人类可读的信息",
  "overlay": {
    "roi_rects": [{
      "x": 100,
      "y": 120,
      "width": 200,
      "height": 250,
      "label": "检测区域"
    }]
  },
  "debug": {"latency_ms": 25.3}
}
```

#### 3.8.2.1. status 字段（必需）

**含义**: 步骤准备结果状态

**取值说明**:
-  **`"OK"`**  : 准备成功，可以继续执行 `execute`
-  **`"ERROR"`**  : 准备失败，需要根据 `suggest_action` 处理

**平台处理逻辑**:
```python
# 伪代码示例
result = algorithm.pre_execute(step_index=0, ...)

if result["status"] == "OK":
    # ✅ 条件满足，继续检测
    proceed_to_execute()
else:
    # ❌ 条件不满足，处理错误
    handle_pre_execute_error(result)
    # 不会调用 execute
```

**实际案例**:
```python
# 案例1: 光照检查通过
{
    "status": "OK",
    "message": "光照充足: 75.5 lux"
}
# 平台行为: 继续执行 execute

# 案例2: 光照不足
{
    "status": "ERROR",
    "message": "光照不足: 35.2 < 50.0 lux"
}
# 平台行为: 提示用户调整光源，不会执行检测
```

---

#### 3.8.2.2. suggest_action 字段（status="ERROR"时必需）

**含义**: 建议平台采取的用户交互动作，**仅在 status="ERROR" 时有效**

**取值说明**:
-  **`"retry"`**  : 提示用户"重新检测"（最常见）
  - 使用场景: 外部条件问题（光照、对焦、产品位置）
  - 平台行为: 显示"调整环境后重试"按钮

-  **`"skip"`**  : 提示用户"人工跳过此产品"
  - 使用场景: 产品本身有问题，无法检测
  - 平台行为: 显示"跳过此产品"按钮

-  **`"abort"`**  : 提示用户"停止整个流程"
  - 使用场景: 严重错误，继续检测无意义
  - 平台行为: 停止产线，通知工程师

**平台UI行为示例**:
```python
if result["status"] == "ERROR":
    action = result.get("suggest_action")

    if action == "retry":
        ui.show_message(result["message"])
        ui.show_button("重新检测")
        if ui.wait_user_click() == "retry":
            algorithm.reset(session)  # 清理上一步状态
            retry_pre_execute()       # 重试

    elif action == "skip":
        ui.show_message(f"{result['message']} - 是否跳过？")
        if ui.user_confirms():
            skip_to_next_product()

    elif action == "abort":
        ui.show_error(result["message"])
        alert_engineer()
        stop_production_line()
```

**实际案例对比**:
```python
# 场景1: 光照不足 → retry
{
    "status": "ERROR",
    "suggest_action": "retry",
    "message": "光照不足: 35.2 < 50.0 lux"
}
# UI显示: [光照不足: 35.2 < 50.0 lux] [重新检测按钮]

# 场景2: 产品缺陷 → skip
{
    "status": "ERROR",
    "suggest_action": "skip",
    "message": "产品表面严重划伤，无法进行检测"
}
# UI显示: [产品表面严重划伤] [跳过按钮]

# 场景3: 相机故障 → abort
{
    "status": "ERROR",
    "suggest_action": "abort",
    "message": "相机连接失败，请检查硬件"
}
# UI显示: [严重错误] [停止产线]
```

---

#### 3.8.2.3. error_type 字段（status="ERROR"时必需）

**含义**: 错误严重程度分类，**仅在 status="ERROR" 时有效**

**取值说明**:
-  **`"recoverable"`**  : 可恢复错误（外部条件问题）
  - 示例: 光照不足、产品未到位、网络超时
  - 特征: 调整外部环境后可解决
  - 平台策略: 允许重试

-  **`"fatal"`**  : 不可恢复错误（算法内部问题）
  - 示例: 模型文件损坏、代码bug、GPU错误
  - 特征: 必须修复算法或环境才能继续
  - 平台策略: 停止该算法，通知工程师

**平台处理策略**:
```python
if result["status"] == "ERROR":
    error_type = result.get("error_type")

    if error_type == "recoverable":
        # 可恢复错误
        ui.show_message(result["message"])
        ui.wait_for_operator_ready()  # 等待操作员调整环境
        algorithm.reset(session)      # 清理状态
        retry_detection()             # 重试

    elif error_type == "fatal":
        # 不可恢复错误
        ui.show_error(result["message"])
        algorithm.teardown()          # 释放算法
        alert_maintenance()           # 通知维护
        stop_production_line()        # 停止产线
```

**关键区别**:
```python
# recoverable: 外部问题 → 用户可以修复
{
    "status": "ERROR",
    "error_type": "recoverable",
    "message": "光照不足"
}
# 操作员调整光源后可以继续

# fatal: 内部问题 → 必须代码/环境修复
{
    "status": "ERROR",
    "error_type": "fatal",
    "message": "模型文件损坏: model.pt not found"
}
# 必须重新部署算法包
```

---

#### 3.8.2.4. message 字段（必需）

**含义**: 人类可读的信息，显示在UI上供操作员阅读

**编写要求**:
1. **简短清晰**: 建议 < 100字符
2. **包含关键数值**: 显示实际值和期望值
3. **中文优先**: 操作员通常是中文环境
4. **避免技术术语**: 使用业务语言

**好坏示例对比**:
```python
# ❌ 不好的示例
{
    "message": "Error occurred"  # 太笼统，无帮助
}
{
    "message": "Light problem"   # 不明确
}
{
    "message": "threshold check failed"  # 技术术语
}

# ✅ 好的示例
{
    "message": "光照不足: 35.2 < 50.0 lux"  # 明确数值，清晰对比
}
{
    "message": "相机未对焦，清晰度: 45 < 80"  # 包含指标
}
{
    "message": "左上角ROI设置成功"  # 清晰描述
}
```

**实际应用场景**:
```python
# 光照检查
{
    "status": "OK",
    "message": f"光照检查通过: {brightness:.1f} lux"
}

# ROI可视化
{
    "status": "OK",
    "message": f"检测区域已显示: x={roi['x']}, y={roi['y']}"
}

# 模板匹配
{
    "status": "ERROR",
    "message": f"模板匹配失败，相似度: {score:.2f} < 0.85"
}
```

---

#### 3.8.2.5. overlay 字段（可选，但强烈推荐）

**含义**: 可视化参考信息，显示在UI上帮助操作员理解算法关注区域

**重要约束**（v0.2.0规范）:
- **只包含坐标信息，不包含图像数据**
- 平台根据坐标自行绘制ROI框到UI
- 降低算法管理内存的复杂度

**结构详解**:
```json
{
  "overlay": {
    "roi_rects": [  // 矩形框列表
      {
        "x": 100,            // 左上角X坐标（像素）
        "y": 120,            // 左上角Y坐标（像素）
        "width": 200,        // 宽度（像素）
        "height": 250,       // 高度（像素）
        "label": "检测区域"  // 标签（显示在框旁边）
      }
    ]
  }
}
```

**使用场景**:

**场景1: ROI可视化**（最常见）
```python
def pre_execute(self, step_index, session, shared_mem_id, image_meta, user_params):
    # 从参数获取ROI
    roi = user_params.get("roi", {"x": 0, "y": 0, "width": 640, "height": 480})

    # 在UI上显示检测区域
    return {
        "status": "OK",
        "overlay": {
            "roi_rects": [{
                "x": roi["x"],
                "y": roi["y"],
                "width": roi["width"],
                "height": roi["height"],
                "label": "检测区域"
            }]
        },
        "message": f"ROI已设置: x={roi['x']}, y={roi['y']}"
    }

# 平台端UI显示:
# ┌─────────────────────┐
# │   相机实时图像       │
# │                     │
# │   ┌──────────┐      │  ← 平台根据坐标绘制红色框
# │   │检测区域  │      │     标签"检测区域"显示在旁边
# │   └──────────┘      │
# │                     │
# └─────────────────────┘
```

**场景2: 多区域检测**
```python
def pre_execute(self, step_index, session, ...):
    # 显示多个检测区域
    return {
        "status": "OK",
        "overlay": {
            "roi_rects": [
                {"x": 100, "y": 100, "width": 80, "height": 80, "label": "螺丝1"},
                {"x": 300, "y": 100, "width": 80, "height": 80, "label": "螺丝2"},
                {"x": 100, "y": 300, "width": 80, "height": 80, "label": "螺丝3"},
                {"x": 300, "y": 300, "width": 80, "height": 80, "label": "螺丝4"}
            ]
        },
        "message": "4个螺丝检测位置已标记"
    }
```

**场景3: 模板匹配预览**
```python
def pre_execute(self, step_index, session, ...):
    # 显示模板匹配位置
    match_result = self._match_template(img)

    return {
        "status": "OK" if match_result.confidence > 0.9 else "ERROR",
        "overlay": {
            "roi_rects": [{
                "x": match_result.x,
                "y": match_result.y,
                "width": match_result.width,
                "height": match_result.height,
                "label": f"模板匹配 (置信度: {match_result.confidence:.2f})"
            }]
        },
        "message": f"模板匹配置信度: {match_result.confidence:.2f}"
    }
```

---

#### 3.8.2.6. debug 字段（可选）

**含义**: 调试信息，用于性能分析和问题排查

**内容示例**:
```json
{
  "debug": {
    "latency_ms": 25.3,          // 耗时（毫秒）
    "model_version": "v1.0.0",   // 模型版本
    "template_matches": 3        // 其他调试信息
  }
}
```

**使用方式**:
```python
import time

def pre_execute(self, step_index, session, ...):
    start_time = time.time()

    # ... 业务逻辑 ...
    brightness = self._check_brightness(img)

    latency_ms = (time.time() - start_time) * 1000

    return {
        "status": "OK",
        "message": f"光照检查通过: {brightness:.1f} lux",
        "debug": {
            "latency_ms": latency_ms,        // 性能指标
            "brightness_value": brightness,  // 检测值
            "threshold": threshold           // 阈值
        }
    }
```

**平台处理**:
- 不用于业务逻辑判断
- 写入日志（JSON格式）
- 用于性能监控和优化
- 远程排查问题时提供上下文

---

### 3.8.3. execute 返回值详解

**适用场景**：
- 真实缺陷检测
- 产品合格与否判断（OK/NG）
- 测量和计数
- **任何需要判断产品是否合格的场景**

**完整结构**：
```json
{
  "status": "OK" | "NG" | "ERROR",
  "ng_reason": "不合格原因描述",
  "suggest_action": "retry" | "skip" | "abort",
  "error_type": "recoverable" | "fatal" | null,
  "defect_rects": [
    {"x": 550, "y": 600, "width": 50, "height": 50, "label": "scratch", "score": 0.82}
  ],
  "position_rects": [
    {"x": 100, "y": 120, "width": 200, "height": 250, "label": "screw_position"}
  ],
  "diagnostics": {
    "confidence": 0.82,
    "brightness": 115.5,
    "defect_count": 3
  },
  "debug": {"latency_ms": 48.7, "model_version": "yolov5s_20240101"}
}
```

#### 3.8.3.1. status 字段（必需）

**取值**（3个状态）：
-  **`"OK"`**  : 检测通过，产品合格
-  **`"NG"`**  : 检测不通过，产品不合格（有缺陷）
-  **`"ERROR"`**  : 检测失败（无法判断合格与否）

**平台处理逻辑**:
```python
result = algorithm.execute(...)

if result["status"] == "OK":
    # 1. 显示"检测通过"
    ui.show_success("检测通过")
    # 2. 自动流转到下一个产品
    move_to_next_product()

elif result["status"] == "NG":
    # 1. 显示NG原因
    # 2. 绘制缺陷位置
    # 3. 等待操作员决策（retry/skip）
    handle_ng(result)

elif result["status"] == "ERROR":
    # 错误处理（同pre_execute）
    handle_error(result)
```

**案例对比**:
```python
# 案例1: 合格品 → OK
{
    "status": "OK",
    "defect_rects": [],  // 空列表
    "diagnostics": {"defect_count": 0}
}
# 平台: ✅ 绿灯，自动下一个

# 案例2: 缺陷品 → NG
{
    "status": "NG",
    "ng_reason": "检测到3处划痕",
    "defect_rects": [...],  // 3个缺陷框
    "diagnostics": {"defect_count": 3}
}
# 平台: ❌ 红灯，显示缺陷，等待人工

# 案例3: 检测失败 → ERROR
{
    "status": "ERROR",
    "error_type": "recoverable",
    "message": "图像读取失败"
}
# 平台: ⚠️ 错误，根据error_type处理
```

---

#### 3.8.3.2. ng_reason 字段（status="NG"时必需）

**含义**: 不合格的具体原因，**仅在 status="NG" 时有效**

**要求**:
- 简短明确（建议 < 50字符）
- 包含关键信息（缺陷类型、数量、位置）
- 直接显示在UI上

**示例**:
```python
# 单缺陷
defects = [{"label": "scratch", "score": 0.85}]
{
    "status": "NG",
    "ng_reason": "检测到1处划痕",
    "defect_rects": defects
}

# 多缺陷
defects = [
    {"label": "scratch", "score": 0.85},
    {"label": "stain", "score": 0.72},
    {"label": "dent", "score": 0.91}
]
{
    "status": "NG",
    "ng_reason": f"检测到{len(defects)}处缺陷: 划痕x1, 污点x1, 凹陷x1",
    "defect_rects": defects
}

# 缺少螺丝（位置明确）
{
    "status": "NG",
    "ng_reason": "右下角螺丝缺失",
    "position_rects": [{"x": 550, "y": 600, "label": "missing_screw"}]
}
```

---

#### 3.8.3.3. defect_rects 字段（status="NG"时推荐）

**含义**: 检测到的缺陷列表，**仅在 status="NG" 时有效**

**每个缺陷的结构**:
```json
{
  "x": 100,        // 左上角X坐标
  "y": 120,        // 左上角Y坐标
  "width": 50,     // 宽度
  "height": 30,    // 高度
  "label": "scratch",  // 缺陷类型标签
  "score": 0.82    // 置信度 (0.0-1.0)
}
```

**完整示例**:
```python
{
    "status": "NG",
    "ng_reason": "检测到2处划痕",
    "defect_rects": [
        {
            "x": 150,
            "y": 200,
            "width": 60,
            "height": 20,
            "label": "scratch",
            "score": 0.85
        },
        {
            "x": 350,
            "y": 180,
            "width": 45,
            "height": 15,
            "label": "scratch",
            "score": 0.72
        }
    ]
}

# 平台UI显示:
# ┌─────────────────────┐
# │   产品图像           │
# │                     │
# │   ┌──────┐          │  ← 红色框标记缺陷1
# │   │划痕  │          │     标签: scratch (85%)
# │   └──────┘          │
# │                     │
# │         ┌────┐      │  ← 红色框标记缺陷2
# │         │划痕│      │     标签: scratch (72%)
# │         └────┘      │
# └─────────────────────┘
# 底部显示: ❌ 检测到2处划痕 [人工跳过] [重新检测]
```

---

#### 3.8.3.4. position_rects 字段（可选）

**含义**: 定位/位置结果（非缺陷），例如螺丝位置、焊接点位置等

**结构与 defect_rects 相同，但表示的是正常位置**:
```json
{
  "position_rects": [
    {
      "x": 100,
      "y": 100,
      "width": 50,
      "height": 50,
      "label": "screw_position"
    }
  ]
}
```

**使用场景**:
1. **显示检测区域**：Step 0的execute返回（如果不需要pre_execute）
2. **显示缺少的组件位置**：与defect_rects配合使用
3. **多点定位**: 螺丝检测、焊点检测等

**案例: 螺丝缺失检测**
```python
{
    "status": "NG",
    "ng_reason": "缺少2颗螺丝",
    "defect_rects": [
        {"x": 100, "y": 100, "width": 20, "height": 20, "label": "missing_screw"},
        {"x": 300, "y": 100, "width": 20, "height": 20, "label": "missing_screw"}
    ],
    "position_rects": [
        {"x": 150, "y": 100, "width": 20, "height": 20, "label": "screw_ok"},
        {"x": 250, "y": 100, "width": 20, "height": 20, "label": "screw_ok"},
        {"x": 350, "y": 100, "width": 20, "height": 20, "label": "screw_ok"}
    ],
    "diagnostics": {"missing_count": 2, "ok_count": 3}
}
# UI显示:
# - 红色框: 2个缺少螺丝的位置 (defect_rects)
# - 绿色框: 3个正常螺丝的位置 (position_rects)
# - 消息: 缺少2颗螺丝
```

---

#### 3.8.3.5. diagnostics 字段（可选，但强烈推荐）

**含义**: 诊断数据，用于远程监控、性能分析和问题排查

**内容示例**:
```json
{
  "diagnostics": {
    "confidence": 0.82,              // 置信度
    "brightness": 115.5,             // 图像亮度
    "defect_count": 3,               // 缺陷数量
    "latency_ms": 48.7,              // 检测耗时
    "model_version": "yolov5s_20240101"  // 模型版本
  }
}
```

**上报方式**: 两种方式

**方式1: 返回值中包含**（推荐）
```python
def execute(self, step_index, pid, session, shared_mem_id, image_meta, user_params):
    # ... 检测逻辑 ...

    return {
        "status": "NG",
        "ng_reason": f"检测到{len(defects)}处缺陷",
        "defect_rects": defects,
        "diagnostics": {  // ← 在返回值中包含
            "confidence": 0.82,
            "brightness": brightness,
            "defect_count": len(defects),
            "model_version": self.model_version
        }
    }
```

**方式2: 使用 diagnostics.publish()**（如果在execute过程中需要逐步上报）
```python
def execute(self, step_index, session, ...):
    # 开始检测
    self.diagnostics.publish("model_loaded", True)

    # 检测中
    confidence = model.detect(img)
    self.diagnostics.publish("confidence", confidence)

    # 结束时获取所有诊断数据
    return {
        "status": "OK" if confidence > 0.8 else "NG",
        "diagnostics": self.diagnostics.get_all()  // 获取所有publish的数据
    }
```

**平台使用场景**:
```python
# 场景1: 远程监控大屏
def update_monitor(result):
    diagnostics = result.get("diagnostics", {})

    # 显示实时指标
    dashboard.update_metric(
        "confidence",
        diagnostics.get("confidence", 0)
    )
    dashboard.update_metric(
        "brightness",
        diagnostics.get("brightness", 0)
    )

    # 告警（连续10次confidence < 0.8）
    if diagnostics.get("confidence", 1.0) < 0.8:
        alert_queue.add("confidence_low")

# 场景2: 质量追溯
# 每个产品的检测数据（含diagnostics）存储到数据库
# 发现批量问题时，分析diagnostics找出根因

# 场景3: 性能优化
# 收集所有检测的latency_ms
# 绘制P50/P95/P99曲线
# 识别性能瓶颈
```

**建议的diagnostics字段**:
```python
{
    "confidence": float,              # 总体置信度
    "brightness": float,              # 图像亮度
    "defect_count": int,              # 缺陷数量
    "latency_ms": float,              # 检测耗时
    "model_version": str,             # 模型版本
    "pid": str,                       # 当前产品型号
    "gpu_memory_mb": float,           # GPU内存使用
    "preprocess_time_ms": float       # 预处理耗时
}
```

---

#### 3.8.3.6. debug 字段（可选）

**含义**: 调试信息，不用于业务逻辑，仅用于开发者排查问题

**内容示例**:
```json
{
  "debug": {
    "latency_ms": 48.7,
    "model_version": "yolov5s_20240101",
    "tensor_shape": [1, 3, 640, 480],
    "gpu_memory_allocated": "1.2 GB"
  }
}
```

**与 diagnostics 的区别**:
- **diagnostics**: 业务指标（置信度、缺陷数等），平台会监控和统计
- **debug**: 技术指标（耗时、模型版本、张量形状等），仅用于问题排查

**使用场景**:
```python
def execute(self, ...):
    start = time.time()

    # 推理
    result = self.model(img)

    latency_ms = (time.time() - start) * 1000

    return {
        "status": "OK" if result.ok else "NG",
        "defect_rects": result.boxes,
        "diagnostics": {
            "confidence": result.confidence,
            "defect_count": len(result.boxes)
        },
        "debug": {  # 技术细节，不用于业务
            "latency_ms": latency_ms,
            "model_version": self.model_version,
            "input_shape": img.shape,
            "gpu_memory": torch.cuda.memory_allocated()
        }
    }
```

---

### 3.8.4. pre_execute vs execute 对比总结

| 字段 | pre_execute | execute | 使用场景差异 |
|------|-------------|---------|--------------|
| **status** | "OK" / "ERROR" | "OK" / "NG" / "ERROR" | pre_execute 没有"NG"（不判断合格与否） |
| **suggest_action** | 有（ERROR时） | 有（NG/ERROR时） | 相同 |
| **error_type** | 有（ERROR时） | 有（ERROR时） | 相同 |
| **message** | 有 | 有 | 相同 |
| **overlay** | ✅ 有（坐标信息） | ❌ 无 | **关键区别** |
| **defect_rects** | ❌ 无 | ✅ 有（检测结果） | **关键区别** |
| **ng_reason** | ❌ 无 | ✅ 有（NG时） | **关键区别** |
| **position_rects** | ❌ 无 | ✅ 有（定位结果） | **关键区别** |
| **diagnostics** | 可选 | 强烈推荐 | execute 更需要诊断数据 |
| **debug** | 可选 | 可选 | 两者相同 |

---

### 3.8.5. 常见错误与纠正

#### ❌ 错误1: status 取值错误
```python
# 错误: pre_execute 返回 NG
return {"status": "NG"}  # ❌ pre_execute 不能有NG

# 正确
return {"status": "ERROR"}  # ✅ 使用ERROR
```

#### ❌ 错误2: 忘记 REQUIRED 字段
```python
# 错误: status="ERROR" 但没有 suggest_action
return {
    "status": "ERROR",
    "message": "光照不足"
}  # ❌ 缺少 suggest_action 和 error_type

# 正确
return {
    "status": "ERROR",
    "suggest_action": "retry",  # ✅ 必需
    "error_type": "recoverable",  # ✅ 必需
    "message": "光照不足"
}
```

#### ❌ 错误3: execute 返回 overlay
```python
# 错误: execute 返回 overlay
return {
    "status": "NG",
    "ng_reason": "有缺陷",
    "overlay": {...}  # ❌ execute 不能有 overlay
}

# 正确
return {
    "status": "NG",
    "ng_reason": "有缺陷",
    "defect_rects": [...]  # ✅ 使用 defect_rects
}
```

#### ❌ 错误4: NG 但没有 ng_reason
```python
# 错误
return {
    "status": "NG",
    "defect_rects": [...]
}  # ❌ 缺少 ng_reason

# 正确
return {
    "status": "NG",
    "ng_reason": "检测到3处划痕",  # ✅ 必需
    "defect_rects": [...]
}
```

#### ❌ 错误5: 在 overlay 中返回图像数据
```python
# 错误: overlay 包含图像base64
return {
    "status": "OK",
    "overlay": {
        "image_base64": "/9j/4AAQ..."  # ❌ 违反内存只读原则
    }
}

# 正确: 只返回坐标
return {
    "status": "OK",
    "overlay": {
        "roi_rects": [{"x": 100, "y": 100, "width": 200, "height": 200}]
    }
}
```

---

### 3.8.6. 最佳实践 checklist

#### get_info() 最佳实践
- [ ] 返回 dict 包含所有必需字段：name, version, supported_pids, steps
- [ ] `supported_pids` 必须与 manifest.json 中的 `supported_pids` 完全一致
- [ ] `name` 必须与 manifest.json 中的 `name` 完全一致
- [ ] `version` 必须与 manifest.json 中的 `version` 完全一致
- [ ] `supported_pids` 数量建议不超过 20 个（便于管理和测试）
- [ ] steps 数组中的每个 step 都有唯一的 index（从 0 开始）
- [ ] 每个 step 的 params 定义清晰，包含 type, default, min/max（如适用）

#### pre_execute 最佳实践
- [ ] status 只能是 "OK" 或 "ERROR"（不能有"NG"）
- [ ] status="ERROR" 时必须包含 suggest_action 和 error_type
- [ ] 返回 overlay 显示ROI或参考信息（坐标信息，不包含图像）
- [ ] message 包含关键数值信息（如亮度、匹配度）
- [ ] debug 包含耗时（latency_ms）用于性能分析

#### execute 最佳实践
- [ ] status 可以是 "OK"、"NG" 或 "ERROR"
- [ ] status="NG" 时必须包含 ng_reason 和 defect_rects
- [ ] defect_rects 包含完整的缺陷信息（坐标、标签、置信度）
- [ ] diagnostics 包含业务指标（置信度、缺陷数、亮度等）
- [ ] debug 包含技术指标（耗时、模型版本、内存使用等）
- [ ] 不使用 overlay（execute 中 overlay 无效）

#### 两个方法通用
- [ ] 所有返回字典必须包含"status"字段
- [ ] 所有数值字段使用标准JSON类型（int, float, str, bool, array, object）
- [ ] 不返回任何图像数据（内存只读原则）
- [ ] message 字段是用户友好的描述（中文，带数值）
- [ ] 使用 self.logger 记录内部逻辑（不要直接 print）

---

## 4. 算法开发与交付流程

### 4.1. 开发环境准备

* **创建独立的Python虚拟环境：** `python -m venv venv`
* **激活虚拟环境：** `source venv/bin/activate` **(Linux) 或** `venv\Scripts\activate` **(Windows)**
* **安装平台SDK：** `pip install path/to/procvision_algorithm_sdk-1.0.0-py3-none-any.whl`
* **安装项目依赖，**如 opencv-python, torch 等： `pip install opencv-python numpy ...`

### 4.2. 编码实现

* **创建您的项目目录，例如** **pa_screw_check**。
* **在目录下创建主文件，例如** **main.py**。
* **在** **main.py** **中，创建您的算法类，使其继承自** **procvision_algorithm_sdk.BaseAlgorithm** **并实现所有抽象方法。**

### 4.3. 配置文件准备

**在您的项目根目录下，必须包含以下三个配置文件：**

* **requirements.txt**

  * **用途**: 列出项目所有的Python依赖及其**精确版本**。
  * **生成方式**: 在激活的虚拟环境中运行 **pip freeze > requirements.txt**。
  * **内容示例**:

    ```text
    numpy==1.21.6
    opencv-python==4.5.5.64
    torch==1.10.2
    procvision_algorithm_sdk==1.0.0
    ```
* **manifest.json**

  * **用途**: 告知平台如何加载您的算法。
  * **内容示例**:

    ```json
    {
      "name": "universal_screw_detection",
      "version": "2.0.0",
      "entry_point": "main:UniversalScrewDetector",
      "description": "通用螺丝检测算法（支持A/B/C系列产品）",
      "supported_pids": ["A01", "A02", "A03", "B01", "B02", "C01"],
      "required_assets": {
        "A01": {
          "config": "configs/A01.json",
          "template": "templates/A01_ref.jpg"
        },
        "A02": {
          "config": "configs/A02.json",
          "template": "templates/A02_ref.jpg"
        },
        "B01": {
          "config": "configs/B01.json"
        },
        "C01": {
          "config": "configs/C01.json",
          "model": "models/model_C01.pt"
        }
      },
      "default_config": {
        "model": "models/default_model.pt"
      }
    }
    ```
  * **字段说明**:

    - **name**: 算法唯一标识（小写字母、数字、下划线）
    - **version**: 语义化版本（推荐 `major.minor.patch`）
    - **entry_point**: 格式为 `[模块名]:[类名]`，例如 `main:ScrewCheckAlgorithm`
    - **supported_pids**: **关键字段** - 声明此算法包支持的所有产品型号（PID）列表。算法需要在execute/pre_execute中根据传入的pid参数动态加载对应配置。[**设计原理**：一个算法实例支持多个PID，通过配置差异化适配不同产品]
    - **required_assets**: **新增** - 可选字段，声明每个PID所需的资源配置（模型、配置文件、模板等）。格式：`{pid: {resource_type: path}}`。
    - **default_config**: **新增** - 可选字段，指定默认使用的资源（当PID未在required_assets中声明时）

### 4.4. 构建离线交付包

 **这是交付前的**最后也是最关键的一步**。**

* **下载离线依赖**:
  在项目根目录下创建一个名为 **wheels** **的文件夹。然后运行** **pip download** **命令，为**目标工作站环境**下载所有依赖的wheel文件。**

```
   bash
   # 清理旧的依赖包
   rm -rf ./wheels
   mkdir ./wheels

   # 示例：为Windows 10 x64, Python 3.8的环境下载依赖
   pip download \
       -r requirements.txt \
       -d ./wheels/ \
       --platform win_amd64 \
       --python-version 3.8 \
       --implementation cp \
       --abi cp38
```

**注意：** `--platform` **,** `--python-version` **等参数必须与平台方提供的目标环境规格严格匹配。**

* **打包最终交付物**:
  将以下所有内容压缩成一个 **.zip** **文件：**
* **您的算法源代码目录 (例如****pa_screw_check/**)
* **requirements.txt** **文件**
* **manifest.json** **文件（包含 entry_point、版本、步骤 schema、`supported_pids` 等信息）**
* **assets/** **目录（可选，用于存放模型/标定/模板等静态文件）**
* **包含所有** **.whl** **文件的** **wheels** **目录**

  **最终压缩包的内部结构应如下所示**:

  ```text
  product_a_screw_check-v1.2.1-offline.zip
  ├── pa_screw_check/
  │   ├── __init__.py
  │   └── main.py
  ├── assets/
  │   └── weld_unet.pt
  ├── wheels/
  │   ├── numpy-1.21.6-cp38-cp38-win_amd64.whl
  │   ├── opencv_python-4.5.5.64-cp38-cp38-win_amd64.whl
  │   └── ... (所有其他依赖的.whl文件)
  ├── manifest.json
  └── requirements.txt
  ```

**命名规范**: 推荐使用 **[算法名]-v[版本号]-offline.zip** **的格式。**

## 5. GitHub CI/CD（构建与发布算法SDK）

CI/CD 针对的是 `procvision_algorithm_sdk` 仓库，而非具体算法实现。推荐配置如下：

1. **触发策略**

   - `main` 分支的合并请求：运行测试与静态检查，确保SDK接口稳定。
   - `v*` 标签推送：在通过测试后构建产物并发布到内部PyPI（或GitHub Packages）。
2. **流水线阶段**

   - Checkout 代码，设置与SDK兼容的 Python 版本（如3.8）。
   - 安装开发依赖，执行 `ruff`/`mypy` 等静态检查及 `pytest` 单元/集成测试。
   - 调用 `python -m build` 生成 sdist 与 wheel。
   - 上传构建产物为 workflow artifact；若为标签构建，使用 `pypa/gh-action-pypi-publish` 将 wheel 上传至内网PyPI或 GitHub Packages。
3. **示例 workflow (`.github/workflows/build.yml`)**：

```yaml
name: build-and-publish

on:
  push:
    branches: [ main ]
    tags: [ "v*" ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.8"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt build twine pytest
      - name: Run tests
        run: pytest
      - name: Build wheel and sdist
        run: python -m build
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: sdk-dist
          path: |
            dist/*.whl
            dist/*.tar.gz
      - name: Publish to GitHub Packages
        if: startsWith(github.ref, 'refs/tags/v')
        uses: pypa/gh-action-pypi-publish@v1.8.8
        with:
          user: __token__
          password: ${{ secrets.PYPI_TOKEN }}
          repository-url: https://upload.pypi.org/legacy/
```

> **注意**：若需发布到 GitHub Packages 或内部PyPI，请将 `repository-url` 替换为对应服务地址；如生产环境完全离线，可在CI完成后将 wheel 同步到内网制品库，由运维在目标环境离线安装。

---

## 6. 结论

本规范聚焦单工位、单镜头、人工可重试的首批场景，要求算法团队在0→1阶段即落实以下要点：

* 输入输出 schema 与步骤可配置参数（含共享内存图像、用户配置、统一返回值）。
* 共享内存传图、Session 状态管理、生命周期钩子与标准化日志/诊断。
* 离线依赖/wheels/资产的完整打包与校验机制。
* 基于 GitHub Actions 的自动化构建、测试与 PIP 包发布流程。

遵循本规范可确保算法包与平台业务流程解耦，并为后续复杂场景的扩展打下统一的抽象基础。
