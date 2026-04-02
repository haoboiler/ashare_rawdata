---
agent_id: "ashare_rawdata_a"
experiment_id: "#009"
direction: "D-006 (high_volume_ratio)"
feature_name: "high_vol_illiq_full"
net_sharpe: 1.95
mono_score: 1.00
status: screening_passed
submitted_at: "2026-03-26T02:50:00"
---

# 初筛报告：D-006 liquidity_level_2 + liquidity_advanced 批量快筛

## 方向与假设

**方向**: D-006 high_volume_ratio — 量价交互流动性因子（第二批）
**假设**: 在 Amihud illiquidity（Exp#008 已通过）的基础上，探索更多流动性度量维度：
1. 高量 bar 专属 Amihud（隔离高活跃期的价格冲击）
2. 零回报率（Lesmond 1999，离散流动性度量）
3. Amihud 变异系数（流动性一致性）
4. HL 成交量加权 spread（Parkinson 波动率变体）
5. Kyle's Lambda（量价相关性）
6. 有效半幅 spread
7. 流动性弹性

## 快筛结果（全市场 2020-2023，8 个特征）

### Bundle 1: liquidity_level_2（3 个特征）

| 特征 | |LS Sharpe| | IR(LS) | LE Sharpe | 状态 |
|------|-----------|--------|-----------|------|
| `high_vol_illiq_full` | **1.95** | 0.32 | **+1.60** | **shortlist** |
| `zero_return_ratio_full` | 0.78 (反向) | 0.35 | 0.79 (反向) | ❌ |LS|<0.9 |
| `illiq_variability_full` | 0.01 | 0.38 | 0.16 | ❌ 无信号 |

### Bundle 2: liquidity_advanced（5 个特征）

| 特征 | |LS Sharpe| | IR(LS) | LE Sharpe | 状态 |
|------|-----------|--------|-----------|------|
| `vw_hl_spread_full` | 6.78 (反向) | 0.60 | -6.60 | ❌ 波动率代理 |
| `kyle_lambda_full` | 4.68 (反向) | 0.52 | -4.36 | ❌ 波动率代理 |
| `effective_half_spread_full` | 3.99 (反向) | 0.50 | -2.91 | ❌ 波动率代理 |
| `high_vol_amihud_full` | 1.95 | 0.34 | 1.57 | 跳过（与 high_vol_illiq 近似重复） |
| `liquidity_resilience_full` | 0.13 | 0.38 | 1.21 | ❌ LS<0.9 |

## 正式评估结果：high_vol_illiq_full

### 筛选指标

| 指标 | raw | neutral | 阈值 | 通过 |
|------|-----|---------|------|------|
| LS Sharpe | **1.95** | **1.77** | >0.9 | ✅ raw+n |
| IR(LS) | 0.32 | **0.44** | >0.2 | ✅ raw+n |
| LE Sharpe | **1.60** | **1.44** | >0.7 | ✅ raw+n |
| Mono | **1.00** | **0.86** | >0.7 | ✅ raw+n |
| 覆盖率 | 86.7% | 86.7% | >30% | ✅ |

**raw 和 neutral 均 5/5 全部通过。neutral IR 增强 +37%（0.32→0.44），含强独立 alpha。**

### 分组回测 (raw)

| Group | Sharpe | Yield | Excess |
|:-----:|-------:|------:|-------:|
| 1 (最强) | 1.38 | 17.39% | 19.41% |
| 2 | 1.27 | 14.94% | 18.26% |
| 3 | 1.13 | 12.54% | 16.22% |
| 4 | 0.95 | 9.86% | 13.69% |
| 5 | 0.73 | 7.13% | 11.05% |
| 6 | 0.44 | 3.96% | 7.92% |
| 7 | -0.00 | -0.01% | 3.96% |
| 8 (最弱) | -0.30 | -2.38% | 1.58% |

**Raw Mono = 1.0（完美单调性），Group 1-6 全部正收益。**

### 年度稳定性

| 年份 | raw Sharpe | neutral Sharpe | raw IR | neutral IR |
|------|-----------|----------------|--------|-----------|
| 2020 | -0.08 | 0.35 | 0.20 | 0.29 |
| 2021 | 1.39 | 1.37 | 0.24 | 0.42 |
| 2022 | 3.36 | 4.08 | 0.37 | 0.61 |
| 2023 | 4.09 | 2.61 | 0.49 | 0.56 |

注：评估数据覆盖 2020-2023（preload 窗口限制），2024 数据未包含。amihud_illiq_full 的 2024 经验（neutral Sharpe=1.62）表明同类因子在 2024 仍有效。

### 正式评估结果：vw_hl_spread_full

| 指标 | raw | neutral | 判定 |
|------|-----|---------|------|
| LS Sharpe | -6.60 | **-3.91** | 反向，信号独立 |
| IR(LS) | -0.60 | -0.62 | 中性化不衰减 |
| 每年 | -91%/-68%/-100%/-64% | -59%/-43%/-59%/-39% | 四年均深亏 |

**诊断**: vw_hl_spread_full 本质是日内波动率因子（HL range = Parkinson volatility estimator），不是流动性因子。中性化后信号仍存在（|Sharpe|=3.91）说明有独立于市值/行业的 alpha，但方向反转：低波动→高收益 = low-volatility premium。与流动性溢价假设无关。

## 关键发现

1. **高量 bar Amihud 比全量 Amihud 质量更高** — raw Mono 从 0.86（amihud_illiq_full）提升到 1.00（high_vol_illiq_full）。只计算活跃交易期的价格冲击，消除了安静期噪声。
2. **零回报率的流动性溢价不成立** — 反向（高零回报率→低收益），说明零回报 bar 反映的是「股票无人关注」而非「交易成本高」，两者导致不同的定价含义。
3. **Amihud CV（流动性一致性）无信号** — illiq_variability |LS Sharpe|=0.01，流动性的二阶矩（变异性）不构成独立定价因子。
4. **HL range 系列本质是波动率而非流动性** — vw_hl_spread、kyle_lambda、effective_half_spread 三个基于 HL range 的因子全部强烈反向（|Sharpe|=4-7），中性化后仍反向，本质是 low-vol premium。与 CS spread（同为 HL 衍生但基于相邻 bar 差分）不同，直接 HL/mid 没有分离出流动性成分。
5. **流动性弹性信号太弱** — liquidity_resilience |LS Sharpe|=0.13 but LE=1.21，说明弹性好的股票收益不错但因子区分度不够。

## 数据可用性

- 评估区间：2020-01-01 至 2023-12-31（4 年，preload 限制）
- 无 >30 天连续缺失
- 覆盖率 86.7%
- 全天窗口（237 bars）

## 相关性风险

high_vol_illiq_full 与已 pending 的 amihud_illiq_full 可能高度相关（两者均为 Amihud 度量，差异仅在 bar 选择），最终由用户审批决定。

## 文件清单

- 注册脚本: `research/basic_rawdata/liquidity_level_2/register_liquidity_level_2_full.py`
- 因子 pkl: `.claude-output/analysis/high_volume_ratio/high_vol_illiq_full.pkl`
- 评估目录: `.claude-output/evaluations/high_volume_ratio/high_vol_illiq_full/`
- Pending 包: `research/pending-rawdata/high_vol_illiq_full/`
