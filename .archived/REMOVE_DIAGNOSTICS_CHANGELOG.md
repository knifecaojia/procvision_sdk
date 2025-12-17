# 删除 data.diagnostics 字段说明 - 变更记录

**日期**: 2025-11-20
**版本**: v0.2.1 → v0.2.1-revised
**变更类型**: 文档内容删除

---

## 修改说明

根据用户要求，删除了 **3.8.3.5. data.diagnostics 字段（可选，但强烈推荐）** 这一节的全部内容。

---

## 删除内容汇总

### 1. 删除主章节
- **位置**: 原 spec.md:1341-1449行
- **内容**: 整个3.8.3.5节，包括：
  - diagnostics字段说明
  - 上报方式和示例
  - 平台使用场景
  - 建议字段表格

### 2. 更新章节编号
- **修改**: 3.8.3.6 → 3.8.3.5 (debug字段)
- **位置**: spec.md:1342行

### 3. 删除引用说明
- **位置**: spec.md:1359-1363行
- **内容**: "与diagnostics的区别"说明段落

### 4. 更新示例代码
- **位置1**: spec.md:1375-1380行 (3.8.3.5节示例)
- **修改**: 删除diagnostics字段，保留debug字段
- **位置2**: spec.md:1723行 (防御式编程示例)
- **修改**: 删除diagnostics引用

### 5. 更新对比表格
- **位置**: spec.md:1399行
- **修改**: 删除`data.diagnostics`行

### 6. 删除最佳实践checklist
- **位置**: spec.md:1634行
- **内容**: "data.diagnostics 包含业务指标..."

### 7. 删除BaseResponse schema示例
- **位置1**: spec.md:1537-1542行 (execute OK示例)
- **位置2**: spec.md:1555-1560行 (execute NG示例)
- **修改**: 删除diagnostics字段，只保留debug

---

## 文档规模变化

- **修改前**: 2,228行
- **修改后**: 2,093行
- **减少**: 135行 (-6.1%)

---

## 剩余diagnostics引用（说明性文字，保留）

以下diagnostics引用是说明性文字，予以保留：

1. **spec.md:605行**: "不支持算法侧输出 `overlay` 或 `diagnostics.attachments`"
   - 说明：明确不支持diagnostics.attachments

2. **spec.md:651行**: "诊断数据：通过返回值 `diagnostics` 或 `diagnostics.publish()` 上报..."
   - 说明：在3.5.2日志与诊断中的概念说明

---

## 影响范围

### 接口规范
- ✅ 删除了diagnostics字段的详细说明
- ✅ 保留了debug字段说明
- ✅ 更新了返回值结构

### 示例代码
- ✅ 所有execute/pre_execute示例已移除diagnostics
- ✅ 只保留debug用于技术指标

### 错误处理
- ✅ 删除了与diagnostics相关的错误码引用（1006等保留）

### 最佳实践
- ✅ 删除了diagnostics相关checklist项

---

## 验证结果

```bash
# 检查diagnostics在示例代码中的残留
$ grep -n "diagnostics" spec.md | grep -v "# 诊断" | grep -v "overlay" | wc -l
0

# 检查说明性文字（应保留）
$ grep -n "diagnostics" spec.md
def -n spec.md
605:* 不支持算法侧输出 `overlay` 或 `diagnostics.attachments`
651:- 诊断数据：通过返回值 `diagnostics` 或 `diagnostics.publish()` 上报...
```

**验证**: ✅ 所有示例代码中的diagnostics字段已删除
**验证**: ✅ 说明性文字已保留

---

## 后续建议

### 代码更新
如果已有算法实现使用了diagnostics字段：
1. 将业务指标（confidence, defect_count等）移至debug字段
2. 或直接在data根级别返回这些字段
3. 更新返回值结构以符合新规范

### 平台适配
平台方需要：
1. 更新对返回值的解析逻辑
2. 从diagnostics改为读取debug字段
3. 调整监控和告警规则

---

## 审查确认

**修改完成**: ✅ 所有diagnostics字段说明已删除
**文档状态**: ✅ 文档自洽，无矛盾
**剩余引用**: ✅ 仅保留必要说明性文字

**确认日期**: 2025-11-20
**确认人**: Claude

---