# AShare RawData Knowledge Base

> 自动生成: 2026-03-19 21:42 | 由 `scripts/regenerate_kb.py` 生成
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

1. **A 股 1m 数据从 2020 年开始** — 回测起始不早于 2020-01-01，确保覆盖完整牛熊周期。（初始化）
2. **复权必须用 hfq** — `origin_*` 字段仅用于涨跌停判断，因子计算必须使用后复权价格。（初始化）

## §三 已排除方向

_尚无已排除方向_

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
| 总实验数 | 0 |
| 已测特征数 | 0 |
| 已注册 Bundle | 8 (pv_stats×4, volatility×4) |
| Waiting | 0 |
| 已排除方向 | 0 |
| 已验证结论 | 2 |
