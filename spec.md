# **工业视觉平台ProcVision算法开发规范**

## 版本变更说明

**当前版本：v0.2.1** (2025-11-20)
**关键更新：修复架构审查问题，增强文档完整性和一致性**

### v0.2.0 → v0.2.1 核心变更

1. **统一时间戳格式**：所有时间戳统一使用 Unix 毫秒时间戳 `timestamp_ms`
2. **优化接口参数顺序**：高频参数（pid, session）前置，提升可读性
3. **简化返回值结构**：删除 BaseResponse Schema，保持简单扁平
4. **简化参数类型系统**：仅支持基本类型（int, float, rect, enum, bool, string）
5. **明确字段约束**：`defect_rects` 限制 20 个元素以内
6. **删除 overlay 字段**：统一为 Phase 01 不支持 overlay
7. **完善代码示例**：补充完整类型注解和文档规范
8. **补充边界场景**：新增 15 个边界场景处理指南
9. **定义标准错误码**：统一定义 7 个标准错误码
10. **简化 Session API**：移除 ttl/reset，仅保留 get/set/delete

### v0.1.0 → v0.2.0 核心变更

1. **`__init__`签名调整**：移除 `pid: str`参数，算法实例不绑定特定PID
2. **`execute/pre_execute`新增 `pid`参数**：每次调用时动态传递当前产品型号
3. **`manifest.json`增强**：新增 `required_assets`字段，声明每个PID的资源配置
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
* **Python版本**: **[例如: Python 3.10.x]**
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

    def __init__(self) -> None:
        """
        构造函数。在算法实例创建时调用。

        说明：
            - 算法实例不绑定具体PID，需支持所有supported_pids中的型号
            - 在此初始化轻量级资源（配置、路径等）
            - 重量级资源（模型、显存）应在setup()中初始化

        示例：
            >>> class MyAlgo(BaseAlgorithm):
            ...     def __init__(self) -> None:
            ...         super().__init__()  # 必须调用父类构造函数
            ...         self.configs = {}  # 配置缓存
            ...         self.model = None  # 模型占位符
            ...         self._resources_loaded = False
        """
        self._resources_loaded: bool = False
        self._model_version: Optional[str] = None
        self._supported_pids: List[str] = []

    # 生命周期钩子（可选实现）
    def setup(self) -> None:
        """
        算法实例启动时调用一次。

        说明：
            - 可选实现，非强制
            - 如需扩展父类行为，请先调用 super().setup()
            - 用于加载模型、建立共享内存/显存池等重量级初始化

        示例：
            >>> def setup(self) -> None:
            ...     super().setup()  # 如需继承父类行为
            ...     manifest = self._load_manifest()
            ...     for pid in manifest["supported_pids"]:
            ...         config = self._load_config(pid)
            ...         self.configs[pid] = config
            ...     self.model = self._load_model()
            ...     self._resources_loaded = True
        """
        return None

    def teardown(self) -> None:
        """
        算法实例销毁前调用一次。

        说明：
            - 可选实现，非强制
            - 如需扩展父类行为，请先调用 super().teardown()
            - 用于释放模型、显存、共享内存、后台线程/连接

        示例：
            >>> def teardown(self) -> None:
            ...     super().teardown()  # 如需继承父类行为
            ...     if self.model:
            ...         self.model.release()
            ...         self.model = None
            ...     self.configs.clear()
        """
        return None

    def on_step_start(self, step_index: int, session: "Session", context: Dict[str, Any]) -> None:
        """
        每步执行前调用。

        说明：
            - 可选实现，非强制
            - 可以清理临时缓存、记录时间戳、校验输入meta

        示例：
            >>> def on_step_start(self, step_index, session, context):
            ...     self.step_start_time = time.time()
            ...     session.set(f"step_{step_index}_start", time.time())
        """
        return None

    def on_step_finish(self, step_index: int, session: "Session", result: Dict[str, Any]) -> None:
        """
        每步执行后调用。

        说明：
            - 可选实现，非强制
            - 可以写日志、统计耗时、清理缓存或写回状态

        示例：
            >>> def on_step_finish(self, step_index, session, result):
            ...     latency = time.time() - self.step_start_time
            ...     self.logger.info(f"步骤{step_index}完成，耗时{latency:.2f}s")
            ...     session.set(f"step_{step_index}_latency", latency)
        """
        return None

    def reset(self, session: "Session") -> None:
        """
        当平台触发重新检测/中断时调用。

        说明：
            - 可选实现，非强制
            - 用于清理本次检测相关的算法内部临时资源
            - 不要在此释放模型等跨会话资源（应在teardown中）
            - Session 由SDK自动管理，无需手动调用 reset

        示例：
            >>> def reset(self, session):
            ...     super().reset(session)  # 如需继承父类行为
            ...     self.temp_cache.clear()
        """
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
        user_params: Dict[str, Any],
        shared_mem_id: str,
        image_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        执行前调用，用于产出参考信息（模板、ROI等）。

        参数说明：
            - step_index: 当前步骤索引（从1开始）
            - pid: 产品型号编码（平台传递）
            - session: 平台为本次工艺提供的 Session 对象（含 state_store/context）
            - user_params: UI/配置下发的可调参数（按步骤 schema 校验）
            - shared_mem_id: 平台提供的共享内存ID，图像数据存放其中
            - image_meta: 图像元信息（分辨率、格式、时间戳等）

        参数分组逻辑：
            1. 步骤控制: step_index
            2. 上下文信息: pid, session
            3. 用户输入: user_params
            4. 图像数据: shared_mem_id, image_meta

        Returns:
            Dict[str, Any]: 参考信息字典，结构见 3.8.2 节

        Raises:
            不应抛出异常，所有错误应通过返回值中的 status="ERROR" 表示

        Example:
            >>> def pre_execute(self, step_index, pid, session, user_params, shared_mem_id, image_meta):
            ...     # 1. 验证参数
            ...     if pid not in self.supported_pids:
            ...         return {
            ...             "status": "ERROR",
            ...             "message": f"不支持的产品型号: {pid}",
            ...             "error_code": "1001"
            ...         }
            ...
            ...     # 2. 获取图像
            ...     img = read_image_from_shared_memory(shared_mem_id, image_meta)
            ...
            ...     # 3. 执行业务逻辑
            ...     brightness = self._check_brightness(img)
            ...
            ...     # 4. 返回结果
            ...     return {
            ...         "status": "OK",
            ...         "message": f"光照检查通过: {brightness:.1f} lux",
            ...         "data": {
            ...             "calibration_rects": [...]
            ...         },
            ...         "debug": {"brightness": brightness}
            ...     }
        """
        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        step_index: int,
        pid: str,
        session: "Session",
        user_params: Dict[str, Any],
        shared_mem_id: str,
        image_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        执行核心检测/引导逻辑。

        参数说明：
            - step_index: 当前步骤索引（从1开始）
            - pid: 产品型号编码（平台传递）
            - session: 平台为本次工艺提供的 Session 对象（含 state_store/context）
            - user_params: UI/配置下发的可调参数（按步骤 schema 校验）
            - shared_mem_id: 平台提供的共享内存ID，图像数据存放其中
            - image_meta: 图像元信息（分辨率、格式、时间戳等）

        参数分组逻辑：
            1. 步骤控制: step_index
            2. 上下文信息: pid, session
            3. 用户输入: user_params
            4. 图像数据: shared_mem_id, image_meta

        Returns:
            Dict[str, Any]: 检测结果字典，结构见 3.8.3 节

        Raises:
            不应抛出异常，所有错误应通过返回值中的 status="ERROR" 表示

        Example:
            >>> def execute(self, step_index, pid, session, user_params, shared_mem_id, image_meta):
            ...     # 1. 验证参数
            ...     if pid not in self.supported_pids:
            ...         return {
            ...             "status": "ERROR",
            ...             "message": f"不支持的产品型号: {pid}",
            ...             "error_code": "1001"
            ...         }
            ...
            ...     # 2. 获取图像
            ...     img = read_image_from_shared_memory(shared_mem_id, image_meta)
            ...
            ...     # 3. 执行业务逻辑
            ...     result = self._detect(img, user_params)
            ...
            ...     # 4. 返回结果
            ...     return {
            ...         "status": "OK",
            ...         "data": {
            ...             "result_status": "OK" if result.ok else "NG",
            ...             "ng_reason": result.reason,
            ...             "defect_rects": result.boxes[:20],  # 限制最大数量
            ...         }
            ...     }
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
      "status": "OK" | "ERROR",           // 首层：通用状态
      "message": "光源初始化完成",           // 错误或提示信息
      "data": {                             // 二层：业务数据
        "calibration_rects": [              // 支持返回多个标定框
          {"x": 100, "y": 120, "width": 200, "height": 250, "label": "roi-1"},
          {"x": 400, "y": 300, "width": 150, "height": 180, "label": "roi-2"}
        ],
        "debug": {"latency_ms": 25.3}
      }
    }
    ```
* **execute(step_index, session, shared_mem_id, image_meta, user_params)**

  * **返回值结构**:

    ```json
    {
      "status": "OK" | "ERROR",            // 首层：通用状态（调用成功/失败）
      "message": "人类可读信息（仅错误时）",
      "data": {                              // 二层：应用业务结果
        "result_status": "OK" | "NG",      // 业务判定（合格/不合格）
        "ng_reason": "右下角螺丝缺失",
        "defect_rects": [
          {"x": 550, "y": 600, "width": 50, "height": 50, "label": "missing_screw", "score": 0.82}
        ],
        "position_rects": [
          {"x": 100, "y": 120, "width": 200, "height": 250, "label": "screw_position"}
        ],
        "debug": {
          "confidence": 0.82,
          "brightness": 115.5,
          "latency_ms": 48.7,
          "model_version": "yolov5s_20240101"
        }
      }
    }
    ```

### 3.3. Session 与状态共享

SDK在每次工艺流程开始时创建 `Session` 对象，并在整个流程中透传给 `pre_execute` / `execute` / 生命周期钩子。

#### 3.3.1. Session API 定义

```python
class Session:
    """会话上下文对象，用于跨步骤数据共享。"""

    @property
    def id(self) -> str:
        """会话唯一标识。"""
        return self._id

    @property
    def context(self) -> Dict[str, Any]:
        """只读上下文信息（产品信息、操作员等）。"""
        return self._context.copy()

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取会话存储中的值。

        **说明**：Session 仅在单次检测流程内有效，跨产品检测会重新初始化。

        Args:
            key: 键名
            default: 默认值（不存在时返回）

        Returns:
            存储的值或默认值

        Example:
            >>> template = session.get("template")
            >>> count = session.get("retry_count", 0)
        """
        return self._state_store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        设置会话存储中的值。

        **说明**：Session 仅在单次检测流程内有效，数据不会跨检测保留。

        Args:
            key: 键名
            value: 值（必须是JSON可序列化的）

        Raises:
            TypeError: 当value不是JSON可序列化时

        Example:
            >>> session.set("template", template_image)
            >>> session.set("alignment_result", result)
        """
        # 验证可序列化
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            raise TypeError(f"值必须是JSON可序列化的: {type(value)}")

        self._state_store[key] = value

    def delete(self, key: str) -> bool:
        """
        删除会话存储中的值。

        Args:
            key: 键名

        Returns:
            成功返回True，不存在返回False
        """
        if key in self._state_store:
            del self._state_store[key]
            return True
        return False

    def exists(self, key: str) -> bool:
        """检查键是否存在。"""
        return key in self._state_store
```

**Session 字段示例**：

```python
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

#### 3.3.2. Session 使用示例

```python
def pre_execute(self, step_index, pid, session, user_params, shared_mem_id, image_meta):
    """使用Session共享数据示例。"""

    # 1. 读取之前步骤的结果
    template = session.get("template")
    if template is None:
        return {
            "status": "ERROR",
            "message": "未找到模板，请先执行模板匹配步骤",
            "error_code": "1003"
        }

    # 2. 存储当前步骤结果
    alignment_result = self._align(image, template)
    session.set("alignment", alignment_result)

    # 3. 计数器用法（需手动get/set）
    retry_count = session.get("retry_count", 0) + 1
    session.set("retry_count", retry_count)
    if retry_count > 3:
        # 检测流程将在本次结束后重新初始化Session
        pass

    return {
        "status": "OK",
        "data": {"alignment": alignment_result}
    }
```

#### 3.3.3. Session 生命周期

```
平台创建Session
    ↓
[setup()] - 只在算法启动时调用一次
    ↓
[pre_execute(step=0)] → [execute(step=0)]  →  [Session数据持久化]
    ↓                                           ↓
[pre_execute(step=1)] → [execute(step=1)]  →  [Session数据持久化]
    ↓                                           ↓
               ...（更多步骤）...
    ↓                                           ↓
[on_step_finish()] - 每步结束后调用
    ↓
平台结束Session（自动清理）
    ↓
[teardown()] - 可选，进程退出前调用
    ↓
进程退出
```

**重要约束**：
- Session 仅在**单次检测流程**内有效，跨产品会重新初始化
- 不同产品的检测流程使用**不同的 Session** 实例
- 算法重启后 Session 数据**不会保留**
- Session 数据存储在**内存**中，不要存储大量数据（建议<100KB）
- 如需跨检测持久化数据，应在算法实例属性中保存

### 3.4. 图像传输（共享内存）

* 平台将相机采集的图像以 **JPEG** 编码写入共享内存，并把 `shared_mem_id` +  `image_meta`（仅时间戳、图像尺寸与相机ID）传给算法。
* 算法必须通过SDK提供的 `read_image_from_shared_memory(shared_mem_id, image_meta)` 工具函数获取图像数据，可自行解码。禁止在JSON中传输Base64图像，也不再支持临时落盘文件。
* Phase 01 阶段不支持 overlay 输出。

#### 3.4.1. image_meta 数据结构（JPEG-only）

**用途**: 提供最小必要元信息（不包含解码细节）。

**必需字段**:

```json
{
  "width": 1920,
  "height": 1200,
  "timestamp_ms": 1714032000123,
  "camera_id": "cam-01"
}
```

#### 3.4.2. JPEG-only 约定

**统一行为**：SDK 始终写入 JPEG。

**image_meta 最小集合**：`width`, `height`, `timestamp_ms`, `camera_id`。

**调用示例**：

```python
img = read_image_from_shared_memory(shared_mem_id, {"width": 1920, "height": 1200, "timestamp_ms": 1714032000123, "camera_id": "cam-01"})
```

### 3.5. 错误、日志与诊断

#### 3.5.1. **程序异常 (ProgramError)**

- 含义：代码/环境/资源/通信问题导致无法执行（如模型文件缺失、GPU OOM、协议解析失败、超时/心跳丢失）。
- 表现：仅使用 `status="ERROR"` 与 `message` 字段，保持最简。
- 示例：

```json
{
  "status": "ERROR",
  "message": "模型文件损坏: model.pt not found"
}
```

#### 3.5.2. 日志与诊断

- 日志API：使用结构化 `logger`，输出 JSON 字段（`timestamp_ms`, `session_id`, `step_index`, `status`, `latency_ms`, `trace_id` 等）。不要直接 `print`。
- 诊断数据：通过返回值 `diagnostics` 或 `diagnostics.publish()` 上报置信度、亮度、耗时等，用于 UI 展示与远程排查。
- 超时与心跳：runner 监控 `pre_execute`/`execute` 调用超时与心跳；超时视为程序异常，记录日志并按固定策略处置。

### 3.6. SDK Runner 与算法进程通信

* **通信方式**：runner 通过启动算法可执行入口（`python main.py serve` 等）并使用 `stdin/stdout` 双向管道通信。协议采用“4字节大端长度 + UTF-8 JSON”帧格式，确保无粘包。
* **消息字段**（RESTful 两层）：
  ```
  {
    "type": "hello|call|result|ping|pong|error|shutdown",
    "request_id": "uuid-1234",
    "method": "pre_execute|execute",   // 仅 call
    "payload": {...},                   // 入参（call）
    "timestamp_ms": 1714032000123,
    "status": "OK|ERROR",              // 首层：通用接口调用状态
    "message": "人类可读信息（仅错误时）",
    "data": { ... }                      // 二层：应用业务数据
  }
  ```
* **握手流程**：算法启动后立即输出 `{"type":"hello","sdk_version":"1.0"}`，runner 返回 `{"type":"hello","runner_version":"1.0"}`。握手完成前不得发送业务消息。
* **调用流程**：runner 发送 `call` 帧，`payload` 中包含 `step_index`, `session`, `shared_mem_id`, `image_meta`, `user_params` 等；算法处理后返回 `result` 帧，其首层为通用状态（`status`/`message`），业务结果放在 `data` 中。
* **心跳/超时**：runner 定期发送 `ping`，算法需在指定超时时间（默认 1s）内回复 `pong`。若超时，runner 记录日志并尝试优雅 shutdown；多次失败后强制终止子进程。
* **日志与协议隔离**：算法必须仅在 stdout 输出协议帧，所有日志写入 stderr（由 `logger` 统一管理），避免协议流被污染。
* **关闭流程**：runner 发送 `{"type":"shutdown"}`，算法应调用 `teardown()` 并返回 `{"type":"shutdown","status":"OK"}` 后退出进程。

#### 3.6.1. 心跳机制

心跳机制用于监控算法进程健康状态，确保长时间运行的检测任务可靠性。

**心跳流程**：

```
Runner ←→ Algorithm (stdin/stdout)
    ↓
[启动后] 算法发送 {"type":"hello"}
Runner 返回 {"type":"hello"}
    ↓
[检测循环]
    ↓
Runner 每 5 秒发送 {"type":"ping", "request_id":"uuid"}
算法需在 2 秒内回复 {"type":"pong", "request_id":"uuid"}
    ↓
[调用算法]
Runner 发送 {"type":"call", "method":"execute", ...}
算法处理（< 30 秒）
算法返回 {"type":"result", ...}
    ↓
[心跳继续]
Runner 继续每 5 秒发送 ping
    ↓
[异常场景]
├─ 心跳超时（> 2 秒未响应）
│   ├─ 记录警告日志
│   ├─ 继续等待 2 秒（重试）
│   └─ 再次超时 → 视为进程僵死，强制终止（SIGKILL）
│
├─ execute 超时（> 30 秒）
│   ├─ Runner 发送 SIGTERM（优雅终止）
│   ├─ 等待 3 秒
│   └─ 仍未退出 → SIGKILL（强制终止）
│
└─ 进程崩溃
    └─ Runner 自动重启（最多 3 次，然后告警）
```

**心跳参数**：

| 参数 | 说明 | 默认值 | 说明 |
|------|------|--------|------|
| ping 间隔 | Runner 发送 ping 的间隔 | 5 秒 | 避免过于频繁 |
| 心跳超时 | 算法回复 pong 的超时时间 | 2 秒 | 包括网络延迟 + 算法处理 |
| 最大重试 | 连续心跳丢失次数 | 2 次 | 超过则判定为僵死 |
| execute 超时 | execute 最大执行时间 | 30 秒 | pre_execute 为 10 秒 |
| 优雅终止超时 | SIGTERM → SIGKILL 等待 | 3 秒 | 给算法清理资源时间 |
| 自动重启上限 | 进程崩溃后自动重启 | 3 次 | 防止无限重启 |

**心跳示例**：

```python
# Runner → Algorithm
{
  "type": "ping",
  "request_id": "ping-20241120-001",
  "timestamp_ms": 1714032005123
}

# Algorithm → Runner (需在 2 秒内回复)
{
  "type": "pong",
  "request_id": "ping-20241120-001",
  "timestamp_ms": 1714032005125
}
```

**算法实现要求**：

1. **必须回复 pong**：收到 ping 后立即回复，不能阻塞
2. **保持异步**：建议在独立线程中处理心跳，避免 execute 阻塞导致心跳超时
3. **不要日志**：心跳日志由 Runner 记录，算法不应输出 ping/pong 日志

**Runner 处理策略**：

```python
# 伪代码
while process.is_alive():
    # 发送 ping
    send_ping()

    # 等待 pong
    try:
        pong = wait_for_pong(timeout=2s)
        if pong.request_id == ping.request_id:
            continue  # 心跳正常
    except TimeoutError:
        retry_count += 1

        if retry_count >= MAX_RETRY:
            # 进程僵死
            logger.error("心跳丢失，进程僵死")
            process.kill()  # SIGKILL
            break

        logger.warning(f"心跳超时，第 {retry_count} 次重试")
```

#### 3.6.2. 接口协议约定（检测异常语义）

**pre_execute（条件未准备好）**

```json
{
  "status": "ERROR",
  "message": "光照不足: 35.2 < 50.0 lux"
}
```

**pre_execute（返回标定框）**

```json
{
  "status": "OK",
  "data": {
    "calibration_rects": [
      {"x": 100, "y": 120, "width": 200, "height": 250, "label": "roi-1"},
      {"x": 400, "y": 300, "width": 150, "height": 180, "label": "roi-2"}
    ]
  }
}
```

**execute（不合格判定）**

```json
{
  "status": "OK",
  "data": {
    "result_status": "NG",
    "ng_reason": "检测到3处划痕",
    "defect_rects": [...],
    "debug": {"defect_count": 3}
  }
}
```

**execute（程序异常）**

```json
{
  "status": "ERROR",
  "message": "模型文件损坏: model.pt not found"
}
```

### 3.7. SDK开发工具 (Dev Runner)

为了确保算法交付质量，SDK 内置了轻量级开发运行器 (Dev Runner)，模拟主平台的调用行为。算法团队**必须**在交付前使用此工具进行自测。

#### 3.7.1. 命令行工具 (CLI)

SDK 提供 `procvision-cli` 命令行工具：

```bash
# 1. 验证算法包结构与 manifest.json
procvision-cli validate ./my_algorithm_project/
# 可省略项目路径，默认当前目录
procvision-cli validate

# 2. 模拟运行算法 (Dev Runner)
procvision-cli run ./my_algorithm_project/ \
    --pid A01 \
    --image ./test_images/sample.jpg \
    --params '{"threshold": 0.8}'
 
# 3. 构建离线交付包 (Package)
procvision-cli package ./my_algorithm_project/ \
    --output ./my_algorithm_project-offline.zip \
    --auto-freeze \
    --wheels-platform win_amd64 \
    --python-version 3.10 \
    --implementation cp \
    --abi cp310

# 4. 初始化脚手架 (Init)
procvision-cli init algorithm-example \
    --pids p001,p002 \
    --version 1.0.0 \
    --dir ./algorithm-example
```

**CLI 参数与输出规范（新增）**

- 验证命令 `validate`
  - 默认项目：省略路径时默认为当前目录 `.`（等价于 `procvision-cli validate .`）
  - 参数：`validate [project] [--manifest <path>] [--zip <path>] [--json]`
  - 输出：默认人类可读清单（逐项 ✅/❌ 与提示）；`--json` 返回机器可读 JSON

- 运行命令 `run`
  - 用法：`run <project> --pid <pid> --image <path> [--params <json>] [--json]`
  - 输出：默认人类可读（显示预执行与执行状态、NG 原因与缺陷数）；`--json` 返回原始结构

- 打包命令 `package`（新）
  - 用法：`package <project> [--output <zip>] [--requirements <path>] [--auto-freeze] [--wheels-platform <p>] [--python-version <v>] [--implementation <impl>] [--abi <abi>] [--skip-download]`
  - 行为：
    - 自动生成或使用 `requirements.txt`
    - 可按目标环境下载 wheels（`--wheels-platform/--python-version/--implementation/--abi`）
    - 打包 `源码/manifest/requirements/assets/` 与 `wheels/` 到 zip（不保存报告）
  - 输出：人类可读的结果行，例如 `打包成功: <zip>` 或具体错误说明
  - 短参数与默认值（便捷用法）：
    - `-o` 等价 `--output`
    - `-r` 等价 `--requirements`
    - `-a` 等价 `--auto-freeze`
    - `-w` 等价 `--wheels-platform`，默认 `win_amd64`
    - `-p` 等价 `--python-version`，默认 `3.10`
    - `-i` 等价 `--implementation`
    - `-b` 等价 `--abi`
    - `-s` 等价 `--skip-download`

- 初始化命令 `init`（新）
  - 用法：`init <name> [-d|--dir <dir>] [--pids <p1,p2>] [-v|--version <ver>] [-e|--desc <text>]`
  - 行为：生成 `manifest.json` 与源码包目录，并在 `main.py` 中以注释形式标注需要算法团队修改的位置（PID 列表、步骤 schema、检测逻辑等）
  - 输出：`初始化成功: <path>` 与后续修改提示

#### 3.7.2. Dev Runner 行为

Dev Runner 运行在开发者本地环境，主要职责如下：

1. **环境模拟**: 启动算法子进程，建立 Stdin/Stdout 管道。
2. **协议校验**: 验证算法发出的 JSON 消息是否符合 3.6 节定义的协议格式。
3. **Schema 校验**: 根据 `get_info()` 返回的 schema，验证 `user_params` 和返回值的字段类型。
4. **资源模拟**:
   * **共享内存**: 使用本地临时文件或 System V 共享内存模拟，将本地图片加载并传递给算法；`shared_mem_id` 绑定当前会话，约定为 `dev-shm:<session.id>`，以便日志与诊断可定位到具体会话。开发模式中会先将本地图片字节写入共享内存，再由算法通过 `read_image_from_shared_memory(shared_mem_id, image_meta)` 读取并解码。
   * **Session**: 创建虚拟 Session 对象，模拟状态存储。
5. **报告生成**: 运行结束后生成简单的 HTML/JSON 报告，展示耗时、返回值和潜在错误。

---

### 3.7.1. 参数类型系统

`get_info()` 返回的 `params` 中定义的参数类型包括：

```python
param_types = {
    "int": {
        "has_min_max": True,
        "unit": "可选单位说明"
    },
    "float": {
        "has_min_max": True,
        "unit": "建议提供单位（如ms, lux）"
    },
    "rect": {
        "has_min_max": False,
        "format": "x,y,width,height",
        "description": "矩形区域，左上角原点"
    },
    "enum": {
        "has_choices": True,
        "choices": ["value1", "value2"]
    },
    "bool": {
        "has_min_max": False
    },
    "string": {
        "has_min_max": True,
        "min_length": 1,
        "max_length": 1000,
        "pattern": "可选正则表达式"
    }
}
```

**使用示例**：

```python
# string类型：模型路径
{
    "key": "model_path",
    "type": "string",
    "description": "模型文件路径",
    "max_length": 500
}

# int类型：曝光时间（ms）
{
    "key": "exposure_ms",
    "type": "int",
    "default": 12,
    "min": 8,
    "max": 20,
    "unit": "ms"
}

# float类型：置信度阈值
{
    "key": "threshold",
    "type": "float",
    "default": 0.7,
    "min": 0.5,
    "max": 0.95
}

# rect类型：检测区域
{
    "key": "roi",
    "type": "rect",
    "required": true,
    "description": "检测区域，左上角原点"
}

# enum类型：运行模式
{
    "key": "mode",
    "type": "enum",
    "choices": ["fast", "balanced", "accurate"],
    "default": "fast"
}

# bool类型：调试开关
{
    "key": "enable_debug",
    "type": "bool",
    "default": false
}
```

**类型校验规则**：
1. Dev Runner会在运行前根据schema校验 `user_params`
2. 类型不匹配时返回 `error_code: "1006"`
3. 值超出min/max范围时返回 `error_code: "1006"`
4. string 长度超出限制时返回 `error_code: "1006"`

---

## 3.8. 返回值详解与使用指南

本节详细解释 `pre_execute` 和 `execute` 方法的返回值结构，防止开发团队因理解偏差导致实现错误。

### 3.8.1. 返回值设计哲学

**核心原则**：

1. **明确的状态机**：平台根据 `status` 字段决定下一步动作
2. **人机分离**：`status` 供平台逻辑使用，`message` 供操作员阅读
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
      └─► status: ERROR ──► handle error

┌──────────┐
│ execute  │
└─────┬────┘
      │
      ├─► status: OK ──► next product (检测通过)
      │
      ├─► status: NG ──► show defects + wait user (人工判断)
      │
      └─► status: ERROR ──► handle error
```

---

### 3.8.2. pre_execute 返回值详解

**适用场景**：

- 光照检查（验证检测条件）
- 相机标定验证
- **任何不需要真实检测结果但需要参考信息的场景**

**完整结构**：

```json
{
  "status": "OK" | "ERROR",
  "message": "人类可读的信息",
  "debug": {"latency_ms": 25.3}
}
```

#### 3.8.2.1. status 字段（必需）

**含义**: 步骤准备结果状态

**取值说明**:

- **`"OK"`**  : 准备成功，可以继续执行 `execute`
- **`"ERROR"`**  : 准备失败，需要由平台统一策略处理

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

#### 3.8.2.2. 交互提示

本阶段不使用 `suggest_action` 字段；错误处理与交互由平台统一策略决定。
- 平台行为: 停止产线，通知工程师

**平台UI行为**：由平台统一策略处理错误与交互，无需算法返回交互指示。

**实际案例对比**:

```python
# 场景1: 光照不足
{
    "status": "ERROR",
    "message": "光照不足: 35.2 < 50.0 lux"
}
# UI显示: [光照不足: 35.2 < 50.0 lux]

# 场景2: 产品缺陷
{
    "status": "ERROR",
    "message": "产品表面严重划伤，无法进行检测"
}
# UI显示: [产品表面严重划伤]
```

---

#### 3.8.2.3. message 字段（必需）

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

# 模板匹配
{
    "status": "ERROR",
    "message": f"模板匹配失败，相似度: {score:.2f} < 0.85"
}
```

---

#### 3.8.2.5. debug 字段（可选）

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
  "status": "OK" | "ERROR",
  "message": "人类可读信息（仅错误时）",
  "data": {
    "result_status": "OK" | "NG",
    "ng_reason": "不合格原因描述",
    "defect_rects": [
      {"x": 550, "y": 600, "width": 50, "height": 50, "label": "scratch", "score": 0.82}
    ],
    "position_rects": [
      {"x": 100, "y": 120, "width": 200, "height": 250, "label": "screw_position"}
    ],
    "debug": {
      "confidence": 0.82,
      "brightness": 115.5,
      "defect_count": 3,
      "latency_ms": 48.7,
      "model_version": "yolov5s_20240101"
    }
  }
}
```

#### 3.8.3.1. status 字段（首层，必需）

**取值**（2个状态）：

- **`"OK"`**  : 调用成功（业务结果在 `data` 内）
- **`"ERROR"`**  : 调用失败（无法返回业务结果）

**平台处理逻辑**（两层）：

```python
result = algorithm.execute(...)

if result["status"] == "ERROR":
    handle_error(result)
else:
    biz = result.get("data", {})
    if biz.get("result_status") == "OK":
        ui.show_success("检测通过")
        move_to_next_product()
    elif biz.get("result_status") == "NG":
        handle_ng(biz)
```

**案例对比**:

```python
# 案例1: 合格品
{
    "status": "OK",
    "data": {
        "result_status": "OK",
        "defect_rects": [],
        "debug": {"defect_count": 0}
    }
}

# 案例2: 缺陷品
{
    "status": "OK",
    "data": {
        "result_status": "NG",
        "ng_reason": "检测到3处划痕",
        "defect_rects": [...],
  "debug": {"defect_count": 3}
    }
}

# 案例3: 检测失败
{
    "status": "ERROR",
    "message": "图像读取失败"
}
```

---

#### 3.8.3.2. ng_reason 字段（`data.result_status="NG"` 时）

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
    "status": "OK",
    "data": {
        "result_status": "NG",
        "ng_reason": "检测到1处划痕",
        "defect_rects": defects
    }
}

# 多缺陷
defects = [
    {"label": "scratch", "score": 0.85},
    {"label": "stain", "score": 0.72},
    {"label": "dent", "score": 0.91}
]
{
    "status": "OK",
    "data": {
        "result_status": "NG",
        "ng_reason": f"检测到{len(defects)}处缺陷: 划痕x1, 污点x1, 凹陷x1",
        "defect_rects": defects
    }
}

# 缺少螺丝（位置明确）
{
    "status": "OK",
    "data": {
        "result_status": "NG",
        "ng_reason": "右下角螺丝缺失",
        "position_rects": [{"x": 550, "y": 600, "label": "missing_screw"}]
    }
}
```

---

#### 3.8.3.3. data.defect_rects 字段（`data.result_status="NG"` 时）

**含义**: 检测到的缺陷列表，**仅在 `data.result_status="NG"` 时有效**

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
    "status": "OK",
    "data": {
        "result_status": "NG",
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

#### 3.8.3.4. data.position_rects 字段（可选）

**含义**: 定位/位置结果（非缺陷），例如螺丝位置、焊接点位置等

**结构与 data.defect_rects 相同，但表示的是正常位置**:

```json
{
  "status": "OK",
  "data": {
    "result_status": "OK",
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
}
```

**使用场景**:

1. **显示检测区域**：在 `data.position_rects` 返回定位结果
2. **显示缺少的组件位置**：与 `data.defect_rects` 配合使用
3. **多点定位**: 螺丝检测、焊点检测等

**案例: 螺丝缺失检测**

```python
{
    "status": "OK",
    "data": {
        "result_status": "NG",
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
        "debug": {"missing_count": 2, "ok_count": 3}
    }
}
# UI显示:
# - 红色框: 2个缺少螺丝的位置 (defect_rects)
# - 绿色框: 3个正常螺丝的位置 (position_rects)
# - 消息: 缺少2颗螺丝
```

---


#### 3.8.3.5. debug 字段（可选）

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

**使用场景**:

```python
def execute(self, ...):
    start = time.time()

    # 推理
    result = self.model(img)

    latency_ms = (time.time() - start) * 1000

    return {
        "status": "OK",
        "data": {
            "result_status": "OK" if result.ok else "NG",
            "defect_rects": result.boxes,
            "debug": {  # 技术指标，不用于业务逻辑
                "latency_ms": latency_ms,
                "model_version": self.model_version,
                "input_shape": img.shape,
                "gpu_memory": torch.cuda.memory_allocated()
            }
        }
  }
```

---

### 3.8.4. pre_execute vs execute 对比总结

| 字段                     | pre_execute    | execute               | 使用场景差异                           |
| ------------------------ | -------------- | --------------------- | -------------------------------------- |
| **status**         | "OK" / "ERROR" | "OK" / "ERROR"        | 首层通用调用状态                      |
| **message**        | 有             | 有                    | 相同                                   |
| **data.result_status** | ❌ 无      | "OK" / "NG"          | 业务判定（execute）                    |
| **data.calibration_rects** | ✅ 有   | ❌ 无                 | pre_execute 可返回多个标定框          |
| **data.defect_rects**   | ❌ 无      | ✅ 有（检测结果）     | 业务数据（execute）                    |
| **data.ng_reason**      | ❌ 无      | ✅ 有（NG时）         | 业务数据（execute）                    |
| **data.position_rects** | ❌ 无      | ✅ 有（定位结果）     | 业务数据（execute）                    |
| **data.debug**          | 可选       | 可选                 | 技术指标，用于问题排查                  |

---

### 3.8.5. 常见错误与纠正

#### ❌ 错误1: status 取值错误

```python
# 错误: pre_execute 返回 NG
return {"status": "NG"}  # ❌ pre_execute 不能有NG

# 正确
return {"status": "ERROR"}  # ✅ 使用ERROR
```

#### ❌ 错误2: 缺少 message 字段

```python
# 错误: status="ERROR" 但没有 message
return {
    "status": "ERROR"
}

# 正确
return {
    "status": "ERROR",
    "message": "光照不足: 35.2 < 50.0 lux"
}
```

#### ❌ 错误3: NG 但没有 ng_reason

```python
# 错误
return {
    "status": "OK",
    "data": {
        "result_status": "NG",
        "defect_rects": [...]
    }
}  # ❌ 缺少 ng_reason

# 正确
return {
    "status": "OK",
    "data": {
        "result_status": "NG",
        "ng_reason": "检测到3处划痕",
        "defect_rects": [...]
    }
}
```

### 3.8.6. 字段约束汇总

为保证系统性能和UI显示效果，以下字段需遵循约束：

| 字段 | 约束 | 说明 |
|------|------|------|
| `supported_pids` | 建议 ≤ 20，最大 50 | 超过20个会影响性能和管理复杂度 |
| `defect_rects` | 最大 20 个元素 | UI渲染性能考虑，超出自动截断 |
| `position_rects` | 建议 ≤ 20 个元素 | 同上 |
| `message` | 建议 < 100 字符 | UI显示空间限制 |
| `ng_reason` | 建议 < 50 字符 | 需简洁明了 |
| ROI 坐标 | x, y ≥ 0，在图像范围内 | 左上角原点，dev runner会校验 |

---

### 3.8.7. 最佳实践 checklist

#### get_info() 最佳实践

- [ ] 返回 dict 包含所有必需字段：name, version, supported_pids, steps
- [ ] `supported_pids` 必须与 manifest.json 中的 `supported_pids` 完全一致
- [ ] `name` 必须与 manifest.json 中的 `name` 完全一致
- [ ] `version` 必须与 manifest.json 中的 `version` 完全一致
- [ ] `supported_pids` 数量建议不超过 20 个（便于管理和测试）
- [ ] steps 数组中的每个 step 都有唯一的 index（从 0 开始）
- [ ] 每个 step 的 params 定义清晰，包含 type, default, min/max（如适用）

#### pre_execute 最佳实践

- [ ] status 只能是 "OK" 或 "ERROR"（首层通用状态）
- [ ] 返回 data.calibration_rects（如需标定，支持多个框）
- [ ] message 包含关键数值信息（如亮度、匹配度）
- [ ] debug 包含耗时（latency_ms）用于性能分析

#### execute 最佳实践

- [ ] 首层 status 只能是 "OK" 或 "ERROR"
- [ ] 业务判定在 data.result_status（OK/NG）
- [ ] NG 时在 data.ng_reason 和 data.defect_rects 给出细节
- [ ] data.defect_rects 包含完整缺陷信息（坐标、标签、置信度）
- [ ] data.debug 包含技术指标（耗时、模型版本、内存使用等）

#### 两个方法通用

- [ ] 所有返回字典必须包含"status"字段
- [ ] 所有数值字段使用标准JSON类型（int, float, str, bool, array, object）
- [ ] 不返回任何图像数据（内存只读原则）
- [ ] message 字段是用户友好的描述（中文，带数值）
- [ ] 使用 self.logger 记录内部逻辑（不要直接 print）

---

### 3.8.8. 防御式编程最佳实践

为增强算法健壮性，建议在 execute/pre_execute 中增加输入校验：

#### 3.8.8.1 图像输入校验

```python
def execute(self, step_index, pid, session, user_params, shared_mem_id, image_meta):
    """执行检测逻辑（含输入校验示例）。"""

    # 1. 验证PID支持
    if pid not in self.supported_pids:
        return {
            "status": "ERROR",
            "message": f"不支持的产品型号: {pid}",
            "error_code": "1001"
        }

    # 2. 验证image_meta必需字段
    required_fields = ["width", "height", "timestamp_ms", "camera_id"]
    for field in required_fields:
        if field not in image_meta:
            return {
                "status": "ERROR",
                "message": f"image_meta缺少必需字段: {field}",
                "error_code": "1006"
            }

    # 3. 验证图像尺寸合理性
    width = image_meta["width"]
    height = image_meta["height"]
    if not (100 <= width <= 8000 and 100 <= height <= 8000):
        return {
            "status": "ERROR",
            "message": f"图像尺寸不合理: {width}x{height}",
            "error_code": "1006"
        }

    # 4. 验证shared_mem_id
    if not shared_mem_id or len(shared_mem_id) < 8:
        return {
            "status": "ERROR",
            "message": "无效的共享内存ID",
            "error_code": "1002"
        }

    # 5. 验证user_params（根据schema）
    schema = self._get_param_schema(step_index)
    validation_result = self._validate_params(user_params, schema)
    if not validation_result["valid"]:
        return {
            "status": "ERROR",
            "message": f"参数校验失败: {validation_result['errors']}",
            "error_code": "1006"
        }

    # 执行检测逻辑
    try:
        img = read_image_from_shared_memory(shared_mem_id, image_meta)

        # 验证图像不为空
        if img is None or img.size == 0:
            return {
                "status": "ERROR",
                "message": "图像数据为空",
                "error_code": "1002"
            }

        # 核心检测逻辑...
        result = self._detect(img, user_params)

        return {
            "status": "OK",
            "data": {
                "result_status": "OK" if result.ok else "NG",
                "ng_reason": result.reason,
                "defect_rects": result.boxes[:20]  # 限制最大数量
            }
        }

    except GPUOutOfMemoryError as e:
        return {
            "status": "ERROR",
            "message": f"GPU显存不足: {e}",
            "error_code": "1004"
        }

    except Exception as e:
        self.logger.error(f"检测异常: {e}", exc_info=True)
        return {
            "status": "ERROR",
            "message": f"检测失败: {str(e)}",
            "error_code": "9999"
        }
```

#### 3.8.8.2 返回值数据校验

```python
def _validate_return_value(self, result: Dict[str, Any]) -> bool:
    """校验返回值格式。"""
    # 1. 检查必需字段
    if "status" not in result:
        self.logger.error("返回值缺少status字段")
        return False

    # 2. 检查status取值
    if result["status"] not in ["OK", "ERROR"]:
        self.logger.error(f"status取值无效: {result['status']}")
        return False

    # 3. ERROR时必须有message
    if result["status"] == "ERROR":
        if "message" not in result or not result["message"]:
            self.logger.error("ERROR状态缺少message字段")
            return False

    # 4. OK时必须有data
    if result["status"] == "OK":
        if "data" not in result or not isinstance(result["data"], dict):
            self.logger.error("OK状态缺少data字段或类型错误")
            return False

        data = result["data"]

        # 5. execute返回必须有result_status
        if "result_status" in data:
            if data["result_status"] not in ["OK", "NG"]:
                self.logger.error(f"result_status取值错误: {data['result_status']}")
                return False

            # 6. NG时必须有ng_reason和defect_rects
            if data["result_status"] == "NG":
                if "ng_reason" not in data:
                    self.logger.error("NG状态缺少ng_reason字段")
                    return False

                if "defect_rects" not in data:
                    self.logger.error("NG状态缺少defect_rects字段")
                    return False

                # 7. defect_rects数量限制
                if len(data["defect_rects"]) > 20:
                    self.logger.warning(f"defect_rects数量超过限制: {len(data['defect_rects'])}")
                    data["defect_rects"] = data["defect_rects"][:20]

    return True
```

---

## 3.9. 边界场景处理指南

### 3.9.1. 边界场景覆盖表

| 场景分类 | 具体场景 | 处理建议 | 推荐错误码 |
|---------|----------|----------|------------|
| **图像输入** | 1. shared_mem_id无效/不存在 | 返回ERROR，检查ID是否正确 | 1002 |
| | 2. image_meta缺少必需字段 | 返回ERROR，列出缺失字段 | 1006 |
| | 3. 图像尺寸超出合理范围 | 返回ERROR，建议调整相机参数 | 1006 |
| | 4. 图像解码失败 | 返回ERROR，检查图像完整性 | 1002 |
| | 5. 图像为空或全黑 | 返回ERROR，提示检查光源 | 1002 |
| **参数输入** | 6. user_params缺少required字段 | 返回ERROR，列出必需字段 | 1006 |
| | 7. user_params类型不匹配 | 尝试转换或返回ERROR | 1006 |
| | 8. params超出min/max范围 | 返回ERROR或自动截断（需日志警告） | 1006 |
| | 9. ROI坐标越界 | 返回ERROR，坐标必须在图像范围内 | 1007 |
| **PID相关** | 10. pid不在supported_pids中 | 返回ERROR，提示检查manifest.json | 1001 |
| | 11. required_assets缺少pid配置 | 在setup()时验证并抛出异常 | 1003 |
| | 12. 配置加载失败 | 返回ERROR，记录详细错误信息 | 1003 |
| **资源管理** | 13. 模型文件不存在 | 在setup()时验证，启动失败 | 1003 |
| | 14. GPU显存不足（OOM） | 返回ERROR，释放资源后重试 | 1004 |
| | 15. 文件句柄泄漏 | 在teardown()中清理，增加监控告警 | - |
| **并发与超时** | 16. pre_execute超时（>10秒） | Runner强制终止，返回TIMEOUT | 1005 |
| | 17. execute超时（>30秒） | Runner强制终止，返回TIMEOUT | 1005 |
| | 18. 心跳丢失 | Runner记录日志，重试或重启进程 | 1005 |
| | 19. 进程崩溃 | Runner自动重启，记录日志 | 1005 |
| **通信协议** | 20. JSON解析失败 | 返回ERROR frame，协议格式错误 | - |
| | 21. 消息粘包/半包 | 校验4字节长度字段，重试或报错 | - |
| | 22. 协议版本不兼容 | hello握手时校验，明确报错 | - |
| **返回值** | 23. defect_rects数量过多（>20） | 自动截断并记录警告 | - |
| | 24. 返回坐标越界 | 在算法内校验，返回ERROR或修正 | 1007 |
| | 25. 返回值缺少必需字段 | Dev Runner中校验并提示 | 1006 |
| | 26. result_status取值错误 | Dev Runner中校验并提示 | 1006 |

### 3.9.2. 处理原则

1. **尽早验证**: 在函数入口处验证所有输入参数
2. **错误分类**: 区分业务错误 (ERROR) 和程序异常 (Exception)
3. **详细日志**: 记录错误发生时的上下文信息
4. **资源清理**: 在 finally 块或 teardown() 中释放资源
5. **不要崩溃**: 所有异常必须捕获并转换为返回值中的 ERROR

---

## 3.10. 标准错误码定义

### 3.10.1. 错误码结构

```json
{
  "status": "ERROR",
  "message": "人类可读的错误描述",
  "error_code": "四位数字编码",
  "debug": {}
}
```

### 3.10.2. 错误码表

| 错误码 | 错误类型 | 说明 | 触发场景 | 推荐处理 |
|--------|----------|------|----------|----------|
| **1001** | invalid_pid | 不支持的产品型号 | pid不在supported_pids中 | 返回ERROR，提示检查manifest.json |
| **1002** | image_load_failed | 图像加载失败 | shared_mem_id无效、图像解码失败 | 返回ERROR，检查图像源 |
| **1003** | model_not_found | 模型/配置不存在 | 模型文件路径错误、配置缺失 | setup()时验证，返回ERROR |
| **1004** | gpu_oom | GPU显存不足 | GPU内存耗尽 | 释放资源后重试，或提示硬件升级 |
| **1005** | timeout | 执行超时 | execute>30秒、pre_execute>10秒 | Runner强制终止，返回TIMEOUT |
| **1006** | invalid_params | 参数校验失败 | 缺少required字段、类型错误、超出范围 | 返回ERROR，说明具体字段 |
| **1007** | coordinate_invalid | 坐标越界 | 返回的坐标超出图像范围 | 在算法内校验，返回ERROR或修正 |
| **9999** | unknown_error | 未知错误 | 未预期的异常 | 记录详细日志，返回通用错误 |

### 3.10.3. 使用示例

```python
def execute(self, ...) -> Dict[str, Any]:
    try:
        # 验证PID
        if pid not in self.supported_pids:
            return {
                "status": "ERROR",
                "message": f"不支持的产品型号: {pid}",
                "error_code": "1001",
                "debug": {"supported_pids": self.supported_pids}
            }

        # ... 执行业务逻辑

    except GPUOutOfMemoryError as e:
        return {
            "status": "ERROR",
            "message": f"GPU显存不足: {e}",
            "error_code": "1004",
            "debug": {"gpu_memory_mb": torch.cuda.memory_allocated()}
        }

    except Exception as e:
        self.logger.error("未知错误", exc_info=True)
        return {
            "status": "ERROR",
            "message": f"检测失败: {str(e)}",
            "error_code": "9999",
            "debug": {"exception": str(e)}
        }
```

**注意**：
- error_code 为字符串类型，便于 JSON 传输
- 业务错误（如 status="NG"）不使用 error_code
- Runner 监控到超时（1005）时自动终止进程
- Dev Runner 应在开发阶段校验所有错误码使用

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
  可通过 CLI 一键打包，或手动压缩。

  **CLI 打包（推荐）**：

  ```bash
  procvision-cli package ./my_algorithm_project/ \
      --output ./my_algorithm_project-offline.zip \
      --auto-freeze \
      --wheels-platform win_amd64 \
      --python-version 3.10 \
      --implementation cp \
      --abi cp310
  ```

  **手动压缩（备选）**：
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
  │   ├── numpy-1.21.6-cp310-cp310-win_amd64.whl
  │   ├── opencv_python-4.5.5.64-cp310-cp310-win_amd64.whl
  │   └── ... (所有其他依赖的.whl文件)
  ├── manifest.json
  └── requirements.txt
  ```

**CLI 输出约定（新增）**：

- 所有命令默认输出人类可读的结果摘要与提示信息（不保存到文件）
- 如需机器可读结果，统一使用 `--json` 输出到控制台

**命名规范**: 推荐使用 **[算法名]-v[版本号]-offline.zip** **的格式。**

## 5. GitHub CI/CD（构建与发布算法SDK）

CI/CD 针对的是 `procvision_algorithm_sdk` 仓库，而非具体算法实现。推荐配置如下：

1. **触发策略**

   - `main` 分支的合并请求：运行测试与静态检查，确保SDK接口稳定。
   - `v*` 标签推送：在通过测试后构建产物并发布到内部PyPI（或GitHub Packages）。
2. **流水线阶段**

  - Checkout 代码，设置与SDK兼容的 Python 版本（如3.10）。
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
          python-version: "3.10"
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
