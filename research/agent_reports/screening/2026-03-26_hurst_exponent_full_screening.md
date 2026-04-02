---
agent_id: "ashare_rawdata_a"
experiment_id: "#020"
direction: "D-010 (hurst_exponent)"
feature_name: "vol_roughness_full"
net_sharpe: 1.42
mono_score: 0.71
status: screening_passed
submitted_at: "2026-03-26T07:30:00"
---

# D-010 Hurst Exponent 方向筛选报告

**Agent**: ashare_rawdata_a | **Experiment**: #020 | **日期**: 2026-03-26

## 研究假设

Hurst exponent 衡量时间序列的长记忆性/持续性。研究方向分两个维度：
1. **R/S Hurst** 对不同输入（volume/return/amount/bar range）计算持续性指数
2. **路径粗糙度** 和 **方差比** 作为 Hurst 的简化替代指标

核心假设：volume 路径粗糙度高（成交量 bar 间变化剧烈）→ 交易行为不可预测 → 执行成本不确定性高 → 流动性溢价。

## 快筛结果（全市场 5013 stocks, 2020-2023）

| 特征 | LS Sharpe | LE Sharpe | IR | 判断 |
|------|-----------|-----------|-----|------|
| `hurst_volume_full` | -4.97 | -2.93 | -0.47 | ❌ 反向，空头端集中 |
| `hurst_return_full` | -3.90 | -1.43 | -0.24 | ❌ 反向 |
| `hurst_amount_full` | -4.97 | -2.93 | -0.47 | ❌ ≈hurst_volume |
| `hurst_range_full` | -5.69 | -3.22 | -0.41 | ❌ 反向，波动率代理 |
| **`vol_roughness_full`** | **+1.64** | **+1.17** | **+0.55** | **✅ 全部通过** |
| `vol_var_ratio_full` | -5.64 | -4.11 | -0.67 | ❌ 反向 |

## Shortlist: vol_roughness_full 正式评估（2020-2024, 1211 dates × 5191 symbols）

### 定义

`vol_roughness_full = mean(|volume[i+1] - volume[i]|) / mean(volume)`

全天窗口 (09:30-11:30, 13:00-14:57)，~237 bars 计算连续 bar 间成交量绝对变化的均值，除以日内平均成交量。

### 物理含义

高 vol_roughness = 成交量在分钟级频繁大幅波动 = 交易活动不稳定 = 执行环境不可预测。投资者面临更高的执行成本不确定性，因此要求更高的回报作为补偿（流动性不确定性溢价）。

与 `amihud_diff_mean_full`（已通过，Exp#014）类似：后者衡量 Amihud 的 bar-to-bar 变化，本特征衡量 volume 的 bar-to-bar 变化。都是"路径粗糙度"范式，但捕捉不同维度的信息。

### 评估结果

| 指标 | Raw | Neutral | 阈值 | 状态 |
|------|-----|---------|------|------|
| LS Sharpe | 1.42 | 1.08 | > 0.9 | ✅ / ✅ |
| LE Sharpe | 0.85 | 0.65 | > 0.7 | ✅ / ❌ |
| IR(LS) | 0.53 | 0.53 | > 0.2 | ✅ / ✅ |
| Mono | 0.71 | 0.71 | > 0.7 | ✅ / ✅ |
| Coverage | 87% | 87% | > 30% | ✅ / ✅ |

**Raw 全部通过 ✅**（任一组通过即可）。

### 年度分拆

| 年份 | Raw Sharpe | Raw IR | Neutral Sharpe | Neutral IR |
|------|-----------|--------|----------------|------------|
| 2020 | -0.49 | 0.376 | -0.38 | 0.382 |
| 2021 | 1.80 | 0.525 | 1.62 | 0.592 |
| 2022 | 3.03 | 0.693 | 2.37 | 0.682 |
| 2023 | 3.66 | 0.695 | 2.40 | 0.622 |
| 2024 | 0.72 | 0.475 | 0.63 | 0.465 |

2020 年弱（负），2021-2023 年强劲（Sharpe 1.8-3.7），2024 年衰减至 0.72。2024 年衰减与结论 #14（2024 年流动性因子信号普遍衰减）一致。

## 失败特征分析

### Hurst exponent 系列（hurst_volume/return/amount/range）

所有 4 个 R/S Hurst 特征都**强烈反向**（|LS Sharpe| = 3.9-5.7），alpha 集中在空头端。hurst_volume_full 正式评估 Mono=0.00（完全反单调），表明 **高 Hurst（持续性成交量）= 差股票**。

**诊断**：
- Hurst exponent 在 237 bars 数据上的估计具有较大方差
- R/S Hurst 的分子（rescaled range）与波动率高度相关 → Hurst 成为波动率代理
- hurst_volume 和 hurst_amount 几乎完全相同（|LS|=4.97 vs 4.97），说明 amount 的价格成分不影响 Hurst 估计
- hurst_range 最强反向（|LS|=5.69），直接测量 bar range 持续性 → 明确的波动率聚集代理
- 即使 neutral 后信号不衰减（|LS| 从 4.77→4.64），说明不是纯市值代理，而是**波动率因子**
- 与结论 #28（Quarticity 是波动率代理）一致

### vol_var_ratio_full

|LS|=5.64, |IR|=0.67 极强反向。方差比 VR<1 = anti-persistent volume，与 D-003 variance ratio 在 returns 上的失败模式一致。虽然输入从 returns 变为 volume，但方差比本身捕捉的仍是"时序可预测性"信号。

## 关键结论

41. **Volume 路径粗糙度是有效的流动性不确定性代理** — vol_roughness_full（mean|Δvol|/mean(vol)）LS=1.42, LE=0.85, IR=0.53, Mono=0.71。这是继 amihud_diff_mean_full（Amihud 路径粗糙度，LS=1.24）之后，路径粗糙度范式在 volume 维度的成功验证。

42. **R/S Hurst exponent 在日内 237 bars 上退化为波动率代理** — 4 个 Hurst 特征（volume/return/amount/range）全部 |LS|=3.9-5.7 强烈反向，Mono=0.00。R/S 方法的 rescaled range 本质测量局部波动范围，在短序列上无法有效分离持续性与波动率。

43. **方差比从 returns 迁移到 volume 不改变信号本质** — vol_var_ratio_full（volume 方差比）与 D-003（return 方差比）呈现相同的失败模式（强反向，空头端集中）。方差比捕捉的"可预测性/均值回复"信号，无论在哪个输入维度上，都退化为波动率/自相关代理。

## Pending 打包

- ✅ `vol_roughness_full` → `research/pending-rawdata/vol_roughness_full/`
