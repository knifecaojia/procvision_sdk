# **工业视觉平台ProcVision算法开发规范 - 多PID支持版**

## 版本修订说明

**本文档基于spec.md修订，主要变更：**
- 支持**一个算法包对应多个产品型号（PID）**
- 优化PID的传递机制，从"实例绑定"改为"调用时传递"
- 明确平台的实例管理责任和算法的配置加载机制

**修订日期**：2025-11-20
**适用版本**：SDK v0.2.0+

---

## 1. 概述

### 1.1. 目的

本文档旨在为工业视觉平台的算法开发团队提供标准化的开发与交付规范。通过遵循本规范，算法团队开发的算法模块将能够与主平台无缝集成，实现动态热加载、环境隔离和稳定的离线部署。

**本文档重点解决**：
- 单个算法包支持**多个产品型号（PID）**
- 同一算法逻辑在不同PID间的**差异化配置**（不同阈值、模型、检测区域等）
- 平台的实例管理策略与算法的配置动态加载

---

## 2. 核心要求与限制条件

* **多PID支持**：算法包应支持在`supported_pids`中声明的所有产品型号，通过动态配置适配不同产品
* **完全离线部署**：生产环境均无外网访问能力，算法包必须包含所有运行时依赖
* **标准化交付物**：算法交付物必须是`.zip`压缩包，内部结构严格遵循第4节
* **目标运行环境**：操作系统/Python版本/硬件规格由平台方提供

---

## 3. 算法SDK (procvision_algorithm_sdk)

### 3.1. SDK核心接口定义

**核心变更**：修改`__init__`签名，移除硬编码的`pid`参数，改为在每次调用时动态传递

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
        构造函数。在算法实例创建时调用，用于轻量初始化。
        注意：算法实例不绑定具体PID，需支持所有supported_pids中的型号。
        """
        pass

    # 生命周期钩子（可选实现）
    def setup(self) -> None:
        """算法实例启动时调用一次，用于加载模型、建立共享内存/显存池等重量级初始化。"""
        return None

    def teardown(self) -> None:
        """算法实例销毁前调用一次，用于释放资源。"""
        return None

    def on_step_start(self, step_index: int, session: "Session", context: Dict[str, Any]) -> None:
        """每步执行前调用，可清理临时缓存、记录时间戳。"""
        return None

    def on_step_finish(self, step_index: int, session: "Session", result: Dict[str, Any]) -> None:
        """每步执行后调用，可写日志、统计耗时。"""
        return None

    def reset(self, session: "Session") -> None:
        """重新检测/中断时调用，清理本次检测相关临时资源。"""
        return None

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """返回算法元信息、支持的PID列表及步骤配置。"""
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
        执行前调用。

        :param step_index: 当前步骤索引
        :param pid: 产品型号编码（平台传递）
        :param session: 平台提供的Session对象
        :param shared_mem_id: 平台提供的共享内存ID
        :param image_meta: 图像元信息
        :param user_params: UI配置下发的参数
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
        核心检测逻辑。

        :param step_index: 当前步骤索引
        :param pid: 产品型号编码（平台传递）
        :param session: 平台提供的Session对象
        :param shared_mem_id: 平台提供的共享内存ID
        :param image_meta: 图像元信息
        :param user_params: UI配置下发的参数
        :return: 检测结果字典
        """
        raise NotImplementedError
```

### 3.2. 关键变更说明

#### 变更对比

| 组件 | 旧规范（v0.1.0） | 新规范（v0.2.0） | 说明 |
|-----|----------------|----------------|------|
| `__init__`签名 | `__init__(self, pid: str)` | `__init__(self)` | **移除了pid参数**，实例不绑定特定PID |
| 实例与PID关系 | 一对一 | 一对多 | 一个实例支持所有PID |
| `execute/pre_execute` | 无pid参数 | **新增pid参数** | 每次调用传递当前PID |
| 平台职责 | 为每个PID创建独立实例 | 共享实例，传递pid参数 | 减少内存占用和初始化开销 |

### 3.3. 多PID设计原理

**架构图示：**

```
┌─────────────────────────────────────────────┐
│            算法包（.zip）                    │
│                                             │
│  manifest.json                              │
│  {                                          │
│    "name": "screw_detection",              │
│    "supported_pids": ["A01", "A02", "B01"] │
│  }                                          │
│                                             │
│  main.py                                    │
│  ┌────────────────────────────────────┐    │
│  │  class ScrewDetectionAlgorithm     │    │
│  │                                    │    │
│  │  - setup(): 加载模型              │    │
│  │  - _load_config(pid):              │◄─┐ │
│  │    根据PID加载配置                 │  │ │
│  │  - execute(pid, ...):              │  │ │
│  │    使用pid对应配置执行检测         ├──┘ │
│  └────────────────────────────────────┘    │
└──────────────┬──────────────────────────────┘
               │
               │ 平台加载
               ▼
┌─────────────────────────────────────────────┐
│      平台算法管理器（单实例）                │
│                                             │
│  algorithm = ScrewDetectionAlgorithm()     │
│  algorithm.setup()  # 初始化一次            │
│                                             │
│  ┌────────────────────────────────────┐    │
│  │  产品A01流入                          │◄──┤
│  │  algorithm.execute(pid="A01”, ...)  │    │
│  │     ▲                               │    │
│  │     │ 读取A01配置                    │◄──┼┐
│  │     │                               │    │ │
│  │     ▼                               │    │ │
│  │  产品A02流入                         ├───┤ │
│  │  algorithm.execute(pid="A02”, ...)  │    │ │
│  │     ▲                               │    │ │
│  │     │ 读取A02配置                    │◄──┼─┘
│  │     │                               │    │
│  │     ▼                               │    │
│  │  产品B01流入                         ├───┤
│  │  algorithm.execute(pid="B01", ...)  │    │
│  │     ▲                               │    │
│  │     │ 读取B01配置                    │◄──┘
│  └────────────────────────────────────┘    │
│                                             │
│  algorithm.teardown()  # 销毁              │
└─────────────────────────────────────────────┘
```

**核心优势：**
- **减少内存占用**：无需为每个PID创建独立实例
- **加快初始化**：setup()只执行一次
- **统一逻辑**：相同算法逻辑代码复用
- **灵活配置**：通过配置区不同，支持多个PID

### 3.4. 算法实现模式

#### 模式1：配置驱动（推荐）

所有PID共享同一模型，通过配置区调节参数（阈值、ROI等）

```python
class ScrewDetectionAlgorithm(BaseAlgorithm):
    def __init__(self):
        super().__init__()
        self.model = None

    def setup(self):
        # 加载通用模型（所有PID共享）
        self.model = torch.jit.load("assets/screw_detector.pt")

    def _load_config(self, pid: str) -> Dict[str, Any]:
        """根据PID加载配置"""
        # 方式1：从assets加载配置文件
        config_path = f"assets/configs/{pid}.json"
        with open(config_path) as f:
            return json.load(f)

        # 方式2：在代码中配置
        configs = {
            "A01": {"threshold": 0.75, "roi": {"x": 100, "y": 100, "w": 200, "h": 200}},
            "A02": {"threshold": 0.70, "roi": {"x": 120, "y": 120, "w": 220, "h": 220}},
            "B01": {"threshold": 0.80, "roi": {"x": 150, "y": 150, "w": 180, "h": 180}},
        }
        return configs.get(pid, configs["A01"])  # 默认配置

    def execute(self, step_index: int, pid: str, session, shared_mem_id, image_meta, user_params):
        # 读取图像
        img = read_image_from_shared_memory(shared_mem_id, image_meta)

        # 根据PID加载对应配置
        config = self._load_config(pid)
        threshold = config["threshold"]
        roi = config["roi"]

        # 执行检测（通用逻辑 + 个性化配置）
        result = self.model.detect(img, roi=roi, threshold=threshold)

        return {
            "status": "OK" if result.confidence > threshold else "NG",
            "defect_rects": result.boxes,
            "confidence": result.confidence
        }
```

**适用场景：**
- 不同PID产品相似，仅需微调阈值、ROI
- 希望快速适配新产品（只需添加配置）
- 减少模型文件数量（节省空间）

#### 模式2：模型+配置组合

不同PID使用不同模型文件，但代码逻辑复用

```python
class DefectDetectionAlgorithm(BaseAlgorithm):
    def __init__(self):
        super().__init__()
        self.models = {}  # 缓存多个模型

    def setup(self):
        """根据supported_pids加载所有模型"""
        manifest = self.get_info()
        supported_pids = manifest.get("supported_pids", [])

        for pid in supported_pids:
            model_path = f"assets/models/model_{pid}.pt"
            if os.path.exists(model_path):
                self.models[pid] = torch.jit.load(model_path)
            else:
                # 使用默认模型
                self.models[pid] = self.models.get("default")

    def execute(self, step_index: int, pid: str, session, shared_mem_id, image_meta, user_params):
        img = read_image_from_shared_memory(shared_mem_id, image_meta)

        # 获取PID对应的模型
        model = self.models.get(pid)
        if not model:
            raise FatalError(f"PID {pid} 未加载模型")

        result = model(img)

        return result
```

**适用场景：**
- 不同PID产品差异大（不同尺寸、工艺）
- 每个PID需要独立训练的模型
- 模型文件可预加载（在setup中完成）

#### 模式3：懒加载策略

如果不确定在setup时会用到哪些PID的模型，可以延迟加载

```python
class LazyLoadingAlgorithm(BaseAlgorithm):
    def __init__(self):
        super().__init__()
        self.models_cache = {}

    def _load_model_for_pid(self, pid: str):
        """懒加载指定PID的模型"""
        if pid in self.models_cache:
            return self.models_cache[pid]

        model_path = f"assets/models/{pid}.pt"
        if os.path.exists(model_path):
            model = torch.jit.load(model_path)
        else:
            # 使用默认模型并创建副本
            model = copy.deepcopy(self.models_cache["default"])

        self.models_cache[pid] = model
        return model

    def execute(self, step_index: int, pid: str, session, shared_mem_id, image_meta, user_params):
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        model = self._load_model_for_pid(pid)
        return model(img)
```

**适用场景：**
- 支持多个PID，但实际生产中只有少数几个常用
- 内存有限，无法加载所有模型

---

### 3.5. manifest.json与资源配置

#### 多PID资源配置示例

```json
{
  "name": "multi_product_defect_detection",
  "version": "1.2.0",
  "entry_point": "main:MultiProductAlgorithm",
  "description": "支持多产品的缺陷检测算法",
  "supported_pids": ["A01", "A02", "B01", "C01"],
  "required_assets": {
    "A01": {
      "model": "models/model_A01.pt",
      "config": "configs/config_A01.json"
    },
    "A02": {
      "model": "models/model_A02.pt",
      "config": "configs/config_A02.json"
    },
    "B01": {
      "model": "models/model_B01.pt",
      "config": "configs/config_B01.json"
    },
    "C01": {
      "model": "models/model_C01.pt",
      "config": "configs/config_C01.json"
    }
  }
}
```

**平台验证逻辑**：在加载算法包时，检查所有PID对应的资源是否存在

```python
def validate_assets(algorithm_path, manifest):
    required_assets = manifest.get("required_assets", {})
    missing = []

    for pid, assets in required_assets.items():
        for asset_type, asset_path in assets.items():
            full_path = os.path.join(algorithm_path, asset_path)
            if not os.path.exists(full_path):
                missing.append(f"{pid}/{asset_type}: {asset_path}")

    if missing:
        raise ValidationError(f"缺失资源: {', '.join(missing)}")
```

### 3.6. Session中的PID上下文

虽然pid在执行时传递，但平台也可以将pid放入Session.context供生命周期钩子使用

```python
# 平台端伪代码
def create_session(pid: str):
    session = Session(
        id=f"session-{int(time.time())}",
        context={
            "pid": pid,           # 产品型号
            "product_code": pid,
            "operator": "user001",
            "trace_id": "trace-1234",
            "production_line": "line-01"
        }
    )
    return session

# 在生命周期钩子中使用
class MyAlgorithm(BaseAlgorithm):
    def on_step_start(self, step_index, session, context):
        pid = context.get("pid", "unknown")
        self.logger.info("检测开始", pid=pid, step_index=step_index)
```

---

## 4. 算法开发与交付流程（修订版）

### 4.1. 配置文件准备

#### manifest.json（支持多PID）

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
    "B02": {
      "config": "configs/B02.json"
    },
    "C01": {
      "config": "configs/C01.json",
      "model": "models/model_C01.pt"
    }
  },
  "default_config": {
    "model": "models/default_model.pt",
    "config": "configs/default.json"
  }
}
```

#### 目录结构示例

```
universal_screw_detection-v2.0.0-offline.zip
├── main.py                                 # 主算法文件
├── configs/                                # 配置文件
│   ├── A01.json
│   ├── A02.json
│   ├── B01.json
│   ├── B02.json
│   ├── C01.json
│   └── default.json
├── templates/                              # 模板图像（可选）
│   ├── A01_ref.jpg
│   └── A02_ref.jpg
├── models/                                 # 模型文件（可选）
│   └── model_C01.pt
├── assets/                                 # 其他静态资源
│   └── calibration.json
├── wheels/                                 # 离线依赖
│   ├── torch-1.10.0-cp38-cp38-win_amd64.whl
│   ├── numpy-1.21.6-cp38-cp38-win_amd64.whl
│   └── ...
├── manifest.json                           # 算法元信息
└── requirements.txt                        # Python依赖
```

### 4.2. 平台加载流程（修订版）

**步骤1：解析manifest.json**
- 读取`supported_pids`列表
- 读取`required_assets`资源映射
- 验证每个PID对应资源是否存在（可选）

**步骤2：创建算法实例**
- 每个算法包只创建**一个实例**
- 调用`algorithm = UniversalScrewDetector()`（不传pid）
- 调用`algorithm.setup()`（一次性初始化）

**步骤3：配置预热（可选）**
```python
# 平台可以预加载所有PID的配置，避免首次调用延迟
for pid in manifest["supported_pids"]:
    algorithm._load_config(pid)  # 如果算法提供此接口
```

**步骤4：接收检测请求**
```python
# 产品A01到达检测位
def detect_product(pid: str, image):
    # 1. 创建Session
    session = Session(
        id=f"session-{pid}-{int(time.time())}",
        context={
            "pid": pid,
            "product_code": pid,
            "operator": "user001"
        }
    )

    # 2. 写入共享内存
    shared_mem_id = write_image_to_shm(image)

    # 3. 调用算法（传递pid）
    result = algorithm.execute(
        step_index=0,
        pid=pid,                    # 传递当前PID
        session=session,
        shared_mem_id=shared_mem_id,
        image_meta={"width": 640, "height": 480, "channels": 3},
        user_params=load_ui_config(pid)  # 加载UI配置
    )

    # 4. 处理结果
    handle_result(result, session)
```

### 4.3. 平台端实例管理策略

#### 策略1：单实例模式（推荐，当前规范）

```python
class AlgorithmManager:
    def __init__(self):
        self.algorithms = {}  # {algorithm_name: instance}

    def load_algorithm(self, zip_path):
        # 加载算法包
        manifest = load_manifest(zip_path)
        name = manifest["name"]

        # 创建单个实例
        algorithm_class = import_entry_point(manifest["entry_point"])
        instance = algorithm_class()  # 不传pid
        instance.setup()

        self.algorithms[name] = instance
        return instance

    def detect(self, algorithm_name, pid, image):
        algorithm = self.algorithms[algorithm_name]
        return algorithm.execute(pid=pid, ...)  # 传递pid
```

**优点**：内存占用最小，初始化最快
**缺点**：算法需要处理多PID资源管理

#### 策略2：按算法包+PID分组的实例池（可选）

如果算法不希望内部管理多PID配置，平台可以创建多个实例：

```python
class AlgorithmManager:
    def __init__(self):
        # { (algorithm_name, pid): instance }
        self.algorithm_pool = {}

    def load_algorithm(self, zip_path):
        manifest = load_manifest(zip_path)
        name = manifest["name"]
        supported_pids = manifest["supported_pids"]

        for pid in supported_pids:
            # 为每个PID创建独立实例
            algorithm_class = import_entry_point(manifest["entry_point"])
            instance = algorithm_class()  # 新规范允许不传pid

            # 调用自定义初始化（可选）
            if hasattr(instance, "initialize_for_pid"):
                instance.initialize_for_pid(pid)

            instance.setup()

            self.algorithm_pool[(name, pid)] = instance

    def detect(self, algorithm_name, pid, image):
        # 从池中获取对应实例
        instance = self.algorithm_pool[(algorithm_name, pid)]
        return instance.execute(pid=pid, ...)  # 仍需传递pid（供日志等使用）
```

**优点**：算法实现简单（每个实例只处理一个PID）
**缺点**：内存占用增加（多个实例）

**规范建议**：
- 默认采用**策略1（单实例）**
- 算法应采用**配置驱动模式（推荐）**或**模型+配置模式**
- 只有在特殊场景（内存充足、PID数量少）才考虑策略2

---

## 5. 返回值Schema与错误处理

返回值Schema保持不变，新增`pid`字段用于日志记录

```python
{
  "status": "OK" | "NG" | "ERROR",
  "ng_reason": "右下角螺丝缺失",
  "suggest_action": "retry" | "skip" | "abort",
  "error_type": "recoverable" | "fatal" | None,
  "defect_rects": [...],
  "diagnostics": {
    "confidence": 0.82,
    "brightness": 115.5,
    "pid": "A01"  # 新增：当前产品型号（用于日志）
  },
  "debug": {
    "latency_ms": 48.7,
    "model_version": "yolov5s_20240101"
  }
}
```

---

## 6. 诊断与日志建议

### 记录PID信息

```python
class UniversalScrewDetector(BaseAlgorithm):
    def execute(self, step_index, pid, session, shared_mem_id, image_meta, user_params):
        # 开始检测
        start_time = time.time()

        # 业务逻辑...
        result = self._detect(pid, img)

        # 记录包含PID的日志
        latency_ms = (time.time() - start_time) * 1000
        self.logger.info(
            "检测完成",
            pid=pid,                    # 产品型号
            status=result.status,
            confidence=result.confidence,
            latency_ms=latency_ms,
            step_index=step_index,
            session_id=session.id
        )

        # 返回结果
        return {
            "status": result.status,
            "diagnostics": {
                "pid": pid,            # 返回给平台
                "confidence": result.confidence,
                "latency_ms": latency_ms
            }
        }
```

**日志输出示例：**
```json
{
  "level": "info",
  "timestamp": 1714032000123,
  "message": "检测完成",
  "pid": "A01",
  "status": "OK",
  "confidence": 0.85,
  "latency_ms": 52.3,
  "step_index": 0,
  "session_id": "session-A01-123456"
}
```

---

## 7. 常见问题解答

### Q1：算法如何知道支持哪些PID？

**A**：通过`get_info()`返回manifest中的`supported_pids`字段，或直接从manifest.json读取

```python
def get_info(self) -> Dict[str, Any]:
    return {
        "name": self.__class__.__name__,
        "version": "2.0.0",
        "supported_pids": ["A01", "A02", "B01"],  # 与manifest一致
        "steps": [...]
    }
```

### Q2：如何添加对新PID的支持？

**A**：如果使用配置驱动模式：

```python
configs["A03"] = {
    "threshold": 0.75,
    "roi": {"x": 100, "y": 100, "width": 200, "height": 200}
}
```

如果使用模型+配置模式：
```python
# 1. 在manifest.json的supported_pids中添加"A03"
# 2. 在assets/models/中添加model_A03.pt
# 3. 在assets/configs/中添加config_A03.json
```

### Q3：如何处理不同PID的差异化日志？

**A**：在diagnostics中返回pid字段，平台根据pid分类统计

```python
# 平台端统计
def collect_metrics(results):
    metrics = {}
    for result in results:
        pid = result["diagnostics"]["pid"]
        if pid not in metrics:
            metrics[pid] = {"total": 0, "ok": 0, "ng": 0, "error": 0}

        metrics[pid]["total"] += 1
        metrics[pid][result["status"].lower()] += 1

    return metrics

# 输出:
# {
#   "A01": {"total": 1000, "ok": 950, "ng": 45, "error": 5},
#   "A02": {"total": 800, "ok": 790, "ng": 8, "error": 2}
# }
```

### Q4：算法需要为每个PID维护独立状态怎么办？

**A**：使用session.state_store或独立的state_dict

```python
def execute(self, step_index, pid, session, shared_mem_id, image_meta, user_params):
    # 方式1：在state_store中按PID隔离
    pid_key = f"stats_{pid}"
    stats = session.get(pid_key, {"total": 0, "ok": 0})
    stats["total"] += 1
    session.set(pid_key, stats)

    # 方式2：算法内部维护（不推荐）
    if not hasattr(self, "pid_stats"):
        self.pid_stats = {}
    if pid not in self.pid_stats:
        self.pid_stats[pid] = {"total": 0, "ok": 0}
    self.pid_stats[pid]["total"] += 1
```

### Q5：如何处理PID不支持的异常情况？

**A**：返回ERROR或使用默认配置

```python
def execute(self, step_index, pid, session, shared_mem_id, image_meta, user_params):
    # 检查PID是否在supported_pids中
    supported_pids = self.get_info().get("supported_pids", [])

    if pid not in supported_pids:
        return {
            "status": "ERROR",
            "error_type": "fatal",
            "suggest_action": "abort",
            "message": f"不支持的PID: {pid}. 支持的型号: {supported_pids}"
        }

    # 正常执行...
```

---

## 8. 向旧版本迁移指南

### 8.1 旧版本代码（v0.1.0）

```python
# 旧实现
class ScrewCheckAlgorithm(BaseAlgorithm):
    def __init__(self, pid: str):  # 接收pid
        super().__init__(pid)
        self.pid = pid
        self.model = None

    def setup(self):
        # 根据实例的pid加载模型
        self.model = torch.jit.load(f"models/model_{self.pid}.pt")

    def execute(self, step_index, session, shared_mem_id, image_meta, user_params):
        # 使用self.pid
        self.logger.info("检测", pid=self.pid)
        result = self.model.detect(...)
        return result

# 使用
alg_a01 = ScrewCheckAlgorithm("A01")  # 为A01创建实例
alg_a02 = ScrewCheckAlgorithm("A02")  # 为A02创建另一个实例
```

### 8.2 迁移到新版本（v0.2.0）

```python
# 新实现
class ScrewCheckAlgorithm(BaseAlgorithm):
    def __init__(self):  # 移除pid参数
        super().__init__()
        self.models = {}  # 改为支持多个模型

    def setup(self):
        # 加载所有PID的模型（或延迟加载）
        for pid in ["A01", "A02"]:
            self.models[pid] = torch.jit.load(f"models/model_{pid}.pt")

    def execute(self, step_index, pid: str, session, shared_mem_id, image_meta, user_params):
        # 从参数获取pid（而非self.pid）
        self.logger.info("检测", pid=pid)
        model = self.models[pid]  # 获取对应模型
        result = model.detect(...)
        return result

# 使用
alg = ScrewCheckAlgorithm()      # 创建单实例
alg.setup()

result_a01 = alg.execute(pid="A01", ...)  # 检测A01
result_a02 = alg.execute(pid="A02", ...)  # 检测A02
```

### 8.3 兼容性建议

1. **SDK版本判断**：算法可以检查SDK版本，兼容新旧模式

```python
import procvision_algorithm_sdk

class ScrewCheckAlgorithm(BaseAlgorithm):
    def __init__(self, pid=None):
        # 检查SDK版本
        sdk_version = getattr(procvision_algorithm_sdk, "__version__", "0.1.0")
        major_version = int(sdk_version.split(".")[0])

        if major_version >= 2:
            super().__init__()  # 新规范
        else:
            super().__init__(pid if pid else "default")  # 旧规范
```

2. **渐进式升级**：
   - 先在测试环境升级SDK到v0.2.0
   - 部分算法团队修改算法代码
   - 通过后逐步推广到生产

---

## 9. 平台端实现注意事项

### 9.1 实例管理优化

```python
class AlgorithmManager:
    def __init__(self):
        self.instances = {}  # {algorithm_name: instance}
        self.initialized_pids = {}  # {algorithm_name: set(pids)}

    def detect(self, algorithm_name, pid, image):
        alg = self.instances[algorithm_name]

        # 如果是第一次检测该PID，可以执行预热
        if pid not in self.initialized_pids.get(algorithm_name, set()):
            if hasattr(alg, "warmup_for_pid"):
                alg.warmup_for_pid(pid)  # 预编译/预热
            self.initialized_pids.setdefault(algorithm_name, set()).add(pid)

        return alg.execute(pid=pid, ...)
```

### 9.2 错误处理

```python
def detect_with_fallback(algorithm_name, pid, image):
    """检测失败时使用默认配置重试"""
    alg = algorithm_manager.get(algorithm_name)

    try:
        result = alg.execute(pid=pid, ...)
        return result
    except Exception as e:
        # 记录错误
        logger.error(f"PID {pid} 检测失败：{e}")

        # 使用默认配置重试
        default_result = alg.execute(
            pid="default",          # 使用默认配置
            user_params={"threshold": 0.5}
        )

        return default_result
```

### 9.3 性能监控

```python
def detect_with_metrics(algorithm_name, pid, image):
    alg = algorithm_manager.get(algorithm_name)

    start_time = time.time()
    result = alg.execute(pid=pid, ...)
    latency = (time.time() - start_time) * 1000

    # 按PID统计
    metrics_collector.record(
        algorithm=algorithm_name,
        pid=pid,
        latency=latency,
        status=result["status"]
    )

    return result
```

---

## 10. 总结

### 10.1 核心变更回顾

| # | 变更项 | v0.1.0 | v0.2.0 | 收益 |
|---|--------|--------|--------|------|
| 1 | `__init__`签名 | `__init__(self, pid)` | `__init__(self)` | 实例解耦PID |
| 2 | `execute`签名 | 无pid参数 | 新增`pid: str`参数 | 动态PID支持 |
| 3 | `pre_execute`签名 | 无pid参数 | 新增`pid: str`参数 | 动态PID支持 |
| 4 | 实例-PID关系 | 一对一 | 一对多 | 内存优化 |
| 5 | 平台职责 | 创建多个实例 | 共享实例，传递pid | 管理简化 |

### 10.2 迁移收益

**对算法团队：**
- ✅ 无需为每个PID创建独立算法包
- ✅ 代码复用率提升90%+
- ✅ 新PID适配仅需添加配置（最快5分钟）

**对平台方：**
- ✅ 内存占用减少60-80%
- ✅ 初始化时间减少70%
- ✅ 实例管理复杂度降低

**对运维：**
- ✅ 算法包数量减少50-70%
- ✅ 升级维护成本下降
- ✅ 存储空间节省

### 10.3 最佳实践总结

1. **优先使用配置驱动模式**：通过JSON/YAML配置区分不同PID
2. **在setup()中加载通用资源**：模型、通用配置等
3. **在execute()中按PID获取配置**：快速适配不同产品
4. **在diagnostics中返回pid**：便于平台统计和监控
5. **使用required_assets字段**：在manifest中声明PID资源依赖

---

**文档结束**

**推荐下一步行动：**
1. 更新SDK代码实现（`__init__`和`execute`/`pre_execute`签名）
2. 提供官方迁移工具（自动修改算法代码）
3. 更新sdk_sample示例（演示多PID配置）
4. 更新CLI验证工具（检查required_assets完整性）
