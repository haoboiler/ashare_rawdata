---
agent_id: "ashare_rawdata_a"
experiment_id: "#019"
direction: "D-004 (corwin_schultz_spread)"
feature_name: "cs_session_asymmetry_full"
net_sharpe: 0.37
mono_score: 0
status: screening_failed
submitted_at: "2026-03-26T06:12:00"
---

# D-004 CS Spread 多尺度/混合变体 — 筛选报告

## 摘要

D-004 最后一轮探索：从**数学结构**和**归一化方式**两个维度尝试拓展 CS spread，而非 Exp#018 已被否定的 bar 条件化。4 个特征全部未通过自动筛选。

**结论**：D-004 方向确认 exhausted。三轮实验（#006/#018/#019），共 14 个特征，仅 Exp#006 的原始 cs_spread_full 和 cs_relative_spread_full 通过。

## 假设

1. **多尺度假设**：将 1m bars 聚合到 5m 分辨率再做 CS 分解，1m/5m 比值捕捉流动性的尺度结构
2. **混合假设**：CS spread × price / amount 归一化到单位交易额，结合结构性流动性（CS spread）与交易活跃度（amount）
3. **时间结构假设**：上午/下午 CS spread 比值捕捉日内流动性动态（信息不对称的时间分布）

## 快筛结果（全市场 2020-2023，basic6）

| 特征 | |LS Sharpe| | LE Net Sharpe | IR(LS) | 覆盖率 | 状态 |
|------|-----------|---------------|--------|--------|------|
| `cs_5m_spread_full` | 0.75 | -0.28 | 0.24 | 86.7% | ❌ LS+LE |
| `cs_multiscale_ratio_full` | 1.91 | +0.11 | 0.23 | 49.6% | ❌ LE 空头端 |
| `cs_spread_per_amount_full` | 0.37 | +0.68 | 0.34 | 86.7% | ❌ LS 太低 |
| `cs_session_asymmetry_full` | 2.12 | +0.05 | 0.20 | 49.2% | ❌ LE 空头端 |

阈值：LS > 0.9, LE > 0.7, IR > 0.2

## 失败诊断

### cs_5m_spread_full
- **假设**：5m 聚合后 CS 分解捕捉更长时间尺度的流动性
- **实际**：LS=0.75 方向反向，LE=-0.28
- **诊断**：5m 聚合的 H-L range 包含了更多真实价格波动，CS 分解的 "spread" 成分被波动率污染。与结论#22（直接 HL range 是波动率代理）一致——增大 bar 窗口等于增大 HL range 中的波动率权重
- **结论**：CS spread 的有效性依赖于 1m 级别相邻 bar 的微小 H-L 差分，聚合破坏了这一特性

### cs_multiscale_ratio_full
- **假设**：1m/5m CS spread 比值反映流动性尺度结构
- **实际**：|LS|=1.91 但 LE=+0.11，经典空头端集中
- **诊断**：比值高的股票 = 1m 微观结构噪声大 → 高波动小盘股的典型特征。实质上是另一种波动率/市值代理
- **结论**：尺度比率不包含独立的流动性信息

### cs_spread_per_amount_full
- **假设**：spread/amount 混合指标，类似 Amihud 但用 CS spread 替代 |return|
- **实际**：LS=0.37, LE=+0.68, IR=0.34
- **诊断**：LE 接近阈值（0.68 vs 0.70），说明 amount 归一化确实引入了一些长端 alpha。但 LS 过低，因为 CS spread 和 amount 在截面上的协方差压缩了 long-short 信号
- **结论**：与 amihud_illiq_full (LS=2.37, LE=1.79) 相比完全冗余——Amihud 用 |return|/amount 更直接

### cs_session_asymmetry_full
- **假设**：上午/下午 CS spread 比值捕捉日内信息分布
- **实际**：|LS|=2.12 但 LE=+0.05，覆盖率仅 49.2%
- **诊断**：(1) 覆盖率低：~50% 股票下午 CS spread ≈ 0，比值无法计算；(2) 空头端集中：session 非对称性极端的股票 = 某一时段流动性极差 → 与结论#8（日内分布截面区分度不足）一致
- **结论**：日内 CS spread 的时间变化模式在个股间差异不足以支撑选股

## D-004 方向总结

| 实验 | 测试数 | 通过数 | 特征 |
|------|--------|--------|------|
| Exp#006 原始 CS | 5 | 2 | cs_relative_spread_full ✅, cs_spread_full ✅ |
| Exp#018 条件化 | 5 | 0 | 条件化不可迁移（结论#39） |
| Exp#019 多尺度 | 4 | 0 | 结构修改无效 |
| **合计** | **14** | **2** | |

**建议**：将 D-004 标记为 exhausted。CS spread 的有效信号仅存在于原始全天平均值和相对值，所有变体（条件化/多尺度/混合/时间结构）均不产生增量 alpha。

## 新结论

40. **CS spread 的有效信号仅限原始均值——结构修改无效** — 多尺度（5m 聚合）、尺度比率（1m/5m）、amount 归一化、session 非对称性四个维度全部失败。5m 聚合破坏了 CS 的微结构分解有效性（与结论#22 一致）；尺度比率和 session 比率都退化为波动率/市值代理；spread/amount 混合则完全被 Amihud 覆盖。D-004 三轮 14 特征仅 2 通过，方向确认 exhausted。（Exp#019）
