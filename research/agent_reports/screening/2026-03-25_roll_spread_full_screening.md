---
agent_id: "ashare_rawdata_b"
experiment_id: "#005"
direction: "D-009 (roll_spread)"
feature_name: "reversal_ratio_full"
net_sharpe: 1.09
mono_score: 0.86
status: screening_passed
submitted_at: "2026-03-25T18:15:00"
---

# D-009 Roll Spread 流动性因子筛选报告

## 方向假设

**Roll (1984) 隐含买卖价差** — 连续收益率的负自协方差反映隐含 bid-ask spread。流动性差的股票（高 spread / 高反转频率）因流动性溢价应有更高预期回报。与之前失败的波动率/动量因子不同，这是「水平/成本」因子而非「动态」因子。

**关键转变**：结论 #6 指出日内价格时序动态因子系统性失败在 Long Excess，建议转向流动性因子。本方向正是对此建议的验证。

## 测试特征汇总

### Bundle 1: roll_spread_0930_1030（5 特征，0930-1030 窗口）

| 特征 | |Sharpe| | Long Excess | |IR| | 状态 |
|------|---------|-------------|------|------|
| roll_spread_bps_0930_1030 | 2.96 | -1.40 | 0.07 | ❌ IR+LE |
| zero_return_pct_0930_1030 | 0.65 | **+0.37** | **0.36** | ❌ Sharpe+LE（但LE首次正值！） |
| reversal_ratio_0930_1030 | 0.22 | **+0.77** | **0.28** | ❌ Sharpe太低（但LE首次达标！） |
| spread_to_vol_0930_1030 | 2.40 | -0.37 | 0.21 | ❌ LE |
| roll_impact_0930_1030 | 9.13 | -7.59 | 0.21 | ❌ LE深度失败(size proxy) |

### Bundle 2: roll_spread_full（5 特征，全天窗口）

| 特征 | |Sharpe| | Long Excess | |IR| | 状态 |
|------|---------|-------------|------|------|
| **reversal_ratio_full** | **1.09** | **+1.21** | **0.35** | **✅ 全部达标！** |
| spread_to_vol_full | 0.78 | +0.66 | 0.34 | ❌ Sharpe+LE边界 |
| zero_return_pct_full | 0.43 | -0.56 | 0.37 | ❌ 方向翻转 |
| roll_spread_bps_full | 0.62 | +0.36 | 0.17 | ❌ IR+Sharpe |
| roll_impact_full | 5.25 | -3.56 | 0.09 | ❌ LE深度失败 |

### Bundle 3: roll_spread_enhanced_0930_1030（5 特征，增强变体）

| 特征 | |Sharpe| | Long Excess | |IR| | 状态 |
|------|---------|-------------|------|------|
| vol_weighted_zero_ret_0930_1030 | 0.68 | +0.52 | 0.35 | ❌ Sharpe+LE |
| abs_return_intensity_0930_1030 | 7.71 | -6.06 | 0.45 | ❌ LE深度失败 |
| small_trade_ratio_0930_1030 | 1.44 | +0.23 | 0.38 | ❌ LE |
| return_concentration_0930_1030 | 5.21 | -3.78 | 0.18 | ❌ IR+LE |
| reversal_asymmetry_0930_1030 | 6.10 | +0.53 | 0.01 | ❌ IR极低 |

## 通过特征详细评估

### reversal_ratio_full — 全天价格方向反转频率

**物理含义**：全天（0930-1130 + 1300-1457, ~237 bars）中连续两个 1m return 方向改变的频率。高反转 = bid-ask bounce 频繁 = 流动性差 = 流动性溢价 → 高预期回报。

**完整评估结果（2022-01-01 ~ 2024-12-31）**：

| 指标 | Raw | Neutralized | 阈值 | 判断 |
|------|-----|-------------|------|------|
| Sharpe_abs_net | 1.09 | 1.19 | >0.9 | ✅ / ✅ |
| Long Excess Net | 1.21 | 1.22 | >0.7 | ✅ / ✅ |
| IR(LS) | 0.35 | 0.36 | >0.2 | ✅ / ✅ |
| Mono (8组) | **0.86** | 0.57 | >0.7 | **✅** / ❌ |
| 覆盖率 | ~95% | ~95% | >30% | ✅ / ✅ |
| Calmar | 0.81 | 0.94 | — | 参考 |
| 胜率 | 55.4% | 56.3% | — | 参考 |

**中性化后信号增强**：Sharpe 1.09→1.19，IR 0.35→0.36。表明 reversal_ratio 含有独立于市值/行业的信号，不是 size proxy。

**分组 Sharpe（Raw，从高到低排列）**：
| G1 | G2 | G3 | G4 | G5 | G6 | G7 | G8 |
|----|----|----|----|----|----|----|---|
| 0.91 | 0.88 | 1.05 | 0.59 | 0.45 | 0.26 | 0.11 | -0.05 |

→ 近乎完美单调递减。G1-G3 绝对 Sharpe 均 >0.88，G8 才接近零。

**年度分解**：
| 年份 | Return | Sharpe | IR(LS) |
|------|--------|--------|--------|
| 2022 | 22.7% | 1.77 | 0.38 |
| 2023 | 18.7% | 1.93 | 0.41 |
| 2024 | 2.2% | 0.13 | 0.27 |

→ 2024 年信号衰减（Sharpe 0.13），需关注是否为暂时性市场风格切换。

## 关键发现

1. **流动性溢价在 A 股日内数据上存在** — reversal_ratio_full 是本项目首个 Long Excess 达标的特征（+1.21），证实了从「价格动态」转向「流动性水平」的策略转变是正确的。

2. **全天窗口显著优于 1h 窗口** — reversal_ratio 在 0930-1030 窗口 |Sharpe| 仅 0.22，全天窗口提升到 1.09。更多 bar 数使反转频率估计更稳健，跨午休的信息也被捕捉。

3. **中性化后增强** — 不同于 BPV（中性化后大幅衰减），reversal_ratio 中性化后 Sharpe 从 1.09→1.19，说明信号独立于市值/行业暴露。

4. **经典 Roll spread (bps) 表现差** — 基于连续价格变化协方差的经典 Roll spread 在 A 股 1m 数据上 IR 仅 0.07，远不如离散化的「反转频率」。可能因为 A 股涨跌停和 T+1 导致连续价格变化的协方差结构被扭曲。

5. **roll_impact 仍是 size proxy** — 与 BPV 类似，roll_impact（spread × √volume）的高 |Sharpe| 和深度负 LE 说明它本质上在排列市值大小。

## 风险提示

- 2024 年信号显著衰减（Sharpe 0.13 vs 2022-2023 的 1.77-1.93）
- Neutral Mono = 0.57，中性化后分组单调性下降
- 日换手率 ~121%，交易成本敏感
