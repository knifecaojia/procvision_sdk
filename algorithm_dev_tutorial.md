# 算法开发教程（ProcVision SDK，Execute-only）

## 目标
- 算法侧仅实现一个方法：`execute`。
- 不存在 `get_info/pre_execute/setup/teardown/reset/on_step_*` 等生命周期与钩子。

## 重要提示：stdio 协议安全（必须遵守）

在 `procvision-cli run`、`procvision-cli validate --full` 以及上位机/客户端算法运行引擎中，算法进程与 Runner 通过 **stdio 帧协议** 交互：
- `stdout`：仅用于协议帧输出
- `stdin`：仅用于接收协议指令
- `stderr`：仅用于日志

必须严格遵守：
- 禁止向 `stdout` 输出任何内容（包括 `print()`、第三方库 banner、进度条）
- 允许向 `stderr` 输出日志（推荐 `StructuredLogger`）
- 禁止读取 `stdin`（会导致协议阻塞/解析失败）

开发期建议强制自检：
- 使用 `procvision-cli validate --full`：该模式会严格检测 stdout 污染，发现即判失败并提示修复。

## 入口类要求
- 入口类必须继承 `BaseAlgorithm`
- `manifest.json.entry_point` 指向该类

## execute 入参
`execute(step_index, step_desc, cur_image, guide_image, guide_info)`
- `step_index`：步骤索引（平台从 1 开始）
- `step_desc`：步骤描述（中英文文本）
- `cur_image`：当前步骤引导图（ndarray）
- `guide_image`：当前步骤相机采集图（ndarray）
- `guide_info`：引导信息（对象数组，包含 label 与 posList 矩形列表）

## execute 返回
- 顶层：`status/message/error_code/data`
- 当 `status="OK"` 时：
  - `data.result_status ∈ {OK,NG}`
  - `NG` 时必须提供 `ng_reason` 与 `defect_rects`，且 `defect_rects ≤ 20`

## 图像输入（cur_image / guide_image）
`execute` 会直接收到两张图像的 ndarray（由 adapter 从共享内存读取并解码后传入）：
- `cur_image`：引导图
- `guide_image`：相机采集图

建议实践：
- 以 `guide_image.shape` 获取图像尺寸（`H×W×C`）
- 不要在算法中读写 stdio 或共享内存

### 如何判断图像格式（开发建议）
在绝大多数情况下，`cur_image/guide_image` 为：
- `numpy.ndarray`
- `dtype=uint8`
- 形状为 `H×W×3`（RGB）

但仍建议兼容这些情况：
- 灰度图：`H×W`（没有通道维）
- 单通道：`H×W×1`
- 带 alpha：`H×W×4`（RGBA，建议丢弃 alpha 只保留 RGB）

建议在 `execute` 开头做一次快速自检与归一化，并使用 `StructuredLogger` 输出到 `stderr`（不要 print 到 stdout）：

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

用法（在 execute 内）：
- `cur = normalize_image(cur_image, "cur_image")`
- `guide = normalize_image(guide_image, "guide_image")`
- `h, w = guide.shape[:2]`

## CLI 使用

### validate（校验）

用途：
- 校验 `manifest.json` 必备字段（`name/version/entry_point`）
- 校验入口类可导入且继承 `BaseAlgorithm`
- 校验 `execute` 的返回结构与关键约束（`result_status`、NG 必备字段、`defect_rects≤20`）

用法：
```bash
procvision-cli validate [project] [--manifest <path>] [--zip <path>] [--full] [--entry <module:Class>] [--tail-logs] [--json]
```

参数说明：
- `project`：算法项目根目录（默认 `.`）
- `--manifest`：显式指定 `manifest.json` 文件路径（用于非标准目录结构）
- `--zip`：离线 zip 包路径（仅检查包内是否包含 `manifest.json/requirements.txt/wheels/`）
- `--full`：通过适配器子进程完成握手并调用一次 `execute`（推荐）
- `--entry`：显式入口 `<module:Class>`（覆盖自动发现，仅 `--full` 使用）
- `--tail-logs`：`--full` 模式实时输出子进程 `stderr` 日志
- `--json`：输出 JSON 报告（便于 CI 解析）

示例：
```bash
procvision-cli validate ./your_algo_project
procvision-cli validate ./your_algo_project --full --tail-logs
procvision-cli validate ./your_algo_project --full --entry your_pkg.main:YourAlgorithm --json
procvision-cli validate --zip ./your_algo-v1.0.0-offline.zip --json
```

### run（本地运行）

用途：
- 将本地图片写入共享内存，并通过适配器子进程调用一次 `execute`

用法：
```bash
procvision-cli run <project> --cur-image <path> (--guide-image <path> | --image <path>) [--step <index>] [--step-desc <text>] [--guide-info <json|@file>] [--entry <module:Class>] [--tail-logs] [--json]
```

参数说明：
- `project`：算法项目根目录（必须包含 `manifest.json`）
- `--cur-image`：引导图路径（JPEG/PNG）
- `--guide-image`：相机采集图路径（JPEG/PNG）
- `--image`：`--guide-image` 的别名（兼容参数）
- `--step`：步骤索引（默认 `1`）
- `--step-desc`：步骤描述文本（中英文均可）
- `--guide-info`：guide_info JSON 字符串，或 `@file.json`
- `--entry`：显式入口 `<module:Class>`（覆盖自动发现）
- `--tail-logs`：实时输出子进程 `stderr` 日志
- `--json`：输出 JSON 结果（否则为摘要输出）

示例：
```bash
procvision-cli run ./your_algo_project --cur-image ./cur.jpg --guide-image ./guide.jpg --json
procvision-cli run ./your_algo_project --cur-image ./cur.jpg --image ./guide.jpg --step 2 --step-desc "Step 2" --guide-info @guide.json --tail-logs
```

### init（初始化脚手架）
```bash
procvision-cli init <name> [-d <dir>] [-v <version>] [-e <desc>]
```

- `name`：算法名称
- `-d/--dir`：目标目录
- `-v/--version`：算法版本（写入 `manifest.json.version`）
- `-e/--desc`：算法描述（写入 `manifest.json.description`）

### package（离线交付打包）
```bash
procvision-cli package <project> [-o <zip>] [-r <requirements.txt>] [-a] [-w <platform>] [-p <pyver>] [-i <impl>] [-b <abi>] [-s] [--embed-python|--no-embed-python] [--python-runtime <dir>] [--runtime-python-version <v>] [--runtime-abi <abi>]
```

常用参数说明：
- `-o/--output`：输出 zip 路径
- `-r/--requirements`：requirements 文件路径
- `-a/--auto-freeze`：缺少 requirements 时自动 `pip freeze`
- `-w/--wheels-platform` / `-p/--python-version` / `-i/--implementation` / `-b/--abi`：目标环境选择（决定下载哪些 wheels）
- `-s/--skip-download`：跳过下载，仅打包现有 wheels
- `--embed-python/--no-embed-python`：是否携带 Python 运行时（默认开启）
- `--python-runtime`：运行时目录（Windows embeddable 或 venv 根目录）
