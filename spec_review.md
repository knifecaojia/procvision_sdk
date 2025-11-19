# ProcVision算法SDK规范评审

## 1. 整体评估
- 当前项目目标是先实现“业务流程与算法的完全解耦”，平台负责流程编排与UI，算法侧仅按SDK约定实现检测逻辑。SPEC给出的离线交付、manifest入口、依赖封装等要求与这一目标匹配。
- 结合最新约束：**单工位、单镜头、单算法串行**，算法NG后由操作员在UI中手动选择“重新检测或人工跳过”。因此SDK首要任务是保证 **0→1 启动**——接口要清晰、依赖要可离线部署、错误提示要能驱动上述人工流程。
- 即便短期内没有多工位、多镜头和跨站点，也建议保留一定扩展点（输入字段、生命周期钩子、资源申明），避免后续产品升级时被现有抽象束缚。
- 当前SDK只暴露 `get_info` / `pre_execute` / `execute`，未对输入输出schema、错误类型、资源引用做约束。在0-1阶段，这会带来“不同算法对重试/跳过的反馈不一致”的集成问题，影响首批项目落地效率。

## 2. 0-1阶段的首要需求
- **[must] 接口契约清晰**：对 `get_info` / `pre_execute` / `execute` 的输入输出字段做最小schema约束（例如 `status`, `ng_reason`, `suggest_action`），确保平台能根据返回值驱动“重新检测/人工跳过”的UI。
- **[must] 错误与重试约定**：规定可恢复错误（平台可提示“重拍”）与不可恢复错误（提示“人工跳过”）的表达方式，可以是显式的 `error_type` 字段或SDK内的标准异常。
- **[must] 离线交付完整**：算法包需包含 wheels、模型、配置、manifest 以及一份演示数据/脚本，保证在目标环境一次性启动，降低0-1期的集成沟通成本。
- **[must] 最小诊断能力**：SDK应要求算法输出关键日志或结构化调试信息（检测耗时、主阈值、图片ID），方便排查NG原因。
- **可配置的步骤信息**：即使只有单步骤，也建议 `get_info` 的 `steps` 字段可承载参数描述，方便UI在不同产品间调整文案、阈值等。

## 3. 算法抽象的改进建议
1. **扩展接口契约**
   - 为 `pre_execute` 与 `execute` 增加输入/输出 Pydantic schema 或 Protocol，并对关键字段做约定说明：`status`（OK/NG/ERROR，用于UI展示结果）、`ng_reason`（简要NG原因文本）、`suggest_action`（enum：`retry`/`skip`/`abort`，引导操作员流程），`error_type`（可恢复/不可恢复），`camera_id`/`station_id`/`timestamp`（为未来扩展留位），`user_params`（从平台配置下发的可调参数）。
   - **[must] 图片传输（共享内存）**：统一采用共享内存传递图像，不走JSON内嵌或落盘文件。平台向算法传递 `shared_mem_id` + `image_meta`（分辨率、格式、时间戳），算法使用SDK提供的共享内存读取函数获取 `np.ndarray`。严禁在JSON中携带整幅图片（base64等），避免粘包与性能问题。

   - **什么是“Pydantic schema or Protocol”**  
     - Pydantic schema：用 Pydantic 模型定义字段、类型、默认值与校验规则，例如  
       `class ExecuteInput(BaseModel): step_index: int; shared_mem_id: str; image_meta: dict; user_params: dict`。好处：自动校验与清晰文档；字段缺失或类型错误时抛结构化异常，便于定位。  
     - Protocol（typing.Protocol）：仅用类型提示描述接口形状，不做运行时校验，例如  
       `class ExecuteInput(Protocol): step_index: int; shared_mem_id: str; image_meta: Dict[str, Any]; user_params: Dict[str, Any]`。好处：零运行时依赖，最轻量。  
     - 选择建议：0-1阶段优先 Pydantic（或 dataclass+手工校验）确保字段一致性；如担心依赖或性能，可先用 Protocol 作静态规范，后续再切换 Pydantic。
2. **生命周期管理**
   - **阶段划分**：`setup()`（算法实例启动时一次）、`teardown()`（退出前一次）、`on_step_start()` / `on_step_finish()`（每次执行的前后），以及可选的 `reset()`（重试前清理状态）。
   - **职责示例**：
     - `setup()`：加载模型/权重、建立共享内存或显存池、读取静态配置与标定数据，在此阶段完成所有重量级初始化。
     - `on_step_start(step_index, context)`：清理上一次的临时数据，记录开始时间、相机/工位元信息，校验 `shared_mem_id` 是否有效。
     - `execute(...)`：专注业务逻辑，依赖前面准备好的资源，不再重复初始化。
     - `on_step_finish(step_index, result)`：统计耗时、写结构化日志，清空本次缓存，必要时将状态写回 `StateStore`。
     - `reset()`（可选）：发生可恢复错误或用户触发“重新检测”时，释放/重建与当前步骤相关的临时资源，避免脏数据影响下一次执行。
     - `teardown()`：释放模型、显存、共享内存、后台线程/连接等资源，防止实例销毁后泄漏。
   - **平台配合**：平台在调用链中显式触发这些钩子，并在异常/人工中断时调用 `reset()` 或 `teardown()`，确保资源被正确回收。需要文档化线程安全要求（单线程或并发）、初始化策略（懒加载/预加载），避免团队各自实现导致行为不一致。
3. **状态与缓存接口**
   - 平台应在一次完整工艺（一次产品流转）的调用链中提供 `Session` 对象：`Session.id` 唯一标识该工件，包含 `state_store` / `context` 字段，可读写JSON可序列化的数据。
   - `Session.state_store` 由SDK托管（可基于内存或本地数据库），保证同一Session内各步骤共享，Session结束或手动 `reset()` 时自动清理；不同Session之间严格隔离，避免并发工件互相污染。
   - 算法在 `on_step_start` / `execute` 内通过 `session.get("template")`、`session.set("pose", value)` 等API共享数据，不需要直接访问文件系统。平台同时负责在重新检测或人工跳过时调用 `session.reset()`，确保状态一致。
4. **错误、日志与诊断**
   - **异常分类**：SDK需定义基础异常类型，例如 `RecoverableError`（算法建议重新检测）、`FatalError`（必须人工跳过或停止），并允许 `execute` 返回 `{"status":"ERROR","error_type":"recoverable","suggest_action":"retry","message":"光源未开启"}` 等结构化字段，平台据此决定UI提示与重试策略。
   - **日志API**：SDK提供 `logger` 封装，默认输出结构化JSON日志（字段含 `timestamp`, `session_id`, `step_index`, `status`, `latency_ms`, `trace_id` 等）。算法禁止直接 `print`，统一通过 `logger.info/debug/error` 记录。日志写到独立文件或stderr，供平台采集。
   - **诊断数据**：在 `on_step_finish` 或异常路径中，算法可通过 `diagnostics.publish("key", value)` 上报关键指标（例如 `confidence`, `brightness`, `defect_count`）和临时调试图（路径或共享内存ID），平台可在UI或日志中呈现，帮助定位NG原因。
   - **超时与心跳**：SDK runner 应在调用期间发心跳或监控超时，当算法超过配置时限未响应，自动抛 `TimeoutError` 并杀掉子进程，防止整条产线阻塞。
5. **可配置流程**
   - 在 `get_info()` 的 `steps` 内为每个步骤增加 `params/schema` 字段，描述可调参数：`key`、`type`（int/float/bool/string/enum/rect）、`default`、`required`、`min/max` 或 `choices`、`unit`、`description`。
   - 平台 UI 依据 schema 自动渲染输入控件并做前端校验；运行时将用户配置注入 `user_params`（或 `step_config`）传入 `pre_execute/execute`，算法直接读取，无需硬编码界面。
   - SDK 在调用前做一层校验（依据 schema），不合规直接返回结构化错误，避免算法内部再做重复校验。
   - 示例（简化）：
     ```json
     {
       "index": 1,
       "name": "螺丝检测",
       "params": [
         {"key": "threshold", "type": "float", "default": 0.7, "min": 0.5, "max": 0.9, "description": "置信度阈值"},
         {"key": "roi", "type": "rect", "required": true, "description": "检测区域"},
         {"key": "mode", "type": "enum", "choices": ["fast", "accurate"], "default": "fast"}
       ]
     }
     ```

## 4. 交付与部署流程优化
- **依赖锁定**：在 `requirements.txt` 之外生成 `pip-tools` 的锁文件或 hash 校验 (PEP 665) 以防依赖被替换。
- **模型与静态资产**：约定 `assets/` 目录和 `assets_manifest.json`（包含文件哈希、版本、加载路径）。
- **包级一致性校验**：要求 zip 顶层附带 `CHECKSUMS` 或 `manifest.sig`（平台签名）用于部署前验证。
- **自动化验收**：提供 `sdk validate <zip>` CLI，执行依赖完整性检查、接口自检、演示数据跑通。
- **步骤超时控制**：在 SDK runner 层提供可配置的超时设置（例如 per-step 超时时间），超时后由平台决定重试或人工处理；不再通过 manifest 声明静态资源需求。

## 5. 结论
在“单工位、单镜头、人工可重试”的当前场景下，SPEC 已具备0-1启动所需的离线交付框架，但仍需补足接口契约、错误约定与最小诊断能力，才能顺利实现业务流程与算法模块的解耦。通过前述增强（结构化接口、基础状态管理、资产与验收规范），平台既能保证首次上线成功。
