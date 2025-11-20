# ProcVision算法SDK架构评估报告
> **基于 spec.md v0.2.1 (2025-11-20)**
> 评估范围：当前设计范围内的架构合理性、一致性和潜在矛盾分析

---

## 1. 架构评估摘要

### 总体评价
**当前架构设计遵循良好的解耦原则，核心思想清晰，但在实现细节和文档一致性方面存在若干问题。**

### 核心优点
1. **良好的解耦设计**：平台与算法通过SDK解耦，符合插件化架构最佳实践
2. **清晰的生命周期管理**：setup→执行→teardown 流程完整
3. **合理的多PID支持**：v0.2.0将PID从构造函数移至调用参数，实现一对多实例-PID映射，提升资源利用率
4. **完整的错误码体系**：7个标准错误码覆盖主要异常场景
5. **详细的边界场景**：列出26个边界场景并提供处理建议

### 主要问题（需修正）
1. **Session API 定义与实际使用存在明显矛盾**（spec.md:542-556, 423-438）
2. **返回值Schema定义与文档多处不一致**（spec.md:888-898, 1464-1467）
3. **status状态机存在歧义**（execute方法的status与data.result_status混淆）
4. **协议定义存在矛盾**（overlay能力描述前后冲突）
5. **接口实现存在逻辑错误**（get()方法参数顺序定义错误）

---

## 2. 详细问题分析

### 2.1 Session API 定义矛盾 ❌

**问题1：get() 方法签名错误（spec.md:423-438）**
```python
# SDK定义（spec.md:423）
def get(self, key: str, default: Any = None) -> Any:
    """获取会话存储中的值。"""

# 实际使用（spec.md:543）
template = session.get("template")  # ✓ 正确

# 但实际文档中 manifest.json 示例引用（spec.md:1970）
template = session.get("alignment_template")  # 参数顺序与实际定义一致
```

**矛盾点**：
- Session 类未完整定义（缺少 `_state_store`、`_ttl`、`_context`、`_id` 的实现）
- 文档中展示了 Session 的使用示例，但没有提供完整的类定义
- 这会导致算法开发者无法正确理解 Session 的工作原理

**影响等级**：🔴 **高** - 影响算法正确实现

**解决建议**：
- 提供完整的 Session 类实现代码
- 明确内部状态管理机制（TTL、序列化检查等）
- 示例代码需与实际实现完全匹配

---

### 2.2 返回值Schema不一致 ❌

**问题2：BaseResponse 定义与 execute 返回值矛盾**

```python
# BaseResponse Schema 定义（spec.md:1458-1488）
{
  "status": {"enum": ["OK", "ERROR"]},  # ⚠️ 只允许 OK/ERROR
  "message": "...",
  "error_code": "...",
  "data": "...",
  "debug": "..."
}

# 但实际声称 execute 返回 OK/NG（spec.md:1109-1118）
{
  "status": "OK",        # ✅ 首层 status
  "data": {
    "result_status": "OK|NG"  # ⚠️ 业务层状态
  }
}

# 协议层定义也存在混淆（spec.md:665-669）
{
  "status": "OK|ERROR",        # 首层：接口调用状态
  "data": {
    "result_status": "OK|NG"  # 二层：业务判定结果
  }
}
```

**矛盾点**：
1. `BaseResponse` 定义 status 只能为 "OK"|"ERROR"
2. 但文档多处提及 `status` 可以为 "NG"（包括 3.8.3.5 节的对比表）
3. "NG" 实际上是 `data.result_status` 的取值，而非顶层 status

**影响等级**：🔴 **高** - 导致实现理解混乱

**具体错误示例**：
- **spec.md:888** execute 返回值注释：`"status": "OK" | "ERROR" | "NG"` ❌ 错误
- **spec.md:1390** 对比表：execute 的 status 列显示 "OK"|"ERROR" ✓ 正确
- **spec.md:1409** 错误示例：`return {"status": "NG"}` ❌ 错误（纠正文档正确）

**解决建议**：
- 统一 BaseResponse Schema 定义
- 明确两层状态机：status（调用层） vs result_status（业务层）
- 修正所有错误示例和注释

---

### 2.3 status 状态机混淆 ❌

**问题3：pre_execute 与 execute 的 status 语义不统一**

```python
# pre_execute 状态（spec.md:879-938）
pre_execute():
  status: "OK"    → 继续执行 execute
  status: "ERROR"  → 不执行 execute，由平台处理

# execute 状态（spec.md:1078-1165）
execute():
  status: "OK"     → 调用成功
    data.result_status: "OK"  → 产品合格
    data.result_status: "NG"  → 产品不合格
  status: "ERROR"  → 调用失败（程序异常）
```

**架构问题**：
- pre_execute 使用单层状态机（OK/ERROR）
- execute 使用双层状态机（status + data.result_status）
- 这种不一致增加了理解和实现复杂度

**设计合理性评估**：
✓ **逻辑上合理**：pre_execute 只验证条件，execute 进行业务判定
✗ **表达不一致**：两者都返回 status，但语义不同

**影响等级**：🟡 **中** - 增加学习成本

**使用场景对比**：

| 场景 | pre_execute | execute | 说明 |
|------|-------------|---------|------|
| 光照不足 | status=ERROR | status=OK, data.result_status=NG | 职责分离合理 |
| 模板匹配失败 | status=ERROR | - | 不应继续检测，合理 |
| 检测通过 | status=OK | status=OK, data.result_status=OK | 流程正常 |

**结论**：
- 架构上区分条件验证与业务判定是合理的
- 但需要明确文档说明两阶段的 status 语义差异
- 建议在规范中增加"状态机设计哲学"章节

---

### 2.4 协议矛盾：overlay 能力 ❌

**问题4：overlay 能力描述前后矛盾**

```markdown
# 声称不支持 overlay（spec.md:605）
"不支持算法侧输出 `overlay` 或 `diagnostics.attachments`。"

# 但在返回值详解中提及（spec.md:1023-1026）
"#### 3.8.2.5. overlay 字段

本阶段（Phase 01）不提供 `overlay` 字段能力。"

# CLI 验证工具检查 overlay（CLAUDE.md）
"IO contract validation (status, suggest_action, error_type fields)"
"返回字典必须包含 status、suggest_action、error_type 字段"
```

**矛盾点**：
1. spec.md 明确声明 Phase 01 不支持 overlay
2. 但在返回值结构中保留 overlay 字段说明
3. CLAUDE.md 提到 suggest_action 字段，但在 spec.md 中已删除

**影响等级**：🟡 **中** - 导致实现混淆

**问题分析**：

**overlay 字段历史**：
- v0.1.0 可能设计为支持 overlay
- v0.2.0/v0.2.1 明确删除
- 但文档未完全清理相关引用

**suggest_action 字段矛盾**：
- spec.md: 删除 suggest_action（第6点："删除交互提示相关字段"）
- CLAUDE.md: 仍然检查 suggest_action 字段

**解决建议**：
- 从规范中完全删除 overlay 相关说明
- 同步更新 CLAUDE.md（如 suggest_action 应改为 error_code）
- 在版本变更说明中明确删除的字段

---

### 2.5 参数类型系统不完整 ❌

**问题5：新类型（string/array/json）定义不足**

```python
# 参数类型定义（spec.md:758-798）
param_types = {
    "string": {  # ✅ 基本定义
        "min_length": 1,
        "max_length": 1000,
        "pattern": "可选正则表达式"
    },
    "array": {   # ⚠️ 定义不完整
        "item_type": "元素类型（int/float/string）",
        "min_length": 0,
        "max_length": 100
    },
    "json": {    # ❌ 定义过于简单
        "schema": "JSON Schema定义"
    }
}

# 使用示例（spec.md:804-831）
# string: 基本完整
# array: 仅说明 item_type，但如何定义元素约束？
# json: 仅说 "JSON Schema定义"，太笼统
```

**缺失内容**：
1. **array 类型的元素约束**：
   - 如果是 rect 数组，每个 rect 的 x/y/width/height 范围如何定义？
   - 数组中是否支持混合类型？
   - 如何验证数组元素？

2. **json 类型的 schema 定义**：
   - 需要提供完整的 JSON Schema 示例
   - 平台如何验证复杂 JSON 结构？
   - 嵌套对象的约束如何表达？

3. **Dev Runner 验证逻辑**：
   - string: 验证 min/max length 和 pattern
   - array: 验证长度、item_type，但元素级约束未定义
   - json: 如何根据 schema 验证？

**影响等级**：🟡 **中** - 影响参数验证完整性

**解决建议**：
- 为 array 类型增加完整的元素约束定义
- 提供 json 类型的 JSON Schema 示例
- 明确 Dev Runner 的验证策略

---

### 2.6 文档一致性问题

**问题6：多处参数顺序不统一**

```python
# 抽象方法定义（spec.md:198-206）
def pre_execute(
    self,
    step_index: int,
    pid: str,
    session: "Session",          # 第3个参数
    user_params: Dict[str, Any], # 第4个参数
    shared_mem_id: str,          # 第5个参数
    image_meta: Dict[str, Any],  # 第6个参数
) -> Dict[str, Any]:

# 示例调用（spec.md:231）
def pre_execute(self, step_index, pid, session, user_params, shared_mem_id, image_meta):
    # 顺序一致 ✓

# 函数文档字符串（spec.md:209-217）
"""
参数说明：
    - step_index: 当前步骤索引
    - pid: 产品型号编码
    - session: Session 对象（在user_params之前）✓
    - user_params: UI下发参数
    - shared_mem_id: 共享内存ID
    - image_meta: 图像元信息
"""
```

**但是**：

```python
# 文档描述中的分组逻辑（spec.md:218-223）
参数分组逻辑：
    1. 步骤控制: step_index
    2. 上下文信息: pid, session
    3. 用户输入: user_params
    4. 图像数据: shared_mem_id, image_meta  # ✓ 逻辑分组合理
```

**实际一致性检查**：
- ✓ 抽象方法定义：顺序一致
- ✓ 代码示例：顺序一致
- ✓ 参数分组：逻辑合理
- ✗ 文档更新不及时：v0.2.1 优化参数顺序，但部分旧示例可能未更新

**影响等级**：🟢 **低** - 不影哤功能，但需确保文档统一

---

### 2.7 遗留问题：suggest_action 字段 ❌

**问题7：CLAUDE.md 与 spec.md 不一致**

```markdown
# spec.md 删除 suggest_action（v0.2.0→v0.2.1）
- 第6点："删除 overlay 矛盾"（隐含删除 suggest_action）
- 第7点："删除交互提示相关字段"
- 3.8.2.2节明确："本阶段不使用 suggest_action 字段"

# CLAUDE.md 仍然保留
"返回字典必须包含 status、suggest_action、error_type 字段"
"Validate IO contract (status, suggest_action, error_type fields)"
```

**矛盾点**：
- spec.md 已明确删除 suggest_action
- CLAUDE.md 仍在验证该字段
- 两者不同步

**影响等级**：🔴 **高** - 导致验证工具与规范不一致

**解决建议**：
- 更新 CLAUDE.md，将 suggest_action 改为 error_code
- 明确返回值必须包含的字段：status（必需）、message（ERROR时必需）、error_code（推荐）、data（OK时必需）

---

## 3. 架构设计评估

### 3.1 PID 设计演进（v0.2.0）✅ 优秀

**设计变更**：
```python
# v0.1.0（旧）
class MyAlgo(BaseAlgorithm):
    def __init__(self, pid: str):
        self.pid = pid  # 一对一绑定

# v0.2.0（新）
class MyAlgo(BaseAlgorithm):
    def __init__(self):
        self.configs = {}  # 支持多个PID

    def execute(self, pid: str, ...):  # 运行时传递
        config = self.configs[pid]
```

**设计合理性**：
- ✓ 大幅减少内存占用（单个实例支持多个PID）
- ✓ 提升初始化效率（避免重复加载模型）
- ✓ 配置驱动差异化（通过 manifest.json 的 required_assets）
- ✓ 符合现代插件架构思想

**潜在风险**：
- 单个实例的状态管理复杂度增加
- 需要在 execute 中频繁查找配置（性能影响可忽略）

**评估**：设计演进合理，解决了 v0.1.0 的核心痛点

---

### 3.2 参数分组设计 ✅ 合理

**参数顺序优化（v0.2.1）**：
```python
# 高频参数前置
1. step_index:    # 必需的步骤标识
2. pid:           # 高频使用
3. session:       # 高频使用（上下文）
4. user_params:   # 配置参数
5. shared_mem_id: # 图像数据入口
6. image_meta:    # 图像元信息
```

**逻辑分组**：
- 步骤控制（step_index）
- 上下文信息（pid, session）
- 用户输入（user_params）
- 图像数据（shared_mem_id, image_meta）

**评估**：分组合理，高频前置提升可读性

---

### 3.3 Session 状态管理 ⚠️ 需明确

**设计优势**：
- ✓ 跨步骤数据共享（state_store）
- ✓ 自动TTL过期
- ✓ 原子计数器（increment/decrement）
- ✓ 只读 context 隔离

**设计不足**：
- Session 对象未完整定义（缺少内部实现）
- 序列化检查机制不明确（spec.md:457-460）
- reset() 方法在算法和 session 中的职责不清（spec.md:180-184）

**潜在问题**：
```python
def reset(self, session: "Session") -> None:
    """当平台触发重新检测/中断时调用。"""
    super().reset(session)  # 推荐调用父类
    session.reset()         # 清空会话数据（是否该由平台调用？）
```

**职责混淆**：
- 算法 reset()：清理算法内临时状态
- session.reset()：清空会话存储
- 两者关系不明确（谁负责调用谁？）

**评估**：概念合理，但接口设计需更明确

---

### 3.4 返回值双层状态机 ✅ 合理但需清晰文档

**架构设计**：
```
┌─────────────────────────────────────┐
│  status: "OK" | "ERROR"            │  ← 首层：调用状态（Runner使用）
│                                     │
│  data: {                            │  ← 二层：业务数据（应用层使用）
│    result_status: "OK" | "NG"      │     └─ 只在 execute 中存在
│    ng_reason: ...                   │
│    defect_rects: [...]              │
│  }                                  │
└─────────────────────────────────────┘
```

**合理性分析**：

| 场景 | status | data.result_status | 说明 |
|------|--------|-------------------|------|
| pre_execute 成功 | OK | 不存在 | 条件满足，继续执行 |
| pre_execute 失败 | ERROR | 不存在 | 条件不满足，终止 |
| execute 检测通过 | OK | OK | 流程正常 |
| execute 检测不通过 | OK | NG | 产品缺陷，流程正常 |
| execute 程序异常 | ERROR | 不存在 | 调用失败 |

**设计价值**：
1. 分离技术层面（调用是否成功）与业务层面（产品是否合格）
2. Runner 只需检查 status，不关心业务逻辑
3. UI/业务系统关注 result_status，进行不同处理

**评估**：设计合理，符合分层架构思想，但需要清晰文档说明

---

### 3.5 错误处理机制 ⚠️ 需补充

**标准错误码设计（spec.md:1830-1896）**：

| 错误码 | 类型 | 触发场景 | 合理性 |
|--------|------|----------|--------|
| 1001 | invalid_pid | PID不在supported_pids中 | ✓ 合理 |
| 1002 | image_load_failed | 图像加载失败 | ✓ 合理 |
| 1003 | model_not_found | 模型/配置不存在 | ✓ 合理 |
| 1004 | gpu_oom | GPU显存不足 | ✓ 合理 |
| 1005 | timeout | 执行超时 | ✓ 合理 |
| 1006 | invalid_params | 参数校验失败 | ✓ 合理 |
| 1007 | coordinate_invalid | 坐标越界 | ✓ 合理 |
| 9999 | unknown_error | 未知错误 | ✓ 合理 |

**设计优点**：
- ✓ 错误码结构清晰（四位数字，分类明确）
- ✓ 覆盖主要异常场景
- ✓ 机器可读（error_code）+ 人类可读（message）

**缺失内容**：
- 心跳丢失（heartbeat lost）无错误码
- Runner 强制终止无明确错误码
- JSON 协议解析失败无错误码

**评估**：错误码设计良好，但需补充通信层错误码

---

### 3.6 共享内存设计 ✅ 合理

**JPEG-only 约定（spec.md:622-632）**：
```python
image_meta = {
  "width": 1920,      # ✓ 必需
  "height": 1200,     # ✓ 必需
  "timestamp_ms": 1714032000123,  # ✓ 必需（v0.2.1统一为毫秒）
  "camera_id": "cam-01"  # ✓ 必需
}
```

**历史演进**：
- v0.1.0：可能支持多种格式
- v0.2.0/v0.2.1：统一为 JPEG-only

**设计优势**：
- ✓ 减少复杂度（无需格式判断）
- ✓ 统一 image_meta 字段（最小必要集合）
- ✓ 调用示例清晰
- ✓ 与平台写入行为一致

**潜在风险**：
- 牺牲格式灵活性（无法支持 RAW、BMP 等无损格式）
- JPEG 压缩可能引入 artifacts，影响检测精度
- 需要权衡：简单性 vs 灵活性

**评估**：
- 对 Phase 01 场景（工业检测）来说，JPEG 质量足够
- 在 spec.md 中已明确声明，设计一致
- 后续可根据需求扩展为支持多格式

---

### 3.7 超时与心跳机制 ⚠️ 需明确定义

**当前定义（spec.md:651-654, 1810-1813）**：
```markdown
1. **pre_execute 超时**：>10秒 → Runner强制终止，返回TIMEOUT
2. **execute 超时**：>30秒 → Runner强制终止，返回TIMEOUT
3. **心跳丢失**：Runner记录日志，重试或重启进程
```

**缺失内容**：
1. **心跳机制细节**：
   - ping/pong 间隔时间？
   - 连续丢失多少次心跳视为失败？
   - 心跳超时与执行超时的关系？

2. **超时处理策略**：
   - Runner 如何强制终止？（SIGTERM？SIGKILL？）
   - 终止后是否自动重启进程？
   - 重启次数限制？

3. **状态管理**：
   - 超时后 Session 状态是否保留？
   - 是否需要算法清理资源？

**错误码问题**：
- spec.md 未定义超时错误码（1005 是 timeout）
- 但心跳丢失没有对应错误码
- 需要明确：心跳丢失是 9999 unknown_error 还是新错误码？

**评估**：机制设计合理，但实现细节需明确

---

### 3.8 参数类型系统 ⚠️ 需完善

**类型系统对比**：

| 类型 | 定义完整性 | 使用场景 | 评估 |
|------|----------|----------|------|
| int | 完整（min, max, unit） | 阈值、计数 | ✓ |
| float | 完整（min, max, unit） | 置信度、曝光时间 | ✓ |
| rect | 完整（format, description）| ROI 区域 | ✓ |
| enum | 完整（choices）| 模式选择 | ✓ |
| bool | 基本完整 | 开关 | ✓ |
| string | 完整（min/max length, pattern）| 路径、文本 | ✓ |
| array | 不完整（无元素级约束）| ROI 列表 | ⚠️ |
| json | 过于简单（仅 schema）| 复杂配置 | ⚠️ |

**array 类型问题**：
```python
# 示例（spec.md:813-818）
{
  "key": "rois",
  "type": "array",
  "item_type": "rect",
  "max_length": 10
  # ❌ 缺失：如何约束每个 rect 的 x/y/width/height？
}
```

**json 类型问题**：
```python
# 示例（spec.md:820-831）
{
  "key": "advanced_config",
  "type": "json",
  "schema": {
    "type": "object",
    "properties": {
      "threshold": {"type": "float"},
      "enabled": {"type": "bool"}
    }
  }
  # ⚠️ 问题：schema 如何定义嵌套约束？
  # ⚠️ 问题：minProperties？required 字段？
}
```

**Dev Runner 验证挑战**：
- int/float：简单 min/max 检查
- rect：需要验证 x/y/width/height 范围
- array：需要验证每个元素（复杂度 O(n)）
- json：需要根据 JSON Schema 验证（需引入验证库）

**评估**：
- 基础类型设计完善
- 复杂类型（array、json）需补充详细定义
- 需明确 Dev Runner 的验证策略和性能影响

---

## 4. 关键设计决策评估

### 4.1 时间戳格式统一 ✅ 优秀

**变更（v0.2.1）**：
- v0.1.0/v0.2.0：未明确时间戳单位（秒？毫秒？纳秒？）
- v0.2.1：**统一为 Unix 毫秒时间戳** `timestamp_ms`

**架构价值**：
- ✓ 消除歧义
- ✓ 与 JavaScript 时间戳兼容（毫秒）
- ✓ 精度足够（毫秒级）
- ✓ 便于跨语言、跨平台交互

**影响范围**：
- image_meta.timestamp_ms
- protocol message timestamp_ms
- 日志时间戳
- Session TTL（秒）与时间戳（毫秒）单位区分清晰

---

### 4.2 BaseResponse Schema 提取 ✅ 合理

**设计（spec.md:1456-1596）**：
- 提取公共返回值结构
- 遵循 DRY 原则（Don't Repeat Yourself）
- 明确定义字段规则和约束

**字段约束汇总表（spec.md:1586-1596）**：

| 字段 | 约束 | 说明 | 合理性 |
|------|------|------|--------|
| supported_pids | 建议 ≤ 20，最大 50 | 便于管理 | ✓ |
| defect_rects | 最大 20 个元素 | UI 渲染性能 | ✓ |
| position_rects | 建议 ≤ 20 | 同上 | ✓ |
| message | 建议 < 100 字符 | UI 显示空间 | ✓ |
| ng_reason | 建议 < 50 字符 | 简洁明了 | ✓ |
| ROI 坐标 | x, y ≥ 0，图像范围内 | 有效性检查 | ✓ |

**评估**：
- Schema 提取减少重复定义
- 约束明确，便于 Dev Runner 验证
- 需要修正与 status 字段的矛盾（见 2.2 节）

---

### 4.3 资源管理策略 ✅ 合理

**生命周期钩子**：

| 钩子 | 调用时机 | 职责 | 合理性 |
|------|--------|------|--------|
| `__init__` | 实例创建 | 初始化配置路径 | ✓ |
| `setup` | 进程启动时（一次） | 加载模型、初始化资源 | ✓ |
| `pre_execute` | 每步执行前 | 条件验证、参考信息 | ✓ |
| `execute` | 每步执行 | 核心检测逻辑 | ✓ |
| `on_step_start` | 每步开始时 | 日志、监控 | ✓ |
| `on_step_finish` | 每步结束时 | 清理、统计 | ✓ |
| `reset` | 重新检测时 | 清理会话数据 | ✓ |
| `teardown` | 进程退出前 | 释放资源 | ✓ |

**资源分类**：

1. **重量级资源**（跨会话共享）：
   - 模型（model.pt）
   - GPU 显存
   - 共享内存池
   - 初始化时机：setup()
   - 释放时机：teardown()

2. **轻量级资源**（可重复初始化）：
   - 配置（config.json）
   - 模板图像
   - 初始化时机：__init__() 或 setup()
   - 释放时机：无需显式释放

3. **会话级资源**（单次检测流程）：
   - 临时缓存
   - 中间结果
   - 初始化时机：on_step_start()
   - 释放时机：on_step_finish() 或 reset()

**评估**：
- 资源分类清晰
- 生命周期管理完整
- 但需要明确 reset() 与 session.reset() 的关系

---

## 5. 与 CLAUDE.md 的对比分析

### 5.1 接口定义对比

| 项目 | spec.md (v0.2.1) | CLAUDE.md | 一致性 |
|------|-----------------|-----------|--------|
| BaseAlgorithm 抽象方法 | get_info, pre_execute, execute | get_info, pre_execute, execute | ✓ |
| 返回值 status | "OK", "ERROR"（首层） | "OK", "NG", "ERROR" | ❌ 不一致 |
| suggest_action | 已删除 | 必须包含 | ❌ 严重不一致 |
| error_type | 无 | 必须包含 | ⚠️ 需确认 |
| error_code | 有（3.10节） | 无 | ⚠️ 需同步 |

**主要差异**：

1. **status 取值**：
   - spec.md: 明确为 "OK" | "ERROR"（首层），"NG" 在 data.result_status 中
   - CLAUDE.md: "OK", "NG", "ERROR" 并列
   - **问题**：CLAUDE.md 未体现双层状态机设计

2. **suggest_action 字段**：
   - spec.md: v0.2.0/v0.2.1 已删除
   - CLAUDE.md: 仍然要求必须包含
   - **问题**：严重不一致，需同步更新

3. **error_code vs error_type**：
   - spec.md: 标准错误码（3.10节）
   - CLAUDE.md: error_type（"recoverable" | "fatal"）
   - **问题**：两个概念不同，需明确关系

---

### 5.2 字段映射关系

假设同步更新 CLAUDE.md 后：

```python
# spec.md 设计
{
  "status": "OK|ERROR",                    # 首层调用状态
  "message": "...",                        # 人类可读
  "error_code": "1001",                    # 标准错误码（机器可读）
  "data": {
    "result_status": "OK|NG",              # 业务判定
    ...
  }
}

# CLAUDE.md 概念映射
status              → status["status"]
suggest_action      → 已删除（v0.2.1）
error_type          → 可能对应 error_code 分类？
```

**建议**：
```python
# 更新后的返回值结构
def return_error(error_code, message, debug=None):
    return {
        "status": "ERROR",           # Runner 层面状态
        "message": message,          # 人类可读
        "error_code": error_code,    # 机器可读（如 "1001"）
        "debug": debug or {}
    }

def return_ok(data, debug=None):
    return {
        "status": "OK",              # Runner 层面状态
        "data": data,                # 业务数据
        "debug": debug or {}
    }
```

---

## 6. 架构问题汇总

### 🔴 严重问题（需立即修复）

| 编号 | 问题描述 | 影响范围 | 优先级 |
|------|----------|----------|--------|
| 1 | Session API 定义不完整（缺少内部实现） | 算法正确实现 | P0 |
| 2 | BaseResponse Schema 与 status 定义矛盾 | 规范理解 | P0 |
| 3 | CLAUDE.md 与 spec.md 严重不一致（suggest_action） | 验证工具 | P0 |
| 4 | 协议字段 overlay 未完全清理 | 文档一致性 | P1 |

### 🟡 中等问题（建议优化）

| 编号 | 问题描述 | 影响范围 | 优先级 |
|------|----------|----------|--------|
| 5 | status 双层状态机文档不清晰 | 学习成本 | P1 |
| 6 | array/json 参数类型定义不完整 | 参数验证 | P1 |
| 7 | 心跳/超时机制缺失细节 | 实现指导 | P1 |
| 8 | reset() 与 session.reset() 职责不清 | 状态管理 | P2 |

### 🟢 轻微问题（可后续改进）

| 编号 | 问题描述 | 影响范围 | 优先级 |
|------|----------|----------|--------|
| 9 | 部分参数顺序参考未更新 | 文档一致性 | P2 |
| 10 | 错误码未覆盖通信层异常 | 完整性 | P2 |

---

## 7. 架构合理性总结

### ✅ 设计良好的部分

1. **核心解耦架构**
   - 平台与算法通过 SDK 解耦 ✓
   - 标准接口定义清晰 ✓
   - 生命周期管理完整 ✓

2. **PID 多对一映射**
   - v0.2.0 演进解决内存问题 ✓
   - manifest.json 配置驱动 ✓
   - 实例复用提升效率 ✓

3. **共享内存机制**
   - JPEG-only 简化实现 ✓
   - 最小 image_meta 集合 ✓
   - 只读设计保证安全 ✓

4. **双层状态机**
   - 分离技术状态与业务状态 ✓
   - Runner 与 UI 职责分离 ✓
   - 逻辑设计合理 ✓

5. **Session 状态共享**
   - 跨步骤数据传递 ✓
   - TTL 自动过期 ✓
   - 原子操作支持 ✓

### ⚠️ 需要改进的部分

1. **文档一致性**
   - Session API 不完整
   - BaseResponse 与 status 矛盾
   - overlay 引用未清理
   - CLAUDE.md 与 spec.md 不同步

2. **机制细节缺失**
   - 心跳/超时具体参数
   - reset 职责界定
   - array/json 类型验证

3. **验证工具定位**
   - Dev Runner 验证策略不明确
   - 错误码覆盖不完整

### ❌ 架构矛盾点

1. **返回值 status 定义冲突**
   - BaseResponse 限定了 "OK"|"ERROR"
   - 但实际需要表达 "NG" 业务状态
   - **解决方案**：明确双层状态机，NG 放在 data.result_status

2. **suggest_action 删除不一致**
   - spec.md 已删除
   - CLAUDE.md 仍保留
   - **解决方案**：同步更新 CLAUDE.md

---

## 8. 改进建议

### 立即修复（P0）

1. **完善 Session API 定义**
   ```python
   class Session:
       """完整定义，包括内部实现"""

       def __init__(self, session_id: str, context: Dict[str, Any]):
           self._id = session_id
           self._context = context  # 只读上下文
           self._state_store = {}   # 状态存储
           self._ttl = {}           # TTL记录

       # ... 完整的方法实现：get/set/delete/reset/increment...
   ```

2. **修正 BaseResponse Schema**
   ```json
   {
     "$schema": "http://json-schema.org/draft-07/schema#",
     "title": "BaseResponse",
     "type": "object",
     "required": ["status"],
     "properties": {
       "status": {
         "type": "string",
         "enum": ["OK", "ERROR"],
         "description": "接口调用状态。OK=成功，ERROR=失败"
       },
       "message": {
         "type": "string",
         "description": "人类可读信息，status=ERROR 时必须提供"
       },
       "error_code": {
         "type": "string",
         "description": "标准错误码（见 3.10 节）"
       },
       "data": {
         "type": "object",
         "description": "业务数据对象，status=OK 时根据场景提供"
       },
       "debug": {
         "type": "object",
         "description": "调试信息，可选"
       }
     }
   }
   ```

3. **同步更新 CLAUDE.md**
   - 删除 suggest_action 字段要求
   - 增加 error_code 字段说明
   - 明确 status 为 "OK"|"ERROR"
   - 补充 data.result_status 为 "OK"|"NG"

### 短期优化（P1）

4. **明确心跳/超时机制**
   - 定义 ping/pong 间隔（建议：5秒）
   - 定义心跳超时时间（建议：10秒）
   - 定义连续失败阈值（建议：3次）
   - 明确超时处理策略（终止→重启→告警）

5. **完善参数类型系统**
   ```python
   # array 类型增强
   {
     "type": "array",
     "item_type": "rect",
     "max_length": 10,
     "item_constraints": {  # ✅ 新增：元素级约束
       "x": {"min": 0, "max": 1920},
       "y": {"min": 0, "max": 1200},
       "width": {"min": 10, "max": 500},
       "height": {"min": 10, "max": 500}
     }
   }

   # json 类型增强
   {
     "type": "json",
     "schema": {
       "$schema": "http://json-schema.org/draft-07/schema#",
       "type": "object",
       "required": ["threshold", "enabled"],
       "properties": {
         "threshold": {"type": "number", "minimum": 0, "maximum": 1},
         "enabled": {"type": "boolean"}
       }
     }
   }
   ```

6. **清理 overlay 残留**
   - 删除 3.8.2.5 节 overlay 说明
   - 确认整个文档无 overlay 引用
   - 更新 5.3 节图像传输说明（已删除 overlay）

### 中期改进（P2）

7. **明确 reset 职责**
   - 算法 reset()：清理算法内部临时状态
   - session.reset()：清空会话存储（平台调用）
   - 不推荐在算法 reset() 中调用 session.reset()

8. **扩展错误码体系**
   - 增加通信层错误码（如：协议解析失败、心跳丢失）
   - 明确 Runner 错误与业务错误的区分

9. **完善 Dev Runner 说明**
   - 验证策略详细说明
   - 性能基准测试
   - 报告格式规范

---

## 9. 结论

### 总体评估

**架构设计**：⭐⭐⭐⭐✨ **（4.5/5）**
- 核心设计思想清晰且合理
- 解耦、生命周期、状态管理设计优秀
- PID 多对一演进解决了 v0.1.0 的核心问题

**文档一致性**：⭐⭐⭐✨ **（3.5/5）**
- 整体结构清晰，内容详尽
- 但存在多处细节不一致（Session、status、overlay、suggest_action）
- CLAUDE.md 与 spec.md 同步问题

**实现指导**：⭐⭐⭐⭐ **（4/5）**
- 代码示例丰富
- 边界场景覆盖全面
- 但部分机制（心跳、超时、验证）细节不足

### 是否自洽

**架构逻辑**：✅ **基本自洽**
- 核心设计无矛盾
- 分层合理（Runner → Algorithm → UI）
- 职责清晰（平台/SDK/算法）

**文档实现**：⚠️ **部分矛盾**
- status 定义存在混淆（BaseResponse vs 实际使用）
- Session API 不完整
- suggest_action 删除不一致
- overlay 残留

**技术约束**：✅ **合理**
- JPEG-only 约定合理
- 共享内存只读正确
- Session 生命周期清晰
- 拆包格式标准

### 最终建议

**当前版本（v0.2.1）**：
- ✅ **可用于开发**：核心架构稳定，主要接口清晰
- ⚠️ **需补充文档**：Session、status、overlay、suggest_action 需修正
- ⏳ **需完善机制**：心跳/超时细节、参数验证策略

**后续版本建议**：
1. **v0.2.2**：修复文档矛盾（P0 问题）
2. **v0.3.0**：完善心跳/超时机制（P1 问题）
3. **v0.3.x**：优化参数类型系统（P1/P2 问题）

**重要提醒**：
- 立即修复 Session API 不完整问题（影响算法实现）
- 立即同步 CLAUDE.md 与 spec.md（影响验证工具）
- BaseResponse Schema 修正需明确 status 与 data.result_status 关系

---

## 10. 附录：架构问题追踪表

| 编号 | 问题类别 | 具体描述 | 优先级 | 状态 |
|------|---------|----------|--------|------|
| A001 | API 定义 | Session 类未完整定义 | P0 | 待修复 |
| A002 | Schema | BaseResponse 与 status 矛盾 | P0 | 待修复 |
| A003 | 文档同步 | CLAUDE.md 与 spec.md 不一致 | P0 | 待修复 |
| A004 | 字段残留 | overlay 未完全清理 | P1 | 待修复 |
| A005 | 状态机 | 双层状态机文档不清晰 | P1 | 待优化 |
| A006 | 参数类型 | array/json 定义不完整 | P1 | 待优化 |
| A007 | 超时机制 | 心跳/超时细节缺失 | P1 | 待补充 |
| A008 | 职责界定 | reset() 与 session.reset() 不清 | P2 | 待明确 |
| A009 | 错误码 | 未覆盖通信层异常 | P2 | 待扩展 |
| A010 | 验证工具 | Dev Runner 验证策略不明确 | P2 | 待完善 |

---

**报告生成时间**：2025-11-20
**评估版本**：spec.md v0.2.1
**评估人**：Claude Code 架构评估
**报告状态**：初稿（待评审）
