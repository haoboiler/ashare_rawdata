---
agent_id: "ashare_rawdata_b"
experiment_id: "#003"
direction: "D-011 (apm_momentum)"
feature_name: "apm_momentum_0930_1130 / apm_momentum_1300_1457"
net_sharpe: 7.39
mono_score: 0
status: screening_failed
submitted_at: "2026-03-25T17:50:00"
---

# Evolve Benchmark 报告：APM Momentum 方向

## 任务说明

本轮为 **evolve 热路径 benchmark**，目标是验证 `evolve_rawdata.py --use-preload` 的端到端速度，并顺带获取两个 apm_momentum 候选的 quick-eval 基线数据。**不做正式 pkl 导出和完整 evaluate**。

## 一、性能 Benchmark

### 环境

- RAY_ADDRESS: 192.168.0.107:26380
- Preload actor: ashare_rawdata_preload
- 股票数: 5090
- 交易日数: 725 (2022-01-01 ~ 2024-12-31)
- field_preset: basic6 (close/open/high/low/volume/amount)
- num-workers: 32

### 时间分解

| 阶段 | Candidate 1 (0930_1130) | Candidate 2 (1300_1457) |
|------|------------------------|------------------------|
| Preload compute | 9.075s | 7.467s |
| Quick-eval (5 fields) | 106.91s | 104.91s |
| **单候选总耗时** | **~116s** | **~112s** |

| 汇总指标 | 值 |
|----------|-----|
| 总 wall time | **~230s (3m50s)** |
| Compute 吞吐 | ~5090 stocks / 7-9s = **565-680 stocks/s** |
| Quick-eval 单字段耗时 | ~21s/field |
| 每候选平均耗时 | ~115s |

### 速度评估

**Preload compute 热路径达到预期速度**。5090 只股票 × 725 个交易日的全量计算在 7-9 秒内完成，throughput 约 600 stocks/s，对于 5 输出字段的 bundle 而言表现良好。

**瓶颈在 quick-eval 阶段**：每个 candidate 的 5 个字段评估需要约 105 秒（~21s/field），这是因为 quick-eval 需要构建完整的日度因子矩阵 + 计算 LS 回测统计量。这是 `compute_rawdata_local.py` 内置逻辑的正常开销，不在 preload 热路径优化范围内。

**结论**：对于典型的 2-candidate explicit evolve，总耗时约 4 分钟是可接受的。如果要做 10+ candidate 的 generator evolve，需要约 20 分钟——建议后续考虑 quick-eval 并行化或轻量化。

## 二、Quick-eval 结果

### Leaderboard（按 |sharpe_abs_net| 排序）

| Rank | Field | |LS Sharpe| | Long Excess Sharpe | |IR(LS)| | Coverage |
|------|-------|-----------|-------------------|---------|----------|
| 1 | pm_vw_avg_return_1300_1457 | **7.39** | -4.00 | 0.21 | 95.2% |
| 2 | pm_late_return_1300_1457 | 5.46 | -3.81 | 0.27 | 95.2% |
| 3 | pm_return_1300_1457 | 5.11 | -4.48 | 0.19 | 95.2% |
| 4 | pm_close_loc_1300_1457 | 4.80 | -1.75 | 0.18 | 94.4% |
| 5 | am_acceleration_0930_1130 | 4.63 | -2.95 | 0.005 | 95.2% |
| 6 | pm_acceleration_1300_1457 | 4.17 | -2.58 | 0.21 | 95.2% |
| 7 | am_vw_avg_return_0930_1130 | 3.54 | -4.06 | 0.05 | 95.2% |
| 8 | am_late_return_0930_1130 | 2.70 | -3.24 | 0.04 | 95.2% |
| 9 | am_return_0930_1130 | 2.21 | -3.48 | 0.04 | 95.2% |
| 10 | am_close_loc_0930_1130 | 0.57 | +0.04 | 0.06 | 95.1% |

**注**：所有字段 `invert_sign=true`，即因子方向需翻转（高动量 → 差未来收益 = 日内动量反转效应）。

### 候选级汇总

| Candidate | Best Field | Fitness (|LS Sharpe|) | Best Long Excess |
|-----------|-----------|----------------------|-----------------|
| apm_momentum_1300_1457 | pm_vw_avg_return | 7.39 | -1.75 (close_loc) |
| apm_momentum_0930_1130 | am_acceleration | 4.63 | +0.04 (close_loc) |

## 三、信号质量诊断

### 筛选阈值检查

| 指标 | 阈值 | 最佳值 | 通过？ |
|------|------|--------|--------|
| |LS Sharpe| | > 0.9 | 7.39 (pm_vw_avg_return) | ✅ |
| |IR(LS)| | > 0.2 | 0.27 (pm_late_return) | ✅ |
| Long Excess Net Sharpe | > 0.7 | +0.04 (am_close_loc) | ❌ |
| 数据覆盖率 | > 30% | 95.2% | ✅ |

**Long Excess 全面失败**：10 个字段中 9 个 Long Excess Sharpe 深度负值（-1.75 到 -4.48），仅 `am_close_loc_0930_1130` 勉强为正（+0.04）但远不达标。

### 与已有结论的一致性

本轮结果完全验证了知识库结论 #6：**日内价格时序动态因子系统性失败在 Long Excess**。

具体表现：
- 所有动量/收益率字段（return, late_return, vw_avg_return, acceleration）都是空头端信号——高动量股票未来表现差
- `close_loc`（收盘位置）虽然 LS Sharpe 相对弱，但 Long Excess 最小负值，说明位置类信号与纯方向性信号有差异
- PM 窗口（1300-1457）整体信号强度是 AM 窗口（0930-1130）的约 1.5-2 倍

### 为什么 APM Momentum 也失败了

假设是：方向性动量因子（vs 之前的波动率/微观结构因子）能捕捉到机构买入信号，选出好股票。

**实际**：日内动量在 A 股市场仍然是反转效应主导。高日内动量的股票次日倾向于回调，而非延续。这与 A 股 T+1 制度下散户追涨 → 次日抛压的市场微观结构一致。动量因子虽然 LS Sharpe 高（说明反转效应强），但 alpha 仍然集中在空头端。

## 四、结论与建议

1. **evolve 热路径工作正常**，preload compute 7-9s 表现优秀，端到端 4 分钟/2 候选可接受
2. **APM momentum 方向 Long Excess 不达标**，与已排除的 D-001/D-002/D-003 结论一致
3. **建议**：
   - D-011 apm_momentum 可考虑标记为已排除方向（原因：Long Excess 系统性失败，与已有结论 #6 一致）
   - 如需继续探索方向性因子，应转向截面相对动量或 alpha 分解方向，而非日内绝对动量
   - evolve driver 的 quick-eval 并行化可作为后续优化方向

## 产出文件

- Run 目录: `.claude-output/evolve/apm_momentum_benchmark/`
- Leaderboard: `.claude-output/evolve/apm_momentum_benchmark/generations/generation_000/leaderboard.csv`
- Field scores: `.claude-output/evolve/apm_momentum_benchmark/generations/generation_000/field_scores.csv`
- Quick-eval reports:
  - `.../candidates/001_register_apm_momentum_0930_1130/reports/`
  - `.../candidates/002_register_apm_momentum_1300_1457/reports/`
