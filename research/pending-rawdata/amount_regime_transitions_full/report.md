---
agent_id: "ashare_rawdata_b"
experiment_id: "#009"
direction: "D-005 (volume_entropy)"
feature_name: "amount_regime_transitions_full"
net_sharpe: 1.60
mono_score: 0.57
status: screening_borderline
submitted_at: "2026-03-26T02:40:00"
---

# amount_regime_transitions_full Pending 审核包

## 说明

该特征未满足自动入选标准，但按当前人工要求手动列入 `pending-rawdata`，供后续审核时集中比较。

## 方向与物理含义

**方向**: D-005 volume_entropy

**特征定义**: 日内成交额在每日中位数上下发生切换的频率。高切换表示成交额分布更均匀，试图刻画流动性质量。

## 正式评估结果

### 自动筛选指标

| 指标 | Raw | Neutral | 阈值 | 结果 |
|------|-----|---------|------|------|
| LS Sharpe (`sharpe_abs_net`) | 1.60 | 1.22 | > 0.9 | ✅ |
| IR(LS) | 0.66 | 0.66 | > 0.2 | ✅ |
| Long Excess Net Sharpe | 1.14 | 0.90 | > 0.7 | ✅ |
| Coverage | 86.7% | 86.7% | > 30% | ✅ |
| Mono (8 groups) | 0.57 | 0.43 | > 0.7 | ❌ |

### 未达标项

唯一未达标指标是 **Mono**。Raw 版本仅 0.57，neutral 后进一步降到 0.43，说明该信号虽然头尾分化存在，但中间组排序不够稳定，横截面单调性不足。

### 分组诊断（Raw）

| 组别 | Excess Return | Sharpe |
|------|---------------|--------|
| G1 | 11.58% | 0.70 |
| G2 | 12.70% | 0.82 |
| G3 | 10.66% | 0.63 |
| G4 | 9.88% | 0.57 |
| G5 | 11.93% | 0.83 |
| G6 | 8.39% | 0.45 |
| G7 | 9.21% | 0.58 |
| G8 | 5.00% | 0.05 |

头尾方向正确，但中间组明显非单调，尤其 `G2 > G1`、`G5 > G3 > G4`，因此未通过 Mono 阈值。

### 年度表现

| 年份 | Raw Sharpe | Neutral Sharpe |
|------|-----------|----------------|
| 2020 | -0.45 | -0.46 |
| 2021 | 1.36 | 1.04 |
| 2022 | 3.71 | 3.08 |
| 2023 | 3.71 | 2.81 |

## 诊断结论

1. 这是一个 **borderline** 候选。收益、IR、覆盖率都已经满足阈值，问题集中在分组排序质量。
2. `amount = price × volume`，相比纯 `volume`，价格水平的引入会放大非线性干扰，削弱 regime transition 在横截面上的排序清晰度。
3. 同方向中的 `vol_regime_transitions_full` 已验证通过，说明问题更可能来自 `amount` 口径本身，而不是 regime transition 范式本身。

## 审核建议

- 若只接受自动标准通过的候选，应拒绝，理由为 `NO_MONOTONICITY`
- 若当前阶段希望保留边界案例做人工对比，可与 `vol_regime_transitions_full`、`amihud_illiq_full` 一并审阅，重点比较是否提供了额外的流动性信息

## 文件路径

- 因子 pkl: `.claude-output/analysis/volume_entropy/amount_regime_transitions_full.pkl`
- 评估目录 (raw): `.claude-output/evaluations/volume_entropy/amount_regime_transitions_full/file-amount_regime_transitions_full-raw/`
- 评估目录 (neutral): `.claude-output/evaluations/volume_entropy/amount_regime_transitions_full/file-amount_regime_transitions_full-neutral-industry-size/`
- 来源报告: `research/agent_reports/screening/2026-03-26_volume_entropy_regime_multi_screening.md`
