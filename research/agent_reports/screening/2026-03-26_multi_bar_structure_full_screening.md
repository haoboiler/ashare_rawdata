---
agent_id: "ashare_rawdata_a"
experiment_id: "#032"
direction: "D-023 (multi_bar_price_structure)"
feature_name: "high_vol_inside_amihud_full"
net_sharpe: 1.35
mono_score: 0.86
status: screening_passed
submitted_at: "2026-03-26T13:10:00"
---

# D-023 Multi-Bar Price Structure 筛选报告

## 方向概述

**物理假设**：相邻 bar 的价格范围包含关系（inside bar = 盘整压缩，engulfing = 范围扩张）是离散化的微结构事件。inside bar 频率衡量订单簿对价格的约束强度（流动性质量），inside bar 条件 Amihud 衡量盘整期流动性成本。

**创新点**：
- 首次使用多 bar 结构模式（range 包含/突破）作为 Amihud 事件选择器
- 与已有单 bar 属性条件（high-vol, reversal, extreme, doji）正交的新维度
- 离散计数框架（proven）+ Amihud 框架（proven）的新组合

## 快筛结果（2020-2023, 全市场 5013 stocks）

| 特征 | |LS Sharpe| | LE Sharpe | IR_LS | 状态 |
|------|-----------|-----------|-------|------|
| inside_bar_freq_full | 0.85 | 0.99 | 0.27 | borderline (LS<0.9) |
| engulfing_freq_full | 0.83 | 1.01 | 0.27 | borderline (LS<0.9) |
| inside_bar_amihud_full | 1.55 | 1.26 | 0.40 | ✅ |
| **high_vol_inside_amihud_full** | **1.76** | **1.51** | 0.39 | ✅ |
| engulfing_amihud_full | 1.46 | 1.25 | 0.38 | ✅ |

## 正式评估结果（2020-2023, raw + neutral）

### 通过筛选的特征

#### 1. high_vol_inside_amihud_full（最优）
- **定义**：mean(|ret|/amount) on inside bars with volume > median
- **经济含义**：高活跃度盘整期间的价格冲击成本（大量交易但价格被约束在上一 bar 范围内）

| 指标 | Raw | Neutral | 阈值 |
|------|-----|---------|------|
| |LS Sharpe| | 1.76 | 1.35 | > 0.9 ✅ |
| LE Sharpe | 1.51 | 1.41 | > 0.7 ✅ |
| IR_LS | 0.39 | 0.47 | > 0.2 ✅ |
| Mono | 1.00 | 0.86 | > 0.7 ✅ |
| Coverage | 85.6% | - | > 30% ✅ |

**特性**：中性化后 IR 从 0.39→0.47（+20%），信号含独立于市值/行业的 alpha。raw Mono=1.00 完美单调。

#### 2. inside_bar_amihud_full
- **定义**：mean(|ret|/amount) on inside bars（不限 volume）
- **经济含义**：盘整期（价格范围被包含）的平均流动性成本

| 指标 | Raw | Neutral | 阈值 |
|------|-----|---------|------|
| |LS Sharpe| | 1.55 | 1.35 | > 0.9 ✅ |
| LE Sharpe | 1.26 | 1.44 | > 0.7 ✅ |
| IR_LS | 0.40 | 0.46 | > 0.2 ✅ |
| Mono | 0.86 | 0.86 | > 0.7 ✅ |

**特性**：中性化后 LE 从 1.26→1.44（+14%），市值中性化后多头端更强。

#### 3. engulfing_amihud_full
- **定义**：mean(|ret|/amount) on engulfing bars（当前 bar range 包含上一 bar）
- **经济含义**：范围突破期的价格冲击成本

| 指标 | Raw | Neutral | 阈值 |
|------|-----|---------|------|
| |LS Sharpe| | 1.46 | 1.23 | > 0.9 ✅ |
| LE Sharpe | 1.25 | 1.43 | > 0.7 ✅ |
| IR_LS | 0.38 | 0.45 | > 0.2 ✅ |
| Mono | 0.86 | 0.71 | > 0.7 ✅ |

**特性**：engulfing 条件与 inside 条件是互补视角（扩张 vs 压缩），但 Amihud 信号相似，预计两者截面高度相关。

### 未通过但有参考价值的特征

#### inside_bar_freq_full / engulfing_freq_full（borderline）
- LS Sharpe 0.83-0.88 略低于 0.9 阈值
- 但 LE 达标（0.99-1.02）、IR 达标（0.27）、Mono 极高（0.86-1.00）
- 两者几乎完全镜像（反相关），实为同一信号
- 中性化后 LS 从 0.85→0.88（微弱增强），但仍不足 0.9
- 这是**非 Amihud 框架**下的流动性质量代理，频率类指标 LS 强度天然低于 Amihud

## 关键发现

1. **Multi-bar 结构模式是 Amihud 框架的有效新事件选择器** — inside bar（range 包含）和 engulfing bar（range 扩张）作为条件选择 bar 后计算 Amihud，3 个变体全部通过筛选（LS 1.23-1.76, LE 1.25-1.51）。这是继 high-vol / reversal / extreme-ret / accel / concordant-discordant / doji / VWAP-cross 之后的第 9-10 种条件 Amihud 事件选择器。

2. **频率指标（离散计数）在多 bar 结构维度信号弱于 Amihud** — inside_bar_freq/engulfing_freq 虽然 Mono 极高（0.86-1.00）且 LE 达标（~1.0），但 LS 仅 0.83-0.88。与 reversal_ratio（LS 1.09）和 vol_regime_transitions（LS 0.94）相比，结构模式频率的截面区分度较弱。

3. **高量+结构双条件再次产生最强信号** — high_vol_inside_amihud（raw Mono=1.00, neutral IR=0.47）是本方向最优特征，与 high_vol_illiq（结论#21）、high_vol_reversal_amihud（结论#25）的模式一致：高量过滤消除安静期噪声，提升排序纯度。

4. **inside 和 engulfing 条件 Amihud 预计高度相关** — 因为两者本质都在不同 bar 集上计算同一 Amihud 公式，且 inside bars 和 engulfing bars 是互补集（加上 partial overlap），截面排序差异有限。

## Pending 特征

- `research/pending-rawdata/high_vol_inside_amihud_full/`
- `research/pending-rawdata/inside_bar_amihud_full/`
- `research/pending-rawdata/engulfing_amihud_full/`

## 评估产出

- pkl: `.claude-output/analysis/multi_bar_structure/`
- 评估报告: `.claude-output/evaluations/multi_bar_structure/`
