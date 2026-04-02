---
agent_id: "ashare_rawdata_b"
experiment_id: "#035"
direction: "D-025 (temporal_microstructure)"
feature_name: "open_gap_amihud_full"
net_sharpe: 1.80
mono_score: 0.71
status: screening_passed
submitted_at: "2026-03-26T14:00:00"
---

# D-025 Temporal Microstructure 初筛报告

## 方向假设

探索日内价格/成交量的**跨 bar 时序结构**作为新因子维度：
- 极值时点（daily high/low 出现的时间）
- 信息流 lead-lag（成交量是否领先于收益率）
- Bar 间 gap（相邻 bar open-close 差异）
- Range 动态（bar 范围收缩/扩张频率）

区别于已有方向：不是水平量/条件化（Amihud 饱和），不是单 bar 内分解（OHLC），而是 bar 间时序结构。

## 快筛结果（全市场 5013 symbols，2020-2023）

| 特征 | |LS Sharpe| | LE Sharpe | IR_LS | 判定 |
|------|-----------|----------|-------|------|
| `open_gap_amihud_full` | **1.34** | **+0.77** | **0.51** | **✅ Shortlist** |
| `volume_lead_return_freq_full` | 5.69 | -4.80 | 0.44 | ❌ 空头集中 |
| `ret_lead_volume_freq_full` | 5.63 | -4.92 | 0.46 | ❌ 空头集中 |
| `high_timing_full` | 5.20 | -2.34 | 0.23 | ❌ 空头集中 |
| `extremum_spread_full` | 4.26 | -0.79 | 0.07 | ❌ IR 极低 |
| `gap_body_ratio_full` | 0.15 | +0.50 | 0.26 | ❌ LS 极低 |
| `range_contraction_freq_full` | 1.65 | -0.19 | 0.03 | ❌ IR/LE 不达标 |
| `volume_return_lag_diff_full` | 7.18 | -0.14 | 0.29 | ❌ LE 几乎为零 |

### 失败分析

- **Lead-lag 频率特征全部空头集中**：volume_lead 和 ret_lead 均 |LS|>5 但 LE 深度负值。高频度的量价跟随事件 = 交易嘈杂 = 只识别差股票，与结论#6/#9 一致。
- **极值时点/范围特征信号极弱**：extremum_spread IR=0.07，range_contraction IR=0.03。日内极值出现时间和范围动态的截面变异不足以支撑选股。
- **gap_body_ratio LS 极低**：虽然 IR=0.26 和 LE=0.50 有潜力，但 |LS|=0.15 说明 inter-bar gap 与 intra-bar body 的比率在截面上绝对信号太弱。

## 正式评估（2020-2023，全量 5013 symbols）

### open_gap_amihud_full

**定义**: `mean(|open_i - close_{i-1}|) / mean(amount) × 1e9`

**物理含义**: 相邻 1 分钟 bar 之间的**价格间断成本**（inter-bar gap）归一化到单位交易额。高 gap = 连续竞价之间的隐式 bid-ask spread 更大 = 流动性更差 → 流动性溢价。

| 指标 | Raw | Neutral | 阈值 | 状态 |
|------|-----|---------|------|------|
| LS Sharpe | 1.34 | **1.80** | >0.9 | ✅ |
| Long Excess Sharpe | 0.77 | **1.32** | >0.7 | ✅ |
| IR(LS) | 0.51 | **0.55** | >0.2 | ✅ |
| Mono (8 组) | **0.86** | **0.71** | ≥0.7 | ✅ |
| 覆盖率 | 86.7% | 86.7% | >30% | ✅ |
| TVR | 0.75 | 0.83 | - | 适中 |

**中性化后信号增强 34%**（LS 1.34→1.80），说明 inter-bar gap 包含独立于市值/行业的流动性 alpha。

### 年度分解（Neutral）

| 年度 | Return | Sharpe | IR_LS | 判断 |
|------|--------|--------|-------|------|
| 2020 | +9.4% | 1.27 | 0.44 | ✅ 稳健 |
| 2021 | +6.8% | 0.90 | 0.45 | ✅ 边缘达标 |
| 2022 | +19.6% | 3.56 | 0.68 | ✅ 极强 |
| 2023 | +12.0% | 2.10 | 0.64 | ✅ 极强 |

**所有年份 neutral Sharpe 均为正**，且 2022-2023 显著强于 2020-2021。

### 分组单调性

**Raw Mono=0.86**: 8 组 excess return 从 Group 1 (+11.4%) 到 Group 8 (+6.2%) 基本单调递减。

**Neutral Mono=0.71**: Groups 1-5 全部 excess 为正（+7.1%~+11.4%），Groups 7-8 深度负值（-31.5%）。信号集中在空头端（高 gap 成本 = 差流动性 = 负超额），但多头端也有正 alpha。

## 关键发现

1. **Inter-bar gap 是有效的新 Amihud numerator** — 用 |open_i - close_{i-1}|（相邻 bar 间的价格间断）替代 |return|（bar 内价格变化），归一化到 amount 后仍能产生有效因子。这是 Amihud 框架的第 8 类 numerator（继 |ret|, |accel|, wick, close_disp, body, open_disp, |r_i×r_{i+1}| 之后）。

2. **时序结构因子中仅 Amihud 变体有效** — 8 个特征中唯一通过的是 Amihud 框架内的 open_gap_amihud。其余 7 个非 Amihud 时序结构特征全部失败，说明日内时序结构（极值时点、lead-lag、范围动态）本身缺乏截面选股能力。

3. **Lead-lag 频率特征重复空头集中失败模式** — vol_lead_return_freq 和 ret_lead_volume_freq 的 |LS|>5 但 LE<-4.8，与所有已知的事件频率类因子（reversal_ratio 除外）失败模式一致。

## 注意事项

- **评估仅覆盖 2020-2023**（preload 数据范围限制），2024 数据待补充
- **与已有 Amihud 因子可能高度相关**：open_gap_amihud 本质仍在 |f(price)|/amount 框架内，需与 amihud_illiq_full 等做相关性检测
- 与 CS spread（用 adjacent bar H-L decomposition 估计 bid-ask spread）可能概念相关但估计方法不同
