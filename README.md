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
  - `procvision-cli validate ./your_algo_project --full`（适配器子进程握手+调用）
  - 显式入口：`procvision-cli validate ./your_algo_project --full --entry your_pkg.main:YourAlgorithm`
  - 旧路径：`procvision-cli validate ./your_algo_project --legacy-validate`
  - 输出日志：`procvision-cli validate ./your_algo_project --full --tail-logs`
- 本地模拟运行：
  - `procvision-cli run ./your_algo_project --pid p001 --image ./test.jpg --json`
  - 运行机制：以适配器子进程方式，通过帧协议通信与共享内存读写；如需旧的本地直接导入执行，追加 `--legacy-run`
  - 输出日志：`procvision-cli run ./your_algo_project --pid p001 --image ./test.jpg --tail-logs`

## 适配器启动（Runner 集成）

- 简化命令：
  - Windows：`<deployed_dir>\venv\Scripts\python.exe -m procvision_algorithm_sdk.adapter`
  - Linux：`<deployed_dir>/venv/bin/python -m procvision_algorithm_sdk.adapter`
- 自动发现入口优先级：`--entry` > `PROC_ENTRY_POINT` > `manifest.json`/`manifest.yaml` > `pyproject.toml [tool.procvision.algorithm]` > 默认 `algorithm.main:Algorithm`

## 离线交付

- 生成 `requirements.txt`：`pip freeze > requirements.txt`
- 下载 wheels：

```
pip download -r requirements.txt -d wheels/ --platform win_amd64 --python-version 3.10 --implementation cp --abi cp310
```

- 打包 zip：包含源码目录、`manifest.json`、`requirements.txt`、`wheels/` 与可选 `assets/`
 
## 打包随包的 Python 运行时（可选）
 
- 默认开启：从 v0.0.6 起，`procvision-cli package` 默认打包 Python 运行时。若需禁用，使用 `--no-embed-python`。
- 适用场景：Runner 端 Python 版本与算法开发版本不一致，导致 wheels 无法加载。
- 准备运行时（Windows 示例）：从 Python 官网下载对应版本的 Embeddable Package（如 `python-3.10.x-embed-amd64.zip`）并解压到本地目录。
- 构建包含运行时的离线包（默认开启）：
  - `procvision-cli package ./algorithm-example --python-runtime <path_to_embeddable_dir> --runtime-python-version 3.10 --runtime-abi cp310`
- 运行时来源的自动发现：
  - 环境变量：`PROC_PYTHON_RUNTIME` 指定目录
  - 项目配置：`.procvision_env.json` 的 `python_runtime` 字段
- 包内将包含：
  - `python_runtime/`：运行时目录
  - `deploy_bootstrap.json`：声明运行时版本与 ABI（Runner 用于部署时选择）
- Runner 部署建议：
  - 使用包内运行时创建隔离 venv 并从 `wheels/` 安装依赖，然后使用该 venv 启动适配器

## 本地打包与发布（pip 包）

- 安装构建与发布工具：
  - `pip install -U build twine`
- 构建 wheel 与源码包（基于 `pyproject.toml`）：
  - `python -m build`
  - 产物输出在 `dist/`（如：`procvision_algorithm_sdk-<version>-py3-none-any.whl` 与 `procvision_algorithm_sdk-<version>.tar.gz`）
- 本地安装验证：
  - `pip install dist/procvision_algorithm_sdk-<version>-py3-none-any.whl`
- 发布到内部 PyPI（示例，仅供参考）：
  - `twine upload --repository-url <your-internal-pypi-url> dist/*`
  - 建议在环境变量或凭据管理中配置用户与令牌，避免将敏感信息写入命令行
- 版本号更新：
  - 编辑 `pyproject.toml` 的 `version` 字段（当前：`pyproject.toml:7`）并重新构建
  - 建议在 CI 中基于标签或提交自动生成版本并构建

## GitHub CI/CD

- 工作流文件：`.github/workflows/sdk-build-and-publish.yml`
- 关键步骤：安装依赖、运行测试、`python -m build` 构建产物、按标签发布到包仓库
 - 运行单元测试：`python -m unittest discover -s tests -p "test_*.py" -v`

## 目录与文件

- 包路径：`procvision_algorithm_sdk`
- 打包配置：`pyproject.toml`
- 单元测试：`tests/`

## 版本与兼容

- 要求 Python `>=3.10`
- 依赖：`numpy>=1.21`
 - 当前版本：`v0.0.6`（新增适配器模块与 CLI 改动）

## 参考

- `protocol_adapter_spec.md`、`runner_spec.md`、`algorithm_dev_tutorial.md` 提供接口契约、通信协议与开发指南
- 版本变更：`docs/release-notes/v0.0.6.md`
