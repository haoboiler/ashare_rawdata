---
agent_id: "ashare_rawdata_b"
experiment_id: "#009"
direction: "D-005 (volume_entropy)"
feature_name: "amount_regime_transitions_full"
net_sharpe: 1.60
mono_score: 0.57
status: screening_failed
submitted_at: "2026-03-26T02:40:00"
---

# D-005 Volume Entropy — 多维度 Regime Transition + 交易活动质量筛选报告

## 概要

本轮对 D-005 volume_entropy 方向进行扩展研究，测试 2 个 bundle（10 个特征）：
1. **regime_transitions_multi_full**（5 特征）：将已验证的 vol_regime_transitions 范式扩展到 amount/bar_range/amihud/body_ratio/vwap_cross 维度
2. **trade_activity_quality_full**（5 特征）：交易活动质量指标（trade_size transitions/volume accel/amount-weighted reversal/cumret zero-cross/vol-price divergence）

**结果**：10 特征测试，0 通过全部自动筛选阈值。

## 快筛结果

### Bundle 1: regime_transitions_multi_full

全市场 5013 股 × 970 天（2020-2023），evolve 热路径快筛。

| 特征 | |LS Sharpe| | LE Sharpe | |IR(LS)| | 状态 |
|------|-----------|-----------|---------|------|
| `amount_regime_transitions_full` | **1.60** | **+1.14** | **0.66** | ⚠️ Mono 不达标 |
| `bar_range_regime_transitions_full` | 1.94 | +0.59 | 0.15 | ❌ IR+LE |
| `amihud_regime_transitions_full` | 2.52 | +0.30 | 0.13 | ❌ IR+LE |
| `body_ratio_transitions_full` | 4.65 | -0.87 | 0.35 | ❌ LE 深度失败 |
| `vwap_cross_transitions_full` | 2.87 | -0.06 | 0.22 | ❌ LE 失败 |

### Bundle 2: trade_activity_quality_full

| 特征 | |LS Sharpe| | LE Sharpe | |IR(LS)| | 状态 |
|------|-----------|-----------|---------|------|
| `trade_size_transitions_full` | 2.96 | -0.16 | 0.20 | ❌ LE 失败 |
| `volume_accel_transitions_full` | 2.00 | +0.11 | 0.62 | ❌ LE 不达标 |
| `amount_weighted_reversal_full` | 4.43 | -0.77 | 0.12 | ❌ LE+IR |
| `cumret_zero_cross_full` | 4.57 | -0.64 | 0.03 | ❌ LE+IR |
| `vol_price_divergence_full` | 6.68 | -1.84 | 0.02 | ❌ LE+IR |

## amount_regime_transitions_full 正式评估（Borderline 特征）

Shortlist 后导出 pkl（5013 symbols × 970 天）+ 正式评估（2020-2023, neutralize）。

### 核心指标

| 指标 | Raw | Neutral | 阈值 | 判定 |
|------|-----|---------|------|------|
| sharpe_abs_net | **1.60** | **1.22** | > 0.9 | ✅ |
| ir_ls | **0.66** | **0.66** | > 0.2 | ✅ |
| sharpe_long_excess_net | **1.14** | **0.90** | > 0.7 | ✅ |
| Mono (8 组) | **0.57** | **0.43** | > 0.7 | ❌ |
| Coverage | 86.7% | 86.7% | > 30% | ✅ |

### 分组分析（Raw）

| 组 | Excess Return | Sharpe |
|----|--------------|--------|
| G1 (高切换) | 11.58% | 0.70 |
| G2 | 12.70% | 0.82 |
| G3 | 10.66% | 0.63 |
| G4 | 9.88% | 0.57 |
| G5 | 11.93% | 0.83 |
| G6 | 8.39% | 0.45 |
| G7 | 9.21% | 0.58 |
| G8 (低切换) | 5.00% | 0.05 |

头尾分化方向正确（G1=11.6% >> G8=5.0%），但中间组非单调（G2>G1, G5>G3>G4），Mono=0.57 不达标。

### 年度表现

| 年份 | Raw Sharpe | Neutral Sharpe | 方向 |
|------|-----------|---------------|------|
| 2020 | -0.45 | -0.46 | 开局负收益 |
| 2021 | 1.36 | 1.04 | ✅ |
| 2022 | 3.71 | 3.08 | ✅ |
| 2023 | 3.71 | 2.81 | ✅ |

2020 年两组均为负值，2021-2023 逐年增强。Neutral 后 2022-2023 信号稍弱但仍强劲。

## 失败诊断

### amount_regime_transitions_full（Borderline）
- **特征**：日内成交额跨越每日中位数的切换频率
- **假设**：成交额频繁切换 = 流动性分布均匀 = 流动性溢价
- **实际**：LS/LE/IR 全部通过，但分组单调性不足（0.57/0.43）
- **诊断**：Amount = price × volume，价格水平引入了非线性干扰。相比 volume（纯股数），amount 的 regime 切换被价格波动主导，降低了截面排序的清晰度。vol_regime_transitions_full（Mono=0.86）不受此问题影响因为只用 volume。
- **结论**：用 amount 做 regime transition 不如用 volume；amount 更适合做水平量（如 Amihud = |ret|/amount 已验证有效），而非 transition 范式。

### trade_activity_quality_full 系统性失败
- 5 个特征中 4 个 LE 深度为负（-0.16 到 -1.84），仅 volume_accel_transitions 勉强正值（+0.11）
- amount_weighted_reversal 看似是 reversal_ratio 的增强版，但加权后反而引入了 size bias
- cumret_zero_cross 和 vol_price_divergence 本质都是微观结构指标，信号集中在空头端

### 其余 4 个 regime_transitions_multi 特征
- bar_range 和 amihud transitions 的 IR 均 < 0.2，说明这些维度的 regime 切换在截面上区分度不足
- body_ratio transitions LE=-0.87，蜡烛实体比的切换频率反映方向性信号→A 股反转效应
- vwap_cross transitions LE=-0.06，价格围绕 VWAP 的穿越频率也无法突破 LE 瓶颈

## 关键发现

1. **Regime transition 范式在 volume 维度上表现最优**：vol_regime_transitions_full 仍是该范式下唯一全部通过的特征。扩展到 amount/bar_range/amihud/body_ratio/vwap_cross 均不如 volume
2. **Amount 做 transition 不如做 level**：amount_regime_transitions（Mono=0.57）不达标，但 amihud_illiq（|ret|/amount 水平量, Mono=0.86）已通过。Amount 信息更适合用连续水平而非离散切换来捕捉
3. **D-005 volume_entropy 方向已充分探索**：共测试 20 个特征（Exp#007 的 10 个 + 本轮 10 个），仅 vol_regime_transitions_full 1 个通过。建议后续切换到其他方向

## 产出文件

- 快筛报告（evolve）：`.claude-output/evolve/20260326-020935/`、`.claude-output/evolve/20260326-022343/`
- 正式评估：`.claude-output/evaluations/volume_entropy/amount_regime_transitions_full/`
- 因子 pkl：`.claude-output/analysis/volume_entropy/amount_regime_transitions_full.pkl`
