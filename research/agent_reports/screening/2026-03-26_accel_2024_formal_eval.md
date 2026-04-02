---
agent_id: "ashare_rawdata_b"
experiment_id: "#018"
direction: "D-008 (price_acceleration)"
feature_name: "high_vol_accel_illiq_full"
net_sharpe: 1.74
mono_score: 0.86
status: screening_passed
submitted_at: "2026-03-26T08:20:00"
---

# D-008 加速度 Amihud 系列正式评估（2020-2024 全覆盖）

## 目的

上轮（Exp#016/#017）的 5 个通过特征仅评估了 2020-2023（preload 窗口限制）。本轮补完 2024 年正式评估，为用户审批提供完整的 5 年业绩数据。

## 评估方法

- **PKL 重新计算**：串行模式（不用 preload），全市场 5191 symbols，覆盖 2020-01-02 至 2026-03-20
- **正式评估**：`evaluate_rawdata.py --start 2020-01-01 --end 2024-12-31 --neutralize`
- **回测参数**：LS / 8 组 / comp / twap_1300_1400 / csi1000 / 万1 / 无印花税

## 核心结果（2020-2024 全覆盖）

### 全部 5 个特征通过自动筛选

| 特征 | Raw LS | Raw LE | Raw IR | Raw Mono | Neu LS | Neu LE | Neu IR | Neu Mono |
|------|--------|--------|--------|----------|--------|--------|--------|----------|
| **high_vol_accel_illiq_full** | 1.56 | 1.12 | 0.32 | **1.00** | **1.74** | 1.15 | **0.44** | 0.86 |
| **low_vol_accel_illiq_full** | 1.50 | 0.97 | 0.33 | 0.86 | **1.60** | **1.17** | 0.41 | 0.86 |
| **accel_illiq_full** | 1.55 | 1.03 | 0.33 | 0.71 | **1.65** | **1.18** | 0.41 | 0.86 |
| **reversal_accel_illiq_full** | 1.50 | 1.12 | 0.35 | 0.86 | 1.44 | 1.15 | 0.41 | 0.86 |
| **extreme_accel_illiq_full** | 1.37 | 0.98 | 0.35 | **1.00** | 1.35 | 1.12 | **0.42** | 0.71 |

## 2024 年表现（关键更新）

### Raw 年度 Sharpe

| 特征 | 2020 | 2021 | 2022 | 2023 | **2024** |
|------|------|------|------|------|----------|
| accel_illiq_full | -0.68 | 1.43 | 3.73 | 3.78 | **1.25** |
| high_vol_accel_illiq_full | -0.11 | 1.46 | 3.40 | 4.27 | **0.77** |
| reversal_accel_illiq_full | -0.66 | 1.50 | 3.59 | 3.42 | **1.10** |
| extreme_accel_illiq_full | -0.84 | 1.25 | 3.69 | 3.46 | **1.06** |
| low_vol_accel_illiq_full | -0.85 | 1.35 | 3.79 | 3.52 | **1.32** |

### Neutral 年度 Sharpe

| 特征 | 2020 | 2021 | 2022 | 2023 | **2024** |
|------|------|------|------|------|----------|
| accel_illiq_full | 0.32 | 1.49 | 3.65 | 2.16 | **1.65** |
| high_vol_accel_illiq_full | 0.46 | 1.50 | 3.96 | 2.56 | **1.47** |
| reversal_accel_illiq_full | 0.06 | 1.38 | 3.30 | 1.95 | **1.31** |
| extreme_accel_illiq_full | 0.09 | 1.20 | 3.23 | 1.87 | **1.31** |
| low_vol_accel_illiq_full | 0.24 | 1.46 | 3.53 | 2.07 | **1.64** |

## 关键发现

### 1. 2024 年 neutral 信号未衰减

5 个特征 2024 neutral Sharpe 范围 1.31-1.65，远好于 CS spread 的 2024 neutral Sharpe 0.45（结论 #14）。加速度 Amihud 因子在 2024 年 A 股市场环境变化中保持了稳健的流动性信号。

### 2. 中性化显著改善 2024 表现

raw 2024 Sharpe 0.77-1.32 → neutral 1.31-1.65。剥离市值/行业暴露后纯流动性信号更强，说明 2024 年加速度 Amihud 含有独立于市值/行业的 alpha。

### 3. 2020 年 neutral 表现转正

之前 raw 2020 全部负值（-0.68 ~ -0.85），neutral 后 4/5 转正（0.06 ~ 0.46）。说明 2020 年疫情初期的负收益主要来自市值/行业暴露，而非因子信号本身。

### 4. Mono 随 2024 数据改善

加入 2024 后多个特征 Mono 提升：
- extreme_accel_illiq_full raw: 0.71 → 1.00（完美单调）
- reversal_accel_illiq_full raw: 0.71 → 0.86
- low_vol_accel_illiq_full raw: 0.71 → 0.86

2024 数据增强了分组排序的单调性。

### 5. 全天覆盖已确认——1504 trading days

PKL 现覆盖 2020-01-02 至 2026-03-20（1504 trading days），正式评估截止 2024-12-31（~1214 trading days）。

## 与之前仅 2020-2023 评估的对比

| 指标 | 2020-2023 (old) | 2020-2024 (new) | 变化 |
|------|-----------------|-----------------|------|
| accel_illiq LS Sharpe | 1.67 | 1.55 | -7% |
| accel_illiq LE Sharpe | 1.20 | 1.03 | -14% |
| accel_illiq IR | 0.35 | 0.33 | -6% |
| high_vol_accel LS Sharpe | 1.93 | 1.56 | -19% |
| high_vol_accel LE Sharpe | 1.50 | 1.12 | -25% |

加入 2024 年后整体指标有所下降（因 2024 年表现弱于 2022-2023 峰值），但**全部仍然通过所有筛选阈值**。

## 方向评估

**D-008 正式确认 exhausted。**

5 个加速度 Amihud 变体全部通过 2020-2024 正式评估。方向空间已饱和，所有变体本质是同一信号的不同 bar 选择视角。建议：
1. 标记 D-008 为 exhausted
2. 入库时与 D-006 return-based Amihud 系列做相关性检测，决定最终保留子集
3. 清除本 Agent 的 current_direction，分配新方向

## 评估路径

- PKL: `.claude-output/analysis/price_acceleration/`
- 评估 (2024): `.claude-output/evaluations/price_acceleration/{feat}_2024/`
- 上轮报告: `research/agent_reports/screening/2026-03-26_price_accel_full_screening.md`
- 条件化报告: `research/agent_reports/screening/2026-03-26_accel_conditioning_full_screening.md`
