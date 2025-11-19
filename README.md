# ProcVision Algorithm SDK

## 概述

- 提供 `BaseAlgorithm` 抽象与最小配套能力，包括 `Session` 状态共享、结构化日志、诊断数据与共享内存读图接口。
- 算法方通过继承 `BaseAlgorithm` 实现 `get_info`、`pre_execute`、`execute` 与生命周期钩子，即可与平台解耦集成。

## 安装

- 从源码构建后安装：`pip install dist/procvision_algorithm_sdk-<version>-py3-none-any.whl`
- 或直接在私有/公网 PyPI 安装：`pip install procvision_algorithm_sdk`

## 快速开始

- 目录结构示例：
  - `pa_screw_check/main.py`
  - `manifest.json`
  - `requirements.txt`
- 代码示例：

```
from procvision_algorithm_sdk import BaseAlgorithm, Session, read_image_from_shared_memory

class ScrewCheckAlgorithm(BaseAlgorithm):
    def get_info(self):
        return {
            "name": "product_a_screw_check",
            "version": "1.0.0",
            "steps": [
                {"index": 0, "name": "定位主板", "params": [{"key": "threshold", "type": "float", "default": 0.7}]}
            ],
        }

    def pre_execute(self, step_index, session, shared_mem_id, image_meta, user_params):
        return {"status": "OK", "overlay": {}}

    def execute(self, step_index, session, shared_mem_id, image_meta, user_params):
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        return {"status": "OK", "diagnostics": {"brightness": float(img.mean())}}
```

## 离线交付

- 生成 `requirements.txt`：`pip freeze > requirements.txt`
- 下载 wheels：

```
pip download -r requirements.txt -d wheels/ --platform win_amd64 --python-version 3.8 --implementation cp --abi cp38
```

- 打包 zip：包含源码目录、`manifest.json`、`requirements.txt`、`wheels/` 与可选 `assets/`。

## GitHub CI/CD（自动编译、打包与发布到 PyPI）

- 前提配置：
  - 在仓库 Settings → Secrets 新建 `PYPI_TOKEN`，值为 PyPI API Token；User 设为 `__token__`。
  - 主分支为 `main`，发版使用 `v*` 标签，例如 `v0.1.0`。
- 工作流文件：`.github/workflows/sdk-build-and-publish.yml` 已创建，关键步骤：
  - 检出代码并设置 Python 3.8。
  - 安装构建与测试依赖，运行 `pytest`。
  - 执行 `python -m build` 生成 `sdist` 与 `wheel`。
  - 上传构建产物为 artifact。
  - 当推送 `v*` 标签时，使用 `pypa/gh-action-pypi-publish` 发布到 PyPI。
- 使用方式：
  - 推送到 `main`：自动执行构建与测试。
  - 创建并推送标签：`git tag v0.1.0 && git push origin v0.1.0`，自动发布到 PyPI。
  - 可将 `repository-url` 替换为企业私有 PyPI 地址，用于内网发布。

## 目录与文件

- 包路径：`algorithm-sdk/sdk/procvision_algorithm_sdk`
- 打包配置：`algorithm-sdk/sdk/pyproject.toml`
- 单元测试：`algorithm-sdk/sdk/tests/`

## 版本与兼容

- 要求 Python `>=3.8`。
- 最小依赖为 `numpy>=1.21`。

## 参考

- `algorithm-sdk/spec.md` 与 `algorithm-sdk/algorithm_dev_tutorial.md` 提供接口契约与交付流程细节。
- 测试版本
