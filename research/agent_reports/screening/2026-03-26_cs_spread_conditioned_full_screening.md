---
agent_id: "ashare_rawdata_a"
experiment_id: "#018"
direction: "D-004 (corwin_schultz_spread)"
feature_name: "cs_high_vol_spread_full"
net_sharpe: 0.43
mono_score: 0
status: screening_failed
submitted_at: "2026-03-26T06:00:00"
---

# D-004 CS Spread 条件化变体筛选报告

## 实验概要

| 项目 | 内容 |
|------|------|
| 方向 | D-004 corwin_schultz_spread |
| Agent | ashare_rawdata_a |
| 实验 | #018 |
| 假设 | Amihud 条件化范式（高量/反转/量加权）迁移到 CS spread 框架 |
| 日期 | 2026-03-26 |

## 物理假设

将 D-006（Amihud 方向）中成功的条件化范式迁移到 CS spread。CS spread 利用相邻 bar 高低价对的统计分解分离流动性成分与波动率成分（结论#22），在不同市场条件下（高量、反转、量加权）计算 CS spread 应产生更纯粹的流动性信号。

## 测试特征

| # | 特征 | 经济含义 |
|---|------|----------|
| 1 | cs_high_vol_spread_full | 仅高量 bar 对的 CS spread（活跃交易时的执行成本） |
| 2 | cs_reversal_spread_full | 仅方向反转 bar 对的 CS spread（bid-ask bounce 事件） |
| 3 | cs_vw_spread_full | 成交量加权 CS spread（经济权重估计） |
| 4 | cs_spread_roughness_full | CS spread 路径粗糙度（执行成本不可预测性） |
| 5 | cs_high_vol_reversal_spread_full | 高量+反转双条件 CS spread（最纯粹 bounce 成本） |

## 快筛结果（全市场 5013 stocks × 970 days, 2020-2023）

| 特征 | LS Sharpe | LE | IR(LS) | Coverage | 状态 |
|------|-----------|-----|--------|----------|------|
| cs_high_vol_spread_full | **0.43** | **+0.52** | **0.30** | 86.7% | ❌ LS+LE 不达标 |
| cs_reversal_spread_full | -3.40 (反向) | -1.40 | 0.05 | 86.2% | ❌ 反向+IR极低 |
| cs_vw_spread_full | -0.79 (反向) | -1.47 | 0.28 | 86.7% | ❌ 反向 |
| cs_spread_roughness_full | -1.81 (反向) | -0.13 | 0.04 | 86.4% | ❌ IR极低 |
| cs_high_vol_reversal_spread_full | -4.94 (反向) | -2.13 | 0.02 | 86.1% | ❌ 反向+IR极低 |

**全部未通过筛选**。

## 失败诊断

### 核心发现：Amihud 条件化范式不可迁移到 CS spread

| 对比维度 | Amihud（成功） | CS spread（失败） |
|----------|---------------|-----------------|
| 基础量 | |return| / amount | H-L range 对的统计分解 |
| 条件化效果 | 选择特定经济事件（高量→价格发现，反转→流动性供给） | 减少统计量但不增加经济含义 |
| 高量条件 | 隔离活跃交易期的价格冲击 → Mono 从 0.86→1.00 | 信号减弱（LS 从 0.55→0.43），H-L range 不因量而改变含义 |
| 反转条件 | 反转 bar = 做市行为事件 → 纯粹流动性供给成本 | 反转 pair = 噪声选择（IC=0.05），H-L 已在 pair 层面捕捉 bounce |
| 双条件 | high_vol + reversal → IR=0.46（最高） | IR=0.02（最低），严重信号退化 |

**根本原因**：
1. **Amihud 是 bar 级量**（|r_i|/amount_i），条件化选择 bar 改变了经济事件的选集
2. **CS spread 是 pair 级估计**（基于相邻 bar 的 H-L range 几何关系），H-L range 已经隐式地包含了 bid-ask bounce 信息
3. 对 CS pair 做条件化子选择，不等于选择不同的经济事件——只是用更少的数据做同一个估计
4. 反转条件实际选出了 H-L range 更大的 pair（因为反转方向的 bar 价格波动更大），引入了波动率偏差

### 对比原始 CS spread

| 原始 CS spread (Exp#006) | 条件化 CS spread (本轮) |
|--------------------------|------------------------|
| cs_spread_full: raw LS=0.55, neutral=1.03 | cs_high_vol_spread_full: raw LS=0.43（↓22%） |
| cs_relative_spread_full: raw LS=0.77, neutral=1.14 | 所有条件化变体均弱于原始 |
| 5 特征，2 通过 | 5 特征，0 通过 |

### 为什么 cs_high_vol_spread_full 也不能通过

- raw LS = 0.43，即使按原始 CS spread 的中性化增益（1.87x），也仅达 ~0.80，低于 0.9
- raw LE = 0.52，中性化后 LE 改善幅度极小（原始 CS spread: 1.05→1.06），无法达到 0.7

## 结论

1. **条件化范式具有方法特异性**——对 Amihud（bar 级量）有效的条件化不可迁移到 CS spread（pair 级分解）
2. D-004 方向的有效信号已被 Exp#006 的 2 个原始特征完全捕捉
3. D-004 总计 2 轮实验，10 个特征，2 个通过（均为原始 CS spread）
4. **建议 D-004 标记为 exhausted**——核心信号已捕获，条件化空间不可扩展

## 相关文件

- **Formula**: `research/basic_rawdata/corwin_schultz_spread/register_cs_spread_conditioned_full.py`
- **Evolve 产出**: `.claude-output/evolve/20260326-055423/`
