---
project_type: research-auto
---
# ashare_rawdata 项目管理要求

## 关键参数速查
<!-- source: docs/params/evaluation.yaml — 以 YAML 为准 -->
- LS Sharpe > 0.9 | IR(LS) > 0.2 | Long Excess Net Sharpe > 0.7 | Mono > 0.7 | 覆盖率 > 30%
- commission = 0.0001 | execution = twap_1300_1400 | benchmark = csi1000 | neutralize
- post-process = comp | num-groups = 8 | mode = long_short

如需完整参数或修改值 → docs/params/evaluation.yaml

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
