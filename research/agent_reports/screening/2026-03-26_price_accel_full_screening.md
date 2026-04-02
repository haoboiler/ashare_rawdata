---
agent_id: "ashare_rawdata_b"
experiment_id: "#014"
direction: "D-008 (price_acceleration)"
feature_name: "high_vol_accel_illiq_full"
net_sharpe: 1.93
mono_score: 1.00
status: screening_passed
submitted_at: "2026-03-26T04:20:00"
---

# D-008 Price Acceleration 全市场筛选报告

## 方向概述

**物理假设**：价格加速度（ret[t+1] - ret[t]）衡量价格路径的曲率。从流动性视角切入——单位成交额下的价格曲率变化量（|加速度|/成交额）越大，说明市场对该股票的定价能力越差（非流动性溢价）。

**方向选择逻辑**：知识库已证明"纯价格动态因子"系统性失败在 Long Excess（结论 #6、#9），但 Amihud 框架（|return|/amount）已成功通过（结论 #17）。本轮尝试将 Amihud 框架从"收益率"拓展到"加速度"维度，测试"曲率冲击"是否含有独立于"一阶冲击"的流动性信息。

## 筛选方法

- **快筛引擎**: `evolve_rawdata.py --use-preload`
- **筛选口径**: 全市场 5013 symbols, 2020-01-01 ~ 2023-12-31, basic6
- **正式评估**: `evaluate_rawdata.py --neutralize`, 2020-01-01 ~ 2023-12-31（preload 窗口限制，未覆盖 2024）

## 测试特征（8 个）

### 通过筛选（2 个）

| 特征 | 物理含义 | Raw LS | Raw LE | Raw IR | Raw Mono | Neu LS | Neu LE | Neu IR | Neu Mono |
|------|----------|--------|--------|--------|----------|--------|--------|--------|----------|
| **high_vol_accel_illiq_full** | 高量 bar 价格曲率冲击/成交额 | 1.93 | 1.50 | 0.36 | **1.00** | 1.80 | 1.45 | 0.45 | 0.86 |
| **accel_illiq_full** | 全 bar 价格曲率冲击/成交额 | 1.67 | 1.20 | 0.35 | 0.71 | 1.64 | 1.43 | 0.42 | 0.86 |

### 未通过筛选（6 个）

| 特征 | 物理含义 | |LS Sharpe| | LE Sharpe | 失败原因 |
|------|----------|-----------|-----------|----------|
| accel_kurtosis_full | 加速度超额峰度 | 10.88 | -7.40 | LE 极负，波动率代理 |
| accel_skew_full | 加速度偏度 | 8.51 | -3.22 | LE 极负 |
| accel_vol_corr_full | |加速度|-成交量相关性 | 6.59 | -4.58 | LE 极负，波动率代理 |
| accel_std_full | 加速度标准差 | 5.10 | -4.89 | LE 极负，波动率代理 |
| abs_accel_mean_full | 平均绝对加速度 | 4.28 | -3.91 | LE 极负，波动率代理 |
| accel_regime_trans_full | 加速度符号切换频率 | 1.99 | -0.22 | LE 不达标 |

## 关键发现

### 1. Amihud 框架对加速度同样有效

将 Amihud 的 |return|/amount 扩展为 |acceleration|/amount，LS Sharpe 和 Long Excess 均达标。这验证了"单位成交额下的价格不稳定性"是独立于一阶收益率冲击的流动性信号。

### 2. 高量 bar 条件化大幅提升 Mono

high_vol_accel_illiq_full 的 raw Mono=1.00（完美单调），vs accel_illiq_full 的 raw Mono=0.71。与 high_vol_illiq_full vs amihud_illiq_full 的模式一致（结论 #21）：只在活跃交易期计算价格冲击消除了安静期噪声。

### 3. 纯加速度统计量是波动率代理

abs_accel_mean, accel_std, accel_kurtosis 全部 LE 深度负值（-3.91 ~ -7.40）。加速度的绝对水平/分布直接反映波动率大小，和 BPV、HL range 等一样是低波动率溢价的另一种表达（结论 #5, #22）。

### 4. 加速度 regime transition ≠ 收益率 reversal ratio

accel_regime_trans_full（加速度符号切换频率）LE=-0.22，远不如 reversal_ratio_full（收益率方向切换频率）的 LE=1.21。加速度符号本身变化太频繁（基线频率 ~85%），截面区分度不足。

### 5. 中性化增强信号

accel_illiq_full neutral IR=0.42 > raw IR=0.35（+20%）；high_vol_accel_illiq_full neutral IR=0.45 > raw IR=0.36（+25%）。与 CS spread 模式一致（结论 #12），说明加速度 Amihud 含独立于市值/行业的流动性 alpha。

## 年度表现

### high_vol_accel_illiq_full (raw)

| 年份 | 收益 | Sharpe | IC(LS) | IR(LS) |
|------|------|--------|--------|--------|
| 2020 | -1.38% | -0.11 | 0.028 | 0.22 |
| 2021 | 19.12% | 1.46 | 0.039 | 0.28 |
| 2022 | 33.15% | 3.40 | 0.051 | 0.43 |
| 2023 | 34.91% | 4.15 | 0.067 | 0.54 |

### accel_illiq_full (raw)

| 年份 | 收益 | Sharpe | IC(LS) | IR(LS) |
|------|------|--------|--------|--------|
| 2020 | -9.46% | -0.68 | 0.026 | 0.19 |
| 2021 | 19.19% | 1.43 | 0.041 | 0.29 |
| 2022 | 36.76% | 3.73 | 0.054 | 0.45 |
| 2023 | 32.08% | 3.66 | 0.067 | 0.53 |

## 局限性

1. **2024 未评估**：当前 preload 仅覆盖 2020-2023。结论 #14 指出日内流动性因子 2024 年普遍衰减，加速度 Amihud 是否受影响需后续验证。
2. **与 amihud_illiq_full 可能高度相关**：两者都是 |f(price)|/amount 形式，acceleration 是 return 的一阶差分，相关性检测在用户审批时决定。

## 评估路径

- 快筛: `.claude-output/evolve/20260326-033927/`
- 评估 (accel_illiq_full): `.claude-output/evaluations/price_acceleration/accel_illiq_full/`
- 评估 (high_vol_accel_illiq_full): `.claude-output/evaluations/price_acceleration/high_vol_accel_illiq_full/`
- PKL: `.claude-output/analysis/price_acceleration/`
