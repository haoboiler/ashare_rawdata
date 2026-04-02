---
agent_id: "ashare_rawdata_b"
experiment_id: "#030"
direction: "D-014 (intraday_momentum)"
feature_name: "max_drawdown_amihud_full"
net_sharpe: 1.89
mono_score: 1.00
status: screening_passed
submitted_at: "2026-03-26T12:20:00"
---

# D-014 Intraday Momentum — 回撤路径 + 影线分解最终轮 (Exp#030)

## 方向与假设

D-014 已经过 Exp#023（路径拓扑）和 Exp#029（正式评估）两轮，产出 3 个 pending 特征。本轮是**最终探索轮**，测试三个尚未尝试的角度：

1. **回撤路径 Amihud**：max_drawdown（从阶段性高点回落） vs max_excursion（从起点偏离），是不同的路径拓扑测度
2. **上/下影线分离 Amihud**：将总影线 wick_amihud 分解为上影线（被拒绝的向上探索）和下影线（被拒绝的向下探索）
3. **累积收益零穿越频率**：路径级别方向切换（区别于 bar 级别 reversal_ratio）

## 快筛结果（全市场 2020-2023，basic6）

| 特征 | |LS Sharpe| | LE | IR(LS) | 状态 |
|------|-----------|------|--------|------|
| `max_drawdown_amihud_full` | **1.89** | **+1.53** | **0.33** | ✅ shortlist |
| `drawdown_area_amihud_full` | 1.76 | +1.50 | 0.27 | ✅ shortlist |
| `max_drawup_amihud_full` | 0.96 | +1.04 | 0.24 | ✅ 边缘 |
| `upper_wick_amihud_full` | 1.26 | +0.74 | **0.46** | ✅ shortlist |
| `lower_wick_amihud_full` | 1.10 | +0.60 | 0.48 | ❌ LE<0.7 |
| `cumret_zero_cross_freq_full` | 4.60 | -0.67 | **0.005** | ❌ IR≈0 |

## 正式评估（2020-2023，含 Mono）

### max_drawdown_amihud_full

| 指标 | Raw | Neutral |
|------|-----|---------|
| LS Sharpe | 1.89 | 1.75 |
| LE Sharpe | 1.53 | 1.42 |
| IR(LS) | 0.33 | 0.49 |
| Mono | **1.00** | **0.86** |

分组 Sharpe (raw): [1.20, 1.25, 1.17, 1.01, 0.88, 0.29, -0.05, -0.19]
分组 Sharpe (neutral): [1.30, 1.12, 0.69, 0.30, 0.14, -0.10, 0.02, -0.16]

**所有阈值通过**，但无 2024 数据验证（pkl 仅 2020-2023）。

### upper_wick_amihud_full

| 指标 | Raw | Neutral |
|------|-----|---------|
| LS Sharpe | 1.26 | **2.18** |
| LE Sharpe | 0.74 | **1.37** |
| IR(LS) | 0.46 | 0.48 |
| Mono | 0.86 | 0.71 |

**中性化后大幅增强**（LS 1.26→2.18），含独立于市值/行业的信号。所有阈值通过。

## 相关性分析（关键发现）

| 对比 | 截面相关性 |
|------|-----------|
| max_drawdown_amihud vs max_excursion_amihud (pending) | **0.87** |
| max_drawdown_amihud vs batch_amihud (pending) | **0.86** |
| drawdown_area_amihud vs batch_amihud (pending) | 0.75 |
| max_drawup_amihud vs max_excursion_amihud (pending) | **0.89** |
| upper_wick_amihud vs wick_amihud (pending) | **0.98** |
| lower_wick_amihud vs wick_amihud (pending) | 0.98 |
| upper_wick vs lower_wick | 0.93 |

**结论：全部 6 个新特征均与已 pending 特征高度相关，不提供独立信号。**

## 最终诊断

### 为什么不创建 pending package

1. **max_drawdown_amihud**：虽通过所有阈值（含 Mono=1.00），但与 max_excursion_amihud 相关 0.87。两者在随机游走假设下近似等价（drawdown ≈ excursion for symmetric paths），截面排序差异仅来自少数有强趋势的股票。
2. **upper_wick_amihud**：与 wick_amihud 相关 0.98，本质相同信号。上/下影线分离未提供有意义的非对称信息（upper vs lower 相关 0.93）。
3. **drawdown_area/max_drawup/lower_wick**：同样高度冗余。
4. **cumret_zero_cross_freq**：IR=0.005，无截面选股信号。路径级零穿越频率在 A 股不构成有效因子。

### D-014 方向 exhausted 总结

D-014 intraday_momentum 经 3 轮实验（Exp#023/#029/#030），共测试 **22 个特征**：

- 通过并 pending：3 个（batch_amihud, up_amihud, max_excursion_amihud）
- 通过但冗余未 pending：4 个（vw_amihud, am/pm_amihud, max_drawdown_amihud, upper_wick_amihud）
- 失败：15 个（路径拓扑/方向性信号/频率计数/冗余变体）

**核心发现**：D-014 的所有通过特征都是 Amihud 框架（|f(price)|/amount）的变体，未产生超越已有流动性框架的新因子类别。"日内动量"概念在 A 股最终归约为"日内流动性水平"。

## 新方向建议

当前方向池已全部 exhausted/explored。建议补充以下新方向：

1. **跨日模式（overnight effects）**：隔夜收益与日内行为的交互——需要多日数据，可能需要修改 formula 框架
2. **高频波动率结构**：不同频率下的波动率分解（realized kernel, pre-averaging），可能发现独立于 Amihud 的 alpha
3. **订单簿压力代理**：利用 OHLC 隐含的订单簿信息（如 bar 内价格是否更接近 high 或 low），构建市场压力因子
