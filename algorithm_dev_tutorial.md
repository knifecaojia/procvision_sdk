# 算法开发教程（ProcVision SDK）

本文以 Wiki 风格，系统性介绍 SDK 的命令行、接口、函数与钩子，帮助第三方团队快速、规范地完成算法开发与交付。内容覆盖环境准备、脚手架初始化、接口实现规范、运行校验、依赖与打包、日志诊断以及常见问题。

## 总览与导航

- SDK 包结构：`procvision_algorithm_sdk`（核心 API 与 CLI）
- 示例项目：`algorithm-example`（清单与入口实现参考）
- 控制台脚本：`procvision-cli`（校验/运行/打包/初始化）
- 关键模块职责：
  - `BaseAlgorithm` 抽象基类与生命周期钩子（`procvision_algorithm_sdk/base.py:9`）
  - `Session` 会话上下文与 KV 状态存储（`procvision_algorithm_sdk/session.py:5`）
  - 共享内存读图（`procvision_algorithm_sdk/shared_memory.py:16`）
  - 结构化日志与诊断（`procvision_algorithm_sdk/logger.py:7`，`procvision_algorithm_sdk/diagnostics.py:4`）
  - CLI 子命令实现（`procvision_algorithm_sdk/cli.py:555`）

## 开发环境

- 安装 Python 3.10 及以上版本
- 创建虚拟环境并安装 SDK：
  - Windows：`python -m venv .venv`，`\.venv\Scripts\activate`
  - Linux/Mac：`python -m venv .venv`，`source .venv/bin/activate`
  - 安装：`pip install procvision_algorithm_sdk`

## 初始化脚手架

- 命令：`procvision-cli init <name> --pids <p1,p2> -v <version> -d <dir> [-e <desc>]`
- 生成内容：
  - `manifest.json`（清单，入口点与支持 PID）
  - 包目录与 `main.py`（入口类，继承 `BaseAlgorithm`）
  - 环境缓存 `.procvision_env.json`（用于打包默认平台参数，`procvision_algorithm_sdk/cli.py:278-299`）
- 入口示例类与注释位置：`procvision_algorithm_sdk/cli.py:377-442`

## 清单规范（manifest.json）

- 必填：`name`、`version`、`entry_point`、`supported_pids`
- 推荐：`description`、`steps`（步骤与参数 schema）
- 入口点格式：`模块路径:类名`，入口类必须继承 `BaseAlgorithm`（`procvision_algorithm_sdk/cli.py:66-73`）
- 一致性要求：`manifest.supported_pids == get_info().supported_pids`（`procvision_algorithm_sdk/cli.py:86-89`）
- 示例：见 `algorithm-example/manifest.json:1-25`

## 接口与生命周期（BaseAlgorithm）

- 抽象方法（必须实现）：
  - `get_info() -> Dict[str, Any]`（`procvision_algorithm_sdk/base.py:32-35`）
  - `pre_execute(...) -> Dict[str, Any]`（`procvision_algorithm_sdk/base.py:36-46`）
  - `execute(...) -> Dict[str, Any]`（`procvision_algorithm_sdk/base.py:48-58`）
- 可选钩子（默认空实现）：`setup/teardown/on_step_start/on_step_finish/reset`（`procvision_algorithm_sdk/base.py:17-30`）
- 调用顺序（Dev Runner）：
  - `setup → on_step_start → pre_execute → execute → on_step_finish → teardown`
  - 校验命令参考调用：`procvision_algorithm_sdk/cli.py:78-124`
  - 运行命令参考调用（适配器模式）：`procvision_algorithm_sdk/cli.py:499`
  - 运行命令参考调用（旧路径 legacy）：`procvision_algorithm_sdk/cli.py:164`
- `step_index` 约定：平台与 Dev Runner 均从 1 开始（本地运行 `--step` 默认为 1，`procvision_algorithm_sdk/cli.py:503-513`）。

## 钩子函数详解

- 名称与签名（定义位置 `procvision_algorithm_sdk/base.py:17-30`）

  - `setup(self) -> None`：算法实例级初始化；加载模型、缓存与句柄，设置 `self._model_version`。
  - `teardown(self) -> None`：释放资源；关闭句柄与缓存，确保无泄漏。
  - `on_step_start(self, step_index: int, session: Session, context: Dict[str, Any]) -> None`：步骤开始回调；记录上下文、复位计时与状态。
  - `on_step_finish(self, step_index: int, session: Session, result: Dict[str, Any]) -> None`：步骤结束回调；输出诊断、汇总耗时与指标。
  - `reset(self, session: Session) -> None`：流程级复位；清理会话内与算法内部的易变状态。
- 调用时机（Dev Runner）

  - validate：`setup → on_step_start(1) → pre_execute(1) → execute(1) → on_step_finish(1) → teardown`（`procvision_algorithm_sdk/cli.py:78-124`）
  - run：`setup → on_step_start(1) → pre_execute(1) → execute(1) → on_step_finish(1) → teardown`（`procvision_algorithm_sdk/cli.py:193-210`）
- 参数语义

  - `step_index`：当前步骤索引（平台与 Dev Runner 从 1 开始；本地运行可通过 `--step` 指定，默认 1）。
  - `session`：会话 KV 存储与只读上下文（`procvision_algorithm_sdk/session.py:19-36`）。
  - `context/result`：平台侧提供的步骤上下文与算法返回的执行结果，用于边界统计与诊断。
- 返回与异常

  - 所有钩子返回 `None`；异常不应中断流程，建议使用 `StructuredLogger.error` 记录并在后续 `execute` 给出 `status="ERROR"` 的清晰提示。
- 最佳实践

  - 幂等：钩子允许重复调用；`setup/teardown` 需正确处理重复初始化/释放。
  - 轻量化：`on_step_start/finish` 不应做重计算；重工作放在 `pre_execute/execute`。
  - 资源管理：统一在 `setup/teardown/reset` 管理模型与句柄；避免在 `execute` 中延迟加载。
  - 诊断输出：在钩子中通过 `Diagnostics.publish` 与 `StructuredLogger.info` 输出关键指标与事件。

## 返回结构规范

- get_info()
  - 必含：`name/version/description/supported_pids/steps`
  - `steps[].index` 建议从 1 开始；`params[].type ∈ {int,float,rect,enum,bool,string}`
- pre_execute(...)
  - 必含：`status ∈ {OK, ERROR}`
  - 可选：`message`、`debug`、`data.calibration_rects`
  - 禁止：`data.result_status/defect_rects`（仅在 execute 中给出业务判定）
- execute(...)
  - 必含：`status ∈ {OK, ERROR}`；当 `status=OK` 时必须包含 `data.result_status ∈ {OK, NG}`
  - 当 `result_status=NG`：需包含 `ng_reason` 与 `defect_rects ≤ 20`（`procvision_algorithm_sdk/cli.py:111-116`）
  - 可选：`position_rects/debug` 等业务辅助输出

## 会话与状态（Session）

- 构造：`Session(id: str, context: Optional[Dict[str, Any]] = None)`（`procvision_algorithm_sdk/session.py:5-10`）
- 只读属性：`id`（`procvision_algorithm_sdk/session.py:11-14`）、`context`（返回副本，`procvision_algorithm_sdk/session.py:15-18`）
- KV 存取：`get/set/delete/exists`（`procvision_algorithm_sdk/session.py:19-36`）
- `set` 值必须可 JSON 序列化，否则抛 `TypeError`（`procvision_algorithm_sdk/session.py:22-27`）

## 共享内存图像

- 读取：`read_image_from_shared_memory(shared_mem_id, image_meta)`（`procvision_algorithm_sdk/shared_memory.py:16-52`）
- 元信息要求：至少包含 `width/height/timestamp_ms/camera_id`；可选 `color_space ∈ {RGB,BGR}`
- 兼容性：同时支持字节数据（JPEG/PNG）与 `numpy.ndarray`（`uint8`，形状 `(H,W,3)`）；灰度会自动扩展为 3 通道；当 `image_meta.color_space=BGR` 时自动转换为 RGB（`procvision_algorithm_sdk/shared_memory.py:16-52`）
- 回退行为：读取失败或无数据返回形状 `(H,W,3)` 的零矩阵（`procvision_algorithm_sdk/shared_memory.py:49-52`）
- 开发/测试写入：
  - 字节写入：`dev_write_image_to_shared_memory(shared_mem_id, image_bytes)`（`procvision_algorithm_sdk/shared_memory.py:6-10`）
  - 数组写入：`write_image_array_to_shared_memory(shared_mem_id, image_array)`（`procvision_algorithm_sdk/shared_memory.py:12-14`）

```python
import numpy as np
from procvision_algorithm_sdk import write_image_array_to_shared_memory, read_image_from_shared_memory

shm_id = "dev-shm:demo"
# 模拟上位机输出的 RGB 三通道 uint8 数组
arr = np.zeros((240, 320, 3), dtype=np.uint8)
arr[0, 0] = np.array([10, 20, 30], dtype=np.uint8)
write_image_array_to_shared_memory(shm_id, arr)

image_meta = {"width": 320, "height": 240, "timestamp_ms": 0, "camera_id": "cam", "color_space": "RGB"}
img = read_image_from_shared_memory(shm_id, image_meta)
assert img.shape == (240, 320, 3)
```

## 结构化日志与诊断

- 结构化日志：`StructuredLogger.info/debug/error`（`procvision_algorithm_sdk/logger.py:17-24`）
  - 输出为单行 JSON，含 `level/timestamp_ms/message` 与自定义字段（`procvision_algorithm_sdk/logger.py:11-15`）
- 诊断聚合：`Diagnostics.publish/get`（`procvision_algorithm_sdk/diagnostics.py:8-12`）
  - 推荐将推理耗时、模型版本、关键指标放入 `debug` 与诊断集合，便于平台 UI 采集

## CLI 参考

- 程序名：`procvision-cli`（`pyproject.toml` 控制台脚本）
  - validate
  - 用法：`procvision-cli validate [project] [--manifest <path>] [--zip <path>] [--full] [--entry <module:Class>] [--legacy-validate] [--json]`
  - 行为：
    - `--full`（默认推荐）：通过适配器子进程执行完整握手与 `pre/execute`，返回通过/失败报告（`procvision_algorithm_sdk/cli.py:862-903`）
    - 旧路径：`--legacy-validate` 走本地导入与最小流程校验（`procvision_algorithm_sdk/cli.py:37-145`）
    - ZIP 校验：始终使用结构校验与 wheels 检查（`procvision_algorithm_sdk/cli.py:129-145`）
  - 输出：人类可读或完整 JSON（`procvision_algorithm_sdk/cli.py:147-161`）
  - 退出码：通过返回 0，否则 1（`procvision_algorithm_sdk/cli.py:645-651`）
- run
  - 用法：`procvision-cli run <project> --pid <pid> --image <path> [--step <index>] [--params <json>] [--entry <module:Class>] [--json]`
  - 行为（默认适配器子进程模式）：启动 `procvision_algorithm_sdk.adapter`，握手后写图片到共享内存，发送 `pre/execute` 两个 `call` 帧并读取 `result`，最后 `shutdown`（`procvision_algorithm_sdk/cli.py:499-553`）
  - 兼容开关：`--legacy-run` 使用旧的本地直接导入执行路径（`procvision_algorithm_sdk/cli.py:652-681`）
  - 输入校验与错误提示：项目/清单/图片/参数 JSON（`procvision_algorithm_sdk/cli.py:653-671`）
  - 输出：人类可读摘要或 JSON（`procvision_algorithm_sdk/cli.py:214-226, 579-584`）
  - 退出码：`execute.status == "OK"` 返回 0，否则 1（`procvision_algorithm_sdk/cli.py:680-681`）
- package
  - 用法：`procvision-cli package <project> [--output <zip>] [--requirements <path>] [--auto-freeze] [--wheels-platform <p>] [--python-version <v>] [--implementation <impl>] [--abi <abi>] [--skip-download]`
  - 行为：缺少 `requirements.txt` 时可自动生成（`pip freeze`），规范化 `requirements.sanitized.txt`，按平台下载 wheels，打包源码与 wheels（`procvision_algorithm_sdk/cli.py:228-326`）
  - 错误与提示：当 `pip download` 无匹配依赖时给出目标环境建议（`procvision_algorithm_sdk/cli.py:301-307`）
  - 成功输出 ZIP 路径与退出 0；失败打印消息并退出 1（`procvision_algorithm_sdk/cli.py:586-603`）
- init
  - 用法：`procvision-cli init <name> [-d|--dir <dir>] [--pids <p1,p2>] [-v|--version <ver>] [-e|--desc <text>]`
  - 行为：生成清单与入口包、写入环境缓存，入口代码包含待修改注释（`procvision_algorithm_sdk/cli.py:344-463, 604-611`）

## 依赖与打包

- 锁定依赖：`pip freeze > requirements.txt`
- 下载 wheels：`pip download -r requirements.sanitized.txt -d ./<project>/wheels --platform <p> --python-version <v> --implementation <impl> --abi <abi>`（`procvision_algorithm_sdk/cli.py:285-301`）
- 打包排除：`.venv/` 与源码树中的 `wheels/`（`procvision_algorithm_sdk/cli.py:311-326`）
- 输出命名：默认 `<name>-v<version>-offline.zip`（`procvision_algorithm_sdk/cli.py:242-244`）

## 约束与最佳实践

- `supported_pids` 一致（清单与 `get_info`）并建议 ≤ 20
- `defect_rects ≤ 20`；坐标在图像范围内；`message < 100` 字符、`ng_reason < 50` 字符（`procvision_algorithm_sdk/cli.py:113-116`）
- `image_meta` 至少含 `width/height/timestamp_ms/camera_id`
- 日志与诊断统一走结构化格式，便于平台采集与排查

## 示例速览

- 完整示例入口：`algorithm-example/algorithm_example/main.py:8-127`
- 清单示例：`algorithm-example/manifest.json:1-25`

## 自检与测试

- 单元测试覆盖：
  - CLI 验证与运行（`tests/test_cli.py:6-17`，`tests/test_cli_validate.py:7-10`）
  - 共享内存读图回退（`tests/test_shared_memory.py:6-13`）
  - Session KV 操作与序列化约束（`tests/test_session.py:6-21`）
  - 基类最小实现流程（`tests/test_base_algo.py:6-62`）

## 常见问题与处理建议

- PID 不一致：统一 `manifest.json.supported_pids` 与 `get_info().supported_pids`（校验项见 `procvision_algorithm_sdk/cli.py:86-89`）
- 返回结构错误：`pre_execute` 不含业务判定；业务结果仅在 `execute.data.result_status`
- wheels 不匹配：在目标 Python 版本与 ABI 环境内执行 `pip freeze`，以生成兼容的 `requirements.txt`（提示逻辑见 `procvision_algorithm_sdk/cli.py:305-307`）
- 图像尺寸异常：确保 `image_meta.width/height` 为正整数，读图失败会回退零矩阵（`procvision_algorithm_sdk/shared_memory.py:19-33`）

## 交付与验收

- 使用 `procvision-cli package` 构建离线 ZIP，并使用 `procvision-cli validate --zip` 进行结构校验
- 将诊断指标与关键耗时放入 `debug/Diagnostics`，并输出结构化日志便于平台侧采集

## 包导出总览

- 直接导入：`from procvision_algorithm_sdk import BaseAlgorithm, Session, read_image_from_shared_memory, StructuredLogger, Diagnostics`（`procvision_algorithm_sdk/__init__.py:1-18`）

本教程确保算法项目在标准化流程下快速上线，并在后续迭代中保持接口与交付一致性与可运维性。

## 完整案例 Demo（附）

- manifest.json

```
{
  "name": "full_demo_inspection",
  "version": "1.0.0",
  "entry_point": "full_demo_inspection.main:FullDemoAlgorithm",
  "description": "完整演示：定位/检测/复核，覆盖所有接口与钩子",
  "supported_pids": ["D01", "D02"],
  "steps": [
    {
      "index": 1,
      "name": "定位",
      "params": [
        {"key": "roi", "type": "rect", "required": true, "description": "定位区域"},
        {"key": "loc_threshold", "type": "float", "default": 0.6, "min": 0.0, "max": 1.0}
      ]
    },
    {
      "index": 2,
      "name": "检测",
      "params": [
        {"key": "det_threshold", "type": "float", "default": 0.7, "min": 0.0, "max": 1.0},
        {"key": "mode", "type": "enum", "choices": ["fast", "accurate"], "default": "fast"}
      ]
    },
    {
      "index": 3,
      "name": "复核",
      "params": [
        {"key": "enable_review", "type": "bool", "default": true}
      ]
    }
  ]
}
```

- main.py

```
from typing import Any, Dict, List
import time

from procvision_algorithm_sdk import BaseAlgorithm, Session, read_image_from_shared_memory, StructuredLogger, Diagnostics


class FullDemoAlgorithm(BaseAlgorithm):
    def __init__(self) -> None:
        super().__init__()
        self._supported_pids = ["D01", "D02"]

    def setup(self) -> None:
        self._model_version = "full_demo_v1"
        self.logger.info("setup", model_version=self._model_version)

    def teardown(self) -> None:
        self.logger.info("teardown")

    def on_step_start(self, step_index: int, session: Session, context: Dict[str, Any]) -> None:
        session.set("step_start_ms", int(time.time() * 1000))
        self.logger.info("on_step_start", step_index=step_index)

    def on_step_finish(self, step_index: int, session: Session, result: Dict[str, Any]) -> None:
        start_ms = session.get("step_start_ms")
        if isinstance(start_ms, (int, float)):
            latency_ms = int(time.time() * 1000) - int(start_ms)
            self.diagnostics.publish("step_latency_ms", latency_ms)
            self.logger.info("on_step_finish", step_index=step_index, latency_ms=latency_ms)

    def reset(self, session: Session) -> None:
        session.delete("step_start_ms")

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": "full_demo_inspection",
            "version": "1.0.0",
            "description": "完整演示：定位/检测/复核",
            "supported_pids": self._supported_pids,
            "steps": [
                {"index": 1, "name": "定位", "params": [
                    {"key": "roi", "type": "rect", "required": True, "description": "定位区域"},
                    {"key": "loc_threshold", "type": "float", "default": 0.6, "min": 0.0, "max": 1.0}
                ]},
                {"index": 2, "name": "检测", "params": [
                    {"key": "det_threshold", "type": "float", "default": 0.7, "min": 0.0, "max": 1.0},
                    {"key": "mode", "type": "enum", "choices": ["fast", "accurate"], "default": "fast"}
                ]},
                {"index": 3, "name": "复核", "params": [
                    {"key": "enable_review", "type": "bool", "default": True}
                ]}
            ]
        }

    def pre_execute(
        self,
        step_index: int,
        pid: str,
        session: Session,
        user_params: Dict[str, Any],
        shared_mem_id: str,
        image_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        if pid not in self._supported_pids:
            return {"status": "ERROR", "message": f"不支持的产品型号: {pid}", "error_code": "1001"}
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        if img is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}
        w = int(image_meta.get("width", 640))
        h = int(image_meta.get("height", 480))
        rect = {"x": max(0, w//4), "y": max(0, h//4), "width": max(10, w//3), "height": max(10, h//3), "label": "roi"}
        return {"status": "OK", "message": "准备就绪", "data": {"calibration_rects": [rect]}, "debug": {"latency_ms": 0.0}}

    def execute(
        self,
        step_index: int,
        pid: str,
        session: Session,
        user_params: Dict[str, Any],
        shared_mem_id: str,
        image_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        start = time.time()
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        if img is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}
        threshold = float(user_params.get("det_threshold", 0.7))
        is_ng = threshold < 0.65
        latency_ms = (time.time() - start) * 1000.0
        dbg = {"latency_ms": latency_ms, "model_version": self._model_version, **self.diagnostics.get()}
        if is_ng:
            defect = {"x": 10, "y": 20, "width": 50, "height": 30, "label": "defect", "score": 0.8}
            return {"status": "OK", "data": {"result_status": "NG", "ng_reason": "置信度阈值偏低", "defect_rects": [defect], "debug": dbg}}
        pos = {"x": 100, "y": 120, "width": 200, "height": 150, "label": "position"}
        return {"status": "OK", "data": {"result_status": "OK", "position_rects": [pos], "debug": dbg}}
```

- 使用命令
  - 初始化：`procvision-cli init full_demo_inspection --pids D01,D02 -v 1.0.0 -d ./full_demo_inspection`
  - 替换入口包为以上 `main.py`，更新 `manifest.json` 为上述示例结构
  - 校验：`procvision-cli validate ./full_demo_inspection`
  - 运行：`procvision-cli run ./full_demo_inspection --pid D01 --image ./test.jpg --params "{\"det_threshold\":0.7}" --json`
  - 说明：默认以适配器子进程通信运行；如需旧路径加 `--legacy-run`
  - 打包：`procvision-cli package ./full_demo_inspection`
