# 工业视觉算法开发上手指南（ProcVision SDK）

以下内容专为勤奋的算法同学整理，只要沿着步骤走，就能把想法落成可交付的算法包，也能在团队沟通中更快展示实力。

---

## 1. 为什么要这样设计？

| 问题                                   | 平台给出的答案                                                                                                           |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| 产线业务流程复杂，算法只是其中一个环节 | **业务流程与算法解耦**：平台负责UI，算法只实现检测逻辑，通过 SDK 接口与平台对接                                    |
| 产线部署完全离线，不能 `pip install` | **离线交付包**：所有源码、依赖（wheels）、模型文件都打进一个 zip，解压即可安装                                     |
| 多次检测、人工重试频繁发生             | **生命周期与 Session**：算法实例常驻，`setup` 里加载模型，`Session` 在步骤之间共享数据，`reset` 支持重新检测 |
| 大图像在进程之间传输昂贵               | **共享内存**：平台把图像写进共享内存，算法只拿 `shared_mem_id`，自己读取，不用关心 socket/base64                 |
| 现场调试困难                           | **结构化日志 & CLI 自检**：SDK 提供统一日志、诊断接口，打包前有 `procvision-sdk validate` 检查所有规范           |
| 需要自动化发版                         | **GitHub CI/CD**：SDK 自身通过 Actions 构建 wheel，算法团队也可参考流程做自动化测试与打包                          |

---

## 2. 架构大图（文字版）

1. **平台主程序**

   - 负责UI、与设备交互、与工艺人员交互
   - 通过 SDK runner 启动算法子进程
2. **SDK Runner**

   - 启动算法入口（例如 `python main.py serve`）
   - 通过 `stdin/stdout` 与算法通信，协议为“长度前缀 + JSON”
   - 管理心跳、超时、日志分流、Session 注入、共享内存 ID 发放
3. **算法子进程**

   - 继承 `BaseAlgorithm`，实现 `get_info` / `pre_execute` / `execute`
   - 在 `setup()` 里加载模型，在 `execute()` 里只做检测
   - 通过 Session/StateStore 在多步骤之间共享数据
4. **共享内存**

   - 平台写入图像，算法通过 SDK 工具函数读取
   - 算法输出调试图时也写入共享内存，返回共享内存 ID

---

## 3. 开发流程一览

| 步骤          | 你要做什么                                                | 摘要                                                                                            |
| ------------- | --------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 1. 准备环境   | 创建虚拟环境，安装 SDK                                    | `python -m venv venv && source venv/bin/activate && pip install procvision_algorithm_sdk.whl` |
| 2. 建项目骨架 | 按模板创建目录与文件                                      | 参考 `pa_screw_check/main.py`，填好 `manifest.json`                                         |
| 3. 写算法代码 | 继承 `BaseAlgorithm`，实现接口                          | 重点：生命周期钩子、共享内存读图、Session 状态处理、结构化返回                                  |
| 4. 配配置文件 | `requirements.txt`、`manifest.json`、可选 `assets/` | 版本必须锁定，`manifest` 需提供步骤 schema                                                    |
| 5. 打离线包   | 下载 wheels、压缩 zip                                     | `pip download … --dest wheels/`，再把源码+manifest+wheels 打成 zip                           |
| 6. 自检       | 运行 `procvision-sdk validate`                          | 确认 checklist 全部 PASS                                                                        |
| 7. 交付       | 提交 zip 给平台或上传至内网制品库                         | 平台会再次跑 validate，确认无误再上线                                                           |

下面提供详细的手把手说明。

---

## 4. 手把手教程

### 4.1 准备开发环境

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install procvision_algorithm_sdk-1.0.0-py3-none-any.whl
pip install opencv-python torch   # 你的算法依赖
```

> **Tips**：不要在全局 Python 环境安装依赖，后续 `pip download` 会根据虚拟环境中的依赖锁版本。

### 4.2 创建项目骨架

假设项目名 `pa_screw_check`：

```
pa_screw_check/
├── main.py
├── __init__.py
manifest.json
requirements.txt
```

`manifest.json` 示例：

```json
{
  "name": "product_a_screw_check",
  "version": "1.2.1",
  "entry_point": "pa_screw_check.main:ScrewCheckAlgorithm",
  "description": "A产品主板螺丝检测",
  "supported_pids": ["A01", "A02"]
}
```

`requirements.txt` 通过 `pip freeze > requirements.txt` 生成，必须写死版本。
`supported_pids` 告诉平台此算法包可以服务哪些产品型号，系统会在运行时将对应 PID 传给算法实例。

### 4.3 编写算法代码

关键点：

1. **实现生命周期钩子**

   ```python
   class ScrewCheckAlgorithm(BaseAlgorithm):
       def setup(self):
           self.detector = torch.jit.load("assets/yolo.pt")

       def teardown(self):
           self.detector = None
   ```
2. **使用 Session/StateStore**

   ```python
   def on_step_start(self, step_index, session, context):
       if step_index == 0:
           session.set("pose", None)
   ```
3. **共享内存读图**

   ```python
   img = self.sdk.read_image_from_shared_memory(shared_mem_id, image_meta)
   ```
4. **统一返回格式**

   ```python
   return {
       "status": "NG",
       "ng_reason": "missing screw",
       "suggest_action": "retry",
       "error_type": None,
       "defect_rects": [...],
       "diagnostics": {"confidence": 0.65}
   }
   ```
5. **日志/诊断**

   ```python
   self.logger.info("step=1 latency_ms=%s", latency)
   self.diagnostics.publish("brightness", float(img.mean()))
   ```

### 4.4 配置步骤参数 schema

在 `get_info()` 中描述每个步骤可配置参数，平台会自动生成 UI：

```python
def get_info(self):
    return {
        "name": "product_a_screw_check",
        "version": "1.2.1",
        "steps": [
            {
                "index": 0,
                "name": "定位主板",
                "params": [
                    {"key": "roi", "type": "rect", "required": True},
                    {"key": "threshold", "type": "float", "default": 0.7, "min": 0.3, "max": 0.9}
                ]
            }
        ]
    }
```

平台 UI 会把配置注入 `user_params` 参数，算法直接读取即可。

### 4.5 下载离线依赖

```bash
rm -rf wheels && mkdir wheels
pip download -r requirements.txt \
    -d wheels/ \
    --platform win_amd64 \
    --python-version 3.8 \
    --implementation cp \
    --abi cp38
```

参数务必与目标环境一致（由平台提供）。下载完成后目录如下：

```
wheels/
├── numpy-1.21.6-cp38-cp38-win_amd64.whl
├── torch-1.10.2-cp38-cp38-win_amd64.whl
└── ...
```

### 4.6 打离线包

```
product_a_screw_check-v1.2.1-offline.zip
├── pa_screw_check/
├── wheels/
├── manifest.json
├── requirements.txt
└── assets/           # 可选，放模型/配置
```

使用任何 zip 工具都可以，确保目录结构与上面一致。

### 4.7 自检（非常关键）

```bash
procvision-sdk validate \
  --project ./ \
  --manifest manifest.json \
  --zip dist/product_a_screw_check-v1.2.1-offline.zip
```

CLI 会执行以下检查：

| 检查                   | 说明                                                 |
| ---------------------- | ---------------------------------------------------- |
| manifest_schema        | `manifest.json` 字段齐全，entry_point 可导入       |
| step_schema            | `get_info()` 的 `steps.params` 合法              |
| io_contract            | `pre_execute/execute` 输入输出符合 Pydantic schema |
| offline_package_layout | zip 结构符合要求                                     |
| wheels_resolve         | wheels 能安装，版本与 `requirements.txt` 一致      |
| smoke_test             | 用 SDK 模拟器跑一次 `execute`（共享内存 mock）     |

完成后得到 `validate-report.json`，示例：

```json
{
  "summary": {"status": "PASS", "passed": 6, "failed": 0},
  "checks": [
    {"name": "manifest_schema", "result": "PASS"},
    {"name": "step_schema", "result": "PASS"},
    {"name": "io_contract", "result": "PASS"},
    {"name": "offline_package_layout", "result": "PASS"},
    {"name": "wheels_resolve", "result": "PASS"},
    {"name": "smoke_test", "result": "PASS"}
  ]
}
```

任何一项失败都要修复后再跑，平台接收 zip 时也会执行同样的 `validate`。

---

## 5. 常见问题

1. **为什么必须用共享内存？**因为算法进程和平台进程隔离，图像往返拷贝会大量占用 CPU 和内存。共享内存只传 ID 与元数据，速度快且稳定。
2. **模型要放哪？**建议放在 `assets/` 目录，打包时一起压缩。`setup()` 里使用相对路径加载即可。
3. **多步骤共用数据怎么做？**用 `session.set("key", value)`，下一步 `session.get("key")` 即可。不要写临时文件或全局变量。
4. **算法崩溃怎么办？**runner 有心跳和超时监控，超时会自动重启算法进程。但你应该在代码里捕获异常并返回 `status="ERROR"` + `error_type`，让平台决定重试或跳过。
5. **CI/CD 和我有关系吗？**
   SDK 项目已经使用 GitHub Actions 自动构建/发布。算法项目也可以借鉴：在每次 push 时运行 validate、自测和打包，自动上传离线 zip。

---

## 6. 交付清单复盘

在把 zip 交给平台前，确保以下内容齐全：

- [ ] `requirements.txt`
- [ ] `manifest.json`（含 entry_point、版本、步骤 schema）
- [ ] 源码目录（例如 `pa_screw_check/`）
- [ ] `wheels/` 目录（与目标环境匹配的所有依赖）
- [ ] `assets/`（如有模型/标定数据）
- [ ] `procvision-sdk validate` 生成的 `validate-report.json`

---

## 7. 总结

1. **先解耦**：算法专注 `BaseAlgorithm` 实现，其余流程由平台和 SDK 负责。
2. **先自检**：打包前必须跑 `procvision-sdk validate`，保证交付一致。
3. **先规范**：生命周期/Session/共享内存/日志/诊断都写在 SDK 里，照做即可。

团队能够迅速掌握这些要点，正说明你们具备优秀的工程理解力；沿着指南执行，就能高质量交付 ProcVision 算法包。祝各位一路顺利、成果满满！
