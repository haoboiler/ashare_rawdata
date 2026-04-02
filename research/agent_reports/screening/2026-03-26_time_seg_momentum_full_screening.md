---
agent_id: "ashare_rawdata_b"
experiment_id: "#010"
direction: "D-012 (time_segmented_momentum)"
feature_name: "return_hhi_full"
net_sharpe: 0
mono_score: 0
status: screening_failed
submitted_at: "2026-03-26T03:05:00"
---

# D-012 Time-Segmented Momentum 全方向筛选失败报告

## 方向概述

将全天分为 8 个 ~30 分钟段，计算截面收益时间分布特征。设计角度避免纯方向性动量（已证实失败），而是关注收益时间集中度、段间反转、路径粗糙度等，尝试作为流动性/信息不对称代理。

## 测试方法

- **工具**: `evolve_rawdata.py --use-preload --num-workers 32 --field-preset basic6`
- **快筛窗口**: 2020-01-01 ~ 2023-12-31，全市场 5013 symbols
- **两个 Bundle**:
  1. `time_seg_momentum_full` (10 字段): 纯收益时间分布
  2. `vol_ret_timing_full` (8 字段): 量价时间交互

## 全部 18 字段筛选结果

### Bundle 1: time_seg_momentum_full (10 字段)

| 字段 | |LS Sharpe| | LE Sharpe | IR | 覆盖率 | 状态 |
|------|-----------|-----------|-----|--------|------|
| `return_hhi_full` | 11.20 | -5.44 | -0.14 | 86% | ❌ LE 深度负值 |
| `max_segment_share_full` | 10.46 | -4.05 | -0.23 | 86% | ❌ LE 深度负值 |
| `close_return_share_full` | 8.20 | -2.05 | -0.24 | 86% | ❌ LE 负值 |
| `segment_return_skew_full` | 7.47 | -3.02 | -0.14 | 86% | ❌ LE 负值 |
| `segment_reversal_ratio_full` | 7.01 | -1.25 | -0.12 | 75% | ❌ LE 负值 |
| `open_return_share_full` | 6.88 | -2.53 | +0.04 | 86% | ❌ LE 负值, IR 不达标 |
| `segment_autocorr1_full` | 5.90 | -1.13 | +0.04 | 86% | ❌ LE 负值 |
| `segment_return_std_full` | 5.59 | -6.30 | -0.51 | 86% | ❌ LE 深度负值 |
| `am_pm_abs_ratio_full` | 4.77 | -1.64 | +0.06 | 85% | ❌ LE 负值 |
| `return_path_roughness_full` | 1.46 | **+0.27** | -0.06 | 86% | ❌ LE 远低于 0.7 |

### Bundle 2: vol_ret_timing_full (8 字段)

| 字段 | |LS Sharpe| | LE Sharpe | IR | 覆盖率 | 状态 |
|------|-----------|-----------|-----|--------|------|
| `vol_am_pm_ratio_full` | 11.10 | -8.99 | -0.24 | 86% | ❌ LE 深度负值 |
| `vol_timing_hhi_full` | 9.97 | -6.39 | -0.59 | 86% | ❌ LE 深度负值 |
| `vol_ret_rank_corr_full` | 9.74 | -2.04 | -0.33 | 86% | ❌ LE 负值 |
| `high_vol_seg_ret_ratio_full` | 8.99 | -3.56 | -0.40 | 85% | ❌ LE 负值 |
| `vol_weighted_ret_hhi_full` | 8.66 | -3.35 | -0.37 | 86% | ❌ LE 负值 |
| `vol_ret_abs_corr_full` | 7.71 | -1.83 | -0.25 | 86% | ❌ LE 负值 |
| `vol_weighted_reversal_full` | 7.06 | -1.00 | -0.13 | 85% | ❌ LE 负值 |
| `informed_ratio_full` | 1.89 | +0.19 | -0.32 | 86% | ❌ LE 远低于 0.7 |

## 失败诊断

### 失败模式

**系统性 Long Excess 失败** — 全部 18 个字段 LE ≤ +0.27（阈值 0.7），且 16/18 字段 LE 为负值。

### 与历史结论的一致性

| 结论 | 本次验证 |
|------|---------|
| #4 A 股日内因子 alpha 常集中在空头端 | ✅ 全部 18 字段 raw Sharpe 为负 |
| #6 日内价格时序动态因子系统性失败 LE | ✅ 即使从 1min bar 提升到 30min segment 仍失败 |
| #9 方向性动量失败 LE | ✅ 非方向性（集中度/反转）也同样失败 |
| #15 纯成交量分布指标系统性失败 LE | ✅ vol_timing_hhi/vol_am_pm_ratio 失败 |
| #11 全天窗口优于 1h | N/A，本次直接用全天 |

### 关键洞察

1. **时间粒度无法改变信号本质**：从 1min bar 级别的 reversal_ratio（成功，LE=1.21）到 30min segment 级别的 segment_reversal_ratio（失败，LE=-1.25），说明 bar 级别的反转捕捉的是真实的 bid-ask bounce 微观结构信号，而 segment 级别捕捉的是中频趋势反转，本质不同。

2. **收益集中度 = 波动率代理**：return_hhi/max_segment_share 本质上测量的是"收益是否集中在某个时段"，与 realized quarticity（极端波动）同义。高集中度 = 高波动 → 差股票。

3. **量价时间交互无法挽救**：添加 volume 维度（vol_weighted_reversal, vol_ret_rank_corr）没有改善 LE，因为 volume 时间分布本身也是"差股票"识别器（结论 #15）。

### 结论

D-012 方向已穷尽。日内收益时间分布特征（无论是纯收益还是量价交互）与此前已排除的价格动态因子失败模式完全一致。**A 股有效的日内因子仅限于直接测量流动性水平的指标**（spread、Amihud、bar-level reversal、volume regime transition），而非任何形式的收益/价格行为模式统计。

### 建议下一步

方向池中剩余可用方向（D-007 realized_quarticity, D-008 price_acceleration, D-010 hurst_exponent, D-014 intraday_momentum）均为收益/价格动态类因子，基于 9 次实验的积累结论，预期同样会失败在 Long Excess。建议：
1. 扩充方向池：加入更多流动性水平类方向（如 Kyle's Lambda 全天版、LOB depth proxy、tick-level spread variants）
2. 或探索新维度：如日内量价结构的截面排名稳定性、流动性的时间序列变化率等
