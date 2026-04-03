---
project_type: research-auto
---
# ashare_rawdata 项目管理要求

## 关键参数
<!-- SSOT: docs/params/evaluation.yaml — 阈值和回测参数数值只在 YAML 中定义，此处不复制 -->
→ **所有阈值和回测参数见 `docs/params/evaluation.yaml`**
→ 指标含义见 `docs/evaluation-standards.md`

## 研究纪律
1. 假设驱动，不做无意义数学变换
2. 单变量迭代，一次只改一个维度
3. 必须做分组回测（不能只看 IC）
4. 连续 2 个失败必须停下反思
5. 失败特征必须写诊断（特征/假设/实际/诊断/结论/下一步）

## 产出位置
| 类型 | 位置 |
|------|------|
| 因子值 pkl | `.claude-output/analysis/` |
| 评估报告 | `.claude-output/evaluations/` |
| 研究报告 | `.claude-output/reports/` |
| 临时文件 | `.claude-tmp/` |
