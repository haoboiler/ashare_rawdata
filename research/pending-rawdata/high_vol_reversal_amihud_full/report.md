---
agent_id: "ashare_rawdata_a"
experiment_id: "#011"
direction: "D-006 (high_volume_ratio)"
feature_name: "high_vol_reversal_amihud_full"
net_sharpe: 1.85
mono_score: 1.00
status: screening_passed
submitted_at: "2026-03-26T03:20:00"
---

# D-006 高量 bar 进阶流动性探索 — Exp#011

## 研究方向

D-006 high_volume_ratio 方向最终探索轮次。上轮（Exp#010）已建议换方向，本轮设计 4 个全新角度做最后验证。

## 物理假设

1. **反转条件 Amihud**（reversal_amihud_full）：只在价格方向反转的 bar 上计算 Amihud。反转 bar 代表流动性供给事件——做市商吸收逆向订单流。这类 bar 的价格冲击度量的是「提供流动性的成本」，而非「消耗流动性的成本」。
2. **高量冲击比率**（high_vol_impact_ratio_full）：高量 bar 的 Amihud / 低量 bar 的 Amihud，度量价格冲击的非线性程度。
3. **日内流动性变化**（amihud_session_diff_full）：下午 Amihud - 上午 Amihud，捕捉日内流动性恶化。
4. **高量+反转双条件 Amihud**（high_vol_reversal_amihud_full）：结合高量过滤和反转条件，获取最纯粹的做市成本信号。

## 快筛结果（evolve, 全市场 2020-2023）

| 特征 | |LS Sharpe| | LE Sharpe | |IR| | 覆盖率 | 判定 |
|------|-----------|-----------|------|--------|------|
| `reversal_amihud_full` | 1.49 | +1.20 | 0.39 | 86.2% | ✅ 通过 |
| `high_vol_reversal_amihud_full` | 1.85 | +1.56 | 0.38 | 85.9% | ✅ 通过 |
| `high_vol_impact_ratio_full` | 6.60(反向) | -7.16 | 0.38 | 86.1% | ❌ 波动率代理 |
| `amihud_session_diff_full` | 5.01(反向) | -0.05 | 0.01 | 86.4% | ❌ 无信号 |

## 正式评估结果

### reversal_amihud_full

| 指标 | Raw | Neutral | 阈值 | 判定 |
|------|-----|---------|------|------|
| |LS Sharpe| | 1.49 | 1.39 | >0.9 | ✅ |
| |IR(LS)| | 0.39 | 0.44 | >0.2 | ✅ |
| LE Sharpe | +1.20 | +1.44 | >0.7 | ✅ |
| Mono (8组) | 0.71 | 0.71 | >0.7 | ✅ (边界) |
| 覆盖率 | 86.2% | - | >30% | ✅ |

**年度分解（raw LE）**：2020=-1.01 / 2021=+1.50 / 2022=+3.55 / 2023=+2.98
**年度分解（neutral LE）**：2020=-0.03 / 2021=+1.39 / 2022=+3.16 / 2023=+1.70

### high_vol_reversal_amihud_full ⭐

| 指标 | Raw | Neutral | 阈值 | 判定 |
|------|-----|---------|------|------|
| |LS Sharpe| | 1.85 | 1.54 | >0.9 | ✅ |
| |IR(LS)| | 0.38 | 0.46 | >0.2 | ✅ |
| LE Sharpe | +1.56 | +1.42 | >0.7 | ✅ |
| Mono (8组) | **1.00** | **0.86** | >0.7 | ✅ 完美/优秀 |
| 覆盖率 | 85.9% | - | >30% | ✅ |

**年度分解（raw LE）**：2020=-0.36 / 2021=+1.48 / 2022=+3.53 / 2023=+3.90
**年度分解（neutral LE）**：2020=+0.06 / 2021=+1.34 / 2022=+3.57 / 2023=+2.21

## 关键发现

1. **反转条件增强了 Amihud 的排序清晰度** — high_vol_reversal_amihud_full raw Mono=1.00（完美单调），比 high_vol_illiq_full（也是 Mono=1.00）多了一层反转过滤，但仍保持完美单调性。反转条件筛选出的是「做市行为」bar 而非「趋势交易」bar，降低了换手率（TVR 79.9% vs high_vol_illiq 的更高换手）。

2. **双条件过滤优于单条件** — high_vol_reversal_amihud_full（高量+反转）优于 reversal_amihud_full（仅反转，Mono=0.71）和 high_vol_illiq_full（仅高量，Mono=1.00 但 LE=1.60）。双条件的 LE=1.56 虽略低于 high_vol_illiq 的 LE=1.60，但 neutral IR 更高（0.46 vs 0.44），2023 年 raw Sharpe 3.90 远超 high_vol_illiq。

3. **冲击比率是波动率代理** — high_vol_impact_ratio（高量 bar Amihud / 低量 bar Amihud）强烈反向（|Sharpe|=6.60），与 vw_hl_spread（结论#22）失败模式一致。Amihud 在不同量级 bar 之间的比率实质捕捉的是波动率结构，而非独立的流动性信息。

4. **日内 Amihud 差异无截面信号** — amihud_session_diff IR=0.01，上午/下午流动性变化在截面上无区分度。A 股日内 Amihud 演化模式可能对所有股票高度一致（U 型），个股差异不足。

## 相关性提醒

两个通过特征均为 Amihud 变体，与已 pending 的 amihud_illiq_full、high_vol_illiq_full 可能存在较高相关性。建议用户审批时进行相关性检测。

## 文件路径

- 注册脚本: `research/basic_rawdata/high_volume_advanced/register_high_volume_advanced_full.py`
- Evolve 产出: `.claude-output/evolve/20260326-030510/`
- 评估 (reversal_amihud): `.claude-output/evaluations/high_volume_ratio/reversal_amihud_full/`
- 评估 (high_vol_reversal_amihud): `.claude-output/evaluations/high_volume_ratio/high_vol_reversal_amihud_full/`
- 因子 pkl: `.claude-output/analysis/high_volume_ratio/`
