---
agent_id: "ashare_rawdata_a"
experiment_id: "#008"
direction: "D-006 (high_volume_ratio)"
feature_name: "amihud_illiq_full"
net_sharpe: 2.37
mono_score: 0.86
status: screening_passed
submitted_at: "2026-03-26T00:40:00"
---

# 初筛报告：amihud_illiq_full

## 方向与假设

**方向**: D-006 high_volume_ratio — 量价交互流动性冲击因子
**假设**: 日内 Amihud 非流动性（|return|/amount）测量市场深度。流动性差的股票需要更高的流动性溢价补偿，因此高 Amihud 值 → 高预期收益。使用 amount（成交额）而非 volume（成交量）避免绝对股数的市值暴露。

## Bundle 设计

`liquidity_impact_0930_1130_1300_1457` (5 fields, 全天窗口 237 bars):

| 特征 | 物理含义 | 快筛结果 |
|------|---------|---------|
| `amihud_illiq_full` | 日内 Amihud 非流动性 | **shortlist** |
| `flow_toxicity_full` | 信息流毒性（连续同方向 run length） | ❌ LE=-14.45 |
| `large_trade_reversal_full` | 大单后反转频率 | ❌ LE=-1.83 |
| `vol_impact_ratio_full` | 高低量 bar 价格冲击比 | ❌ LE=-5.17 |
| `order_flow_imbalance_full` | 订单流失衡 | ❌ IR=0.01 |

## 正式评估结果

### 筛选指标

| 指标 | raw | neutral | 阈值 | 通过 |
|------|-----|---------|------|------|
| LS Sharpe | 2.37 | 2.31 | >0.9 | ✅ raw+n |
| IR(LS) | 0.38 | **0.47** | >0.2 | ✅ raw+n |
| LE Sharpe | 1.79 | 1.78 | >0.7 | ✅ raw+n |
| Mono | **0.86** | 0.57 | >0.7 | ✅ raw only |
| 覆盖率 | 95.2% | 95.2% | >30% | ✅ raw+n |

**raw 版本 5/5 全部通过。neutral IR 增强 +24%，含独立于市值/行业的 alpha。**

### 分组回测 (raw, w1)

| Group | Sharpe | Yield | Excess |
|:-----:|-------:|------:|-------:|
| 1 (最强) | 1.67 | 26.80% | 29.16% |
| 2 | 1.49 | 22.43% | 25.80% |
| 3 | 1.44 | 20.79% | 24.54% |
| 4 | 0.97 | 13.38% | 17.30% |
| 5 | 1.18 | 15.06% | 19.05% |
| 6 | 0.76 | 9.19% | 13.22% |
| 7 | 0.64 | 7.03% | 11.06% |
| 8 (最弱) | 0.41 | 4.10% | 8.11% |

### 年度稳定性

| 年份 | raw Sharpe | neutral Sharpe | raw IR | neutral IR |
|------|-----------|----------------|--------|-----------|
| 2022 | 3.71 | 3.60 | 0.44 | 0.57 |
| 2023 | 3.67 | 2.20 | 0.53 | 0.50 |
| 2024 | 1.26 | 1.62 | 0.26 | 0.38 |

三年全正收益。2024 年衰减但仍正向（neutral Sharpe 1.62 > 之前 CS spread 的 0.45）。

## 关键发现

1. **Amihud 非流动性是继 CS spread 之后第二个基于不同方法的流动性因子**。CS spread 基于 high-low range，Amihud 基于 |return|/amount，计算方法完全不同但都反映流动性水平。
2. **neutral 后 IR 增强**（0.38→0.47），与 CS spread 行为一致（结论#12），进一步验证流动性方向含独立 alpha。
3. **2024 年表现远优于 CS spread**：neutral Sharpe 1.62 vs CS spread 的 0.45。可能因为 Amihud 捕捉了更微观的价格冲击信息。
4. **其他 4 个特征全部失败**，与已有结论一致：
   - flow_toxicity（信息毒性）LE 深度失败 → 连续方向 = 趋势追踪 = A 股反转效应
   - vol_impact_ratio LE 失败 → 纯量价弹性 = 波动率代理
   - order_flow_imbalance IR 极低 → 方向性信号在 A 股无效
5. **raw Mono=0.86 但 neutral Mono=0.57**：说明部分排序能力来自市值暴露（小市值股票流动性差 → Amihud 高），但核心信号仍独立存在。

## 数据可用性

- 评估区间：2022-01-01 至 2024-12-31（3 年）
- 无 >30 天连续缺失
- 覆盖率 95.2%
- 全天窗口（237 bars）

## 相关性风险

需要与已有 pending 因子检查相关性：
- vs `cs_relative_spread_full` / `cs_spread_full`：两者都是流动性测度，可能有中等相关性（但计算方法完全不同）
- vs `reversal_ratio_full`：离散 vs 连续，低相关性预期
- vs `vol_regime_transitions_full`：量 regime 切换 vs 价格冲击，低相关性预期

## 文件清单

- 注册脚本: `research/basic_rawdata/liquidity_impact/register_liquidity_impact_full.py`
- 因子 pkl: `.claude-output/analysis/high_volume_ratio/amihud_illiq_full.pkl`
- 评估目录: `.claude-output/evaluations/high_volume_ratio/amihud_illiq_full/`
- Pending 包: `research/pending-rawdata/amihud_illiq_full/`
