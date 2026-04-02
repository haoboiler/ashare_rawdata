---
agent_id: "ashare_rawdata_a"
experiment_id: "#027"
direction: "D-018 (amihud_asymmetry)"
feature_name: "high_vol_down_amihud_full"
net_sharpe: 1.83
mono_score: 1.00
status: screening_passed
submitted_at: "2026-03-26T10:45:00"
---

# D-018 Amihud 价格冲击买卖不对称性 — 全天窗口筛选报告

## 方向概述

**假设**: 逆向选择理论 — 如果卖出（下跌 bar）的价格冲击高于买入（上涨 bar），股票面临知情卖出/分布压力。这种不对称性是截面风险因子。

**新意**: 我们已有 `up_amihud_full`（pending），但从未探索**下行 Amihud** 及其与上行 Amihud 的不对称性。

## 快筛结果（evolve, 全市场 5013 stocks, 2020-2023）

| 特征 | |LS Sharpe| | LE | |IR_LS| | 覆盖率 | 快筛 |
|------|-----------|------|---------|--------|--------|
| `down_amihud_full` | 1.42 | +1.14 | 0.38 | 86.2% | ✅ |
| `high_vol_down_amihud_full` | 1.83 | +1.53 | 0.38 | 86.3% | ✅ |
| `amihud_asymmetry_full` | 7.49 | -0.30 | 0.13 | 86.2% | ❌ LE 负/IR 低 |
| `amihud_sell_ratio_full` | 2.59 | -1.70 | 0.30 | 86.2% | ❌ LE 负 |
| `high_vol_amihud_asymmetry_full` | 6.77 | -1.42 | 0.12 | 86.3% | ❌ LE 负/IR 低 |

## 正式评估结果（2020-01-01 ~ 2023-12-31, pkl 覆盖范围）

### down_amihud_full

| 指标 | Raw | Neutral | 阈值 | 状态 |
|------|-----|---------|------|------|
| LS Sharpe | 1.42 | 1.36 | >0.9 | ✅ |
| LE Sharpe | +1.14 | +1.41 | >0.7 | ✅ |
| IR(LS) | 0.38 | 0.43 | >0.2 | ✅ |
| Mono (8组) | 0.71 | 0.86 | >0.7 | ✅ |
| 覆盖率 | 86.2% | — | >30% | ✅ |

年度 Sharpe (neutral): 2020=-0.04 / 2021=+1.30 / 2022=+3.13 / 2023=+1.69

### high_vol_down_amihud_full

| 指标 | Raw | Neutral | 阈值 | 状态 |
|------|-----|---------|------|------|
| LS Sharpe | 1.83 | 1.52 | >0.9 | ✅ |
| LE Sharpe | +1.53 | +1.43 | >0.7 | ✅ |
| IR(LS) | 0.38 | 0.44 | >0.2 | ✅ |
| Mono (8组) | **1.00** | **1.00** | >0.7 | ✅ |
| 覆盖率 | 86.3% | — | >30% | ✅ |

年度 Sharpe (raw): 2020=-0.39 / 2021=+1.53 / 2022=+3.67 / 2023=+3.69
年度 Sharpe (neutral): 2020=+0.07 / 2021=+1.35 / 2022=+3.49 / 2023=+2.05

## 失败特征诊断

### amihud_asymmetry_full / high_vol_amihud_asymmetry_full

- **假设**: 买卖不对称性（up - down）/（up + down）是截面因子
- **实际**: |LS Sharpe| 极高（7.49/6.77）但 LE 深度负值；IR_LS 极低（0.13/0.12）
- **诊断**: 不对称性比率的 alpha 完全集中在空头端——高不对称性=高波动/异常交易=只能识别坏股票。高换手率（TVR=2.72）也表明信号噪声大
- **结论**: 比率/不对称性类因子与之前结论#6、#9 一致——比率类截面信号在 A 股识别坏股票但无法选出好股票

### amihud_sell_ratio_full

- **假设**: 卖出价格冲击占总冲击比例
- **实际**: |LS|=2.59 但 LE=-1.70
- **诊断**: 同上——比率类信号空头端集中

## 关键发现

1. **下行 Amihud 是有效的流动性水平因子** — down_amihud_full（仅下跌 bar 的 |ret|/amount）与 amihud_illiq_full 结构类似，但只看卖出方价格冲击，是 Amihud 框架的自然扩展
2. **high_vol_down_amihud_full 达到完美单调性** — raw 和 neutral 双 Mono=1.00，表明高量下跌 bar 的价格冲击在截面上有极其清晰的分层
3. **Neutral 后 IR 增强** — 两个特征均表现为 neutral IR > raw IR（0.38→0.43, 0.38→0.44），信号独立于市值/行业
4. **不对称性比率（up-down 差异）系统性失败在 LE** — 与结论#6 一致，比率/相对量类信号在 A 股只能识别差股票
5. **pkl 覆盖 2020-2023**（preload 窗口限制），2024 segment 无数据

## 产出

- **Evolve 产出**: `.claude-output/evolve/20260326-103512/`
- **评估 (down_amihud_full)**: `.claude-output/evaluations/amihud_asymmetry/down_amihud_full/`
- **评估 (high_vol_down_amihud_full)**: `.claude-output/evaluations/amihud_asymmetry/high_vol_down_amihud_full/`
- **Pending**: `research/pending-rawdata/down_amihud_full/`, `research/pending-rawdata/high_vol_down_amihud_full/`
