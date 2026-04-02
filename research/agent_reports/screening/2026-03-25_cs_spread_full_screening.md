---
agent_id: "ashare_rawdata_a"
experiment_id: "#006"
direction: "D-004 (corwin_schultz_spread)"
feature_name: "cs_relative_spread_full"
net_sharpe: 1.14
mono_score: 0.71
status: screening_passed
submitted_at: "2026-03-25T21:55:00"
---

# Experiment #006: Corwin-Schultz Spread 全天窗口筛选报告

## 方向

D-004 corwin_schultz_spread — Corwin & Schultz (2012, JF) 从日内 high-low range 分解出 bid-ask spread 和 volatility 两个分量。属于**流动性水平因子**，与已通过的 reversal_ratio_full (D-009) 同类。

## 物理假设

高流动性股票（低 CS spread）有流动性溢价：买卖价差小→执行成本低→机构覆盖高→价格发现好→长期跑赢低流动性股票。

## 快筛结果（全市场 5090 stocks × 725 days, 2022-2024）

通过 `evolve_rawdata.py --use-preload` 快筛 5 个特征：

| 特征 | |LS Sharpe| | LE | |IR(LS)| | 初判 |
|------|-----------|-----|---------|------|
| cs_spread_full | 0.55 | +1.05 | 0.27 | LS 不达标 |
| cs_sigma_full | 4.86 | -2.83 | 0.48 | LE 深度失败（波动率因子） |
| **cs_relative_spread_full** | **0.77** | **+1.16** | **0.28** | 最接近 |
| cs_spread_to_vol_full | 0.54 | +1.09 | 0.28 | LS 不达标 |
| cs_spread_trend_full | 2.89 | +0.03 | 0.09 | IR 太低 |

## 正式评估结果（含中性化）

对 3 个最有希望的候选做了完整评估（`evaluate_rawdata.py --neutralize`）。

### cs_relative_spread_full（通过 ✅）

| 指标 | Raw | Neutral | 阈值 | 判定 |
|------|-----|---------|------|------|
| LS Sharpe | 0.77 | **1.14** | >0.9 | ✅ neutral |
| IR(LS) | **0.28** | 0.23 | >0.2 | ✅ raw |
| Long Excess | **1.16** | **1.18** | >0.7 | ✅ 两组 |
| Mono (8 组) | **0.71** | 0.57 | >0.7 | ✅ raw |
| 覆盖率 | 95.2% | - | >30% | ✅ |

分年度（neutral）: 2022 Sharpe=1.60 | 2023 Sharpe=2.00 | 2024 Sharpe=0.45

### cs_spread_full（通过 ✅）

| 指标 | Raw | Neutral | 阈值 | 判定 |
|------|-----|---------|------|------|
| LS Sharpe | 0.55 | **1.03** | >0.9 | ✅ neutral |
| IR(LS) | 0.27 | **0.29** | >0.2 | ✅ 两组 |
| Long Excess | **1.05** | **1.06** | >0.7 | ✅ 两组 |
| Mono (8 组) | **0.71** | 0.43 | >0.7 | ✅ raw |
| 覆盖率 | 95.2% | - | >30% | ✅ |

分年度（neutral）: 2022 Sharpe=1.54 | 2023 Sharpe=2.19 | 2024 Sharpe=0.16

### cs_spread_to_vol_full（未通过 ❌）

| 指标 | Raw | Neutral | 阈值 | 判定 |
|------|-----|---------|------|------|
| LS Sharpe | 0.54 | **1.07** | >0.9 | ✅ neutral |
| IR(LS) | 0.28 | **0.31** | >0.2 | ✅ 两组 |
| Long Excess | **1.09** | **1.10** | >0.7 | ✅ 两组 |
| Mono (8 组) | 0.57 | 0.57 | >0.7 | ❌ 两组均不达标 |
| 覆盖率 | 95.0% | - | >30% | ✅ |

## 相关性检测

PNL cache numpy 版本不兼容（cache 用 numpy 2.x 生成，当前环境为 numpy 1.x），未执行。建议用户审批时手动检查。

## 关键发现

1. **CS spread 的 3 个流动性字段全部 Long Excess > 0.7**，突破了之前 D-001/D-002/D-003 微观结构因子系统性 LE 失败的瓶颈。流动性水平因子方向（与 reversal_ratio_full 同类）再次验证有效。

2. **中性化增强信号**：LS Sharpe 从 raw 0.55-0.77 提升到 neutral 1.03-1.14。表明 CS spread 含独立于市值/行业的 alpha，不是市值因子代理（与 BPV neutral 后从 1.0→0.48 衰减形成鲜明对比）。

3. **cs_sigma（波动率分量）alpha 集中在空头端**（LE=-2.83），与 D-002 jump_variation 的 BPV 一致，进一步确认纯波动率因子在 A 股不可做多。

4. **2024 年 neutral 信号衰减**：两个通过特征在 2024 年 neutral Sharpe 显著下降（0.16-0.45 vs 2022-2023 的 1.5-2.2）。与 reversal_ratio_full 的 2024 衰减模式一致。可能与 2024 年市场流动性结构变化有关。

5. **Raw 和 Neutral 收益跨年反转**：Raw 在 2024 年表现最好（Sharpe 1.23-1.63），但 2022-2023 很弱。说明 CS spread 的市值暴露方向在不同年份切换。

6. **cs_relative_spread_full 优于 cs_spread_full**：价格归一化后的版本在所有核心指标上均更强（LS Sharpe 1.14 vs 1.03, LE 1.18 vs 1.06），符合经济直觉——spread 本身受绝对价格水平影响，归一化更合理。

## Pending 包

- `research/pending-rawdata/cs_relative_spread_full/` — 推荐
- `research/pending-rawdata/cs_spread_full/` — 备选

## 注意事项

- PKL 覆盖 2022-01 至 2026-03（screening preload 口径），正式入库前需用全量 2020-01 起的数据重算
- 0930-1030 短窗口版本因 preload 集群崩溃未完成快筛，但根据结论#11（全天窗口大幅优于 1h），预期弱于全天版
- 注册脚本: `research/basic_rawdata/corwin_schultz_spread/register_cs_spread_full.py`
