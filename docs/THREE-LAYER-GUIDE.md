# 三层研究结构操作指南

## 架构

```
Layer 0  KNOWLEDGE-BASE.md    ← 自动生成 (regenerate_kb.py)，启动时读
Layer 1  EXPERIMENT-LOG.md    ← 研究员追加：结论 + 排除方向 + 实验记录
Layer 2  .claude-output/      ← 原始评估数据/报告（按需读取）
```

更新顺序：L2 → L1 → L0（从下往上）

## EXPERIMENT-LOG.md 写入规范

### §一 结论
- 编号全局递增：`grep -oP '^\d+\.' research/EXPERIMENT-LOG.md | sed 's/\.//' | sort -n | tail -1` + 1
- 只追加不修改，修正旧结论用新编号注明"修正 #{旧编号}"
- 格式：`{N}. **{标题}** — {描述+数据}。（#{实验号}）`

### §二 排除方向
- 追加到表格末尾：`| {方向名} | {失败原因+数据} | #{实验号} |`

### §三 实验记录
- 追加到 §三 末尾、§四 之前
- 模板：

```markdown
### Experiment #{N}: {方向简述}（{日期}）
**方向**: {D-XXX} | **Agent**: {id} | **结果**: {N} 测试，{M} 通过
| 特征 | Net Sharpe | Mono | 状态 |
**关键发现**: {1-3 句}
#### Related
- **报告**: `research/agent_reports/screening/{report}.md`
- **评估**: `.claude-output/evaluations/{dirs}/`
```

### §四 统计
每次实验后用 `grep -c` 更新计数。

## 多 Agent 并发
- 写入前读取最新编号，编号冲突取较大值
- 不修改其他 Agent 的记录
