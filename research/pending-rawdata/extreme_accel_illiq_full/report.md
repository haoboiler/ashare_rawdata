---
agent_id: "ashare_rawdata_b"
experiment_id: "#017"
direction: "D-008 (price_acceleration)"
feature_name: "reversal_accel_illiq_full"
net_sharpe: 1.66
mono_score: 0.71
status: screening_passed
submitted_at: "2026-03-26T05:00:00"
---

# D-008 加速度 Amihud 条件化变体筛选报告

## 方向概述

**物理假设**：将 D-006 中已验证的 Amihud 条件化模式（反转 bar、极端收益 bar、低量 bar）迁移到加速度维度，测试 |acceleration|/amount 在不同 bar 子集上的表现是否与 |return|/amount 保持一致。

**研究动机**：上轮（Exp#016）验证了 Amihud 框架从一阶（收益率）拓展到二阶（加速度）仍有效。本轮测试条件化变体能否进一步分离信号。若模式一致 → D-008 条件化空间遵循与 D-006 相同的饱和规律，方向可标记为 exhausted。

## 筛选方法

- **快筛引擎**: `evolve_rawdata.py --use-preload`
- **筛选口径**: 全市场 5013 symbols, 2020-01-01 ~ 2023-12-31, basic6
- **正式评估**: `evaluate_rawdata.py --neutralize`, 2020-01-01 ~ 2023-12-31（preload 窗口限制，未覆盖 2024）

## 测试特征（3 个）

### 全部通过筛选

| 特征 | 物理含义 | Raw LS | Raw LE | Raw IR | Raw Mono | Neu LS | Neu LE | Neu IR | Neu Mono |
|------|----------|--------|--------|--------|----------|--------|--------|--------|----------|
| **reversal_accel_illiq_full** | 反转 bar 价格曲率冲击/成交额 | 1.66 | 1.34 | 0.37 | 0.71 | 1.46 | 1.39 | 0.43 | 0.71 |
| **low_vol_accel_illiq_full** | 低量 bar 价格曲率冲击/成交额 | 1.57 | 1.12 | 0.35 | 0.71 | 1.58 | 1.41 | 0.42 | 0.86 |
| **extreme_accel_illiq_full** | 极端加速度 bar 曲率冲击/成交额 | 1.49 | 1.16 | 0.39 | 0.71 | 1.35 | 1.35 | 0.44 | 0.57 |

## 关键发现

### 1. D-006 条件化模式完全迁移到加速度维度

三种条件化方式（反转/极端/低量）在加速度 Amihud 上全部通过筛选，与 D-006 中 return-based Amihud 的条件化结果一致。这进一步验证了 |f(price)|/amount 模板的通用性（结论 #35）。

### 2. 中性化信号增强模式一致

三个特征的 neutral IR 均显著高于 raw IR（+16% ~ +20%），与 Exp#016 的 accel_illiq_full/high_vol_accel_illiq_full 模式一致，含独立于市值/行业的流动性 alpha。

### 3. low_vol_accel_illiq_full neutral Mono 最高

low_vol_accel_illiq_full neutral Mono=0.86（8 组中 6 组严格单调），是本轮 Mono 最高的特征。低量时段的价格曲率冲击分离出更纯净的流动性信号。

### 4. D-008 条件化空间饱和

两轮实验（Exp#016 + #017）共测试 11 个特征，5 个通过。通过的全部是 |accel|/amount 的不同 bar 选择变体，与 D-006 的饱和模式完全一致（结论 #33）。所有变体本质是"从不同角度测量同一个加速度 Amihud 水平量信号"。

### 5. 2020 年系统性负收益

三个特征在 2020 年均为负 Sharpe（-0.66 ~ -0.85），与上轮 accel_illiq_full/high_vol_accel_illiq_full 一致。说明加速度 Amihud 信号在 2020 年市场环境下无效，可能与疫情初期流动性异常有关。

## 年度表现（raw）

### reversal_accel_illiq_full

| 年份 | 收益 | Sharpe | IC(LS) | IR(LS) |
|------|------|--------|--------|--------|
| 2020 | -0.09% | -0.66 | 0.029 | 0.21 |
| 2021 | 0.21% | 1.50 | 0.047 | 0.31 |
| 2022 | 0.39% | 3.59 | 0.061 | 0.47 |
| 2023 | 0.31% | 3.29 | 0.072 | 0.54 |

### extreme_accel_illiq_full

| 年份 | 收益 | Sharpe | IC(LS) | IR(LS) |
|------|------|--------|--------|--------|
| 2020 | -0.12% | -0.84 | 0.031 | 0.23 |
| 2021 | 0.17% | 1.25 | 0.046 | 0.32 |
| 2022 | 0.36% | 3.69 | 0.058 | 0.49 |
| 2023 | 0.29% | 3.33 | 0.069 | 0.55 |

### low_vol_accel_illiq_full

| 年份 | 收益 | Sharpe | IC(LS) | IR(LS) |
|------|------|--------|--------|--------|
| 2020 | -0.12% | -0.85 | 0.024 | 0.18 |
| 2021 | 0.18% | 1.35 | 0.041 | 0.29 |
| 2022 | 0.38% | 3.79 | 0.054 | 0.45 |
| 2023 | 0.30% | 3.39 | 0.066 | 0.52 |

## 方向评估

**D-008 建议标记为 exhausted。**

理由：
1. 两轮实验共 11 个特征，所有纯加速度统计量（6 个）均为波动率代理，只有 |accel|/amount 变体（5 个）通过
2. 5 个通过的特征全部是同一信号的不同 bar 选择视角，预计彼此高度相关
3. 与 D-006 的 return-based Amihud 也预计高度相关（acceleration = return 的一阶差分）
4. 条件化空间遵循与 D-006 相同的饱和规律，无法产生根本性新信号

## 局限性

1. **2024 未评估**：preload 仅覆盖 2020-2023，结论 #14 指出 2024 年流动性因子普遍衰减
2. **与 D-006 Amihud 系列高度相关**：最终入库时需做相关性检测决定保留哪些

## 评估路径

- 快筛: `.claude-output/evolve/20260326-043526/`
- 评估 (reversal): `.claude-output/evaluations/price_acceleration/reversal_accel_illiq_full/`
- 评估 (extreme): `.claude-output/evaluations/price_acceleration/extreme_accel_illiq_full/`
- 评估 (low_vol): `.claude-output/evaluations/price_acceleration/low_vol_accel_illiq_full/`
- PKL: `.claude-output/analysis/price_acceleration/`
