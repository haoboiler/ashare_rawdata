---
agent_id: "ashare_rawdata_b"
experiment_id: "#031"
direction: "D-022 (microstructure_noise)"
feature_name: "excess_bounce_amihud_full"
net_sharpe: 1.29
mono_score: 0.86
status: screening_passed
submitted_at: "2026-03-26T13:20:00"
---

# D-022 微观结构噪声 — 全市场筛选报告

## 方向概述

**假设**：通过比较不同时间尺度的已实现方差（RV_1min vs RV_5min/10min），衡量日内价格中的微观结构噪声（bid-ask bounce）。Amount 归一化后转化为"每单位交易的噪声成本"。

**理论基础**：D-003 variance_ratio 测试了收益率自相关但因 Long Excess 失败（alpha 集中在空头端）。结论#48 证明 amount 归一化可以挽救失败的价格指标。本方向验证 amount 归一化能否挽救 variance_ratio/autocovariance 信号。

## 快筛结果（2020-2023, 全市场 5013 股）

### 第一轮：基础噪声指标

| 特征 | |LS Sharpe| | IR | LE | 状态 |
|------|-----------|------|------|------|
| high_vol_noise_amihud_full | 4.90 | 0.13 | -0.05 | ❌ 空头端集中 |
| noise_ratio_10_full | 1.90 | 0.28 | 0.26 | ❌ LE 不达标 |
| noise_ratio_5_full | 1.40 | 0.32 | 0.35 | ❌ LE 不达标 |
| noise_amihud_10_full | 0.70 | 0.30 | 1.06 | ❌ LS 不达标 |
| autocov_amihud_full | 0.55 | 0.28 | 0.99 | ❌ LS 不达标 |
| noise_amihud_5_full | 0.36 | 0.33 | 1.10 | ❌ LS 不达标 |

**关键发现**：amount 归一化确实挽救了 Long Excess（noise_amihud LE=1.06-1.10 vs 原始 noise_ratio LE=0.26-0.35），但 LS Sharpe 过低。

### 第二轮：噪声-流动性交互项

| 特征 | |LS Sharpe| | IR | LE | 状态 |
|------|-----------|------|------|------|
| **excess_bounce_amihud_full** | **1.50** | **0.38** | **1.26** | **✅ 全通过** |
| **bar_pair_noise_amihud_full** | **1.10** | **0.23** | **1.07** | **✅ 全通过** |
| high_vol_autocov_amihud_full | 0.75 | 0.19 | 0.21 | ❌ |
| neg_autocov_amihud_full | 0.60 | 0.39 | 1.15 | ❌ LS 不达标 |
| noise_amihud_product_full | 0.52 | 0.42 | 1.19 | ❌ LS 不达标 |
| noise_depth_full | 0.13 | 0.43 | 1.31 | ❌ LS 不达标 |

## 正式评估结果（2020-2023, 含中性化 + 分组回测）

**注意**：当前 preload 仅覆盖 2020-2023，2024 数据待串行计算完成后补充评估。

### excess_bounce_amihud_full

定义：Amihud 仅在 bounce bar（下一根 bar 方向反转）上计算。mean(|r_i|/amount_{i+1}) on bars where r_i×r_{i+1} < 0。

| 指标 | Raw (w0) | Neutral (w1) | 阈值 | 状态 |
|------|---------|-------------|------|------|
| |LS Sharpe| | 1.50 | 1.29 | > 0.9 | ✅ |
| IR(LS) | 0.38 | **0.44** | > 0.2 | ✅ |
| Long Excess | 1.26 | **1.43** | > 0.7 | ✅ |
| Mono | 0.86 | 0.86 | > 0.7 | ✅ |
| Coverage | 0.86 | - | > 0.30 | ✅ |
| TVR | 0.98 | 0.84 | - | 适中 |

年度分解（neutral）：
- 2020: Sharpe=-0.20, IR=0.29
- 2021: Sharpe=1.33, IR=0.46
- 2022: Sharpe=3.00, IR=0.55
- 2023: Sharpe=1.73, IR=0.49

### bar_pair_noise_amihud_full

定义：连续收益率乘积的 amount 归一化。mean(|r_i×r_{i+1}|/avg(amount_i, amount_{i+1}))×1e18。衡量微观结构噪声（bid-ask bounce 的量级）per unit of trading。

| 指标 | Raw (w0) | Neutral (w1) | 阈值 | 状态 |
|------|---------|-------------|------|------|
| |LS Sharpe| | 1.10 | **0.91** | > 0.9 | ✅ (边缘) |
| IR(LS) | 0.23 | **0.31** | > 0.2 | ✅ |
| Long Excess | 1.07 | **1.23** | > 0.7 | ✅ |
| Mono | **1.00** | 0.86 | > 0.7 | ✅ |
| Coverage | 0.87 | - | > 0.30 | ✅ |
| TVR | 0.96 | 0.93 | - | 适中 |

年度分解（neutral）：
- 2020: Sharpe=-0.27, IR=0.17
- 2021: Sharpe=0.66, IR=0.31
- 2022: Sharpe=3.12, IR=0.45
- 2023: Sharpe=1.00, IR=0.37

## 相关性检测（参考）

| 因子对 | 均值 | 中位数 |
|--------|------|--------|
| excess_bounce vs amihud_illiq | 0.83 | **0.89** |
| excess_bounce vs reversal_amihud | 0.73 | 0.82 |
| bar_pair_noise vs amihud_illiq | 0.74 | 0.81 |
| bar_pair_noise vs reversal_amihud | 0.77 | 0.81 |
| excess_bounce vs bar_pair_noise | 0.73 | 0.80 |

**注意**：excess_bounce_amihud 与 amihud_illiq 中位数相关 0.89，本质上是 Amihud 在 bounce bar 条件下的变体。bar_pair_noise_amihud 更独立（与 amihud_illiq 中位数相关 0.81），概念上是全新的。

## 方向关键结论

1. **Amount 归一化成功挽救了 variance_ratio/autocovariance 信号的 Long Excess** — 原始噪声比率 LE=0.26 → amount 归一化后 LE=1.06-1.10。结论#48 再次验证。
2. **Bar-pair 级别归一化优于聚合级别** — bar_pair_noise_amihud（per-pair 归一化，|LS|=1.10）vs autocov_amihud（聚合级别归一化，|LS|=0.55）。与标准 Amihud 的经验一致（per-bar 归一化优于 batch 聚合）。
3. **Bounce 条件 Amihud 是第 9 种有效的事件选择器** — 继 high-vol/reversal/extreme-ret/accel/concordant/discordant/down/doji 之后，bounce（前向反转）也是有效条件。但与 reversal_amihud（后向反转）相关 0.82。
4. **连续收益率乘积是新的 Amihud numerator 维度** — |r_i×r_{i+1}|/amount 衡量"微观结构噪声成本"，是继 |ret|、|accel|、wick、close_disp 之后的第 5 类独立 numerator。

## 待审批特征

1. **excess_bounce_amihud_full** — w1 Sharpe=1.29, LE=1.43, IR=0.44, Mono=0.86
   - 风险：与 amihud_illiq 中位数相关 0.89
2. **bar_pair_noise_amihud_full** — w1 Sharpe=0.91(边缘), LE=1.23, IR=0.31, Mono=0.86
   - 更独立，概念创新性更强
