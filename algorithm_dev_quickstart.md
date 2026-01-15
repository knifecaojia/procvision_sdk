# ProcVision 算法快速入门（Execute-only）

## SDK版本从V0.0.7 跃迁到 V0.3.0

重要变更提示：

删除全部算法运行周期支持

删除算法Session上下文管理与全部钩子函数

仅保留一个算法入口 execute

极大的精简了开发需遵守的运行规范

## 重要提示：stdio 协议安全（必须遵守）

在 `procvision-cli run`、`procvision-cli validate --full` 以及上位机/客户端算法运行引擎中，算法进程与 Runner/CLI 通过 **stdio 帧协议** 交互控制指令：

- `stdout`：专用于协议帧输出（hello/result/error/pong/shutdown）
- `stdin`：专用于接收 Runner/CLI 指令（hello/ping/call/shutdown）
- `stderr`：专用于日志（允许输出文本或结构化 JSON 行）

因此算法开发过程中必须严格遵守：

- 禁止向 `stdout` 输出任何内容：不要 `print()`，不要写 `sys.stdout`，不要让第三方库把日志/进度条/告警打印到 stdout
- 允许向 `stderr` 输出日志：推荐使用 `StructuredLogger`（SDK 内置）或将第三方日志改为输出到 stderr
- 禁止读取 `stdin`：stdio 输入由协议使用，读取会导致协议阻塞或解析失败

常见踩坑清单（建议逐条自检）：

- 使用 `print()`/`pprint()`/`rich.print()`/`tqdm` 默认输出到 stdout
- 依赖库在 import 时打印 banner/版本信息到 stdout
- 运行时告警（例如 warnings）被重定向到 stdout
- 多线程/子进程把日志写到 stdout（尤其是外部推理引擎包装层）

一旦 stdout 被污染，Runner/CLI 会出现：握手失败、结果解析失败、随机卡死、误报超时等问题。

开发期建议强制自检：

- 使用 `procvision-cli validate --full`：该模式会严格检测 stdout 污染，发现即判失败并提示修复。

## 1. 项目初始化

```bash
procvision-cli init demo_algo -d ./demo_algo -v 1.0.0 -e "demo"
```

生成：

- `manifest.json`
- `<module>/main.py`（入口类，仅需实现 execute）

### init 参数说明

用法：

```bash
procvision-cli init <name> [-d <dir>] [-v <version>] [-e <desc>]
```

- `name`：算法名称（用于 `manifest.json.name`，以及生成模块目录/类名）
- `-d/--dir`：目标目录（默认在当前目录以算法名创建）
- `-v/--version`：算法版本（默认 `1.0.0`，写入 `manifest.json.version`）
- `-e/--desc`：算法描述（可选，写入 `manifest.json.description`）

## 2. manifest.json（最小）

```json
{
  "name": "demo_algo",
  "version": "1.0.0",
  "entry_point": "demo_algo.main:DemoAlgoAlgorithm",
  "description": "demo"
}
```

## 3. 实现 execute

`main.py` 只需要实现一个函数：

```python
from typing import Any, Dict
from procvision_algorithm_sdk import BaseAlgorithm

class DemoAlgoAlgorithm(BaseAlgorithm):
    def execute(
        self,
        step_index: int,
        step_desc: str,
        cur_image: Any,
        guide_image: Any,
        guide_info: Any,
    ) -> Dict[str, Any]:
        if cur_image is None or guide_image is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}
	cur = normalize_image(cur_image, "cur_image")
        guide = normalize_image(guide_image, "guide_image")
#####################################算法业务逻辑#####################################


        return {"status": "OK", "data": {"result_status": "OK", "defect_rects": []}}
```

### 如何判断与统一图像格式（开发建议）

`cur_image/guide_image` 通常为 `numpy.ndarray`，`dtype=uint8`，形状 `H×W×3`（RGB）。但建议兼容灰度/单通道/RGBA，并在 `execute` 开头归一化：

```python
from typing import Any
import numpy as np

def normalize_image(img: Any, name: str) -> np.ndarray:
    if not isinstance(img, np.ndarray):
        raise ValueError(f"{name} 不是 ndarray: {type(img)}")
    if img.dtype != np.uint8:
        img = img.astype(np.uint8, copy=False)
    if img.ndim == 2:
        img = np.stack([img, img, img], axis=-1)
    elif img.ndim == 3:
        if img.shape[2] == 1:
            img = np.repeat(img, 3, axis=2)
        elif img.shape[2] == 4:
            img = img[:, :, :3]
        elif img.shape[2] != 3:
            raise ValueError(f"{name} 通道数异常: shape={img.shape}")
    else:
        raise ValueError(f"{name} 维度异常: shape={img.shape}")
    return img
```

### execute 返回数据格式（必须遵守）

- 返回类型：`Dict[str, Any]`，且必须是 JSON 可序列化（不要返回自定义对象/ndarray/bytes）。
- `status == "ERROR"`：
  - 必须提供 `message`（用于定位问题）
  - 建议提供 `error_code`（便于平台侧分类/统计）
  - `data` 可省略
- `status == "OK"`：
  - 必须提供 `data.result_status in {"OK","NG"}`
  - 若 `result_status == "NG"`：必须提供 `ng_reason` 与 `defect_rects`，且 `defect_rects ≤ 20`
  - 建议统一返回 `defect_rects` 字段：OK 时返回空数组，便于平台侧统一解析

返回示例：

OK（无缺陷）：

```json
{
  "status": "OK",
  "data": {
    "result_status": "OK",
    "defect_rects": [],
    "debug": {"latency_ms": 12.3}
  }
}
```

NG（有缺陷）：

```json
{
  "status": "OK",
  "data": {
    "result_status": "NG",
    "ng_reason": "检测到划伤",
    "defect_rects": [
      {"x": 94, "y": 269, "width": 319, "height": 398, "label": "scratch", "score": 0.87}
    ]
  }
}
```

ERROR（执行失败）：

```json
{
  "status": "ERROR",
  "message": "模型加载失败",
  "error_code": "2001"
}
```

## 4. 本地运行与校验

```bash
procvision-cli validate ./demo_algo
procvision-cli validate ./demo_algo --full --tail-logs
procvision-cli run ./demo_algo --cur-image ./cur.jpg --guide-image ./guide.jpg --step-desc "Step 1" --guide-info @guide.json --json
```

### validate 参数说明

用途：

- 校验项目目录中的 `manifest.json` 与入口类可导入、`execute` 结构正确
- 可选校验离线 zip 的结构完整性

用法：

```bash
procvision-cli validate [project] [--manifest <path>] [--zip <path>] [--full] [--entry <module:Class>] [--tail-logs] [--json]
```

- `project`：算法项目根目录（默认 `.`）
- `--manifest`：显式指定 `manifest.json` 路径
- `--zip`：离线包路径（检查包内是否包含 manifest/requirements/wheels）
- `--full`：通过适配器子进程完成握手并调用一次 `execute`
- `--entry`：显式入口 `<module:Class>`（覆盖自动发现，仅 `--full` 使用）
- `--tail-logs`：`--full` 模式实时跟随子进程 `stderr` 日志
- `--json`：输出 JSON 报告（用于 CI/脚本）

### run 参数说明

用途：

- 用本地图片写入共享内存后，通过适配器子进程调用一次 `execute`

用法：

```bash
procvision-cli run <project> --cur-image <path> (--guide-image <path> | --image <path>) [--step <index>] [--step-desc <text>] [--guide-info <json|@file>] [--entry <module:Class>] [--tail-logs] [--json]
```

- `project`：算法项目根目录（必须包含 `manifest.json`）
- `--cur-image`：引导图路径（JPEG/PNG）
- `--guide-image`：相机采集图路径（JPEG/PNG）
- `--image`：`--guide-image` 的别名（兼容参数）
- `--step`：步骤索引（默认 `1`）
- `--step-desc`：步骤描述文本（中英文均可）
- `--guide-info`：guide_info JSON 字符串，或 `@file.json`
- `--entry`：显式入口 `<module:Class>`（覆盖自动发现）
- `--tail-logs`：实时跟随子进程 `stderr` 日志
- `--json`：输出 JSON 结果

退出码：

- `0`：`execute.status == "OK"`
- `1`：其它情况

### package 参数说明（离线交付）

用法：

```bash
procvision-cli package <project> [-o <zip>] [-r <requirements.txt>] [-a] [-w <platform>] [-p <pyver>] [-i <impl>] [-b <abi>] [-s] [--embed-python|--no-embed-python] [--python-runtime <dir>] [--runtime-python-version <v>] [--runtime-abi <abi>]
```

- `-o/--output`：输出 zip 路径（默认按 `name/version` 生成）
- `-r/--requirements`：requirements 文件路径（默认使用项目内文件；缺失时尝试自动生成）
- `-a/--auto-freeze`：缺少 requirements 时自动执行 `pip freeze` 生成（当前实现默认开启）
- `-w/--wheels-platform`：目标平台（默认 `win_amd64` 或读取 `.procvision_env.json`）
- `-p/--python-version`：目标 Python 版本（默认 `3.10` 或读取 `.procvision_env.json`）
- `-i/--implementation`：实现（默认 `cp`）
- `-b/--abi`：ABI（默认 `cp310`）
- `-s/--skip-download`：跳过 `pip download`，仅打包现有 `wheels/`
- `--embed-python/--no-embed-python`：是否把 Python 运行时一并打包（默认开启）
- `--python-runtime`：运行时目录（Windows embeddable 或 venv 根目录）
- `--runtime-python-version`：运行时版本标识（如 `3.10`）
- `--runtime-abi`：运行时 ABI（如 `cp310`）
