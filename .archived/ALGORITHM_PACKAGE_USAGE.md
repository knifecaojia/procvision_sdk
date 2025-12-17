# 算法SDK使用指南：开发、集成与测试全流程

本文档详细说明如何使用procvision_algorithm_sdk开发、测试和交付算法包。基于当前SDK实现状态（2025-11-20）。

---

## 1. 开发环境准备

### 1.1 安装SDK

```bash
# 方式1：从源码安装（开发模式）
cd F:\Ai-LLM\southwest\09sdk\algorithm-sdk
pip install -e .

# 验证安装
python -c "from procvision_algorithm_sdk import BaseAlgorithm; print('✓ SDK installed')"
```

### 1.2 创建算法项目

```bash
mkdir my_algorithm
cd my_algorithm

# 创建标准目录结构
mkdir wheels assets logs
touch requirements.txt manifest.json main.py
```

---

## 2. 实现算法核心逻辑

### 2.1 完整代码模板

```python
# main.py

from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from procvision_algorithm_sdk import (
    BaseAlgorithm,
    Session,
    read_image_from_shared_memory,
    RecoverableError,
    FatalError
)


class MyDetectionAlgorithm(BaseAlgorithm):
    """
    工业产品缺陷检测算法示例

    功能：检测产品表面的划痕和污点
    依赖：opencv-python, torch>=1.10
    """

    def __init__(self):
        super().__init__()
        self.model = None
        self.device = None

    def setup(self) -> None:
        """
        生命周期：算法实例启动时调用一次

        职责：
        - 加载深度学习模型
        - 初始化GPU/显存
        - 加载静态配置
        """
        try:
            # 1. 模型加载（重量级初始化）
            import torch
            from pathlib import Path

            model_path = Path("assets") / "defect_detector.pt"
            if not model_path.exists():
                raise FatalError(f"模型文件不存在: {model_path}")

            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model = torch.jit.load(str(model_path), map_location=self.device)
            self.model.eval()

            self.logger.info(
                "模型加载完成",
                model_path=str(model_path),
                device=str(self.device),
                model_version="1.0.0"
            )

        except Exception as e:
            self.logger.error("模型加载失败", error=str(e))
            raise FatalError(f"Setup失败: {e}")

    def on_step_start(self, step_index: int, session: Session, context: Dict[str, Any]) -> None:
        """
        生命周期：每步执行前调用

        职责：
        - 清理临时数据
        - 记录开始时间
        - 校验输入
        """
        # 记录开始时间（用于计算latency）
        import time
        session.set("step_start_time", time.time())

        # 清理上一步的overlay数据
        session.delete("last_overlay")

        self.logger.info(
            "步骤开始",
            step_index=step_index,
            session_id=session.id
        )

    def on_step_finish(self, step_index: int, session: Session, result: Dict[str, Any]) -> None:
        """
        生命周期：每步执行后调用

        职责：
        - 统计耗时
        - 写结构化日志
        - 清理缓存
        """
        import time

        start_time = session.get("step_start_time")
        if start_time:
            latency_ms = (time.time() - start_time) * 1000
            result["debug"] = result.get("debug", {})
            result["debug"]["latency_ms"] = latency_ms

            self.logger.info(
                "步骤完成",
                step_index=step_index,
                session_id=session.id,
                status=result.get("status"),
                latency_ms=latency_ms
            )

    def reset(self, session: Session) -> None:
        """
        生命周期：重新检测/人工跳过时调用

        职责：
        - 清理本次检测相关临时资源
        - 避免脏数据影响下次执行
        """
        # 清理Session状态
        keys_to_delete = [k for k in session.state_store.keys() if k.startswith("detect_")]
        for k in keys_to_delete:
            session.delete(k)

        # 清理GPU缓存（如需要）
        # if self.device and str(self.device).startswith("cuda"):
        #     import torch
        #     torch.cuda.empty_cache()

        self.logger.info("Session已重置", session_id=session.id)

    def teardown(self) -> None:
        """
        生命周期：算法实例销毁前调用

        职责：
        - 释放模型
        - 释放显存
        - 关闭文件/连接
        """
        if self.model:
            del self.model
            self.model = None

        self.logger.info("算法实例已释放")

    def get_info(self) -> Dict[str, Any]:
        """
        返回算法元信息和步骤配置

        返回值schema：
        {
            "name": str,           # 算法唯一标识
            "version": str,        # 语义化版本（如"1.2.1"）
            "description": str,    # 算法描述
            "steps": [{            # 步骤列表
                "index": int,      # 步骤索引（从0开始）
                "name": str,       # 步骤显示名称
                "params": [{       # 可配置参数schema
                    "key": str,    # 参数名
                    "type": str,   # "float"|"int"|"rect"|"enum"|"bool"
                    "default"?: any,
                    "min"?: number,       # float/int类型
                    "max"?: number,
                    "choices"?: list,     # enum类型
                    "required"?: bool,
                    "unit"?: str,         # 单位（如"ms","mm"）
                    "description": str
                }]
            }]
        }
        """
        return {
            "name": "my_product_defect_detection",
            "version": "1.0.0",
            "description": "工业产品表面划痕和污点检测算法",
            "supported_pids": ["PRODUCT-A", "PRODUCT-B"],
            "steps": [
                {
                    "index": 0,
                    "name": "光照检查",
                    "params": [
                        {
                            "key": "brightness_threshold",
                            "type": "float",
                            "default": 50.0,
                            "min": 30.0,
                            "max": 80.0,
                            "unit": "lux",
                            "description": "最低亮度阈值，低于此值认为光照不足"
                        }
                    ]
                },
                {
                    "index": 1,
                    "name": "划痕检测",
                    "params": [
                        {
                            "key": "scratch_threshold",
                            "type": "float",
                            "default": 0.75,
                            "min": 0.5,
                            "max": 0.95,
                            "description": "划痕置信度阈值"
                        },
                        {
                            "key": "roi",
                            "type": "rect",
                            "required": True,
                            "description": "检测区域（格式：x,y,width,height）"
                        },
                        {
                            "key": "mode",
                            "type": "enum",
                            "choices": ["fast", "accurate"],
                            "default": "fast",
                            "description": "检测模式（快速/精确）"
                        }
                    ]
                }
            ]
        }

    def pre_execute(
        self,
        step_index: int,
        session: Session,
        shared_mem_id: str,
        image_meta: Dict[str, Any],
        user_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        预执行：执行前准备或产生参考信息

        典型用途：
        - 光照检查
        - 相机标定
        - 模板匹配
        - ROI可视化

        返回值schema：
        {
            "status": "OK"|"ERROR",
            "suggest_action": "retry"|"skip"|"abort",  # 仅在ERROR时有效
            "error_type": "recoverable"|"fatal"|None,
            "message": str,                           # 人类可读信息
            "overlay?: {                               # 可视化参考信息（坐标）
                "roi_rects": [{x,y,width,height,label}]
            },
            "debug?: {                                # 调试信息
                "latency_ms": float
            }
        }

        **内存管理原则**：
        - 算法从共享内存读取图像（只读）
        - 算法不申请任何共享内存
        - overlay只包含坐标信息，不包含图像
        - 平台负责创建/写入/销毁共享内存
        """
        try:
            # 读取图像（用于参考）
            img = read_image_from_shared_memory(shared_mem_id, image_meta)

            # 根据step_index执行不同逻辑
            if step_index == 0:
                # 光照检查
                brightness = self._check_brightness(img)
                threshold = user_params.get("brightness_threshold", 50.0)

                if brightness < threshold:
                    return {
                        "status": "ERROR",
                        "suggest_action": "retry",
                        "error_type": "recoverable",
                        "message": f"光照不足: {brightness:.1f} < {threshold}",
                        "debug": {"brightness": brightness}
                    }

                return {
                    "status": "OK",
                    "message": f"光照检查通过: {brightness:.1f}lux"
                }

            elif step_index == 1:
                # ROI可视化
                roi = user_params.get("roi", {"x": 0, "y": 0, "width": 640, "height": 480})

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
                        # 注意：overlay只包含坐标信息，不包含图像
                        # 平台根据坐标自行绘制ROI框到UI
                    }
                }

            else:
                raise FatalError(f"未知的step_index: {step_index}")

        except Exception as e:
            self.logger.error("pre_execute失败", error=str(e), step_index=step_index)
            raise RecoverableError(f"Pre-execution failed: {e}")

    def execute(
        self,
        step_index: int,
        session: Session,
        shared_mem_id: str,
        image_meta: Dict[str, Any],
        user_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        核心检测逻辑

        返回值schema：
        {
            "status": "OK"|"NG"|"ERROR",
            "ng_reason": str,                         # 仅在NG时有效
            "suggest_action": "retry"|"skip"|"abort", # 仅在NG/ERROR时有效
            "error_type": "recoverable"|"fatal"|None,  # 仅在ERROR时有效
            "defect_rects": [{x,y,width,height,label,score}],  # 检测到的缺陷
            "position_rects": [{x,y,width,height,label}],     # 定位结果
            "diagnostics": {
                "confidence": float,
                "brightness": float
                # 注意：算法不返回任何图像（调试图由平台生成）
            },
            "debug": {
                "latency_ms": float,
                "model_version": str
            }
        }

        **内存管理原则**：
        - 算法不申请任何共享内存
        - 算法不返回调试图像
        - 平台负责创建/写入/销毁共享内存
        - 算法只读共享内存中的输入图像
        """
        try:
            # 1. 读取图像（从共享内存）
            img = read_image_from_shared_memory(shared_mem_id, image_meta)

            self.logger.debug(
                "图像读取完成",
                shape=img.shape,
                dtype=str(img.dtype)
            )

            # 2. 执行业务逻辑
            if step_index == 0:
                # 光照检查步骤（通常无需execute）
                return {"status": "OK"}

            elif step_index == 1:
                # 缺陷检测
                return self._detect_defects(img, user_params)

            else:
                raise FatalError(f"未知的step_index: {step_index}")

        except RecoverableError:
            # 可恢复错误，抛给平台处理
            raise
        except Exception as e:
            # 未知错误，转为FatalError
            self.logger.error("执行失败", error=str(e), step_index=step_index)
            raise FatalError(f"Execution failed: {e}")

    def _check_brightness(self, img: np.ndarray) -> float:
        """检查图像平均亮度"""
        if len(img.shape) == 3:
            gray = np.mean(img, axis=2)
        else:
            gray = img
        return float(np.mean(gray))

    def _detect_defects(self, img: np.ndarray, user_params: Dict[str, Any]) -> Dict[str, Any]:
        """执行缺陷检测（这里是mock实现）"""
        import time
        import random

        # 模拟推理耗时
        time.sleep(0.05)

        # 从参数读取配置
        threshold = user_params.get("scratch_threshold", 0.75)
        roi = user_params.get("roi", {"x": 0, "y": 0, "width": img.shape[1], "height": img.shape[0]})

        # 模拟检测结果（实际应调用模型）
        mock_defects = []
        if random.random() < 0.1:  # 10%概率检测到缺陷
            mock_defects = [{
                "x": roi["x"] + 100,
                "y": roi["y"] + 100,
                "width": 50,
                "height": 20,
                "label": "scratch",
                "score": 0.82
            }]

        if mock_defects:
            # NG情况
            result = {
                "status": "NG",
                "ng_reason": f"检测到{len(mock_defects)}处划痕",
                "suggest_action": "retry",  # 允许操作员重新检测
                "error_type": None,
                "defect_rects": mock_defects,
                "position_rects": [{
                    **roi,
                    "label": "检测区域"
                }],
                "diagnostics": {
                    "defect_count": len(mock_defects),
                    "confidence": mock_defects[0]["score"] if mock_defects else 1.0
                },
                "debug": {
                    "latency_ms": 50.0,
                    "threshold": threshold
                }
            }

            self.logger.info(
                "检测到缺陷",
                defect_count=len(mock_defects),
                confidence=mock_defects[0]["score"]
            )

            return result

        else:
            # OK情况
            return {
                "status": "OK",
                "ng_reason": None,
                "suggest_action": None,
                "error_type": None,
                "defect_rects": [],
                "position_rects": [{
                    **roi,
                    "label": "检测区域"
                }],
                "diagnostics": {
                    "defect_count": 0,
                    "confidence": 1.0
                },
                "debug": {
                    "latency_ms": 50.0
                }
            }


# 可选：提供命令行入口（用于测试）
if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        print("用法：python main.py test")
        sys.exit(1)

    if sys.argv[1] == "test":
        # 简单测试
        alg = MyDetectionAlgorithm()
        alg.setup()

        # Mock Session
        from procvision_algorithm_sdk import Session
        session = Session("test-session-001")

        # Mock图像元数据
        image_meta = {"width": 640, "height": 480, "channels": 3}

        # 测试execute
        result = alg.execute(
            step_index=1,
            session=session,
            shared_mem_id="mock_mem_id",
            image_meta=image_meta,
            user_params={"threshold": 0.75}
        )

        print("测试结果：")
        print(result)

        alg.teardown()
```

### 2.2 编写manifest.json

```json
{
  "name": "my_product_defect_detection",
  "version": "1.0.0",
  "entry_point": "main:MyDetectionAlgorithm",
  "description": "工业产品表面划痕和污点检测算法",
  "supported_pids": [
    "PRODUCT-A",
    "PRODUCT-B"
  ],
  "author": "Your Name",
  "created_at": "2025-11-20"
}
```

**字段说明：**
- `name`: 算法唯一标识（小写字母、数字、下划线）
- `version`: 语义化版本（推荐`major.minor.patch`）
- `entry_point`: `模块名:类名`（对于main.py中的MyDetectionAlgorithm，值为`main:MyDetectionAlgorithm`）
- `supported_pids`: 支持的产品型号列表

### 2.3 配置requirements.txt

```text
# 生产依赖
numpy>=1.21.6
opencv-python==4.5.5.64
torch>=1.10.0

# SDK本身（在开发环境中已安装）
# procvision_algorithm_sdk==0.1.0

# 其他依赖
pillow==9.0.1
```

**生成精确版本：**
```bash
# 在虚拟环境中安装所有依赖后
pip freeze > requirements.txt

# 编辑requirements.txt，删除不需要的包
```

### 2.4 返回值规范参考

关于 `pre_execute` 和 `execute` 的返回值详细说明（包括每个字段的含义、使用场景、平台处理逻辑），请参考：
- **spec.md 第 3.7 节** - 返回值详解与使用指南（完整版）

该章节包含：
- 940+ 行的详细文档
- 每个返回字段的完整说明
- 状态机流转图
- 实际案例对比
- 常见错误与纠正
- 最佳实践 checklist

建议算法开发团队仔细阅读该章节，避免因理解偏差导致实现错误。

---

## 3. 本地测试与验证

### 3.1 使用CLI工具验证

```bash
# 在算法项目根目录执行
procvision-sdk validate --project .
```

**成功输出示例：**
```json
{
  "summary": {
    "status": "PASS",
    "passed": 9,
    "failed": 0
  },
  "checks": [
    {
      "name": "manifest_exists",
      "result": "PASS",
      "message": "loaded"
    },
    {
      "name": "manifest_fields",
      "result": "PASS",
      "message": ""
    },
    {
      "name": "entry_import",
      "result": "PASS",
      "message": "imported"
    },
    {
      "name": "step_schema",
      "result": "PASS",
      "message": "steps present"
    },
    {
      "name": "smoke_execute",
      "result": "PASS",
      "message": "done"
    },
    {
      "name": "io_contract_status",
      "result": "PASS",
      "message": "OK"
    },
    {
      "name": "io_contract_suggest",
      "result": "PASS",
      "message": "None"
    },
    {
      "name": "io_contract_error_type",
      "result": "PASS",
      "message": "None"
    }
  ]
}
```

**失败处理：**
- 检查返回的`failed`字段
- 根据`message`定位问题
- 常见错误：
  - `manifest.json`字段缺失
  - `entry_point`格式错误
  - `get_info()`返回非dict
  - 返回值缺少`status`字段

### 3.2 手动测试算法逻辑

```bash
# 使用main.py中的测试入口
python main.py test
```

**预期输出：**
```
测试结果：
{
    'status': 'OK',  # 或 'NG'
    'ng_reason': None,
    'suggest_action': None,
    'defect_rects': [],
    'position_rects': [...],
    'diagnostics': {'defect_count': 0, 'confidence': 1.0},
    'debug': {'latency_ms': 50.0}
}
```

### 3.3 测试错误处理

```python
# 在main.py中添加错误模拟
if __name__ == "__main__":
    import sys

    alg = MyDetectionAlgorithm()
    alg.setup()
    session = Session("test-session-001")
    image_meta = {"width": 640, "height": 480, "channels": 3}

    # 测试1：正常执行
    print("=== 测试1：正常执行 ===")
    result = alg.execute(1, "TEST", session, "mem1", image_meta, {})
    print(f"Status: {result['status']}")

    # 测试2：光照不足（recoverable error）
    print("\n=== 测试2：光照不足 ===")
    result = alg.pre_execute(0, "TEST", session, "mem2", image_meta, {"brightness_threshold": 999})
    print(f"Status: {result['status']}")
    print(f"Suggest action: {result.get('suggest_action')}")
    print(f"Error type: {result.get('error_type')}")

    alg.teardown()
```

---

## 4. 构建离线交付包

### 4.1 下载离线依赖

```bash
# 清理旧的依赖
rm -rf ./wheels
mkdir ./wheels

# 为Windows 10 x64, Python 3.8环境下载依赖
pip download \
    -r requirements.txt \
    -d ./wheels/ \
    --platform win_amd64 \
    --python-version 3.8 \
    --implementation cp \
    --abi cp38

# 验证下载的包
ls ./wheels/
# 应该看到：numpy-1.21.6-cp38-cp38-win_amd64.whl等
```

**注意：**
- `--platform`、`--python-version`必须与目标平台严格匹配
- 如果算法包含CUDA代码，需要额外指定`--platform`为对应的Linux/Windows版本

### 4.2 准备assets目录

```bash
# 将模型文件、配置、模板等静态资源放入assets/
cp /path/to/defect_detector.pt ./assets/
cp /path/to/calibration.json ./assets/

# 验证assets清单
ls -lh ./assets/
```

### 4.3 打包ZIP

```bash
# 确保所有文件都在
ls -la .
# ├── assets/
# ├── wheels/
# ├── manifest.json
# ├── requirements.txt
# └── main.py

# 创建最终交付包（推荐命名规范）
zip -r my_algorithm-v1.0.0-offline.zip \
    assets/ \
    wheels/ \
    manifest.json \
    requirements.txt \
    main.py

# 验证ZIP内容
unzip -l my_algorithm-v1.0.0-offline.zip
```

---

## 5. 在平台端集成

### 5.1 平台部署流程（示意图）

```
┌─────────────────┐
│ 1. 上传ZIP包     │
│    (平台UI)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. 解压并验证    │
│    - manifest    │
│    - wheels      │
│    - assets      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. 安装依赖      │
│    pip install   │
│    --no-index    │
│    --find-links  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. 加载算法      │
│    import main   │
│    alg = main.MyDetectionAlgorithm(pid)
│    alg.setup()   │
└────────┬────────┘
         │
         ▼
┌──────────────────┐
│ 5. 接收检测请求   │
│    - 相机采集     │
│    - 写入共享内存 │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 6. 调用算法       │
│    alg.pre_execute(...)  # 显示ROI
│    result = alg.execute(...)  # 检测
└────────┬──────────┘
         │
         ▼
┌──────────────────┐
│ 7. 处理结果       │
│    - status (OK/NG/ERROR)
│    - defect_rects 绘制到UI
│    - 根据suggest_action提示用户
└──────────────────┘
```

### 5.2 平台端伪代码示例

```python
# platform_runner.py（平台侧）

from procvision_algorithm_sdk import Session
import subprocess
import json

class PlatformRunner:
    def __init__(self, algorithm_zip_path):
        self.algorithm = self._load_algorithm(algorithm_zip_path)
        self.alg_instance = None

    def _load_algorithm(self, zip_path):
        # 1. 解压
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall("./algorithm")

        # 2. 安装依赖
        subprocess.run([
            "pip", "install", "--no-index",
            "--find-links=./algorithm/wheels",
            "-r", "./algorithm/requirements.txt"
        ], check=True)

        # 3. 导入算法
        sys.path.insert(0, "./algorithm")
        from main import MyDetectionAlgorithm
        return MyDetectionAlgorithm

    def start(self, pid):
        # 4. 实例化并setup
        self.alg_instance = self.algorithm(pid)
        self.alg_instance.setup()

    def detect(self, image_data, product_id):
        # 5. 写入共享内存
        shared_mem_id = self._write_to_shm(image_data)

        # 6. 调用算法
        session = Session(f"session-{int(time.time())}")
        image_meta = {
            "width": image_data.shape[1],
            "height": image_data.shape[0],
            "channels": image_data.shape[2]
        }

        try:
            # Pre-execute（显示ROI等）
            pre_result = self.alg_instance.pre_execute(
                step_index=0,
                session=session,
                shared_mem_id=shared_mem_id,
                image_meta=image_meta,
                user_params={"brightness_threshold": 50.0}
            )

            if pre_result["status"] == "ERROR":
                return self._handle_error(pre_result)

            # Execute（核心检测）
            result = self.alg_instance.execute(
                step_index=1,
                session=session,
                shared_mem_id=shared_mem_id,
                image_meta=image_meta,
                user_params={"scratch_threshold": 0.75}
            )

            # 7. 处理结果
            return self._process_result(result, session)

        except RecoverableError as e:
            # 提示用户"重新检测"
            return {"ui_action": "retry", "message": str(e)}
        except FatalError as e:
            # 提示用户"人工跳过"或"停止"
            return {"ui_action": "abort", "message": str(e)}

    def stop(self):
        if self.alg_instance:
            self.alg_instance.teardown()
```

### 5.3 平台端UI状态流转

```python
# 基于算法返回值的UI状态机

def handle_detection_result(result):
    """
    result = {
        "status": "OK|NG|ERROR",
        "ng_reason": str,
        "suggest_action": "retry"|"skip"|"abort",
        "error_type": "recoverable"|"fatal"
    }
    """
    status = result["status"]

    if status == "OK":
        # 显示"检测通过"
        ui.show_success("检测通过")
        return "next_product"  # 自动流转到下一个产品

    elif status == "NG":
        # 显示NG原因和缺陷位置
        ui.show_ng(
            reason=result["ng_reason"],
            defect_rects=result.get("defect_rects", []),
            suggest_action=result.get("suggest_action")
        )

        # 等待操作员选择
        action = ui.wait_for_operator_action()  # "retry" 或 "skip"

        if action == "retry":
            # 触发重新检测
            algorithm.reset(session)
            return "retry_detection"
        else:
            # 人工跳过
            return "manual_override"

    elif status == "ERROR":
        error_type = result.get("error_type")

        if error_type == "recoverable":
            # 可恢复错误（如光照不足）
            ui.show_error(
                message=result.get("message", "未知错误"),
                suggest_action="retry"
            )

            # 等待操作员调整环境后重试
            ui.wait_for_operator_ready()
            algorithm.reset(session)
            return "retry_detection"

        else:  # fatal
            # 不可恢复错误（如模型损坏）
            ui.show_error(
                message=result.get("message", "严重错误"),
                suggest_action="abort"
            )

            # 停止整条线体，等待工程师处理
            return "stop_production"
```

---

## 6. 调试与诊断

### 6.1 查看结构化日志

```bash
# 运行算法并捕获日志
python main.py test 2> algorithm.log

# 查看JSON日志
cat algorithm.log | jq .
```

**日志格式：**
```json
{
  "level": "info",
  "timestamp": 1714032000123,
  "message": "检测到缺陷",
  "session_id": "test-session-001",
  "step_index": 1,
  "defect_count": 2,
  "confidence": 0.82
}
```

### 6.2 诊断数据收集

在算法中主动上报关键指标：

```python
def execute(self, ...):
    # ... 检测逻辑 ...

    # 上报诊断数据
    self.diagnostics.publish("confidence", confidence)
    self.diagnostics.publish("brightness", brightness)
    self.diagnostics.publish("defect_count", len(defect_rects))

    # 在返回值中包含（平台会收集）
    return {
        # ... 其他字段 ...
        "diagnostics": self.diagnostics.get()
    }
```

平台端可以在**远程监控大屏**上展示这些指标的时间序列。

### 6.3 调试图像附件

```python
# 在返回值的diagnostics中包含调试图
result = {
    "diagnostics": {
        "confidence": 0.82,
        "attachments": [
            {
                "type": "image",
                "shared_mem_id": "debug_overlay_001",  # 通过共享内存传递
                "description": "缺陷位置叠加图"
            }
        ]
    }
}
```

平台端可以：
1. 读取共享内存获取调试图
2. 在UI上显示（帮助操作员判断）
3. 保存到日志服务器（远程工程师排查）

---

## 7. 性能优化建议

### 7.1 模型加载优化

```python
class MyAlgorithm(BaseAlgorithm):
    def __init__(self, pid):
        super().__init__(pid)
        self.model = None
        self.warmup_done = False

    def setup(self):
        # 1. 加载模型（一次）
        self.model = load_model()

        # 2. 预热（避免第一次推理慢）
        dummy_input = torch.randn(1, 3, 640, 480)
        self.model(dummy_input.to(self.device))
        self.warmup_done = True
```

### 7.2 批处理支持

如果平台支持一次检测多个图像：

```python
def execute(self, ...):
    # image_meta包含batch信息
    batch_size = image_meta.get("batch_size", 1)

    if batch_size > 1:
        # 批量推理
        results = self.model(batch_images)
    else:
        # 单张推理
        result = self.model(image)
```

### 7.3 GPU内存管理

```python
def reset(self, session):
    # 每次检测后清理GPU缓存（避免内存泄漏）
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
```

---

## 8. 常见问题与解答

### Q1：如何测试真实图像读取？
**当前问题**：shared_memory.py是stub实现，总是返回全黑图像。

**临时方案**：
```python
# 在算法中添加debug模式
class MyAlgorithm(BaseAlgorithm):
    def __init__(self, debug=True):
        super().__init__()
        self.debug = debug
        self.test_image = cv2.imread("test_image.jpg") if debug else None

    def execute(self, ...):
        if self.debug:
            img = self.test_image  # 使用真实图像
        else:
            img = read_image_from_shared_memory(shared_mem_id, image_meta)
```

**长期方案**：等待SDK实现真实共享内存读取。

### Q2：如何传递复杂的ROI参数？

```python
# 在get_info的params中定义
{
    "key": "scan_regions",
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "x": {"type": "int"},
            "y": {"type": "int"},
            "width": {"type": "int"},
            "height": {"type": "int"},
            "label": {"type": "string"}
        }
    }
}

# 在execute中读取
regions = user_params.get("scan_regions", [])
for region in regions:
    roi_img = img[region["y"]:region["y"]+region["height"],
                  region["x"]:region["x"]+region["width"]]
```

### Q3：如何支持多工位/多相机（未来扩展）？

```python
# 从image_meta获取相机信息
camera_id = image_meta.get("camera_id")
station_id = image_meta.get("station_id")

# 根据相机使用不同模型
if camera_id == "camera_top":
    result = self.top_camera_model(img)
elif camera_id == "camera_side":
    result = self.side_camera_model(img)
```

### Q4：如何处理超长检测时间？

```python
import signal

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("检测超时")

def execute(self, ...):
    # 设置超时（例如5秒）
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(5)

    try:
        result = self.model(img)
        signal.alarm(0)  # 取消闹钟
        return result
    except TimeoutError:
        return {
            "status": "ERROR",
            "error_type": "recoverable",
            "suggest_action": "retry",
            "message": "检测超时（可能图像过大）"
        }
```

---

## 9. 交付检查清单

在交付算法包前，确认以下所有项：

### 代码层面
- [ ] 继承自`BaseAlgorithm`，实现所有抽象方法
- [ ] 返回值包含`status`字段（OK/NG/ERROR）
- [ ] 错误情况设置`suggest_action`（retry/skip/abort）
- [ ] 错误情况设置`error_type`（recoverable/fatal）
- [ ] `get_info()`返回正确的steps和params schema
- [ ] 使用`self.logger`记录关键日志（非print）
- [ ] 模型加载在`setup()`中（非execute）
- [ ] 资源释放在`teardown()`中
- [ ] 通过`session.get/set`共享状态（非全局变量）

### 测试层面
- [ ] `procvision-sdk validate --project .`全部PASS
- [ ] 测试OK场景（status="OK"）
- [ ] 测试NG场景（status="NG" + ng_reason）
- [ ] 测试ERROR-recoverable场景
- [ ] 测试ERROR-fatal场景
- [ ] 测试Session隔离（多个Session互不干扰）
- [ ] 测试reset()清理状态

### 打包层面
- [ ] `manifest.json`字段完整
- [ ] `requirements.txt`包含所有依赖及精确版本
- [ ] `wheels/`目录包含所有.whl文件
- [ ] `assets/`目录包含模型和配置
- [ ] ZIP包命名规范：`算法名-v版本号-offline.zip`
- [ ] 在目标环境测试`pip install`（离线）

### 文档层面
- [ ] README.md包含算法描述
- [ ] 说明支持的产品型号（supported_pids）
- [ ] 记录可调参数含义和推荐值
- [ ] 提供性能基线（单张检测耗时）

---

## 10. 参考资源

### 规范文档
- `spec.md` - 技术规范（完整接口定义）
- `spec_review.md` - 规范评审（0→1阶段重点）
- `CODE_REVIEW.md` - 当前实现审查报告

### 示例代码
- 等待`sdk_sample/`目录创建（待实现）

### 开发工具
```bash
# 格式化代码
pip install black
black main.py

# 类型检查
pip install mypy
mypy main.py --ignore-missing-imports

# 查看算法元信息
python -c "from main import MyDetectionAlgorithm; alg = MyDetectionAlgorithm('TEST'); print(alg.get_info())"
```

---

**文档版本**：v1.0
**最后更新**：2025-11-20
**SDK版本**：0.1.0
