---
agent_id: "ashare_rawdata_a"
experiment_id: "#028"
direction: "D-019 (price_absorption_depth)"
feature_name: "doji_amihud_full"
net_sharpe: 1.78
mono_score: 0.86
status: screening_passed
submitted_at: "2026-03-26T11:25:00"
---

# D-019 Price Absorption & Depth 初筛报告

## 方向概述

**假设**: 日内 bar 级 OHLC 结构中的"影线"(wick = high-low-|close-open|) 反映被订单簿拒绝的价格探索。将 wick 作为 Amihud 框架的新维度，测量不同维度的流动性深度。

**方法**: 3 轮迭代，15 个特征测试

## 迭代路线

### 迭代 1: 基础吸收频率（5 特征）
- absorption_freq_full (|LS|=3.69, LE=-0.27) ❌ 空头端集中
- zero_return_freq_full (|LS|=0.78) ❌ 信号弱
- depth_volume_ratio_full (|LS|=2.93, LE=-0.37) ❌ 空头端集中
- absorption_amihud_full (|LS|=1.11, LE=+1.59) ⚠️ IR 边缘, 覆盖率 66.8%
- impact_efficiency_full (|LS|=2.09, LE=+1.63) ⚠️ 与 batch_amihud 冗余

**诊断**: 离散频率计数（类 reversal_ratio）在"价格吸收"维度上失败在 LE。原因：基于日内中位数的阈值使截面变异被市值结构主导。impact_efficiency 本质是 batch_amihud。

### 迭代 2: Bar 微观结构（5 特征）
- wick_ratio_full (|LS|=1.43, LE=+0.61, IR=0.17) ❌ IR<0.2
- **wick_amihud_full** (|LS|=1.30, LE=+0.68) ⚠️ LE 边缘
- **high_vol_wick_amihud_full** (|LS|=1.43, LE=+0.67) ⚠️ LE 边缘
- bar_efficiency_full (|LS|=3.65, LE=-3.28) ❌ 波动率代理
- low_impact_amihud_full (|LS|=0.01) ❌ 无信号

**关键发现**: wick_amihud（影线/成交额）是有效方向！LE 接近阈值。

### 迭代 3: Wick 扩展变体（5 特征）
- wick_roughness_full (|LS|=0.84, LE=+0.72) ❌ |LS| 不达标
- **doji_amihud_full** (|LS|=1.68, LE=+1.39) ✅ 全通过
- **high_vol_doji_amihud_full** (|LS|=1.78, LE=+1.45) ✅ 全通过
- wick_regime_transitions_full (|LS|=4.10, LE=-1.03) ❌ LE 负
- rejection_intensity_full (|LS|=4.63, LE=-4.58) ❌ 波动率代理

## 正式评估结果（w1, 2020-2023）

| 特征 | Raw |LS| | Raw LE | Raw IR | Raw Mono | Ntrl |LS| | Ntrl LE | Ntrl IR | Ntrl Mono | TVR |
|------|---------|--------|--------|----------|----------|---------|---------|-----------|-----|
| **doji_amihud_full** | 1.68 | 1.39 | 0.38 | 0.86 | 1.48 | 1.35 | 0.47 | 0.86 | 1.34 |
| **high_vol_doji_amihud_full** | 1.78 | 1.45 | 0.38 | 0.86 | 1.44 | 1.32 | 0.48 | 0.86 | 1.15 |
| **wick_amihud_full** | 1.30 | 0.68 | 0.47 | 1.00 | 2.36 | 1.43 | 0.49 | 0.86 | 0.79 |
| **high_vol_wick_amihud_full** | 1.43 | 0.67 | 0.50 | 0.86 | 2.15 | 1.38 | 0.52 | 0.86 | 0.67 |
| wick_roughness_full | 0.84 | 0.72 | 0.25 | 0.86 | 2.51 | 0.12 | 0.36 | 0.86 | 1.32 |

## 通过筛选的特征（4 个）

### 1. doji_amihud_full ✅
- **定义**: 标准 Amihud (|ret|/amount) 仅在 doji-like bars (wick > body) 上计算
- **物理含义**: Doji bar = 订单簿吸收了初始价格运动并推回 → 这些 bar 上的 Amihud 衡量"吸收事件"期间的价格冲击成本
- **Raw**: LS=1.68, LE=1.39, IR=0.38, Mono=0.86 | **Neutral**: LS=1.48, LE=1.35, IR=0.47, Mono=0.86
- **特点**: Raw 和 neutral 均通过所有阈值；neutral 后 IR 增强（0.38→0.47）

### 2. high_vol_doji_amihud_full ✅
- **定义**: 高量 + doji 双条件 Amihud
- **物理含义**: 活跃交易期的吸收事件价格冲击，排除安静期噪声
- **Raw**: LS=1.78, LE=1.45, IR=0.38, Mono=0.86 | **Neutral**: LS=1.44, LE=1.32, IR=0.48, Mono=0.86
- **特点**: 所有特征中最高的 raw LE=1.45；TVR=1.15 较低

### 3. wick_amihud_full ✅（neutral 通过）
- **定义**: mean((H-L-|C-O|)/amount)，影线大小除以成交额
- **物理含义**: 每单位交易的"被拒绝价格探索"幅度，衡量市场深度的不同角度
- **Raw**: LS=1.30, LE=0.68 | **Neutral**: LS=2.36, LE=1.43, IR=0.49, Mono=0.86
- **特点**: neutral 后大幅增强（LS 1.30→2.36, LE 0.68→1.43），raw Mono=1.00 完美单调
- **独特性**: 唯一使用 wick 作为 Amihud numerator 的因子，可能与标准 Amihud 低相关

### 4. high_vol_wick_amihud_full ✅（neutral 通过）
- **定义**: 高量 bar 的 wick Amihud
- **Raw**: LS=1.43, LE=0.67 | **Neutral**: LS=2.15, LE=1.38, IR=0.52, Mono=0.86
- **特点**: neutral IR=0.52 是本批最高；TVR=0.67 最低（换手率低=稳定信号）

## 未通过特征诊断

| 特征 | 最佳 |LS| | 失败原因 |
|------|---------|----------|
| absorption_freq_full | 3.69 | LE=-0.27，频率计数在吸收维度是空头端信号 |
| zero_return_freq_full | 0.78 | |LS|<0.9，零收益频率截面区分度不足 |
| depth_volume_ratio_full | 2.93 | LE=-0.37，同 absorption_freq |
| bar_efficiency_full | 3.65 | LE=-3.28，|C-O|/(H-L) 是波动率代理 |
| wick_regime_transitions_full | 4.10 | LE=-1.03，regime transition 仅 volume 有效（结论#19 扩展） |
| rejection_intensity_full | 4.63 | LE=-4.58，wick/close 无 amount 归一化=波动率代理 |
| wick_roughness_full | 0.84/2.51 | raw |LS|<0.9, neutral LE=0.12；roughness 在 wick 维度不如 volume |
| low_impact_amihud_full | 0.01 | 无信号，低冲击 bar 的 Amihud 截面无区分度 |
| impact_efficiency_full | 2.09 | 与 batch_amihud (pending) 本质冗余 |
| absorption_amihud_full | 1.11 | 覆盖率仅 66.8%，IR=0.20 边缘 |
| wick_ratio_full | 1.43 | IR=0.17<0.2 |

## 关键结论

1. **Bar 形态（doji 条件）是 Amihud 框架的有效新事件选择器** — doji bar (wick > body) 代表"价格探索被拒绝"事件，在这些 bar 上计算 Amihud 产生有效因子。这是继 high-vol / reversal / extreme-return / acceleration 之后的第 5 种条件 Amihud。

2. **Wick 是 Amihud numerator 的有效新维度** — (H-L-|C-O|)/amount 衡量"被拒绝的价格探索"每单位交易，是 |ret|/amount 的互补视角。neutral 后大幅增强（LS 1.30→2.36），说明信号独立于市值/行业。

3. **离散频率计数在"吸收"维度失败** — absorption_freq/depth_volume_ratio 的 LE 为负。频率计数成功需要物理事件有截面差异（如 bid-ask bounce 频率），而"高量低冲击"事件频率受制于日内中位数定义，跨股票差异不大。

4. **Wick regime transitions 失败** — 与结论#19（regime transitions 仅 volume 有效）一致。Wick 大小的变化不具有与 volume 相同的截面区分度。

5. **Roughness 范式在 wick 维度部分有效但不如 volume** — wick_roughness raw LE=0.72 通过但 |LS|=0.84 不达标。neutral 后 LE 大幅衰减（0.72→0.12），说明 wick 粗糙度的信号主要来自市值暴露。
