# ProcVision Algorithm SDK

## 概述

- 提供 `BaseAlgorithm` 抽象与最小配套能力：`Session` 状态共享、结构化日志、诊断数据与共享内存读图接口。
- 算法方通过实现 `get_info`、`pre_execute`、`execute` 与生命周期钩子，按 `spec.md` 与平台解耦集成。

## 安装

- 从源码构建后安装：`pip install dist/procvision_algorithm_sdk-<version>-py3-none-any.whl`
- 或直接安装：`pip install procvision_algorithm_sdk`

## 接口要点（v1.0.0 对齐规范 v0.2.1）

- `BaseAlgorithm.__init__()` 不绑定 PID；每次调用通过参数传入 `pid`
- `pre_execute(step_index, pid, session, user_params, shared_mem_id, image_meta)`
- `execute(step_index, pid, session, user_params, shared_mem_id, image_meta)`
- 日志时间戳字段统一为 `timestamp_ms`
- 共享内存传图 JPEG-only，`image_meta` 最小集合：`width/height/timestamp_ms/camera_id`
- `pre_execute` 不返回真实检测结果；`execute` 的业务判定在 `data.result_status`（`OK/NG`）

## 快速开始

- 最小目录：
  - `your_algo/main.py`
  - `manifest.json`
  - `requirements.txt`
- 代码示例：

```
from typing import Any, Dict
from procvision_algorithm_sdk import BaseAlgorithm, Session, read_image_from_shared_memory

class MyAlgo(BaseAlgorithm):
    def __init__(self) -> None:
        super().__init__()
        self._supported_pids = ["p001", "p002"]

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": "my_algo",
            "version": "1.0",
            "supported_pids": self._supported_pids,
            "steps": [{"index": 0, "name": "示例", "params": [{"key": "threshold", "type": "float", "default": 0.5, "min": 0.0, "max": 1.0}]}],
        }

    def pre_execute(self, step_index: int, pid: str, session: Session, user_params: Dict[str, Any], shared_mem_id: str, image_meta: Dict[str, Any]) -> Dict[str, Any]:
        if pid not in self._supported_pids:
            return {"status": "ERROR", "message": f"不支持的产品型号: {pid}", "error_code": "1001"}
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        if img is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}
        return {"status": "OK", "message": "准备就绪", "debug": {"latency_ms": 0.0}}

    def execute(self, step_index: int, pid: str, session: Session, user_params: Dict[str, Any], shared_mem_id: str, image_meta: Dict[str, Any]) -> Dict[str, Any]:
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        if img is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}
        return {"status": "OK", "data": {"result_status": "OK", "defect_rects": [], "debug": {"latency_ms": 0.0}}}
```

## CLI（Dev Runner）

- 程序名：`procvision-cli`
- 校验算法包：
  - `procvision-cli validate --project ./your_algo_project`
- 本地模拟运行：
  - `procvision-cli run ./your_algo_project --pid p001 --image ./test.jpg --json`

## 离线交付

- 生成 `requirements.txt`：`pip freeze > requirements.txt`
- 下载 wheels：

```
pip download -r requirements.txt -d wheels/ --platform win_amd64 --python-version 3.10 --implementation cp --abi cp310
```

- 打包 zip：包含源码目录、`manifest.json`、`requirements.txt`、`wheels/` 与可选 `assets/`

## GitHub CI/CD

- 工作流文件：`.github/workflows/sdk-build-and-publish.yml`
- 关键步骤：安装依赖、运行测试、`python -m build` 构建产物、按标签发布到包仓库

## 目录与文件

- 包路径：`procvision_algorithm_sdk`
- 打包配置：`pyproject.toml`
- 单元测试：`tests/`

## 版本与兼容

- 要求 Python `>=3.10`
- 依赖：`numpy>=1.21`

## 参考

- `spec.md` 与 `spec_runner.md` 提供接口契约、通信协议与交付流程
