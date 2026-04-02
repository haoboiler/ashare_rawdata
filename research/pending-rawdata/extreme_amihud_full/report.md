---
agent_id: "ashare_rawdata_b"
experiment_id: "#012"
direction: "D-007 (realized_quarticity)"
feature_name: "extreme_amihud_full"
net_sharpe: 1.47
mono_score: 0.86
status: screening_passed
submitted_at: "2026-03-26T03:20:00"
---

# D-007 Realized Quarticity 全天窗口筛选报告

**Agent**: ashare_rawdata_b | **日期**: 2026-03-26 | **方向**: D-007 realized_quarticity

## 研究背景

连续 2 轮失败（D-005 volume_entropy + D-012 time_segmented_momentum）后，反思指出需回到**流动性水平**因子方向。D-007 原始定义为"四阶矩/尾部风险"，属价格动态类因子，预期纯 quarticity 会像 BPV 一样成为波动率/市值代理。

**策略调整**：将 quarticity **重新框架为流动性指标**，用 amount 归一化、引入离散化变体。

## 物理假设

极端收益 bar 上的价格冲击（|return|/amount）衡量市场在压力下吸收冲击的能力。如果一只股票在极端收益 bar 上的 Amihud 非流动性指标更高，说明即使少量交易也能导致大幅价格变动 → 差流动性。

本质上是 **条件 Amihud**：不是对所有 bar 计算 |r|/amount，而是只对 |r| > 2×median(|r|) 的极端 bar 计算。

## 快筛结果（8 特征，全市场 2020-2023）

| 特征 | |LS Sharpe| | LE Sharpe | |IR| | 状态 |
|------|-----------|-----------|------|------|
| realized_quarticity_full | 10.76 | -10.63 | 0.625 | ❌ 波动率代理 |
| amihud_quarticity_full | 1.21 | -0.45 | 0.001 | ❌ r^4 权重过大 |
| kurtosis_ratio_full | 11.61 | -7.33 | 0.446 | ❌ 波动率代理 |
| extreme_bar_ratio_full | 4.18 | +0.38 | 0.120 | ❌ IR 不足 |
| **extreme_amihud_full** | **1.47** | **+1.19** | **0.390** | **✅ 通过** |
| extreme_amihud_ratio_full | 4.12 | -0.81 | 0.065 | ❌ 信号弱 |
| quarticity_concentration_full | 8.93 | -2.54 | 0.477 | ❌ LE 深负 |
| tail_volume_share_full | 6.95 | -1.36 | 0.087 | ❌ LE 负 |

**关键发现**：8 个特征中，7 个确认纯 quarticity 是波动率代理（结论#5/#6），唯一通过的 extreme_amihud_full 本质是**条件流动性指标**。

## extreme_amihud_full 正式评估（2020-2023，w1）

### Raw

| 指标 | 值 | 阈值 | 状态 |
|------|------|------|------|
| LS Sharpe | 1.47 | > 0.9 | ✅ |
| IR(LS) | 0.39 | > 0.2 | ✅ |
| LE Net Sharpe | 1.19 | > 0.7 | ✅ |
| Mono (8组) | 0.86 | > 0.7 | ✅ |
| Coverage | 86.7% | > 30% | ✅ |

### Neutralized (行业 + 市值)

| 指标 | 值 | 阈值 | 状态 |
|------|------|------|------|
| LS Sharpe | 1.26 | > 0.9 | ✅ |
| IR(LS) | 0.45 | > 0.2 | ✅ |
| LE Net Sharpe | 1.36 | > 0.7 | ✅ |
| Mono (8组) | 0.71 | > 0.7 | ✅ (边缘) |
| Coverage | 86.7% | > 30% | ✅ |

### 年度表现

| 年份 | Raw Return | Raw Sharpe | Neutral Return | Neutral Sharpe |
|------|-----------|------------|----------------|----------------|
| 2020 | -12.41% | -0.90 | +0.03% | 0.00 |
| 2021 | +17.41% | 1.29 | +10.24% | 1.06 |
| 2022 | +35.66% | 3.59 | +25.00% | 3.15 |
| 2023 | +28.33% | 3.23 | +13.86% | 1.72 |

## 分组详情

### Raw Mono = 0.86（优秀）

| 组 | Sharpe | Annual Return | Excess Return |
|----|--------|--------------|---------------|
| G1 (高 extreme_amihud) | 0.93 | 13.3% | 15.6% |
| G2 | 1.16 | 14.4% | 17.8% |
| G3 | 0.94 | 10.7% | 14.4% |
| G4 | 0.83 | 8.8% | 12.7% |
| G5 | 0.52 | 5.1% | 9.1% |
| G6 | 0.47 | 4.2% | 8.3% |
| G7 | 0.30 | 2.6% | 6.7% |
| G8 (低 extreme_amihud) | 0.26 | 2.1% | 6.2% |

### Neutral Mono = 0.71（边缘通过）

G6 (-3.2%) 低于 G7/G8，说明中性化后信号集中在极端标的。

## 物理解释

extreme_amihud_full 衡量**极端收益事件期间的价格冲击**：
- 高值 = 少量交易即引发大幅波动 → 差流动性，但也意味着**市场对该股票极端事件的定价不充分**
- 做多高 extreme_amihud 股票获得**流动性溢价** + **错误定价补偿**
- 与 high_vol_illiq_full（条件于高成交量）互补：一个从收益极端性条件化，一个从成交量条件化

## 与已有 Pending 因子的关系

| 因子 | 条件化维度 | 估计方法 |
|------|-----------|---------|
| amihud_illiq_full | 全 bar | |r|/amount |
| high_vol_illiq_full | 高成交量 bar | |r|/amount |
| **extreme_amihud_full** | **极端收益 bar** | **|r|/amount** |

三者使用相同的 Amihud 度量但在不同条件下计算，可能存在中等相关性。最终是否入库需用户审批时判断。

## 注意事项

1. **数据仅覆盖 2020-2023**（preload 窗口），2024 segment 未评估
2. Neutral Mono = 0.71 边缘达标，若 2024 数据拉低可能不达标
3. 2020 年 raw 表现为负 (-0.90 Sharpe)，可能与疫情冲击下极端事件频率异常有关
4. 与 amihud_illiq_full / high_vol_illiq_full 可能高度相关，需相关性检测确认

## 结论

extreme_amihud_full **通过全部自动筛选阈值**（raw + neutral），进入 pending 审批。
