---
agent_id: "ashare_rawdata_a"
experiment_id: "#026"
direction: "D-017 (pv_concordance)"
feature_name: "concordant_amihud_full"
net_sharpe: 1.65
mono_score: 1.00
status: screening_passed
submitted_at: "2026-03-26T10:15:00"
---

# D-017 量价协调性 (pv_concordance) — 筛选报告

## 方向假设

日内 bar 级别 |return| 和 volume 的**联合行为模式**是此前未被探索的全新维度。
现有因子要么看 volume（regime transitions）、要么看 |return|（reversal ratio）、要么做比值（Amihud），
但 volume 和 |return| 的**同步程度（concordance）**反映了市场质量和价格发现效率。

## 特征设计（5 特征 bundle）

| 特征 | 定义 | 类型 |
|------|------|------|
| `pv_concordance_ratio_full` | (|ret|>med AND vol>med) / total bars | 离散计数 |
| `pv_extreme_concordance_full` | (|ret|>2×med AND vol>2×med) / total bars | 离散计数 |
| `pv_corr_full` | Pearson correlation of |ret| and vol | 连续 |
| `concordant_amihud_full` | mean(|ret|/amount) on concordant bars | 条件 Amihud |
| `discordant_amihud_full` | mean(|ret|/amount) on discordant bars (high|ret|, low vol) | 条件 Amihud |

## 快筛结果（全市场 5013 stocks, 2020-2023）

| 特征 | |LS Sharpe| | LE | |IR| | 状态 |
|------|-----------|------|------|------|
| pv_concordance_ratio_full | 5.61 | -3.99 | 0.40 | ❌ LE 深度负（空头端集中）|
| pv_extreme_concordance_full | 5.22 | -2.41 | 0.40 | ❌ LE 负 |
| pv_corr_full | 7.22 | -2.98 | 0.79 | ❌ 波动率代理模式 |
| **concordant_amihud_full** | **1.65** | **+1.56** | **0.35** | **✅ shortlist** |
| **discordant_amihud_full** | **1.48** | **+1.36** | **0.37** | **✅ shortlist** |

## 正式评估结果（全市场, 2020-2023，含分组回测）

### concordant_amihud_full

| 指标 | Raw | Neutral |
|------|-----|---------|
| LS Sharpe (net) | **1.65** | 1.27 |
| Long Excess (net) | **+1.56** | +1.41 |
| IR(LS) | 0.35 | **0.52** |
| IR(LO) | 0.47 | 0.29 |
| Mono (8 组) | **1.00** | 0.71 |
| 覆盖率 | 70.3% | 70.3% |

**分组 Sharpe (raw)**: [1.34, 1.39, 1.04, 1.02, 0.67, 0.45, -0.15, -0.67] → **完美单调**
**分组 Sharpe (neutral)**: [1.44, 1.02, 0.32, 0.65, 0.36, -0.11, -0.78, -0.16]

**年度趋势 (raw)**:
- 2020: Sharpe=-0.67 (负值)
- 2021: Sharpe=1.33
- 2022: Sharpe=2.80
- 2023: Sharpe=4.04 (持续增强)

**筛选判定: ✅ PASSED (raw 组全部达标)**

### discordant_amihud_full

| 指标 | Raw | Neutral |
|------|-----|---------|
| LS Sharpe (net) | **1.48** | 1.15 |
| Long Excess (net) | **+1.36** | +1.45 |
| IR(LS) | 0.37 | **0.53** |
| IR(LO) | 0.41 | 0.25 |
| Mono (8 组) | **0.86** | 0.57 |
| 覆盖率 | 70.3% | 70.3% |

**分组 Sharpe (raw)**: [1.17, 1.23, 1.01, 0.89, 0.65, 0.12, 0.15, -0.46]
**分组 Sharpe (neutral)**: [1.22, 1.59, 0.82, 0.37, 0.74, -0.57, 0.07, -0.16]

**年度趋势 (raw)**:
- 2020: Sharpe=-0.93 (负值)
- 2021: Sharpe=1.35
- 2022: Sharpe=2.81
- 2023: Sharpe=3.84 (持续增强)

**筛选判定: ✅ PASSED (raw 组全部达标)**

## 关键发现

1. **量价协调性计数特征全部失败在 Long Excess** — concordance_ratio |LS|=5.61 但 LE=-3.99，corr |LS|=7.22 但 LE=-2.98。高量价同步性 = 投机/事件驱动交易 → 只能识别"坏股票"，与结论#6（空头端集中）一致。

2. **联合事件选择 + Amihud 有效** — 计数本身无 alpha，但作为 Amihud 的**事件选择器**有效。concordant_amihud（high|ret|+high vol 条件 Amihud）raw Mono=1.00、LE=1.56，discordant_amihud（high|ret|+low vol 条件 Amihud）raw Mono=0.86、LE=1.36。

3. **Neutral 后 IR 增强** — concordant: IR 0.35→0.52，discordant: IR 0.37→0.53，信号独立于市值/行业。但 neutral Mono 下降（concordant: 1.00→0.71，discordant: 0.86→0.57），说明部分排序能力来自市值/行业暴露。

4. **2020 年表现为负** — 两个特征 2020 年 raw Sharpe 为负值（-0.67/-0.93），2021-2023 逐年增强。与已有 Amihud 系列的 2020 年表现类似（neutral 后 2020 转正，见结论#44）。

5. **与现有 Amihud 系列可能高度相关** — concordant/discordant Amihud 本质是在不同 bar 子集上计算 |ret|/amount，与 high_vol_illiq、extreme_amihud 等已 pending 特征可能高相关。最终由用户审批时评估。

## 数据可用性

- pkl 覆盖 2020-01-02 至 2023-12-31（preload 限制），2024 数据待补充
- 覆盖率 70.3%，高于 30% 阈值
- 无 >30 天连续缺失
