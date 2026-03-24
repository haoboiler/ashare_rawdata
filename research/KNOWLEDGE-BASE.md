# AShare RawData Knowledge Base

> 自动生成: 2026-03-25 00:58 | 由 `scripts/regenerate_kb.py` 生成
> Layer 0 入口 — 研究员启动时必读

## §一 已注册 RawData

| Bundle | 字段数 | 时间窗口 | Slot | 状态 |
|--------|--------|----------|------|------|
| pv_stats_0930_1030 | 15 | 09:30-10:30 | midday | ✅ validated |
| pv_stats_0930_1130 | 15 | 09:30-11:30 | midday | ✅ validated |
| pv_stats_1300_1400 | 15 | 13:00-14:00 | evening | ✅ validated |
| pv_stats_0930_1130_1300_1457 | 15 | 全天 | evening | ✅ validated |
| volatility_0930_1030 | 20 | 09:30-10:30 | midday | ✅ validated |
| volatility_0930_1130 | 20 | 09:30-11:30 | midday | ✅ validated |
| volatility_1300_1400 | 20 | 13:00-14:00 | evening | ✅ validated |
| volatility_0930_1130_1300_1457 | 20 | 全天 | evening | ✅ validated |

共计: 8 bundles, 140 fields

## §二 已验证结论（Top 20）

3. **100-symbol Quick eval 不可靠判断因子方向** — jump_var_ratio 在 100 和 5191 symbols 上方向完全翻转。Quick eval 仅用于快速排除 IR 极低的特征，不能据此确定因子方向。（Exp#001）
4. **A 股日内因子的 alpha 常集中在空头端** — bipower_var 和 jump_var_ratio 均表现为 |LS Sharpe| 高但 Long Excess 差。做空端（高波动/高跳跃股票）贡献了主要收益，做多端无法跑赢 CSI1000。设计因子时应同时关注 Long Excess，不能只看 LS Sharpe。（Exp#001）
5. **BPV (bipower variation) 本质是市值因子代理** — Raw Mono=1.0 但 Neutral Mono=0.57，说明 BPV 的排序能力几乎全部来自市值/行业暴露。（Exp#001）
6. **日内价格时序动态因子系统性失败在 Long Excess** — 3 个方向（smart_money, jump_variation, variance_ratio）共 15 个特征全部 Long Excess 不达标。即使 |LS Sharpe| 达 11.44、|IR| 达 0.61，所有分组绝对收益仍为负。这类因子本质识别「交易行为异常的差股票」，无法选出跑赢 CSI1000 的好股票。后续应转向截面水平/流动性因子或方向性因子。（Exp#001+#002）
7. **abs_AR(1) 信号 neutral 后增强** — 与 BPV 不同，abs_ar1 的 |LS Sharpe| 从 9.37→11.44（neutral 后增强），说明收益率自相关结构含有独立于市值/行业的信号。但仍无 Long Excess。（Exp#002）
1. **A 股 1m 数据从 2020 年开始** — 回测起始不早于 2020-01-01，确保覆盖完整牛熊周期。（初始化）
2. **复权必须用 hfq** — `origin_*` 字段仅用于涨跌停判断，因子计算必须使用后复权价格。（初始化）

## §三 已排除方向

| 方向 | 原因 | 来源 |
|------|------|------|
| D-001 smart_money (0930-1030) | S=|r|/sqrt(v) 选出噪声bar非知情交易；IR极低(0.04-0.09)，集中度指标(s_ratio) IR=0.28但LS Sharpe仅0.29 | Exp#001 |
| D-002 jump_variation (0930-1030) | Long Excess 两个方向均不达标(<0.7)；BPV为市值因子代理(neutral后Sharpe从1.0→0.48)；JVR alpha集中在空头端 | Exp#001 |
| D-003 variance_ratio (0930-1030) | 5特征全部Long Excess深度负值(最佳-1.50)；abs_ar1虽|LS Sharpe|=11.44、|IR|=0.61但所有分组绝对收益为负；因子只能识别差股票不能选出好股票 | Exp#002 |

## §四 研究方向池

| ID | 名称 | 优先级 | 状态 | 认领者 |
|----|------|--------|------|--------|
| D-001 | smart_money | high | available | - |
| D-002 | jump_variation | high | available | - |
| D-003 | variance_ratio | medium | available | - |
| D-004 | corwin_schultz_spread | medium | available | - |
| D-005 | volume_entropy | medium | available | - |
| D-006 | high_volume_ratio | medium | available | - |
| D-007 | realized_quarticity | low | available | - |
| D-008 | price_acceleration | low | available | - |
| D-009 | roll_spread | low | available | - |
| D-010 | hurst_exponent | low | available | - |
| D-011 | apm_momentum | medium | available | - |
| D-012 | time_segmented_momentum | medium | available | - |
| D-013 | closing_volume_ratio | medium | available | - |
| D-014 | intraday_momentum | low | available | - |

## §五 实验统计

| 指标 | 值 |
|------|-----|
| 总实验数 | 2 |
| 已测特征数 | 15 |
| 已注册 Bundle | 8 (pv_stats×4, volatility×4) |
| Waiting | 0 |
| 已排除方向 | 3 (D-001 smart_money 0930-1030, D-002 jump_variation 0930-1030, D-003 variance_ratio 0930-1030) |
| 已验证结论 | 7 |
