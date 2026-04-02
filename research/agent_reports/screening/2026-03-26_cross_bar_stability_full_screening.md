---
agent_id: "ashare_rawdata_a"
experiment_id: "#033"
direction: "D-024 (cross_bar_stability)"
feature_name: "rs_amihud_full"
net_sharpe: 1.82
mono_score: 1.00
status: screening_passed
submitted_at: "2026-03-26T13:40:00"
---

# D-024 Cross-Bar Stability Patterns — 全天窗口初筛报告

## 方向概述

**核心假设**：路径粗糙度范式（mean|ΔX|/mean(X)）已在 volume（vol_roughness, Exp#020）和 Amihud（amihud_diff_mean, Exp#014）维度验证有效。本方向测试：
1. 粗糙度推广到新维度（amount, range, body）
2. 复合离散事件频率（reversal × vol regime change）
3. Rogers-Satchell OHLC 高效波动率 / amount（RS Amihud）

## 快筛结果（evolve, 2020-2023, 全市场 5013 股）

| 特征 | |LS Sharpe| | IR | LE | 判断 |
|------|-----------|------|------|------|
| `rs_amihud_full` | **1.82** | 0.26 | **1.34** | **SHORTLIST** |
| `amount_roughness_full` | **1.46** | **0.55** | **1.00** | **SHORTLIST** |
| `range_roughness_full` | 1.01 (反向) | 0.18 | 0.49 | ❌ IR<0.2 |
| `body_roughness_full` | 0.37 | 0.45 | 0.75 | ❌ LS<0.9 |
| `joint_reversal_vol_full` | 0.54 | 0.04 | 0.97 | ❌ IR≈噪声 |

## 正式评估结果（2020-2023, 8组, neutralize）

### rs_amihud_full — PASSED

Rogers-Satchell 波动率 / mean(amount)。RS_bar = ln(H/O)·ln(H/C) + ln(L/O)·ln(L/C)，使用全部4个OHLC价格估计bar内方差，除以成交额。

| 指标 | Raw | Neutral | 阈值 | 判定 |
|------|-----|---------|------|------|
| LS Sharpe | **1.82** | **1.77** | >0.9 | ✅✅ |
| Long Excess | **1.34** | **1.35** | >0.7 | ✅✅ |
| IR(LS) | 0.26 | **0.30** | >0.2 | ✅✅ |
| Mono (8组) | **1.00** | **0.86** | >0.7 | ✅✅ |
| 覆盖率 | 86.7% | - | >30% | ✅ |
| TVR | 0.92 | 1.03 | - | 低换手 |

**分组 Sharpe (Raw)**: 1.10 → 0.91 → 0.93 → 0.66 → 0.55 → 0.04 → -0.06 → -0.36 (完美单调)

**年度 Sharpe (Raw)**: 2020=-0.18 | 2021=1.39 | 2022=3.92 | 2023=3.16
**年度 Sharpe (Neutral)**: 2020=0.18 | 2021=1.53 | 2022=4.63 | 2023=1.74

**关键特点**:
- Raw Mono=1.00（完美单调） — 截面排序极清晰
- 中性化后 LS 仅下降 3%（1.82→1.77），信号高度独立于市值/行业
- Segment stability=0.91（raw）/0.93（neutral），时间稳定性极好
- 2020年 neutral 后转正（-0.18→+0.18），2020负收益主要来自市值暴露

### amount_roughness_full — PASSED (neutral, borderline Mono)

成交额路径粗糙度 = mean(|Δamount|) / mean(amount)，衡量bar间成交额变化的不稳定性。

| 指标 | Raw | Neutral | 阈值 | 判定 |
|------|-----|---------|------|------|
| LS Sharpe | **1.46** | **1.04** | >0.9 | ✅✅ |
| Long Excess | **1.00** | **0.73** | >0.7 | ✅✅ |
| IR(LS) | **0.55** | **0.55** | >0.2 | ✅✅ |
| Mono (8组) | 0.57 | **0.71** | >0.7 | ❌✅ (borderline) |
| 覆盖率 | 86.7% | - | >30% | ✅ |
| TVR | 1.07 | 1.20 | - | 中等 |

**分组 Sharpe (Neutral)**: -0.12 → 0.52 → 0.32 → 0.49 → 0.35 → 0.23 → 0.02 → -0.15

**年度 Sharpe (Neutral)**: 2020=-0.66 | 2021=1.53 | 2022=2.16 | 2023=2.18

**关键特点**:
- IR=0.55 是本方向所有特征中最高的 — 信号极强但分组排序不够清晰
- Raw Mono=0.57（不达标）→ Neutral Mono=0.71（borderline），中性化改善了排序
- 中性化后 LS 下降 29%（1.46→1.04），部分信号来自市值暴露
- 与 vol_roughness（IR=0.53, Mono=0.71）高度相似：roughness 范式在 amount 维度成功泛化

## 失败特征诊断

### range_roughness_full（❌ IR=0.18）
- **假设**: bar range(H-L)的稳定性衡量"vol-of-vol"
- **实际**: |LS|=1.01 但反向（高range roughness=低收益），IR=0.18 不足
- **诊断**: HL range 本身是波动率代理（结论#22），其roughness = 波动率的波动率 ≈ quarticity（结论#28），不含独立流动性信息

### body_roughness_full（❌ LS=0.37）
- **假设**: |C-O|稳定性衡量方向性承诺的一致性
- **实际**: IR=0.45（不低），但LS=0.37（极弱），TVR=1.67（高）
- **诊断**: body(|C-O|)的截面变异被信号噪声淹没，尽管IC有区分度但无法转化为收益

### joint_reversal_vol_full（❌ IR=0.04）
- **假设**: 价格反转+成交量regime变化的复合事件频率有独立信号
- **实际**: IR=0.04（≈噪声），LE=0.97（尚可）但无截面区分度
- **诊断**: 复合事件太稀少（~13%的bar同时发生两种事件），截面变异被压缩到极窄范围

## 结论

1. **RS Amihud 是 Amihud 框架的高效升级版** — 使用 Rogers-Satchell OHLC 4点估计量替代 |ret|（close-close 2点估计量），在信号效率上大幅提升（raw Mono 1.00 vs 标准 amihud_illiq 0.86），且几乎不受市值/行业影响（中性化后 LS 仅降 3%）

2. **Amount roughness 验证了粗糙度范式的泛化** — 从 volume（vol_roughness）成功推广到 amount。但 amount=price×volume 引入了市值暴露（neutral 后 LS 降 29%），分组排序也不如 vol_roughness 清晰

3. **价格衍生指标的 roughness 退化为波动率代理** — range roughness 和 body roughness 都失败，与 wick_roughness（结论#66）一致。Roughness 范式仅在"交易活动量"维度（volume, amount）有效，在"价格表现"维度仍是波动率代理

4. **复合离散事件的交集过稀** — reversal × vol_regime 的联合频率（~13%）截面变异不足以选股。离散事件有效需要事件本身有足够的截面差异和频率

## Pending Features

- `rs_amihud_full` → `research/pending-rawdata/rs_amihud_full/`
- `amount_roughness_full` → `research/pending-rawdata/amount_roughness_full/`
