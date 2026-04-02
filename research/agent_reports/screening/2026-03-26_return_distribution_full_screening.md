---
agent_id: "ashare_rawdata_a"
experiment_id: "#023"
direction: "D-015 (return_distribution)"
feature_name: "return_kurtosis_full"
net_sharpe: 9.38
mono_score: 0.29
status: screening_failed
submitted_at: "2026-03-26T09:10:00"
---

# D-015 Return Distribution 全面筛选报告

## 方向概述

**假设**：日内 1 分钟收益率分布的高阶矩（偏度、峰度、尾部结构）反映个股的微观结构风险特征，负偏度/高峰度股票携带不同的风险溢价。

**方法**：两轮迭代，分别使用连续分布矩和离散频率型度量。

## 第一轮：连续分布矩（5 特征）

### Bundle: return_distribution_full

| 特征 | |LS Sharpe| raw | |LS Sharpe| neutral | |IR| neutral | Mono raw | Mono neutral |
|------|---------------|---------------------|-------------|----------|--------------|
| return_kurtosis_full | 11.55 | **9.38** | **0.53** | 0.14 | 0.29 |
| return_skewness_full | 10.30 | **9.43** | **0.33** | 0.00 | 0.14 |
| tail_asymmetry_full | 5.97 | **6.50** | **0.31** | 0.14 | **0.57** |
| downside_deviation_ratio_full | 4.01 | — | 0.07 | — | — |
| amihud_skew_interaction_full | 6.28 | — | 0.04 | — | — |

**诊断**：
- 信号极强（|LS Sharpe|>9），IR 中性化后增强（0.44→0.53），确认存在独立于市值/行业的信号
- 但 Mono 极低（0.00~0.29 neutral），信号集中在极端低峰度/低偏度尾部
- 分组分析显示 Group 1（极端低值）sharpe=-6.43，其余组 sharpe 在 -0.14~-3.24 之间几乎平坦
- 这是"尾部驱动"模式：因子加权放大极端值，但截面排序能力缺失

## 第二轮迭代：离散频率型（5 特征）

**迭代假设**：将连续分布矩转换为离散计数（极端收益出现频率），遵循 reversal_ratio/regime_transitions 的成功范式。

### Bundle: return_extremes_full

| 特征 | |LS Sharpe| raw | |LS Sharpe| neutral | |IR| neutral | Mono raw | Mono neutral |
|------|---------------|---------------------|-------------|----------|--------------|
| positive_extreme_freq_full | 4.33 | **4.59** | **0.24** | 0.43 | 0.43 |
| extreme_volume_ratio_full | 4.18 | **5.35** | **0.31** | 0.43 | 0.29 |
| extreme_asymmetry_freq_full | 4.44 | — | 0.15 | — | — |
| extreme_return_freq_full | 3.68 | — | 0.20 | — | — |
| extreme_amihud_ratio_full | 2.40 | — | 0.09 | — | — |

**诊断**：
- 离散化后信号减弱（|LS| 从 11→4），Mono 从 0.29 改善到 0.43，但仍远低于 0.7
- 分组分析显示 U 型模式（极高和极低都表现相对较好）
- 覆盖率从 86.4% 降至 66.8%（部分股票极端收益过少）

## 根本原因分析

日内收益分布形态在 A 股截面上呈 **非线性/U 型关系**：

1. **极端分布的股票**（极高/极低峰度、偏度）都是"异常股"，但这种异常不具备单调排序能力
2. 中性化后 IR 增强说明信号独立于 size/industry，但非线性结构无法被线性因子排序捕捉
3. 无论用连续矩还是离散频率，本质都测量同一个"分布形态"维度

**与已有结论的关系**：
- 结论#4："A 股日内因子的 alpha 常集中在空头端" — 收益分布因子同样如此
- 结论#16："离散化 >> 连续分布统计" — 在分布矩维度上不成立，离散化仅带来边际改善

## 方向结论

D-015 return_distribution **已确认 exhausted**：
- 2 轮迭代，10 个特征，5 个正式评估
- 最佳 Mono = 0.57（tail_asymmetry neutral），但对应 |IR|=0.31 也仅勉强达标
- 收益分布形态不是 A 股日频有效的截面排序维度

## 新结论

23. **日内收益分布矩信号极强但非单调** — return_kurtosis |LS Sharpe|=11.55, |IR|=0.53（neutral 后增强），但 Mono=0.14~0.29。信号集中在极端低峰度/低偏度尾部（Group 1 sharpe=-6.43 vs 其余 -0.14~-3.24），无法创造单调排序关系。（Exp#023）

24. **离散化对分布矩维度仅有边际改善** — 与结论#16（volume regime transitions >> volume entropy）不同，将连续分布矩转为离散极端频率后，Mono 仅从 0.29→0.43，仍远低于 0.7。分布矩维度的非线性/U 型本质无法通过离散化克服。（Exp#023）
