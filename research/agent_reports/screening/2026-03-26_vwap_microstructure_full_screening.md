---
agent_id: "ashare_rawdata_a"
experiment_id: "#025"
direction: "D-016 (vwap_microstructure)"
feature_name: "high_vol_vwap_cross_amihud_full"
net_sharpe: 1.26
mono_score: 1.00
status: screening_passed
submitted_at: "2026-03-26T09:50:00"
---

# D-016 VWAP 微观结构 — 筛选报告

## 方向假设

**日内价格相对累积 VWAP 的行为模式**是一个全新的信号维度。VWAP 是机构最重要的执行基准：
- 价格频繁穿越 VWAP = bid-ask bounce around 成交加权中心 = 高流动性
- 在 VWAP 穿越事件上叠加 Amihud 框架 = 在均值回复临界点测量流动性供给成本

核心假设：**VWAP 穿越事件上的价格冲击（|ret|/amount）衡量了均值回复成本**，高冲击 = 差流动性 = 执行成本高 → 投资者要求溢价。

## 实验结果

### Round 1: 基础 VWAP 特征（5 个特征，0 通过）

| 特征 | |LS Sharpe| | LE | |IR| | Mono | 状态 |
|------|-----------|------|------|------|------|
| `vwap_cross_freq_full` | 2.88 | -0.065 | 0.22 | 1.00 | ❌ LE 不达标 |
| `vwap_distance_full` | 5.23 | -5.68 | 0.42 | — | ❌ 波动率代理 |
| `vwap_distance_amihud_full` | 0.14 | +0.36 | 0.25 | — | ❌ LS 太低 |
| `high_vol_vwap_amihud_full` | 0.17 | +0.36 | 0.20 | — | ❌ LS 太低 |
| `vwap_tracking_error_full` | 5.24 | -5.99 | 0.49 | — | ❌ 波动率代理 |

**关键发现**：
- vwap_cross_freq 有完美 Mono=1.00，但 LE≈0（alpha 集中在空头端）
- VWAP 距离/跟踪误差是波动率代理（结论#22 一致）
- Amihud 形式的 VWAP 距离 LS 太低（0.14-0.17）

### Round 2: VWAP 交叉事件 + Amihud（3 个特征，2 通过 ✅）

| 特征 | |LS Sharpe| (r/n) | LE (r/n) | |IR| (r/n) | Mono (r/n) | 状态 |
|------|---------------------|------------|-------------|-------------|------|
| **`high_vol_vwap_cross_amihud_full`** | 1.26/0.82 | +1.31/+1.21 | 0.37/0.45 | **1.00**/0.86 | **✅ pending** |
| **`vwap_cross_amihud_full`** | 0.93/0.58 | +0.92/+1.12 | 0.38/0.43 | 0.71/0.86 | **✅ pending** |
| `vwap_distance_roughness_full` | 4.59/— | -4.64/— | 0.56/— | — | ❌ 波动率代理 |

## 通过特征详细分析

### high_vol_vwap_cross_amihud_full（首推）

物理含义：在**高成交量 + 价格穿越 VWAP** 的 bar 上计算 mean(|ret|/amount)。双条件选择：高量确保价格发现有效，VWAP 穿越确保是均值回复事件。

| 指标 | Raw | Neutral | 阈值 |
|------|-----|---------|------|
| |LS Sharpe| | **1.26** | 0.82 | >0.9 |
| LE Sharpe | **1.31** | 1.21 | >0.7 |
| |IR| | 0.37 | **0.45** | >0.2 |
| Mono | **1.00** | 0.86 | >0.7 |

年度表现（raw）：
| 年份 | LS Sharpe | IR |
|------|-----------|-----|
| 2020 | -0.93 | 0.24 |
| 2021 | +0.95 | 0.30 |
| 2022 | **+2.99** | 0.45 |
| 2023 | **+3.30** | 0.53 |

**趋势强劲改善**：2020年负（一致于其他 Amihud 因子），2021~2023 持续增强。中性化后 2020 改善为 -0.45。

### vwap_cross_amihud_full（辅助）

所有 bar（不限高量）的 VWAP 交叉 Amihud。Raw 勉强通过（LS=0.93, Mono=0.71），neutral 则 Mono=0.86 但 LS=0.58 不达标。预期与 high_vol 变体高度相关。

## 新结论

1. **VWAP 穿越事件 + Amihud 是有效的流动性因子** — high_vol_vwap_cross_amihud_full 是第一个基于 VWAP 锚点的通过因子，Mono=1.00。这是 Amihud 框架的进一步泛化：事件触发器从"收益率方向反转"扩展到"价格穿越 VWAP"。

2. **VWAP 穿越频率有完美排序但无多头 alpha** — vwap_cross_freq Mono=1.00（完美单调），但 LE≈0，alpha 集中在空头端（高穿越频率=嘈杂交易=差股票）。低穿越频率不等于好流动性，只是"不那么差"。

3. **VWAP 距离/跟踪误差是波动率代理** — 与结论#22（HL range）和#47（路径拓扑）一致，VWAP 偏差的绝对水平是波动率的另一种度量。

4. **高量条件继续改善 Amihud 信号** — 与结论#21 一致，high_vol 条件将 Mono 从 0.71→1.00，LE 从 0.92→1.31。

## 数据覆盖

- 因子值 pkl：2020-01-02 至 2023-12-29（970 天 × 5013 symbols）
- 覆盖率：86.7%（>30% 阈值）
- ⚠️ 2024 数据未覆盖（preload 限制），需后续补充
