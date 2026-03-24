---
agent_id: "ashare_rawdata_a"
experiment_id: "#001"
direction: "D-002 (jump_variation)"
feature_name: "jump_var_ratio_0930_1030"
net_sharpe: 1.00
mono_score: 0.57
status: screening_failed
submitted_at: "2026-03-24T21:40:00"
---

# Jump Variation 0930-1030 初筛报告

## 方向概述

**D-002 jump_variation**: 基于 Barndorff-Nielsen & Shephard (2006) 方法论，将日内已实现方差分解为连续（扩散）和跳跃两个成分。Bipower Variation (BPV) 稳健估计连续方差，RV - BPV 分离跳跃成分。跳跃强度、方向和体量占比提供了超越简单波动率的信息维度。

## 测试特征（5 个 Quick + 2 个 Full）

### Quick Eval (100 symbols) → 筛选出 2 个候选

| 特征 | 物理含义 | |LS Sharpe| | |IR| | 状态 |
|------|---------|-----------|------|------|
| bipower_var | 连续方差估计 (BPV) | 1.82 | 0.32 | → 进入全量 |
| jump_var_ratio | 跳跃方差占比 (JVR) | 1.04 | 0.21 | → 进入全量 |
| jump_intensity | 跳跃 bar 比例 | 2.43 | 0.01 | ❌ IR 极低 |
| signed_jump | 跳跃方向偏好 | 2.70 | 0.03 | ❌ IR 极低 |
| jump_vol_fraction | 跳跃成交量占比 | 2.81 | 0.04 | ❌ IR 极低 |

### Full Eval (5191 symbols, 含 Mono)

**neg_bipower_var_0930_1030**（取反：低 BPV → 做多）:

| 指标 | Raw | Neutralized | 阈值 | 判定 |
|------|-----|-------------|------|------|
| LS Sharpe | 1.00 | 0.48 | >0.9 | ❌ Neutral 不达标 |
| IR | 0.44 | 0.51 | >0.2 | ✅ 两组均通过 |
| Long Excess | 0.36 | 0.43 | >0.7 | ❌ 两组均不达标 |
| Mono | 1.00 | 0.57 | >0.7 | ❌ Neutral 不达标 |

**jump_var_ratio_0930_1030**（原始方向：高 JVR → 做多）:

| 指标 | Raw | Neutralized | 阈值 | 判定 |
|------|-----|-------------|------|------|
| |LS Sharpe| | 2.07 | 2.59 | >0.9 | ✅ 两组均通过 |
| |IR| | 0.36 | 0.34 | >0.2 | ✅ 两组均通过 |
| Long Excess | -0.32 | -0.34 | >0.7 | ❌ 两组均不达标 |
| Mono | 0.57 | 0.86 | >0.7 | ⚠️ Neutral 通过 |

## 失败诊断

### 核心问题：Alpha 集中在空头端

两个特征共同的失败原因是 **Long Excess 远未达标**。这意味着：
- 因子的多空价差（LS Sharpe）主要由空头端贡献
- 做多端（无论是低 BPV 还是高 JVR 股票）无法显著跑赢 CSI1000 TWAP 基准
- 对于实际应用（需要多头超额收益），这些因子价值有限

### bipower_var 的特别问题

- **Raw vs Neutral 剧烈衰减**：LS Sharpe 从 1.00 → 0.48，Mono 从 1.00 → 0.57
- 这说明 BPV 信号本质是**市值/行业因子的代理变量**：大市值、稳定行业的股票 BPV 低
- 中性化后信号大幅消失，剩余的独立 alpha 不足

### jump_var_ratio 的特别问题

- **100-symbol 样本方向误判**：Quick eval 显示负 Sharpe，但全量数据实际上两个方向都不行
- **LS Sharpe 强但 Long Excess 弱**：说明 JVR 的选股能力集中在空头端（高 JVR 股票的空头贡献大于低 JVR 股票的多头贡献）
- **Neutral Mono 0.86 达标**：说明 JVR 在行业市值中性化后仍有单调的分组排序，但绝对收益不足

### 假设 vs 实际

| 维度 | 假设 | 实际 |
|------|------|------|
| 跳跃成分识别信息事件 | JVR 捕捉离散信息到达 | JVR 更多捕捉噪声和流动性冲击 |
| 低 BPV → 低风险溢价 → 超额收益 | 低波动股票跑赢 | Raw 有效但本质是市值因子代理 |
| Long Excess 与 LS Sharpe 对称 | Long 和 Short 端均衡贡献 | Alpha 集中在 Short 端 |

### 关键发现

1. **BPV ≈ 市值因子的高频代理**：中性化后信号几乎消失，不构成独立 alpha
2. **JVR 的截面预测力来自空头端**：高跳跃占比的股票系统性underperform，但低跳跃占比的股票并不显著outperform
3. **100-symbol Quick eval 可靠性不足**：JVR 在 100 和 5191 symbols 上的方向完全翻转，凸显了小样本的危险性
4. **跳跃检测 (3×median threshold) 在 A 股 1m 数据上可能过于简单**：A 股的涨跌停、集合竞价等机制使得"跳跃"的定义需要更多 A 股特化处理

### 排除建议

D-002 jump_variation 在 0930-1030 窗口的当前实现不建议继续迭代：
- 核心瓶颈（Long Excess）在两个方向、两种处理下都未达标
- BPV 与已有 volatility bundle 的 realized_vol 高度相关
- 建议标记为 **"需更长窗口/不同阈值重试"** 而非完全排除
