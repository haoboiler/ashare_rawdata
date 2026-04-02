---
agent_id: "ashare_rawdata_b"
experiment_id: "#024"
direction: "D-014 (intraday_momentum)"
feature_name: "batch_amihud_full"
net_sharpe: 1.73
mono_score: 1.00
status: screening_passed
submitted_at: "2026-03-26T12:00:00"
---

# D-014 Intraday Momentum / Amihud 路径变体 — 正式评估报告（2020-2024）

## 背景

上轮（Exp#023）通过快筛（2020-2023）产出 4 个特征候选，本轮完成 2020-2024 全量 pkl 计算和正式评估（含分组回测 Mono）。

## 正式评估结果（2020-01-01 至 2024-12-31，1211 交易日）

### 通过特征（3/4）

| 特征 | LS Sharpe (r/n) | LE Sharpe (r/n) | IR (r/n) | Mono (r/n) | 结果 |
|------|----------------|-----------------|----------|------------|------|
| `batch_amihud_full` | 1.73/1.93 | 1.22/1.20 | 0.33/0.46 | 1.00/0.86 | ✅ 全指标通过 |
| `up_amihud_full` | 1.45/1.47 | 1.08/1.17 | 0.35/0.42 | 1.00/0.71 | ✅ 全指标通过 |
| `max_excursion_amihud_full` | 1.08/0.98 | 0.88/0.80 | 0.25/0.42 | 1.00/0.86 | ✅ 全指标通过 |

### 失败特征（1/4）

| 特征 | LS Sharpe (r/n) | LE Sharpe (r/n) | IR (r/n) | Mono (r/n) | 结果 |
|------|----------------|-----------------|----------|------------|------|
| `cumret_area_amihud_full` | 0.66/0.18 | 0.64/0.52 | 0.26/0.42 | 0.86/0.71 | ❌ LS/LE 不达标 |

### 失败诊断：cumret_area_amihud_full

- **特征**: mean(|cumret_i|) / mean(amount_per_bar)
- **假设**: 累积收益路径的面积（积分）除以成交额应捕捉流动性溢价
- **实际**: 快筛（2020-2023）raw LS=1.08 → 正式（2020-2024）raw LS=0.66，信号衰减 39%
- **诊断**: 累积收益面积是路径长度的积分，对日内波动率的暴露比 bar 级 Amihud 更深。2024 年 A 股波动率结构变化导致该指标的截面区分能力下降
- **结论**: 从 pending 列表移除。cumret_area 比 batch_amihud 对波动率环境更敏感，不具备时间稳定性

## 年度分解（batch_amihud_full raw 为例）

| 年份 | Return | Sharpe | IC(LS) | IR(LS) |
|------|--------|--------|--------|--------|
| 2020 | 1.28% | 0.11 | 0.029 | 0.23 |
| 2021 | 20.57% | 1.57 | 0.040 | 0.28 |
| 2022 | 36.01% | 3.74 | 0.052 | 0.44 |
| 2023 | 36.65% | 4.30 | 0.068 | 0.54 |
| 2024 | 18.00% | 0.95 | 0.047 | 0.24 |

2024 年信号有所衰减（Sharpe 从 2022-2023 的 3.7-4.3 降至 0.95）但仍为正，整体 5 年稳定性可接受（seg_pos_ratio=0.8）。

## 分组单调性分析（batch_amihud_full raw）

| 组 | Sharpe | 年化收益 | 说明 |
|----|--------|----------|------|
| G1（低非流动性）| 1.04 | 15.92% | 最流动股票 |
| G2 | 0.97 | 14.09% | |
| G3 | 0.82 | 11.35% | |
| G4 | 0.63 | 8.19% | |
| G5 | 0.61 | 7.19% | |
| G6 | 0.48 | 5.36% | |
| G7 | -0.01 | -0.06% | |
| G8（高非流动性）| -0.24 | -2.26% | 最不流动股票 |

**Mono=1.0**：完美单调递减。因子方向为反向（低 Amihud = 高流动性 → 高收益），与流动性溢价假设一致。

## 相关性检测

相关性检测因内部评估环境问题未完成（pnl_cache 与 admission_corr_check 环境不兼容）。基于已知信息：

- `batch_amihud_full` 与已有 `amihud_illiq_full` 为同框架变体（sum|ret|/sum(amount) vs mean(|ret|/amount)），预计 |ρ| > 0.8
- `up_amihud_full` 是条件化变体（仅上涨 bar），与 `amihud_illiq_full` 相关但信息集不同
- `max_excursion_amihud_full` 是路径极值指标，与 bar 级 Amihud 构造不同

**相关性结果仅供参考，最终由用户审批决定。**

## 结论

- 3 个特征通过正式评估，进入 pending
- 1 个特征（cumret_area_amihud_full）因 2024 信号衰减从 pending 移除
- D-014 方向正式 explored 完毕

## 评估路径

- **PKL**: `.claude-output/analysis/intraday_momentum/{feature_name}.pkl`
- **评估**: `.claude-output/evaluations/intraday_momentum/{feature_name}/`
- **图表**: `file-{feature_name}-raw/charts/` 和 `file-{feature_name}-neutral-industry-size/charts/`
