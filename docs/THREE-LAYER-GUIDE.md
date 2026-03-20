# 三层研究结构操作指南

> **读者**: 所有研究员 Agent（ashare_rawdata_a, ashare_rawdata_b, ...）
> **何时读**: 首次启动前必读；每次执行数据更新时参照。
> **权威文件**: 本文件是三层结构的 **唯一规范**。`researcher.md` 中的模板为简化版，冲突时以本文件为准。

---

## 架构总览

```
Layer 0  KNOWLEDGE-BASE.md    ← 自动生成，≤300行，研究员启动时读
           │ regenerate_kb.py
Layer 1  EXPERIMENT-LOG.md    ← 研究员追加，结论+排除+实验记录
         .claude-output/index.md  ← 研究员追加，产出索引
           │ Related blocks 引用
Layer 2  .claude-output/      ← evaluate.py 自动生成 + 研究员写报告
         evaluations/  reports/  analysis/
```

**信息流向**: Layer 2（原始数据）→ Layer 1（结构化摘要）→ Layer 0（自动浓缩）

**更新顺序**: 永远从下往上 — 先写 Layer 2 → 再追加 Layer 1 → 最后 `regenerate_kb.py` 刷新 Layer 0

---

## §一 结论编号规则（EXPERIMENT-LOG.md §一）

### 核心原则：一个编号 = 一条结论，全局唯一

### 获取下一个可用编号

```bash
grep -oP '^\d+\.' research/EXPERIMENT-LOG.md | sed 's/\.//' | sort -n | tail -1
```

**新结论编号 = 上述输出 + 1**。

### 规则清单

| 规则 | 说明 |
|------|------|
| **只追加，不插入** | 新结论追加到对应子标题的**末尾** |
| **全局递增** | 不管属于哪个子标题，编号全局递增 |
| **不复用已有编号** | 旧结论被标注过时也不回收 |
| **不修改已有结论** | 如需修正旧结论，追加新编号并注明"修正 #{旧编号}" |
| **写入前必须读取** | 获取最新编号，防止与其他 Agent 冲突 |

### 格式

```markdown
{N}. **{一句话结论标题}** — {补充描述，含数据佐证}。（#{实验号}）
```

### 追加位置

§一 内部有 3 个子标题：

```markdown
### ✅ 方法论结论      ← 通用策略/技巧
### ✅ 信号维度结论     ← 具体信号/字段的发现
### ⚠️ 重要注意事项    ← A 股特有的注意事项
```

---

## §二 排除方向规则（EXPERIMENT-LOG.md §二）

### 格式

```markdown
| {方向名} | {失败原因，含关键数据} | #{实验号} |
```

### 规则

- **只追加到表格末尾**，不删除、不修改已有行
- 排除理由必须有数据支撑
- 如果排除了整个方向族，加粗标注

---

## §三 实验记录规则（EXPERIMENT-LOG.md §三）

### 插入位置

**追加到 `## 三、实验记录` 末尾、`## 四、统计` 之前。**

### 模板（严格遵循）

```markdown
### Experiment #{N}: {方向简述}（{日期}）

**方向**: {D-XXX} {方向名}
**Agent**: {your_agent_id}
**结果**: {测试特征数} 特征测试，{通过数} 通过

| 特征 | Net Sharpe | w1 Mono | 状态 |
|------|--------|----------|------|
| `feature_1` | X.XX | 0.XX | ✅ pending / ❌ 拒绝(原因) |

**关键发现**: {1-3 句核心 insight}

#### Related
- **报告**: `research/agent_reports/screening/{report}.md`
- **评估**: `.claude-output/evaluations/{dirs}/`
- **Pending**: `research/pending-rawdata/{feature}/` （如有）
```

### Related 块要求

| 字段 | 必须 | 说明 |
|------|:----:|------|
| 报告 | ✅ | 指向 screening 报告文件 |
| 评估 | ✅ | 指向关键评估目录 |
| Pending | 如有 | 列出进入 pending 的特征 |

**Related 块中的路径必须是真实存在的文件/目录。写入前 `ls` 验证。**

---

## §四 统计更新规则

每次实验完成后必须更新统计表：

```markdown
## 四、统计

| 指标 | 值 |
|------|-----|
| 总实验数 | {N} |
| 已测特征数 | {~累计} |
| 已注册 Bundle | {当前数} |
| Waiting | {当前数} |
| 已排除方向 | {当前数} |
| 已验证结论 | {当前数} |
```

**数法**：用 `grep -c` 计数，不凭记忆。

---

## §五 技术备忘

放在 §四 之后，记录技术坑点。格式：

```markdown
{N}. **{坑点标题}**: {描述和解决方案}
```

---

## Layer 2 产出与索引规则

### 文件存放

| 产出类型 | 路径 | 命名规则 |
|---------|------|---------|
| 筛选报告 | `research/agent_reports/screening/` | `{date}_{agent}_{direction}.md` |
| 评估数据 | `.claude-output/evaluations/` | `{direction}/{feature}/w{N}/` |
| 分析结果 | `.claude-output/analysis/` | `{direction}/{feature}.pkl` |
| Pending 包 | `research/pending-rawdata/` | `{feature}/` |

### index.md 追加规则

**必须索引**：筛选报告、通过特征的评估目录、重要拒绝（提供新结论的）

**不需要索引**：中间评估（指标不达标且无特殊发现的）

---

## 多 Agent 并发写入规则

### §一 结论
1. **写入前读取**当前文件，获取最新编号
2. **追加到对应子标题末尾**
3. 编号冲突时以较大编号为准

### §三 实验记录
- 各自追加到 §三 末尾
- **不修改对方的记录**

---

## 常见错误

| 错误 | 正确做法 |
|------|---------|
| 结论编号凭记忆 | `grep` 获取最大编号后 +1 |
| 缺少 Related 块 | 必须包含，路径必须真实 |
| 修改其他 Agent 的记录 | 只追加自己的内容 |
| §四 统计不更新 | 每次实验后更新 |

---

*本文档最后更新: 2026-03-19 | 关联: `researcher.md`, `CLAUDE.md`, `regenerate_kb.py`*
