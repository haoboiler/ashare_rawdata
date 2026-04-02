# AShare RawData Knowledge Base

> 自动生成: 2026-03-26 14:30 | 由 `scripts/regenerate_kb.py` 生成
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
8. **日内成交量分布截面区分度不足** — 8 个尾盘成交量占比特征全部 IR < 0.2（最高 0.17），A 股日内成交量 U 型分布模式固定，个股间差异不足以支撑选股。与价格微观结构因子不同，这类因子不是空头端集中问题，而是信号本身就弱。（Exp#003）
9. **日内方向性动量同样失败在 Long Excess** — apm_momentum 方向 10 个字段（AM/PM 两窗口各 5 个）全部 LE 不达标（最佳 +0.04），PM 窗口 |LS Sharpe| 达 7.39 但 alpha 仍集中在空头端。日内动量在 A 股是反转效应（T+1 散户追涨→次日抛压），即使从"波动率/微观结构"转向"方向性动量"也无法突破 Long Excess 瓶颈。（Exp#004）
10. **流动性溢价在 A 股日内数据上存在** — reversal_ratio_full（全天价格方向反转频率）是首个 Long Excess 达标的特征（+1.21），证实了从「价格动态」转向「流动性水平」因子方向的有效性。高反转频率 = bid-ask bounce 频繁 → 流动性溢价。（Exp#005）
11. **全天窗口大幅优于 1h 窗口（反转频率类因子）** — reversal_ratio 从 1h 窗口 |Sharpe| 0.22 提升到全天 1.09（5 倍提升）。~237 bars vs ~60 bars 使频率估计更稳健，跨午休的信息也被捕捉。（Exp#005）
12. **CS spread 中性化后信号增强** — cs_relative_spread_full 的 |LS Sharpe| 从 raw 0.77→neutral 1.14（+48%），cs_spread_full 从 0.55→1.03。与 BPV（neutral 后从 1.0→0.48 衰减）形成鲜明对比，说明 CS spread 含独立于市值/行业的流动性 alpha。（Exp#006）
13. **日内流动性水平因子方向二次验证** — CS spread 的 3 个流动性字段（spread/relative_spread/spread_to_vol）全部 LE > 0.7，继 reversal_ratio_full (D-009) 之后再次确认：日内**流动性水平**因子（而非价格动态/微观结构因子）是突破 Long Excess 瓶颈的关键方向。（Exp#006）
14. **2024 年日内流动性因子 neutral 信号普遍衰减** — cs_relative_spread_full neutral Sharpe 2022=1.60/2023=2.00/2024=0.45；reversal_ratio_full 同样 2024 衰减。可能与 2024 年 A 股市场流动性结构变化（量化交易监管等）有关。（Exp#006）
15. **纯成交量分布指标系统性失败在 Long Excess** — volume_entropy/gini/dispersion_ratio/autocorr1 全部 LE 为负。与价格微观结构因子相同的失败模式：识别"坏股票"（成交量不均匀=差流动性）但无法选出"好股票"。volume_autocorr1 信号极强（|IR|=0.74）但纯空头端。（Exp#007）
16. **离散化 regime 切换频率 >> 连续分布统计** — vol_regime_transitions（离散二值化切换计数）远优于 volume_entropy/gini（连续分布统计），与 reversal_ratio >> Roll spread 一致。可能因为离散化消除了绝对量级的市值暴露，保留了纯粹的时序切换信息。（Exp#007）
17. **Amihud 非流动性（|return|/amount）是有效的流动性水平因子** — amihud_illiq_full LS Sharpe=2.37, LE=1.79, IR=0.38，raw Mono=0.86。使用 amount 而非 volume 避免了市值暴露。这是继 CS spread（基于 high-low range）之后，用完全不同的估计方法验证了流动性溢价假设。（Exp#008）
18. **方向性信号/趋势追踪在 A 股日频无效** — order_flow_imbalance（IR=0.01）和 flow_toxicity（LE=-14.45）再次确认：日内方向性净买卖压力和趋势追踪信号在 A 股无法产生有效因子，与结论#6、#9 一致。（Exp#008）
19. **Regime transition 范式仅在 volume 维度上有效** — 将 vol_regime_transitions 扩展到 amount/bar_range/amihud/body_ratio/vwap_cross 共 5 个新维度，均不如 volume。amount_regime_transitions 虽 LS/LE/IR 优秀但 Mono 仅 0.57（amount=price×volume，价格水平引入非线性排序干扰）。Volume（纯股数）是 regime transition 范式最纯净的输入。（Exp#009）
20. **Amount 适合做水平量，不适合做 transition** — 对比：amihud_illiq（|ret|/amount 水平量）Mono=0.86 ✅ vs amount_regime_transitions（切换频率）Mono=0.57 ❌。Amount 信息通过连续水平指标（如 Amihud）更有效地转化为截面因子。（Exp#009）
21. **高量 bar Amihud 优于全量 Amihud** — high_vol_illiq_full（top-25% 量 bar）raw Mono=1.00 完美单调 vs amihud_illiq_full raw Mono=0.86；neutral IR=0.44 vs 0.47。只计算活跃交易期的价格冲击消除了安静期噪声，但两者可能高度相关。（Exp#010）
22. **直接 HL range 是波动率代理，非流动性因子** — vw_hl_spread/kyle_lambda/effective_half_spread 三个基于 HL range 的因子全部强烈反向（|Sharpe|=4-7），中性化后仍反向（|Sharpe|=3.9）。这是 low-vol premium 而非流动性溢价。与 CS spread 的区别：Corwin-Schultz 用相邻 bar 差分，分离出了独立于波动率的流动性成分；直接 HL/mid 没有做到这一分离。（Exp#010）

## §三 已排除方向

| 方向 | 原因 | 来源 |
|------|------|------|
| D-001 smart_money (0930-1030) | S=|r|/sqrt(v) 选出噪声bar非知情交易；IR极低(0.04-0.09)，集中度指标(s_ratio) IR=0.28但LS Sharpe仅0.29 | Exp#001 |
| D-002 jump_variation (0930-1030) | Long Excess 两个方向均不达标(<0.7)；BPV为市值因子代理(neutral后Sharpe从1.0→0.48)；JVR alpha集中在空头端 | Exp#001 |
| D-003 variance_ratio (0930-1030) | 5特征全部Long Excess深度负值(最佳-1.50)；abs_ar1虽|LS Sharpe|=11.44、|IR|=0.61但所有分组绝对收益为负；因子只能识别差股票不能选出好股票 | Exp#002 |
| D-013 closing_volume_ratio (full-day) | 8特征全部IR<0.2(最高0.17)，LE全为负值；日内成交量分布截面区分度不足，中性化后无改善 | Exp#003 |
| D-011 apm_momentum (0930-1130/1300-1457) | 10特征全部LE失败（最佳+0.04）；日内方向性动量仍为反转效应，alpha集中在空头端；与结论#6一致 | Exp#004 |
| D-012 time_segmented_momentum (full-day) | 18特征全部LE≤+0.27（2 bundle: 纯收益10+量价交互8）；段级反转≠bar级反转；alpha全集中空头端 | Exp#011 |
| D-010 hurst_exponent (full-day) | 两轮9特征仅vol_roughness_full独立有效（已pending）；R/S Hurst退化为波动率代理；粗糙度变体与一阶vol_roughness相关0.9948；log变换破坏Mono(0.86→0.43) | Exp#020+#022 |
| D-014 intraday_momentum (full-day) | 3轮22特征，3 pending+4冗余通过+15失败。所有通过特征均为 Amihud 框架变体（|f(price)|/amount），未产生超越流动性水平的新因子类别。回撤路径与偏移路径相关0.87，影线分离与总影线相关0.98 | Exp#023+#029+#030 |
| D-015 return_distribution (full-day) | 两轮10特征全部Mono不达标；连续矩(skewness/kurtosis)最佳Mono=0.29(neutral)，离散频率(extreme_freq)最佳Mono=0.43；收益分布形态截面呈U型非线性关系 | Exp#024 |
| D-025 temporal_microstructure (full-day) | 两轮14特征仅1个Amihud变体通过(open_gap_amihud)；非Amihud时序结构(gap反转/lead-lag/量加速/路径效率/量价同步)全部LE<-1.0；离散计数范式迁移到gap维度无效 | Exp#035+#036 |

## §四 研究方向池

| ID | 名称 | 优先级 | 状态 | 认领者 |
|----|------|--------|------|--------|
| D-001 | smart_money | high | exhausted | - |
| D-002 | jump_variation | high | exhausted | - |
| D-003 | variance_ratio | medium | exhausted | - |
| D-004 | corwin_schultz_spread | medium | exhausted | - |
| D-005 | volume_entropy | medium | exhausted | - |
| D-006 | high_volume_ratio | medium | exhausted | - |
| D-007 | realized_quarticity | low | exhausted | - |
| D-008 | price_acceleration | low | exhausted | - |
| D-009 | roll_spread | low | exhausted | - |
| D-010 | hurst_exponent | low | exhausted | ashare_rawdata_a |
| D-011 | apm_momentum | medium | exhausted | - |
| D-012 | time_segmented_momentum | medium | exhausted | - |
| D-013 | closing_volume_ratio | medium | exhausted | - |
| D-014 | intraday_momentum | low | exhausted | ashare_rawdata_b |
| D-015 | return_distribution | medium | exhausted | ashare_rawdata_a |
| D-016 | vwap_microstructure | medium | claimed | ashare_rawdata_a |
| D-017 | pv_concordance | medium | claimed | ashare_rawdata_a |
| D-018 | amihud_asymmetry | medium | claimed | ashare_rawdata_a |
| D-019 | price_absorption_depth | medium | claimed | ashare_rawdata_a |
| D-020 | ohlc_microstructure_decomposition | medium | claimed | ashare_rawdata_a |
| D-021 | range_discovery_dynamics | medium | claimed | ashare_rawdata_a |
| D-022 | microstructure_noise | medium | claimed | ashare_rawdata_b |
| D-023 | multi_bar_price_structure | medium | claimed | ashare_rawdata_a |
| D-024 | cross_bar_stability | medium | claimed | ashare_rawdata_a |
| D-025 | temporal_microstructure | medium | claimed | ashare_rawdata_b |
| D-026 | robust_liquidity_estimators | medium | claimed | ashare_rawdata_a |

## §五 实验统计

| 指标 | 值 |
|------|-----|
| 总实验数 | 38 |
| 已测特征数 | 269 |
| 已注册 Bundle | 8 (pv_stats×4, volatility×4) |
| Pending | 48 (reversal_ratio_full, cs_relative_spread_full, cs_spread_full, vol_regime_transitions_full, amihud_illiq_full, high_vol_illiq_full, reversal_amihud_full, high_vol_reversal_amihud_full, extreme_amihud_full, amihud_diff_mean_full, amihud_vol_accel_full, amihud_low_vol_full, amihud_return_weighted_full, accel_illiq_full, high_vol_accel_illiq_full, reversal_accel_illiq_full, extreme_accel_illiq_full, low_vol_accel_illiq_full, vol_roughness_full, batch_amihud_full, up_amihud_full, max_excursion_amihud_full, vwap_cross_amihud_full, high_vol_vwap_cross_amihud_full, concordant_amihud_full, discordant_amihud_full, down_amihud_full, high_vol_down_amihud_full, doji_amihud_full, high_vol_doji_amihud_full, wick_amihud_full, high_vol_wick_amihud_full, close_disp_amihud_full, high_vol_close_disp_amihud_full, upper_wick_amihud_full, lower_wick_amihud_full, body_amihud_full, open_disp_amihud_full, high_vol_inside_amihud_full, inside_bar_amihud_full, engulfing_amihud_full, excess_bounce_amihud_full, bar_pair_noise_amihud_full, rs_amihud_full, amount_roughness_full, open_gap_amihud_full, log_impact_amihud_full, harmonic_amihud_full) |
| 已排除方向 | 10 (D-001, D-002, D-003, D-010, D-011, D-012, D-013, D-014, D-015, D-025) |
| 已验证结论 | 93 |
