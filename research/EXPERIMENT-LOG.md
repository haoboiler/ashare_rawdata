# 实验日志 — AShare RawData

## 一、已验证结论

### ✅ 方法论结论

3. **100-symbol Quick eval 不可靠判断因子方向** — jump_var_ratio 在 100 和 5191 symbols 上方向完全翻转。Quick eval 仅用于快速排除 IR 极低的特征，不能据此确定因子方向。（Exp#001）

### ✅ 信号维度结论

4. **A 股日内因子的 alpha 常集中在空头端** — bipower_var 和 jump_var_ratio 均表现为 |LS Sharpe| 高但 Long Excess 差。做空端（高波动/高跳跃股票）贡献了主要收益，做多端无法跑赢 CSI1000。设计因子时应同时关注 Long Excess，不能只看 LS Sharpe。（Exp#001）
5. **BPV (bipower variation) 本质是市值因子代理** — Raw Mono=1.0 但 Neutral Mono=0.57，说明 BPV 的排序能力几乎全部来自市值/行业暴露。（Exp#001）

### ⚠️ 重要注意事项

1. **A 股 1m 数据从 2020 年开始** — 回测起始不早于 2020-01-01，确保覆盖完整牛熊周期。（初始化）
2. **复权必须用 hfq** — `origin_*` 字段仅用于涨跌停判断，因子计算必须使用后复权价格。（初始化）

## 二、已排除方向

| 方向 | 原因 | 来源 |
|------|------|------|
| D-001 smart_money (0930-1030) | S=|r|/sqrt(v) 选出噪声bar非知情交易；IR极低(0.04-0.09)，集中度指标(s_ratio) IR=0.28但LS Sharpe仅0.29 | Exp#001 |
| D-002 jump_variation (0930-1030) | Long Excess 两个方向均不达标(<0.7)；BPV为市值因子代理(neutral后Sharpe从1.0→0.48)；JVR alpha集中在空头端 | Exp#001 |

## 三、实验记录

### Experiment #001: Smart Money + Jump Variation（2026-03-24）

**方向**: D-001 smart_money + D-002 jump_variation
**Agent**: ashare_rawdata_a
**结果**: 10 特征测试，0 通过

| 特征 | Net Sharpe (raw) | |IR| (raw) | Long Excess (raw) | w1 Mono | 状态 |
|------|-----------------|-----------|-------------------|---------|------|
| `smart_money_0930_1030` | -2.05 | 0.09 | -1.05 | - | ❌ IR不达标 |
| `smart_money_direction_0930_1030` | -2.96 | 0.04 | -1.91 | - | ❌ IR极低 |
| `smart_money_bar_ratio_0930_1030` | -0.52 | 0.23 | 0.43 | - | ❌ LS Sharpe不达标 |
| `smart_money_s_ratio_0930_1030` | -0.29 | 0.28 | 0.66 | - | ❌ LS Sharpe不达标 |
| `bulk_volume_oib_0930_1030` | -2.26 | 0.05 | -0.93 | - | ❌ IR不达标 |
| `neg_bipower_var_0930_1030` | 1.00 | 0.44 | 0.36 | 1.00/0.57(n) | ❌ Long Excess + Neutral衰减 |
| `jump_var_ratio_0930_1030` | -2.07 | 0.36 | -0.32 | 0.57/0.86(n) | ❌ Long Excess不达标 |
| `jump_intensity_0930_1030` | -2.43 | 0.01 | -0.56 | - | ❌ IR极低(quick) |
| `signed_jump_0930_1030` | -2.70 | 0.03 | -1.18 | - | ❌ IR极低(quick) |
| `jump_vol_fraction_0930_1030` | -2.81 | 0.04 | -1.03 | - | ❌ IR极低(quick) |

**关键发现**:
1. Smart Money 的 S 评分在 A 股 0930-1030 窗口选出的是噪声bar而非知情交易，核心因子 IR 仅 0.04-0.09
2. Jump Variation 的 BPV 和 JVR 有较强的 |LS Sharpe| 和 |IR|，但 alpha 集中在空头端，Long Excess 均不达标
3. BPV 中性化后信号大幅衰减（Sharpe 1.00→0.48, Mono 1.00→0.57），本质是市值因子代理

#### Related
- **报告**: `research/agent_reports/screening/2026-03-24_smart_money_0930_1030_screening.md`
- **报告**: `research/agent_reports/screening/2026-03-24_jump_variation_0930_1030_screening.md`
- **评估**: `.claude-output/evaluations/smart_money/`, `.claude-output/evaluations/jump_variation/`

## 四、统计

| 指标 | 值 |
|------|-----|
| 总实验数 | 1 |
| 已测特征数 | 10 |
| 已注册 Bundle | 8 (pv_stats×4, volatility×4) |
| Waiting | 0 |
| 已排除方向 | 2 (D-001 smart_money 0930-1030, D-002 jump_variation 0930-1030) |
| 已验证结论 | 5 |

## 五、技术备忘

（暂无）
