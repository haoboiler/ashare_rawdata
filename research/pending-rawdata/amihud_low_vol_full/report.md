---
agent_id: "ashare_rawdata_a"
experiment_id: "#015"
direction: "D-006 (high_volume_ratio)"
feature_name: "amihud_vol_accel_full"
net_sharpe: 1.53
mono_score: 0.86
status: screening_passed
submitted_at: "2026-03-26T04:10:00"
---

# D-006 Exp#015: Amihud 条件化变体 — 全天窗口筛选报告

## 研究背景

D-006 方向（high_volume_ratio）经过 4 轮实验（#008/#010/#012/#014），已通过 5 个 Amihud 条件化特征。上轮建议方向接近饱和。本轮作为最后一次系统性探索，设计了 5 个新的条件化/聚合方式。

## 假设

D-006 成功的核心模式是"通过不同 bar 选择条件测量 Amihud 水平量"。本轮探索 3 个新维度：
1. **量增条件**：仅在 volume 上升的 bar 上计算 Amihud（reactive liquidity）
2. **低量条件**：仅在低量 bar 上计算（quiet-period structural cost，high_vol_illiq 的补集）
3. **收益率加权**：用 |r| 作为连续权重代替离散条件（与 extreme_amihud 的离散阈值不同）
4. **Herfindahl 集中度**：Amihud 的 HHI（分布集中性度量）
5. **变异系数**：Amihud 的 CV（执行成本不确定性）

## 快筛结果（evolve, 全市场 2020-2023, basic6）

| 特征 | |LS Sharpe| | LE Sharpe | IR | 状态 |
|------|-----------|-----------|-----|------|
| amihud_vol_accel_full | 1.71 | 1.41 | 0.36 | shortlist |
| amihud_low_vol_full | 1.61 | 1.23 | 0.37 | shortlist |
| amihud_return_weighted_full | 1.55 | 1.21 | 0.39 | shortlist |
| amihud_hhi_full | 0.69 | -0.51 | 0.38 | LE 负值 |
| amihud_cv_full | 0.01 | 0.16 | 0.38 | 无信号 |

## 正式评估结果（w1, 2020-2023, neutralize）

### amihud_vol_accel_full

| 指标 | raw | neutral |
|------|-----|---------|
| LS Sharpe | 1.71 | **1.53** |
| LE Sharpe | 1.41 | **1.40** |
| IR(LS) | 0.36 | **0.43** |
| IC(LS) | 0.047 | 0.055 |
| Mono (8 groups) | **1.00** | **0.86** |

**物理解释**: 量增 bar = 新需求涌入期。此时的价格冲击成本（|r|/amount）反映了市场在面对需求激增时的流动性吸收能力。高值 = 市场无法有效消化突发需求 = 非流动性溢价。

**信号特征**: neutral 后 IR 从 0.36→0.43 增强，说明信号独立于市值/行业。raw Mono=1.00 完美单调，neutral 后仍 0.86。

### amihud_low_vol_full

| 指标 | raw | neutral |
|------|-----|---------|
| LS Sharpe | 1.61 | **1.53** |
| LE Sharpe | 1.23 | **1.45** |
| IR(LS) | 0.37 | **0.44** |
| IC(LS) | 0.050 | 0.056 |
| Mono (8 groups) | 0.86 | **0.71** |

**物理解释**: 低量 bar（bottom-25%）= 市场安静期。此时的 Amihud 反映了结构性基线非流动性，而非活跃交易期的临时冲击。high_vol_illiq 的互补信号。

**信号特征**: neutral 后 LE 从 1.23→1.45 显著增强。Mono 刚达阈值（0.71）。

### amihud_return_weighted_full

| 指标 | raw | neutral |
|------|-----|---------|
| LS Sharpe | 1.55 | **1.47** |
| LE Sharpe | 1.21 | **1.43** |
| IR(LS) | 0.39 | **0.45** |
| IC(LS) | 0.052 | 0.058 |
| Mono (8 groups) | 0.86 | **0.71** |

**物理解释**: 用 |r| 作为连续权重，大波动 bar 贡献更多。与 extreme_amihud（离散阈值 |r|>2×median）不同，这是平滑加权。IR=0.45 是本 bundle 中最高的。

**信号特征**: neutral 后 IR 从 0.39→0.45，IC 从 0.052→0.058，信号含独立 alpha。Mono 刚达阈值（0.71）。

## 失败特征诊断

### amihud_hhi_full ❌
- **假设**: Amihud 的 Herfindahl 集中度反映"闪崩非流动性"事件频率
- **结果**: |LS Sharpe|=0.69, LE=-0.51
- **诊断**: LE 为负说明 alpha 集中在空头端。HHI 高 = 非流动性集中在少数 bar = 极端事件多。这实质是识别"有极端事件的坏股票"，与结论#6（价格动态因子系统性失败在 LE）一致。分布集中度是分布形状统计量，与 tail_ratio（Exp#014）的失败模式相同。

### amihud_cv_full ❌
- **假设**: Amihud 的变异系数度量执行成本不确定性
- **结果**: |LS Sharpe|=0.01, LE=0.16
- **诊断**: 几乎无信号。IC 存在（IR=0.38）但 Sharpe≈0 说明因子值高度不稳定（高换手率 day_tvr=1.54 证实）。CV 是无量纲比率，消除了 Amihud 水平量信息，仅保留离散度。与 amihud_tail_ratio（Exp#014）同属分布形状统计量，再次确认：Amihud 的水平量有效，分布形状无效。

## 关键发现

1. **Amihud 水平量的条件化空间已接近饱和** — 3 个新条件（量增/低量/收益加权）全部通过，但预计与已有 5 个 Amihud 特征高度相关
2. **分布形状统计量再次失败** — HHI 和 CV 都是 Amihud 分布的形状度量，与 Exp#014 的 tail_ratio/autocorr 失败模式一致。结论：Amihud 的有效信号仅在水平量维度
3. **连续加权 vs 离散条件均有效** — return_weighted（连续）和 vol_accel（半离散）都通过，说明信号不依赖于特定的条件化方式
4. **建议方向 D-006 正式标记为 exhausted** — 经 5 轮实验、25 个特征测试、8 个通过，Amihud 条件化的所有合理角度已穷尽

## 数据说明

- 当前评估仅覆盖 2020-2023（preload 窗口限制），2024 年数据待补
- 结论#14 提到 2024 年日内流动性因子 neutral 信号普遍衰减，新特征需关注
