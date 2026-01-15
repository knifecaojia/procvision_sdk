# ProcVision Algorithm SDK

## 概述

- 提供 `BaseAlgorithm` 抽象与最小配套能力：`Session` 上下文、结构化日志、诊断数据与共享内存读图接口。
- 算法方仅需实现 `execute`，按 `spec.md` 与平台解耦集成。

## 安装

- 从源码构建后安装：`pip install dist/procvision_algorithm_sdk-<version>-py3-none-any.whl`
- 或直接安装：`pip install procvision_algorithm_sdk`

## 接口要点

- `BaseAlgorithm.__init__()` 不承载业务状态
- `execute(step_index, step_desc, cur_image, guide_image, guide_info)` 为唯一必实现接口
- 日志时间戳字段统一为 `timestamp_ms`
- Runner/CLI 通过共享内存传双图，adapter 解码为 ndarray 后调用 `execute`
- `execute` 的业务判定在 `data.result_status`（`OK/NG`）

## 返回数据类型（Runner/Engine 必看）

### 1) execute 返回（算法 → adapter）
- 返回类型：`Dict[str, Any]`
- 顶层字段（必须理解其语义与类型）：
  - `status: "OK" | "ERROR"`
  - `message: str`（可选）
  - `error_code: str`（可选）
  - `data: Dict[str, Any]`（当且仅当 `status=="OK"` 时必填）
- `data`（当 `status=="OK"`）：
  - `result_status: "OK" | "NG"`
  - `defect_rects: List[Rect]`（当 `result_status=="NG"` 必填，且 ≤20）
  - `ng_reason: str`（当 `result_status=="NG"` 必填）
  - `position_rects: List[Rect]`（可选）
  - `debug: Dict[str, Any]`（可选）

Rect（建议类型）：
- `x/y/width/height: int`（像素坐标）
- `label: str`（可选）
- `score: float`（可选，0~1）

算法侧必须遵守：
- 仅返回 JSON 可序列化的字典；不要返回自定义对象/ndarray/bytes。
- `status=="ERROR"`：必须提供 `message`；建议提供 `error_code`；`data` 可省略。
- `status=="OK"`：必须提供 `data.result_status`；当 `NG` 时必须有 `ng_reason` 与 `defect_rects`（≤20）。
- 坐标使用整数像素，原点左上，`width/height > 0`。

示例：
- OK（无缺陷）：
```json
{"status":"OK","data":{"result_status":"OK","defect_rects":[],"debug":{"latency_ms":12.3}}}
```
- NG（有缺陷）：
```json
{"status":"OK","data":{"result_status":"NG","ng_reason":"检测到划伤","defect_rects":[{"x":94,"y":269,"width":319,"height":398,"label":"scratch","score":0.87}]}}
```
- ERROR（执行失败）：
```json
{"status":"ERROR","message":"模型加载失败","error_code":"2001"}
```
### 2) result 帧（adapter → Runner/Engine）
adapter 会把 `execute` 的返回映射成 `result` 帧，并额外注入 `step_index`：
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
    "debug": {}
  }
}
```

### 3) error 帧（adapter → Runner/Engine）
当发生协议/入参/运行异常时，adapter 返回 `error` 帧（Runner/Engine 应按 `error_code` 分类处理）：
```json
{
  "type": "error",
  "request_id": "rid-123",
  "timestamp_ms": 1714032000456,
  "status": "ERROR",
  "message": "missing cur_image_shm_id/guide_image_shm_id",
  "error_code": "1000"
}
```

## 约束与最佳实践

- `defect_rects ≤ 20`；坐标在图像范围内；`message < 100` 字符、`ng_reason < 50` 字符
- `guide_info` 推荐结构：`[{label: str, posList: [{x,y,width,height}]}]`

## 快速开始

- 最小目录：
  - `your_algo/main.py`
  - `manifest.json`
  - `requirements.txt`
- manifest 最小示例：

```json
{
  "name": "your_algo",
  "version": "1.0.0",
  "entry_point": "your_algo.main:YourAlgorithm"
}
```

- 代码示例：

```
from typing import Any, Dict
from procvision_algorithm_sdk import BaseAlgorithm

class MyAlgo(BaseAlgorithm):
    def __init__(self) -> None:
        super().__init__()

    def execute(self, step_index: int, step_desc: str, cur_image: Any, guide_image: Any, guide_info: Any) -> Dict[str, Any]:
        if cur_image is None or guide_image is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}
        return {"status": "OK", "data": {"result_status": "OK", "defect_rects": [], "debug": {"step_index": step_index, "step_desc": step_desc}}}
```

## CLI（Dev Runner）

- 程序名：`procvision-cli`

### 重要提示：stdio 协议安全（必须遵守）

在 `procvision-cli run`、`procvision-cli validate --full` 以及上位机/客户端算法运行引擎中，算法进程与 Runner/CLI 通过 **stdio 帧协议** 交互：
- `stdout`：专用于协议帧输出（hello/result/error/pong/shutdown）
- `stdin`：专用于接收 Runner/CLI 指令（hello/ping/call/shutdown）
- `stderr`：专用于日志（允许输出文本或结构化 JSON 行）

必须严格遵守：
- 禁止向 `stdout` 输出任何内容：不要 `print()`，不要写 `sys.stdout`，避免第三方库把日志/进度条/告警输出到 stdout
- 允许向 `stderr` 输出日志：推荐使用 `StructuredLogger`，或将第三方日志重定向到 stderr
- 禁止读取 `stdin`：读取会导致协议阻塞或解析失败

常见踩坑：
- `print/pprint/rich/tqdm` 默认写 stdout
- import 阶段打印 banner/版本信息
- warnings 被重定向到 stdout
- 多线程/子进程输出污染 stdout

开发期建议强制自检：
- 使用 `procvision-cli validate --full`：该模式会严格检测 stdout 污染，发现即判失败并提示修复。

### validate（校验）

用途：
- 校验 `manifest.json` 必备字段、入口可导入、`execute` 返回结构是否符合约束
- 可选校验离线 zip 的结构完整性（manifest/requirements/wheels）

用法：
```bash
procvision-cli validate [project] [--manifest <path>] [--zip <path>] [--full] [--entry <module:Class>] [--tail-logs] [--json]
```

参数说明：
- `project`：算法项目根目录（默认 `.`），用于定位 `manifest.json` 以及作为导入路径
- `--manifest`：显式指定 `manifest.json` 路径（当项目目录不标准时使用）
- `--zip`：离线交付包路径（仅做包结构检查：是否包含 manifest/requirements/wheels）
- `--full`：使用“适配器子进程”执行一次完整握手 + `execute` 调用（更接近生产 Runner 行为）
- `--entry`：显式指定入口 `<module:Class>`（仅 `--full` 模式使用；覆盖适配器自动发现）
- `--tail-logs`：`--full` 模式下实时打印子进程 `stderr` 日志到当前控制台
- `--json`：输出完整 JSON 报告（便于脚本/CI 消费）

示例：
```bash
procvision-cli validate ./algorithm-example
procvision-cli validate ./algorithm-example --full --tail-logs
procvision-cli validate ./algorithm-example --full --entry algorithm_example.main:AlgorithmExample --json
procvision-cli validate --zip ./your_algo-v1.0.0-offline.zip --json
```

退出码：
- `0`：通过
- `1`：失败

### run（本地运行）

用途：
- 使用本地图片写入共享内存，并通过适配器子进程调用一次 `execute`

用法：
```bash
procvision-cli run <project> --cur-image <path> (--guide-image <path> | --image <path>) [--step <index>] [--step-desc <text>] [--guide-info <json|@file>] [--entry <module:Class>] [--tail-logs] [--json]
```

参数说明：
- `project`：算法项目根目录（必须包含 `manifest.json`）
- `--cur-image`：引导图路径（JPEG/PNG），将写入共享内存
- `--guide-image`：相机采集图路径（JPEG/PNG），将写入共享内存
- `--image`：`--guide-image` 的别名（兼容参数）
- `--step`：步骤索引（默认 `1`）
- `--step-desc`：步骤描述文本（中英文均可）
- `--guide-info`：guide_info JSON 字符串，或 `@file.json`
- `--entry`：显式指定入口 `<module:Class>`（覆盖适配器自动发现）
- `--tail-logs`：实时打印子进程 `stderr` 日志
- `--json`：输出结果 JSON（默认输出人类可读摘要）

示例：
```bash
procvision-cli run ./algorithm-example --cur-image ./cur.jpg --guide-image ./guide.jpg --json
procvision-cli run ./algorithm-example --cur-image ./cur.jpg --image ./guide.jpg --step 2 --step-desc "Step 2" --guide-info @guide.json --tail-logs
```

退出码：
- `0`：`execute.status == "OK"`
- `1`：其它情况（包括 `ERROR` 或运行失败）

### init（初始化脚手架）

用途：
- 生成算法项目骨架：`manifest.json` + 入口包目录 + `main.py`（仅需实现 `execute`）

用法：
```bash
procvision-cli init <name> [-d <dir>] [-v <version>] [-e <desc>]
```

参数说明：
- `name`：算法名称（用于 `manifest.json.name`，以及生成模块目录/类名）
- `-d/--dir`：目标目录（默认在当前目录以算法名创建）
- `-v/--version`：算法版本（默认 `1.0.0`，写入 `manifest.json.version`）
- `-e/--desc`：算法描述（可选，写入 `manifest.json.description`）

### package（离线交付打包）

用途：
- 规范化 `requirements.txt`、下载 wheels、打包源码与依赖，生成离线 zip

用法：
```bash
procvision-cli package <project> [-o <zip>] [-r <requirements.txt>] [-a] [-w <platform>] [-p <pyver>] [-i <impl>] [-b <abi>] [-s] [--embed-python|--no-embed-python] [--python-runtime <dir>] [--runtime-python-version <v>] [--runtime-abi <abi>]
```

参数说明（常用）：
- `project`：算法项目根目录
- `-o/--output`：输出 zip 路径（默认按 `name/version` 生成）
- `-r/--requirements`：requirements 文件路径（默认使用项目内文件；缺失时会尝试自动生成）
- `-a/--auto-freeze`：缺少 requirements 时自动执行 `pip freeze` 生成（当前实现默认开启）
- `-w/--wheels-platform`：目标平台（默认 `win_amd64` 或读取 `.procvision_env.json`）
- `-p/--python-version`：目标 Python 版本（默认 `3.10` 或读取 `.procvision_env.json`）
- `-i/--implementation`：实现（默认 `cp`）
- `-b/--abi`：ABI（默认 `cp310`）
- `-s/--skip-download`：跳过 `pip download`，仅打包当前项目已有的 `wheels/`
- `--embed-python/--no-embed-python`：是否把 Python 运行时一并放入离线包（默认开启）
- `--python-runtime`：运行时目录（Windows embeddable 或 venv 根目录）
- `--runtime-python-version`：运行时版本标识（如 `3.10`）
- `--runtime-abi`：运行时 ABI（如 `cp310`）

## 适配器启动（Runner 集成）

- 简化命令：
  - Windows：`<deployed_dir>\venv\Scripts\python.exe -m procvision_algorithm_sdk.adapter`
  - Linux：`<deployed_dir>/venv/bin/python -m procvision_algorithm_sdk.adapter`
- 自动发现入口优先级：`--entry` > `PROC_ENTRY_POINT` > `manifest.json`/`manifest.yaml` > `pyproject.toml [tool.procvision.algorithm]` > 默认 `algorithm.main:Algorithm`

环境变量速查：
- `PROC_ALGO_ROOT`：算法项目根目录（Runner/CLI 在启动适配器时会注入）
- `PROC_ENTRY_POINT`：显式入口 `<module:Class>`（可替代 `--entry`）
- `PROC_PYTHON_RUNTIME`：`package` 自动发现 Python 运行时的候选目录

## 离线交付

- 生成 `requirements.txt`：`pip freeze > requirements.txt`
- 下载 wheels：

```
pip download -r requirements.txt -d wheels/ --platform win_amd64 --python-version 3.10 --implementation cp --abi cp310
```

- 打包 zip：包含源码目录、`manifest.json`、`requirements.txt`、`wheels/` 与可选 `assets/`
 
## 打包随包的 Python 运行时（可选）
 
- 默认开启：`procvision-cli package` 默认打包 Python 运行时。若需禁用，使用 `--no-embed-python`。
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
- 当前版本：`v0.3.0`（execute 入参硬切：step_desc/双图/guide_info，协议与 CLI 对齐）

## 参考

- `protocol_adapter_spec.md`、`runner_spec.md`、`algorithm_dev_tutorial.md` 提供接口契约、通信协议与开发指南
- 版本变更：`docs/release-notes/v0.3.0.md`
