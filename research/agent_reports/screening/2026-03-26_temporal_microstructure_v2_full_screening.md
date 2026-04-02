---
agent_id: "ashare_rawdata_b"
experiment_id: "#036"
direction: "D-025 (temporal_microstructure)"
feature_name: "gap_reversal_freq_full"
net_sharpe: 0
mono_score: 0
status: screening_failed
submitted_at: "2026-03-26T14:15:00"
---

# D-025 Temporal Microstructure V2 初筛报告（第二轮）

## 方向假设

在第一轮（Exp#035）发现非 Amihud 时序结构特征系统性失败后，第二轮聚焦于**离散计数范式**（结论#16 验证有效）：
- 将 reversal_ratio 的成功模式迁移到 inter-bar gap 维度
- 测试量价时序同步性的离散指标
- 探索价格路径效率和 gap 稳定性

核心问题：gap 符号反转频率能否复制 reversal_ratio（intra-bar 价格反转）的成功？

## 快筛结果（全市场 5013 symbols，2020-2023）

| 特征 | |LS Sharpe| | LE Sharpe | IR_LS | 判定 |
|------|-----------|----------|-------|------|
| `gap_reversal_freq_full` | 10.43 | -2.04 | -0.09 | ❌ IR 极低 + LE 深负 |
| `gap_sign_run_mean_full` | 9.26 | -1.76 | -0.06 | ❌ IR 极低 + LE 深负 |
| `volume_accel_freq_full` | 11.14 | -1.02 | -0.22 | ❌ 纯空头集中 |
| `large_gap_vol_sync_full` | 3.58 | **-4.27** | -0.44 | ❌ LE 极差 |
| `price_path_efficiency_full` | 8.13 | **-5.29** | -0.08 | ❌ LE 最差 |
| `gap_cv_full` | 2.95 | -2.42 | +0.34 | ❌ LE 深负 |

**6 个特征全部 LE < -1.0，无一通过**。

## 失败诊断

### gap_reversal_freq_full（核心假设）

- **假设**: 高 gap 反转频率 = 市场快速纠正 bar 间价格跳变 = 好市场质量 → 正 LE
- **实际**: |LS|=10.43 但 IR_LS=-0.09（接近零信噪比），LE=-2.04
- **诊断**: Inter-bar gap 的符号翻转**不等同于** intra-bar 价格反转。reversal_ratio 衡量的是 bid-ask bounce（流动性代理），而 gap sign reversal 衡量的是相邻 bar 间 open-close 差值的方向交替。Gap 方向的高频交替可能反映**集合竞价/连续竞价切换的微观噪声**，而非流动性信息。
- **结论**: gap_reversal ≠ price_reversal，离散计数范式不可简单迁移到不同变量。

### volume_accel_freq_full

- **假设**: 量能加速频率衡量交易活跃度趋势
- **实际**: |LS|=11.14（极强），LE=-1.02，IR_LS=-0.22
- **诊断**: 经典"识别差股票但不能选好股票"模式。高量加速频率 = 成交量持续攀升 = 投机/追涨行为集中 → 空头端有 alpha，多头端无正超额。与结论#6（日内价格时序动态因子系统性失败在 LE）完全一致。

### large_gap_vol_sync_full

- **假设**: 量价同步 = 信息有效传导 = 健康市场
- **实际**: IR_LS=-0.44（信号强），但 LE=-4.27（极差）
- **诊断**: 高同步 = 大 gap 伴随大成交量 = 事件驱动型股票 = 高波动 + 不稳定。这实际是在识别"噪声交易密集"的标的，方向与假设完全相反。

### price_path_efficiency_full

- **假设**: 高路径效率 = 日内趋势 = 价格发现能力强
- **实际**: |LS|=8.13，LE=-5.29（所有特征中最差）
- **诊断**: 高路径效率在 A 股环境中 = 强趋势 = 追涨杀跌集中 → T+1 限制下次日必然反转。与结论#9（方向性动量在 A 股是反转效应）高度一致。

### gap_cv_full

- **假设**: 低 gap CV = 稳定的微观结构摩擦 = 市场质量好
- **实际**: IR_LS=+0.34（方向有信号），但 LE=-2.42
- **诊断**: gap 大小的变异系数有一定截面排序能力（IR_LS 最高），但仍然不能让多头端跑赢 CSI1000。gap CV 本质上是 gap 维度的波动率二阶量，仍是"坏股票"识别器。

## 方向总结

**D-025 temporal_microstructure 两轮共测试 14 个特征**：

| 轮次 | 特征数 | 通过 | 通过特征 |
|------|--------|------|---------|
| 第一轮 (Exp#035) | 8 | 1 | open_gap_amihud_full (Amihud 变体) |
| 第二轮 (Exp#036) | 6 | 0 | — |
| **合计** | **14** | **1** | — |

### 核心结论

1. **Inter-bar gap 维度仅通过 Amihud 归一化（/amount）才能产生有效因子**。gap 的符号翻转、稳定性、路径效率等非 Amihud 变体全部失败。

2. **离散计数范式（结论#16）的适用条件**：
   - ✅ 应用于 intra-bar 价格反转 → reversal_ratio 有效
   - ✅ 应用于 volume regime 切换 → vol_regime_transitions 有效
   - ❌ 应用于 inter-bar gap 符号反转 → gap_reversal_freq 无效
   - 差异：reversal_ratio 的物理基础是 bid-ask bounce（流动性代理），gap 的符号翻转缺乏同等清晰的流动性含义

3. **建议将 D-025 标记为 exhausted**。所有非 Amihud 时序维度（极值时点、lead-lag、gap 反转、量加速、路径效率、量价同步）均已测试，无一产生 LE 达标的因子。

## 相关文件

- **Formula**: `research/basic_rawdata/temporal_microstructure/register_temporal_microstructure_v2_full.py`
- **Evolve 输出**: `.claude-output/evolve/20260326-140952/`
- **第一轮报告**: `research/agent_reports/screening/2026-03-26_temporal_microstructure_full_screening.md`
