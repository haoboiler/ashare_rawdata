---
agent_id: "ashare_rawdata_a"
experiment_id: "#001"
direction: "D-001 (smart_money)"
feature_name: "smart_money_s_ratio_0930_1030"
net_sharpe: 0.29
mono_score: 0
status: screening_failed
submitted_at: "2026-03-24T20:20:00"
---

# Smart Money 0930-1030 初筛报告

## 方向概述

**D-001 smart_money**: 基于 Guangfa 证券 Smart Money Factor 方法论，通过 S = |return|/sqrt(volume) 评分识别"聪明钱"交易 bar，选取累计成交量达 20% 的最高 S 值 bar，计算其 VWAP 溢价、方向性信号、集中度指标和 BVC 订单不平衡度。

## 测试特征（5 个）

| 特征 | 物理含义 | LS Sharpe (raw) | |IR| (raw) | Long Excess (raw) | 状态 |
|------|---------|-----------------|-----------|-------------------|------|
| `smart_money_0930_1030` | 聪明钱 VWAP 溢价 | -2.05 | 0.09 | -1.05 | ❌ IR 不达标 |
| `smart_money_direction_0930_1030` | 聪明钱方向性信号 | -2.96 | 0.04 | -1.91 | ❌ IR 极低 |
| `smart_money_bar_ratio_0930_1030` | 聪明钱 bar 占比 | -0.52 | 0.23 | 0.43 | ❌ LS Sharpe + Long Excess 不达标 |
| `smart_money_s_ratio_0930_1030` | S 评分集中度 | -0.29 | 0.28 | 0.66 | ❌ LS Sharpe 远不达标 |
| `bulk_volume_oib_0930_1030` | BVC 订单不平衡 | -2.26 | 0.05 | -0.93 | ❌ IR 不达标 |

**最佳特征**: `smart_money_s_ratio_0930_1030`（IR=0.28 达标，但 |LS Sharpe|=0.29 远低于 0.9 阈值）

## 失败诊断

### 核心问题

1. **S 评分选择的不是"聪明钱"**：S = |return|/sqrt(volume) 选出的是高价格冲击/低成交量的 bar。在 A 股开盘首小时，这些更可能是流动性冲击和噪声交易，而非知情交易。LS Sharpe 大幅为负证实了这一点——高 S 值 bar 的 VWAP 溢价方向实际上是反向指标。

2. **信号不稳定**：核心 smart_money 因子 |IR| 仅 0.09，说明价格冲击方向在截面上的预测力极不稳定。高 S bar 在不同市场环境下的含义变化大。

3. **集中度指标有信号但幅度不足**：s_ratio（IR=0.28）显示"S 评分集中度"具有一定截面预测力（集中度高→未来收益略好），但信号强度（LS Sharpe 0.29）不足以产生可盈利的组合。

### 假设 vs 实际

| 维度 | 假设 | 实际 |
|------|------|------|
| S 评分识别知情交易 | 高 S → 信息含量高 | 高 S → 噪声/流动性冲击 |
| 聪明钱 VWAP 溢价预测未来收益 | 正相关 | 反向（负 Sharpe） |
| 0930-1030 窗口含信息 | 开盘信息丰富 | 噪声太大，信噪比低 |

### 排除结论

D-001 smart_money 方向在 0930-1030 窗口的初始实现未达到筛选标准。核心假设（S 评分识别知情交易）在 A 股 1m 数据上不成立——高价格冲击 bar 更多是噪声。集中度指标有微弱信号但不足以入库。

### 下一步

- 本方向暂不继续，转向 D-002 jump_variation（基于更稳健的计量经济学理论）
- 未来可考虑：不同 S 评分公式（Amihud |r|/amount）、不同时间窗口（午后更安静）、不同选择阈值（10%）
