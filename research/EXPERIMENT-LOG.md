# 实验日志 — AShare RawData

## 一、已验证结论

### ✅ 方法论结论

3. **100-symbol Quick eval 不可靠判断因子方向** — jump_var_ratio 在 100 和 5191 symbols 上方向完全翻转。Quick eval 仅用于快速排除 IR 极低的特征，不能据此确定因子方向。（Exp#001）

### ✅ 信号维度结论

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

23. **时间分段收益模式 = 价格动态因子的粗粒度版本** — 将 1min bar 聚合到 30min 段后计算收益集中度/反转/路径粗糙度，18 个字段 LE 全部 ≤ +0.27。bar 级别 reversal_ratio 有效（捕捉 bid-ask bounce），而 segment 级别 reversal_ratio 失败（捕捉中频趋势反转），说明微观结构信号不可通过时间聚合保留。（Exp#011）

24. **A 股有效日内因子的边界已明确** — 历经 11 次实验、104 个特征，通过筛选的因子类型仅限于：(1) 流动性水平量（CS spread, Amihud, reversal_ratio）；(2) 流动性 regime 切换（vol_regime_transitions）。所有收益/价格行为模式（动量、方差比、时间分段、成交量分布）均因 alpha 集中在空头端而失败。（Exp#001-#011）

25. **反转条件 + 高量过滤进一步提升 Amihud 排序清晰度** — high_vol_reversal_amihud_full（高量+反转双条件 Amihud）raw Mono=1.00、neutral Mono=0.86、neutral IR=0.46，2023 年 raw Sharpe=3.90。反转条件筛选「做市行为」bar（流动性供给事件），高量条件排除安静期噪声，双条件交叉构建了最纯粹的流动性供给成本度量。（Exp#012）

26. **Amihud 量比率（高量/低量）是波动率代理** — high_vol_impact_ratio_full（高量 bar Amihud / 低量 bar Amihud）|Sharpe|=6.60 强烈反向，失败模式与 vw_hl_spread 一致。Amihud 在不同量级 bar 间的比率捕捉波动率结构而非独立流动性信息。（Exp#012）

27. **日内 Amihud 上下午差异无截面信号** — amihud_session_diff_full IR=0.01。A 股日内 Amihud 演化模式（U 型）对所有股票高度一致，上下午差异不构成截面区分度。（Exp#012）

28. **纯 Quarticity（四阶矩）是波动率/市值代理** — realized_quarticity_full |LS Sharpe|=10.76、kurtosis_ratio_full |LS Sharpe|=11.61，但 LE 均深度负值（-10.63/-7.33）。与结论#5（BPV 是市值代理）一致，高阶矩放大了波动率暴露。（Exp#013）

29. **条件 Amihud（极端收益 bar）是有效的流动性因子** — extreme_amihud_full（仅计算 |r|>2×median(|r|) bar 的 |r|/amount）LS Sharpe=1.47, LE=1.19, IR=0.39, Mono=0.86。这是第三种 Amihud 条件化方式（全 bar → 高量 bar → 极端收益 bar），均产生有效因子，说明 Amihud 框架在不同条件下具有鲁棒性。（Exp#013）

30. **r^4/amount 不如条件 |r|/amount** — amihud_quarticity_full（r^4 权重）IR≈0，而 extreme_amihud_full（离散选择极端 bar 后用 |r|/amount）IR=0.39。连续的 r^4 权重过度集中在极少数超大收益 bar，信号被噪声淹没；离散条件选择更稳健，与结论#16（离散 >> 连续）一致。（Exp#013）

31. **流动性路径粗糙度（bar-to-bar Amihud 变化）是独立于 Amihud 水平的有效因子** — amihud_diff_mean_full（连续 bar 间 |ΔAmihud| 均值 / Amihud 均值）raw Mono=1.00、neutral Mono=0.71、LS Sharpe=1.24、LE=1.21。高粗糙度=流动性分钟级频繁波动→执行成本不可预测→投资者要求溢价。这是 Amihud 的**二阶属性**（变化率）而非一阶（水平量），与 illiq_variability（全天 CV，无信号）不同——连续 bar 间的时序邻接变化比整体离散度更有效。（Exp#014）

32. **Amihud 自相关是波动率聚集的代理** — amihud_autocorr1_full |LS Sharpe|=9.39、LE=-6.21，典型空头端集中模式。Amihud 的时序持续性（高自相关=聚集性非流动性）本质是 volatility clustering 的流动性维度映射，失败模式与 BPV、HL range 一致。（Exp#014）

33. **Amihud 水平量的条件化空间已饱和** — 5 轮实验（#008/#010/#012/#014/#015）共 25 个特征测试，8 个通过。有效的条件化方式包括：全 bar、高量 bar、反转 bar、高量+反转、极端收益 bar、量增 bar、低量 bar、收益加权。所有这些本质都是"从不同角度测量同一个 Amihud 水平量信号"，预计彼此高度相关。方向 D-006 建议标记为 exhausted。（Exp#015）

34. **Amihud 分布形状统计量系统性无效** — HHI（集中度，LE=-0.51）和 CV（变异系数，|LS|=0.01）与 tail_ratio/autocorr（Exp#014）失败模式一致。所有将 Amihud bar 分布转化为形状/离散度统计量的方式均失败。结论：Amihud 的截面选股信号仅存在于水平量维度，形状/高阶矩维度无效。（Exp#014+#015）

35. **Amihud 框架可拓展到价格加速度维度** — accel_illiq_full（|acceleration|/amount）LS=1.67, LE=1.20, IR=0.35；high_vol_accel_illiq_full LS=1.93, LE=1.50, IR=0.36, raw Mono=1.00。加速度 = ret[t+1]-ret[t]（价格路径曲率），|曲率|/成交额 衡量"单位交易下价格方向的不稳定性"。这是 Amihud 框架的第四类变体（全 bar→高量→极端收益→加速度），进一步验证了 |f(price)|/amount 模板的通用性。（Exp#016）

36. **纯加速度统计量是波动率代理** — abs_accel_mean（LE=-3.91）、accel_std（LE=-4.89）、accel_kurtosis（LE=-7.40）全部深度负值。加速度的绝对水平/分布直接反映价格路径的粗糙程度∝波动率，未经 amount 归一化则无法分离流动性成分。与 BPV（结论#5）、HL range（结论#22）失败模式完全一致。（Exp#016）

37. **加速度 regime transition 不同于收益率 reversal ratio** — accel_regime_trans_full LE=-0.22（失败），而 reversal_ratio_full LE=+1.21（成功）。原因：加速度符号切换的基线频率 ~85%（ret 差分高频正负交替是白噪声特征），远高于收益率方向切换频率 ~50%，截面离散度被压缩，无法提供选股区分度。（Exp#016）

38. **加速度 Amihud 条件化空间遵循与收益率 Amihud 相同的饱和规律** — reversal/extreme/low-vol 三种条件化方式在 |accel|/amount 上全部通过（LS Sharpe 1.49~1.66, LE 1.12~1.39），与 D-006 的 |return|/amount 条件化结果完全一致。D-008 两轮实验共 11 个特征中 5 个通过，全部是同一 |accel|/amount 信号的不同 bar 选择变体。条件化空间已饱和，且与 D-006 Amihud 系列预计高度相关。（Exp#016+#017）

39. **条件化范式具有方法特异性——CS spread 不可条件化** — 将 Amihud 成功的条件化（高量/反转/量加权/双条件）迁移到 CS spread，5 个变体全部失败。Amihud 条件化有效是因为选择特定 bar 改变了经济事件选集（高量=价格发现, 反转=做市行为）；CS spread 基于 pair 级 H-L range 分解，H-L range 已隐式包含 bid-ask bounce，条件化 pair 只减少统计量不增加经济含义。反转条件还引入波动率偏差（选出 H-L range 更大的 pair），导致信号反向。（Exp#018）

40. **CS spread 的有效信号仅限原始均值——结构修改无效** — 多尺度（5m 聚合）、尺度比率（1m/5m）、amount 归一化、session 非对称性四个维度全部失败。5m 聚合破坏了 CS 的微结构分解有效性（与结论#22 一致）；尺度比率和 session 比率都退化为波动率/市值代理；spread/amount 混合完全被 Amihud 覆盖。D-004 三轮 14 特征仅 2 通过，方向确认 exhausted。（Exp#019）


<!-- Agent append: 2026-03-26T07:34:13.136221 -->
41. **Volume 路径粗糙度是有效的流动性不确定性代理** — vol_roughness_full（mean|Δvol|/mean(vol)）LS=1.42, LE=0.85, IR=0.53, Mono=0.71。这是继 amihud_diff_mean_full（Amihud 路径粗糙度，LS=1.24）之后，路径粗糙度范式在 volume 维度的成功验证。高 vol_roughness = 交易活动不稳定 = 执行成本不确定性溢价。（Exp#020）

42. **R/S Hurst exponent 在日内 237 bars 上退化为波动率代理** — hurst_volume/return/amount/range 全部 |LS|=3.9-5.7 强烈反向，Mono=0.00（完全反单调）。R/S 的 rescaled range 本质测量局部波动范围，短序列上无法分离持续性与波动率。neutral 后信号不衰减（|LS| 4.77→4.64），说明是波动率因子而非市值代理。（Exp#020）

43. **方差比从 returns 迁移到 volume 不改变信号本质** — vol_var_ratio_full（volume 方差比）|LS|=5.64, |IR|=0.67，与 D-003 return 方差比呈现相同失败模式。方差比捕捉的「可预测性」信号在任何输入维度上都退化为自相关/波动率代理。（Exp#020）

44. **加速度 Amihud 在 2024 年保持稳健——优于其他日内流动性因子** — 5 个 |accel|/amount 变体 2024 neutral Sharpe 1.31-1.65，远优于 CS spread 2024 neutral Sharpe 0.45（结论#14）。中性化后 2024 表现反而强于 raw（raw 0.77-1.32 → neutral 1.31-1.65），说明 2024 年独立于市值/行业的纯流动性 alpha 仍然稳健。2020 年 neutral 也转正（4/5 特征），之前的负收益主要来自市值暴露。（Exp#021）

45. **Volume 路径粗糙度的变体全部退化为一阶差分** — vol_accel_full（二阶差分 mean|Δ²vol|/mean(vol)）通过所有指标阈值（LS=1.79, LE=1.25, IR=0.56, Mono=0.86），但与 vol_roughness_full 截面相关性 0.9948。对于噪声时序，连续差分近似独立，mean|Δ²x|≈√2·mean|Δx|，二阶差分本质是一阶差分的缩放。路径粗糙度在 volume 维度上只有一个独立自由度。（Exp#022）

46. **Log 变换破坏粗糙度因子的截面区分度** — log_vol_roughness_full（mean|Δlog(vol+1)|）Raw Mono 从 vol_roughness 的 0.71→0.43，分组1 excess 仅 0.018。vol_roughness 的有效信号恰恰依赖极端量变（大单/block trades）来区分流动性不确定性，log 变换压缩了这些关键差异。这与 CS spread（用 raw HL range）优于 log range 的观察一致——流动性信号在极值端。（Exp#022）

<!-- Agent append: 2026-03-26T09:10:00 -->
47. **纯路径拓扑特征全部是波动率代理** — path_efficiency（|total_ret|/sum|ret_i|）|LS|=8.23, LE=-5.36; vw_path_efficiency |LS|=6.78, LE=-2.05; cumret_area_norm |LS|=5.64, LE=-5.33; max_excursion_ratio |LS|=3.86, LE=-1.72。日内累积收益曲线的几何形状（效率/面积/偏移比）本质度量路径复杂度∝波动率，未经 amount 归一化则无法分离流动性成分。与 BPV（结论#5）、HL range（结论#22）、quarticity（结论#28）失败模式完全一致。（Exp#023）

48. **Amount 归一化可以挽救路径拓扑特征** — cumret_area_norm LE=-5.33（失败）→ cumret_area_amihud（mean|cumret|/mean(amount)）LE=+1.11（通过）；max_excursion_ratio LE=-1.72 → max_excursion_amihud（max|cumret|/total_amount）LE=+1.35。这是 Amihud 框架的进一步泛化：不仅 bar 级 |ret|/amount 有效，path 级 |cumret|/amount 也有效。|f(path)|/amount 模板的通用性再次验证。（Exp#023）

49. **Batch Amihud（sum|ret|/sum(amount)）≈ Bar-level Amihud** — batch_amihud LS=2.12 vs amihud_illiq LS=2.37（接近）。volume-weighted 聚合（高成交额 bar 贡献更多到分母）几乎不改变截面排序。两种聚合方式预计高度相关。（Exp#023）

50. **方向性 Amihud 各自有效但非对称性无效** — up_amihud（ret>0 bar 的 |ret|/amount）LS=1.58, LE=1.28; down_amihud LS=1.47, LE=1.14; 但 amihud_directional_asym（两者差值）|IR|=0.12 接近噪声。A 股日内买卖双方价格冲击的截面排序一致，方向差异不构成独立信号。与结论#18（方向性信号无效）一致。（Exp#023）

51. **宏观 Amihud（|净收益|/总成交额）信号极弱** — macro_amihud |LS|=0.18, IR=0.287。全天净收益 = |close_end/close_start - 1| 因反转 bar 互相抵消而丢失微观结构信息。Bar 级 |ret|/amount（保留每个 bar 的绝对冲击）远优于 path 级 |net_ret|/amount。（Exp#023）

52. **日内收益分布矩信号极强但非单调** — return_kurtosis_full |LS Sharpe|=11.55（raw）/9.38（neutral），|IR|=0.53（neutral 后增强），但 Mono=0.14（raw）/0.29（neutral）。信号集中在极端低峰度端（Group 1 sharpe=-6.43 vs 其余 -0.14~-3.24），截面呈 U 型/非线性关系而非单调排序。return_skewness_full 同样 Mono=0.0/0.14，tail_asymmetry_full Mono=0.14/0.57（最好但仍不达标）。（Exp#024）

53. **离散化对分布矩维度仅有边际改善** — 与结论#16（volume regime transitions >> volume entropy）不同，将连续分布矩转为离散极端频率（extreme_return_freq/positive_extreme_freq）后，Mono 仅从 0.29→0.43，仍远低于 0.7。extreme_volume_ratio neutral Mono=0.29。分布形态的非线性/U 型本质无法通过离散化克服——分布矩维度根本不存在单调的截面排序关系。（Exp#024）


<!-- Agent append: 2026-03-26T10:25:14.267105 -->
58. **量价协调性计数特征是空头端集中信号** — pv_concordance_ratio（|LS|=5.61, LE=-3.99）和 pv_corr（|LS|=7.22, LE=-2.98, |IR|=0.79）信号极强但 LE 深度负值。高量价同步性（价格和成交量同时异常活跃）=投机/事件驱动交易=只能识别差股票。量价联合行为的**水平统计量**（计数/相关系数）与纯价格动态因子（结论#6）、纯成交量分布因子（结论#15）有相同的失败模式。（Exp#026）

59. **联合事件条件 Amihud 有效** — concordant_amihud（|ret|>med AND vol>med 条件 Amihud）raw Mono=1.00、LS=1.65、LE=1.56；discordant_amihud（|ret|>med AND vol<med 条件 Amihud）raw Mono=0.86、LS=1.48、LE=1.36。量价联合事件作为 Amihud 的事件选择器有效，进一步验证了 |f(price)|/amount 模板在不同 bar 选择条件下的通用性（结论#33+#38+#54）。但 Amihud 条件化空间进一步饱和。（Exp#026）
<!-- Agent append: 2026-03-26T11:30:00 -->
62. **Doji 条件（wick > body）是 Amihud 框架的有效新事件选择器** — doji_amihud_full（仅在影线>实体 bar 上计算 |ret|/amount）LS=1.68, LE=1.39, IR=0.38, Mono=0.86。Doji bar = 价格探索被订单簿拒绝并推回 = "吸收事件"，在此类 bar 上的 Amihud 衡量吸收期间的流动性成本。这是继 high-vol / reversal / extreme-ret / accel / concordant/discordant / down 之后的第 8 种条件 Amihud 事件选择器。（Exp#028）

63. **Wick（影线）是 Amihud numerator 的有效新维度** — wick_amihud_full（mean((H-L-|C-O|)/amount)）neutral LS=2.36, LE=1.43, IR=0.49, Mono=0.86。raw Mono=1.00（完美单调）但 raw LE=0.68（边缘），neutral 后大幅增强（LS 1.30→2.36, LE 0.68→1.43）。Wick/amount 衡量"每单位交易的被拒绝价格探索"，是 |ret|/amount 的互补视角：Amihud 看成功的价格冲击，wick Amihud 看失败的价格冲击。（Exp#028）

64. **离散频率计数在"价格吸收"维度失败在 LE** — absorption_freq（vol>med AND |ret|<med 占比）|LS|=3.69 但 LE=-0.27；depth_volume_ratio 类似。频率计数成功（如 reversal_ratio LE=+1.21）需要事件本身有截面差异，而"高量低冲击"事件频率受制于日内中位数定义，截面变异被市值结构主导。不是所有离散计数都有效。（Exp#028）

65. **Bar 效率（|C-O|/(H-L)）是波动率代理** — bar_efficiency_full |LS|=3.65, LE=-3.28。无量纲的 body/range 比率本质度量 bar 内趋势效率∝波动率。与 path_efficiency（结论#47）失败模式一致——从 whole-day 缩小到 bar 级别不改变本质。（Exp#028）

66. **Wick roughness 信号主要来自市值暴露** — wick_roughness_full raw LE=0.72 但 |LS|=0.84（不达标），neutral 后 LE 从 0.72 骤降至 0.12。与 vol_roughness（neutral 后保持）形成对比：volume 粗糙度含独立于市值的流动性信号，而 wick 粗糙度的信号几乎全部来自市值/行业暴露。（Exp#028）
67. **累积收益路径积分不具备时间稳定性** — cumret_area_amihud_full 快筛（2020-2023）raw LS=1.08 → 正式评估（2020-2024）raw LS=0.66，信号衰减 39%。同框架的 batch_amihud_full（bar 级 |ret|/amount 求和）2024 仍保持 Sharpe=0.95。路径积分（mean|cumret|）对波动率环境变化更敏感：当 2024 年 A 股日内波动率结构改变时，路径面积的截面区分能力比 bar 级价格冲击衰减更快。（Exp#029）


<!-- Agent append: 2026-03-26T12:09:59.610817 -->
67. **OHLC 分解后的 Amihud 变体在中性化后信号大幅增强** — upper_wick_amihud_full neutral LS=2.18（raw 1.26→+72%）、lower_wick_amihud_full neutral LS=2.16（raw 1.10→+96%）、close_disp_amihud_full neutral Mono=0.89（raw 0.75→+19%）。4/5 特征通过筛选。bar 内 OHLC 结构（close displacement, upper/lower wick）归一化到 amount 后包含独立于市值/行业的流动性 alpha。（Exp#029）

68. **上影线和下影线 Amihud 几乎等强** — upper_wick_amihud neutral LS=2.18/LE=1.37 vs lower_wick_amihud neutral LS=2.16/LE=1.36，差异 <1%。卖压拒绝成本（upper wick）和买压拒绝成本（lower wick）提供几乎相同的截面信号，流动性溢价不依赖于价格探索方向。这与结论#50（方向性 Amihud 各自有效但非对称性无效）高度一致。（Exp#029）

69. **Close displacement 是有效的新 Amihud numerator** — close_disp_amihud_full 使用 |C-(H+L)/2|/amount（实现价差代理），neutral LS=1.55、LE=1.28、Mono=0.89。与 |ret|/amount（Amihud）和 wick/amount（wick_amihud）是三种不同的 numerator，但预计截面排序高度相关。（Exp#029）

<!-- Agent append: 2026-03-26T12:25:00 -->
70. **回撤路径 Amihud ≈ 偏移路径 Amihud** — max_drawdown_amihud（peak-to-trough/total_amount）与 max_excursion_amihud（start-to-max/total_amount）截面相关 0.87。对称随机游走路径中 max_drawdown ≈ max_excursion，两者仅在强趋势股票上有差异。drawdown_area_amihud 与 batch_amihud 相关 0.75。回撤路径分解不产生独立于已有 Amihud 框架的新信号。（Exp#030）

71. **路径级零穿越频率无截面信号** — cumret_zero_cross_freq_full（累积收益穿越零点的频率）|LS|=4.60 但 IR=0.005。与 bar 级 reversal_ratio（IR=0.35，有效）形成鲜明对比：reversal_ratio 捕捉 bid-ask bounce（微秒级做市行为），而累积收益零穿越是中频路径行为，频率受波动率主导（高波动→更多穿越），截面变异来自波动率而非流动性。（Exp#030）

70. **Roughness 范式仅在 volume 维度有效——close displacement 和 wick 均失败** — close_disp_roughness IR=0.06（本实验），wick_roughness raw LE=0.72→neutral LE=0.12（结论#66）。路径粗糙度的截面选股信号仅存在于 volume 维度（vol_roughness IR=0.53），其他维度的粗糙度主要反映市值暴露。（Exp#029+Exp#028）
<!-- Agent append: 2026-03-26T12:45:00 -->
73. **|C-O|/amount (body Amihud) 是 Amihud 框架的有效新 numerator** — body_amihud_full neutral LS=1.34, LE=1.24, IR=0.45, Mono=0.86。|C-O| 衡量 bar 内收盘相对开盘的定向价格承诺，不同于 |ret|（bar 间变化）和 |C-midpoint|（close 相对 range 中点）。中性化后信号增强 37%（0.98→1.34），独立于市值/行业暴露。（Exp#031）

74. **|O-midpoint|/amount (open displacement Amihud) 互补于 close displacement** — open_disp_amihud_full neutral LS=1.38, LE=1.27, IR=0.47, Mono=0.86。与 close_disp_amihud（neutral LS=1.55, Exp#029）构成 bar 内位置 Amihud 的完整对：open 和 close 相对 bar range 中点的偏离。预计两者截面相关性较高。（Exp#031）

75. **日内价格区间扩展频率是波动率代理** — range_discovery_freq_full |LS|=2.91 但强烈反向，IR=0.11。日内后半段设新 high/low 的 bar 比例本质度量价格区间扩张速度∝波动率。离散计数范式（结论#16）不能救波动率本质的度量——离散化有效的前提是底层度量非波动率（如 reversal_ratio 底层是 bid-ask bounce，vol_regime_transitions 底层是交易活跃度）。（Exp#031）

<!-- Agent append: 2026-03-26T13:15:00 -->
76. **Multi-bar 结构模式（inside bar / engulfing bar）是 Amihud 框架的有效新事件选择器** — inside bar（high[t]≤high[t-1] AND low[t]≥low[t-1]，range 被包含）和 engulfing bar（range 扩张）作为 bar 选择条件后计算 Amihud，3 个变体全部通过（neutral LS 1.23-1.35, LE 1.41-1.44, Mono 0.71-0.86）。这是第 9-10 种有效的条件 Amihud 事件选择器。高量+inside 双条件 raw Mono=1.00。（Exp#032）

77. **Multi-bar 结构频率指标 Mono 极高但 LS 不足** — inside_bar_freq_full（inside bar 占比）neutral LS=0.88, Mono=0.86；engulfing_freq_full neutral LS=0.85, Mono=1.00（完美单调）。两者本质是同一信号的镜像（anti-correlated）。LS 略低于 0.9 阈值，但 LE 达标（~1.0）且 Mono 极高，说明多 bar 结构模式频率在截面上有良好的单调排序但信号幅度较弱。与 reversal_ratio（LS=1.09）和 vol_regime_transitions（LS=0.94）相比，结构模式频率的截面区分度较弱。（Exp#032）

78. **Amihud 条件化空间确认饱和——多 bar 结构条件进一步验证** — 继 D-006 高量/反转/极端收益/量增/低量/收益加权（结论#33），D-008 加速度条件（结论#38），D-017 concordant/discordant（结论#59），D-019 doji（结论#62），D-016 VWAP 穿越（结论#54）之后，D-023 inside bar/engulfing bar 又贡献了 2 种新条件，但本质仍在"不同角度选 bar → 计算同一 Amihud 公式"。总计 12+ 种条件化方式，预计全部截面排序高度相关。新方向应探索非 Amihud 框架。（Exp#032）

<!-- Agent append: 2026-03-26T13:30:00 -->
79. **Amount 归一化挽救 autocovariance/variance_ratio 的 Long Excess** — noise_ratio（1-RV_5/RV_1）LE=0.26-0.35 → noise_amihud（(RV_1-RV_5)/mean(amount)）LE=1.06-1.10。与结论#48（路径拓扑 amount 归一化）一致，进一步验证了 |f(price)|/amount 模板在微观结构噪声维度的有效性。但 amount 归一化后 LS 骤降（noise_ratio LS=1.90 → noise_amihud LS=0.36），LE 和 LS 不可兼得。（Exp#033）

80. **Bar-pair 归一化优于聚合归一化** — bar_pair_noise_amihud（per-pair |r_i×r_{i+1}|/avg(amount)，LS=1.10）vs autocov_amihud（|sum(r_i×r_{i+1})|/(n×mean_amt)，LS=0.55）。与标准 Amihud（bar 级 |r|/amount 优于 batch sum|r|/sum(amount)，结论#49）一致——在 numerator 维度扩展后，per-observation 归一化仍优于全局聚合。（Exp#033）

81. **Bounce 条件（前向反转）是 Amihud 框架的有效事件选择器** — excess_bounce_amihud_full（仅在 r_i×r_{i+1}<0 bar 上计算 |r_i|/amount）neutral LS=1.29, LE=1.43, IR=0.44, Mono=0.86。这是继 high-vol/reversal/extreme-ret/accel/concordant/discordant/down/doji/inside/engulfing 之后的第 11 种条件 Amihud。但与 reversal_amihud（后向反转，r_{i-1}×r_i<0）中位数相关 0.82，独立信息有限。（Exp#033）

82. **连续收益率乘积是新的 Amihud numerator 维度** — |r_i×r_{i+1}|/amount 衡量"微观结构噪声成本"（bid-ask bounce 量级 per unit trading），是继 |ret|、|accel|、wick、close_disp、body、open_disp 之后的第 7 类 Amihud numerator。bar_pair_noise_amihud neutral LS=0.91（边缘通过），概念上最独立但信号相对较弱。（Exp#033）

<!-- Agent append: 2026-03-26T13:45:00 -->
83. **Rogers-Satchell Amihud（OHLC 4点方差/amount）是标准 Amihud 的高效升级** — rs_amihud_full 使用 bar 内 4 点 OHLC 估计方差（RS_bar = ln(H/O)·ln(H/C) + ln(L/O)·ln(L/C)），而非标准 |ret|/amount 的 2 点 close-close 估计。Raw Mono=1.00（完美单调），中性化后 LS 仅降 3%（1.82→1.77），信号高度独立于市值/行业。与 amihud_illiq_full（raw Mono=0.86）相比，OHLC 全信息利用显著改善了截面排序清晰度。（Exp#034）

84. **Amount roughness 验证了粗糙度范式的 amount 维度泛化** — amount_roughness_full（mean|Δamount|/mean(amount)）neutral LS=1.04, LE=0.73, IR=0.55, Mono=0.71（borderline）。与 vol_roughness（IR=0.53, Mono=0.71）高度一致。但 raw→neutral LS 降 29%（1.46→1.04），部分信号来自市值暴露（amount=price×volume 含市值成分）。（Exp#034）

85. **价格衍生指标的 roughness 退化为波动率代理** — range_roughness（|Δ(H-L)|/(H-L) IR=0.18）和 body_roughness（|Δ|C-O||/|C-O| LS=0.37）均失败。与 wick_roughness（结论#66）一致：roughness 范式仅在"交易活动量"维度（volume, amount, Amihud）有效，在"价格表现"维度仍退化为波动率代理。（Exp#034）

86. **复合离散事件的交集频率过低无法选股** — joint_reversal_vol（价格反转 AND 成交量 regime 变化同时发生）IR=0.04（≈噪声）。联合事件频率≈13%的 bar，截面变异被压缩到极窄范围。离散事件有效需要足够的基线频率：reversal_ratio（~50%）有效，vol_regime_transitions（~35%）有效，但两者的交集（~13%）不够。（Exp#034）

<!-- Agent append: 2026-03-26T14:05:00 -->
87. **Inter-bar gap 是有效的新 Amihud numerator** — open_gap_amihud_full（mean(|open_i - close_{i-1}|)/mean(amount)×1e9）neutral LS=1.80, LE=1.32, IR=0.55, raw Mono=0.86, neutral Mono=0.71。中性化后 LS 增强 34%（1.34→1.80），信号高度独立于市值/行业。Inter-bar gap 衡量相邻 1m bar 间的隐式 bid-ask spread，是继 |ret|、|accel|、wick、close_disp、body、open_disp、|r_i×r_{i+1}| 之后的第 8 类 Amihud numerator。（Exp#035）

88. **日内时序结构特征本身缺乏截面选股能力** — 极值时点（high_timing |LS|=5.20, LE=-2.34）、量价 lead-lag 频率（vol_lead LE=-4.80, ret_lead LE=-4.92）、极值距离（extremum_spread IR=0.07）、范围收缩频率（range_contraction IR=0.03）均失败。时间维度的截面变异不足（日内极值时点/范围动态模式对所有股票高度一致），或信号集中在空头端。（Exp#035）

89. **量价 lead-lag 频率是又一种空头集中因子** — volume_lead_return_freq（|LS|=5.69, LE=-4.80）和 ret_lead_volume_freq（|LS|=5.63, LE=-4.92）几乎完全同步失败。频繁的量价跟随事件 = 嘈杂投机交易 = 差股票，与所有已知的频率类因子（reversal_ratio 除外）失败模式一致。两个指标性能几乎相同说明在 A 股日内数据中，量→价 和 价→量 的跟随关系是同一现象的两面。（Exp#035）
90. **离散计数范式不可简单跨变量迁移** — gap_reversal_freq（inter-bar gap 符号反转）尝试复制 reversal_ratio（intra-bar 价格反转）的成功，但 IR_LS=-0.09 接近噪声。关键差异：reversal_ratio 的物理基础是 bid-ask bounce（流动性代理），而 gap 符号翻转可能只反映集合竞价/连续竞价切换的微观噪声，缺乏流动性含义。离散计数范式（结论#16）的有效性取决于底层变量是否含流动性信息，不能盲目套用。（Exp#036）

<!-- Agent append: 2026-03-26T14:30:00 -->
91. **算术均值 Amihud 是最优聚合函数——稳健估计器丢失信号** — 5 种聚合函数（sqrt/log/harmonic/median/trimmed）全部不如标准 mean(|r|/amount)。标准 Amihud LS=2.37, LE=1.79 > log LS=2.11, LE=1.67 > harmonic LS=1.85, LE=1.61。极端冲击 bar 携带最多截面信息：它们区分了"一笔大单就能推动价格"（差流动性）和"大单被充分吸收"（好流动性）的股票。压缩极端值（log/sqrt/trimmed）或忽略极端值（median）都丢失了这一核心区分能力。（Exp#037）

92. **中位数 Amihud 完全丢失空头端信号** — median_amihud_full IC_LS≈0、IR_LS=-0.01（无截面预测力），但 IC_LO=0.038、LE=1.61（多头端有效）。说明标准 Amihud 的空头 alpha（识别差股票）完全来自极端高冲击 bar，中位数将其排除后只剩下多头端的温和信号。这进一步验证了结论#4（alpha 常集中在空头端）：空头端信号依赖极端事件。（Exp#037）

93. **调和均值 Amihud 捕捉不同维度** — harmonic_amihud_full 与标准 Amihud 相关 0.945（最低），raw Mono=1.00（完美单调）。调和均值由最小 Amihud bar 主导（最流动时刻），衡量"最优执行潜力"而非"平均冲击成本"。11% 独立信息可能在集成模型中有价值，但作为独立因子指标不如标准 Amihud。（Exp#037）

### ⚠️ 重要注意事项

1. **A 股 1m 数据从 2020 年开始** — 回测起始不早于 2020-01-01，确保覆盖完整牛熊周期。（初始化）
2. **复权必须用 hfq** — `origin_*` 字段仅用于涨跌停判断，因子计算必须使用后复权价格。（初始化）


<!-- Agent append: 2026-03-26T09:57:00.437782 -->
<!-- Agent append: 2026-03-26T09:55:00 -->
54. **VWAP 穿越事件 + Amihud 框架有效** — high_vol_vwap_cross_amihud_full（高量+VWAP穿越双条件 Amihud）raw Mono=1.00、LE=1.31、LS=1.26、IR=0.37。事件触发器从「收益率方向反转」（reversal_amihud）扩展到「价格穿越累积 VWAP」，进一步验证了 |ret|/amount 在不同事件选择下的鲁棒性。（Exp#025）

55. **VWAP 穿越频率有完美截面排序但无多头 alpha** — vwap_cross_freq_full Mono=1.00（完美单调），|LS|=2.88, IR=0.22，但 LE=-0.065。高穿越频率=价格频繁震荡=嘈杂交易=差股票；低穿越频率只是「不那么差」，不构成正 alpha。这是结论#6（空头端集中）在 VWAP 维度的又一验证。（Exp#025）

56. **VWAP 距离/跟踪误差是波动率代理** — vwap_distance_full（|LS|=5.23, LE=-5.68）和 vwap_tracking_error_full（|LS|=5.24, LE=-5.99）与 HL range（结论#22）、路径拓扑（结论#47）失败模式完全一致。VWAP 偏差的绝对水平度量价格路径复杂度∝波动率。（Exp#025）

57. **VWAP 距离 Amihud 信号极弱** — vwap_distance_amihud_full（mean|close-VWAP|/mean(amount)）|LS|=0.14，远低于标准 Amihud（|LS|=2.37）。原因：|close-VWAP| 是累积量（依赖整条路径历史），而 |ret| 是局部量（单 bar 价格冲击），后者截面离散度更高。Amihud 框架在累积路径统计量上效率下降。（Exp#025）

<!-- Agent append: 2026-03-26T10:53:24.901563 -->
60. **下行 Amihud（卖出方价格冲击）是 Amihud 框架的有效扩展** — down_amihud_full raw LS=1.42, LE=+1.14; high_vol_down_amihud_full raw LS=1.83, LE=+1.53, Mono=1.00（完美单调）。仅看下跌 bar 的 |ret|/amount 不会丢失信号，反而在高量过滤后更纯净。Neutral 后 IR 均增强（0.38→0.43, 0.38→0.44）。（Exp#027）
61. **Amihud 买卖不对称性比率类因子系统性失败在 LE** — amihud_asymmetry_full（|LS|=7.49, LE=-0.30）和 high_vol_amihud_asymmetry_full（|LS|=6.77, LE=-1.42）的 alpha 完全集中在空头端。IR_LS 极低（0.12-0.13），换手率极高（TVR=2.72）。比率/不对称性类截面因子在 A 股只能识别差股票，与结论#6、#9、#15 一致。（Exp#027）
## 二、已排除方向

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

### Experiment #002: Variance Ratio（2026-03-25）

**方向**: D-003 variance_ratio
**Agent**: ashare_rawdata_a
**结果**: 5 特征测试（4 全量评估），0 通过

| 特征 | |Net Sharpe| (r/n) | |IR| (r/n) | Long Excess (r/n) | w1 Mono (r/n, 翻转) | 状态 |
|------|---------------------|-------------|---------------------|---------------------|------|
| `abs_ar1_0930_1030` | 9.37/11.44 | 0.50/0.61 | -2.73/-3.03 | 0.86/0.71 | ❌ LE深度失败 |
| `vr_2_0930_1030` | 5.27/5.44 | 0.23/0.25 | -1.81/-1.82 | 0.86/0.71 | ❌ LE失败 |
| `ar1_0930_1030` | 5.18/5.35 | 0.23/0.25 | -1.89/-1.92 | 0.57/0.86 | ❌ LE失败 |
| `vr_5_0930_1030` | 4.11/4.32 | 0.19/0.20 | -1.52/-1.50 | 0.71/0.43 | ❌ LE+IR边缘 |
| `vr_ratio_5_2_0930_1030` | - | 0.08/0.09 | - | - | ❌ Quick排除(IR极低) |

**关键发现**:
1. abs_ar1（|return|自相关）信号极强（|LS Sharpe|=11.44, |IR|=0.61），neutral 后反而增强，非市值代理
2. 所有 8 个分组的绝对 Sharpe 均为负值，即使最好的分组（翻转后多头端）也跑不过 CSI1000
3. 连续第 3 个日内微观结构方向失败在 Long Excess 上：这类因子能识别"差股票"但无法选出"好股票"
4. Quick eval (100 symbols) 的 |IR| 从 0.18 提升到全量的 0.61，再次验证 Quick 不可靠

#### Related
- **报告**: `research/agent_reports/screening/2026-03-25_variance_ratio_0930_1030_screening.md`
- **评估**: `.claude-output/evaluations/variance_ratio/`

### Experiment #003: Closing Volume Ratio（2026-03-25）

**方向**: D-013 closing_volume_ratio
**Agent**: ashare_rawdata_a
**结果**: 8 特征测试（8 全量评估），0 通过

| 特征 | |Sharpe_abs| (r/n) | |IR_LS| (r/n) | LE_net (r/n) | 状态 |
|------|---|---|---|---|
| `vol_last_quarter_ratio_full` | 1.21/1.25 | 0.15/0.15 | -0.87/-0.82 | ❌ IR+LE |
| `vol_center_of_mass_full` | 1.02/1.18 | 0.12/0.12 | -0.87/-0.94 | ❌ IR+LE |
| `vol_back_half_ratio_full` | 1.19/1.35 | 0.13/0.12 | -0.78/-0.86 | ❌ IR+LE |
| `amt_last_quarter_ratio_full` | 1.03/1.20 | 0.11/0.11 | -0.89/-0.95 | ❌ IR+LE |
| `close_open_vol_ratio_full` | 2.19/2.22 | 0.08/0.08 | -0.55/-0.59 | ❌ IR+LE |
| `close_buy_pressure_full` | 1.04/1.22 | 0.15/0.14 | -0.82/-0.86 | ❌ IR+LE |
| `close_vwap_return_full` | 2.58/2.60 | 0.17/0.17 | -1.11/-0.98 | ❌ IR+LE |
| `close_vol_momentum_full` | 2.39/2.45 | 0.10/0.10 | -0.63/-0.67 | ❌ IR+LE |

**关键发现**:
1. 所有 8 个特征 IR_LS 均 < 0.2（最高 0.17），尾盘成交量分布在截面上选股能力极弱
2. Long Excess 全为负值（最佳 -0.55），翻转因子方向后 LE 仍不达标
3. 中性化后无改善（IR 和 Sharpe 均略恶化），信号非市值/行业代理，而是信号本身就弱
4. A 股日内成交量分布模式较固定（U 型），个股间差异不足以支撑截面选股

#### Related
- **报告**: `research/agent_reports/screening/2026-03-25_closing_volume_ratio_full_screening.md`
- **评估**: `.claude-output/evaluations/closing_volume_ratio/`

### Experiment #004: APM Momentum Evolve Benchmark（2026-03-25）

**方向**: D-011 apm_momentum
**Agent**: ashare_rawdata_b
**任务类型**: Evolve 热路径 benchmark + 信号快筛
**结果**: 10 特征快筛（2 bundle × 5 fields），0 通过

| 特征 | |LS Sharpe| | |IR(LS)| | Long Excess | 状态 |
|------|-----------|---------|-------------|------|
| `pm_vw_avg_return_1300_1457` | 7.39 | 0.21 | -4.00 | ❌ LE深度失败 |
| `pm_late_return_1300_1457` | 5.46 | 0.27 | -3.81 | ❌ LE深度失败 |
| `pm_return_1300_1457` | 5.11 | 0.19 | -4.48 | ❌ LE深度失败 |
| `pm_close_loc_1300_1457` | 4.80 | 0.18 | -1.75 | ❌ LE+IR |
| `am_acceleration_0930_1130` | 4.63 | 0.005 | -2.95 | ❌ LE+IR |
| `pm_acceleration_1300_1457` | 4.17 | 0.21 | -2.58 | ❌ LE深度失败 |
| `am_vw_avg_return_0930_1130` | 3.54 | 0.05 | -4.06 | ❌ LE+IR |
| `am_late_return_0930_1130` | 2.70 | 0.04 | -3.24 | ❌ LE+IR |
| `am_return_0930_1130` | 2.21 | 0.04 | -3.48 | ❌ LE+IR |
| `am_close_loc_0930_1130` | 0.57 | 0.06 | +0.04 | ❌ LS Sharpe+IR |

**性能 Benchmark**:
- Preload compute: 7-9s / 5090 stocks × 725 days (throughput ~600 stocks/s)
- Quick-eval: ~105s / candidate (5 fields)
- 总 wall time: 230s (2 candidates)
- 结论：preload 热路径速度达到预期

**关键发现**:
1. 日内方向性动量在 A 股仍是反转效应（invert_sign=true for all），与 D-001/D-002/D-003 结论一致
2. PM 窗口（1300-1457）信号强度是 AM（0930-1130）的 1.5-2 倍
3. 所有 10 个字段 Long Excess 深度失败（最佳仅 +0.04），进一步验证结论 #6

#### Related
- **报告**: `research/agent_reports/screening/2026-03-25_apm_momentum_evolve_benchmark.md`
- **Evolve 产出**: `.claude-output/evolve/apm_momentum_benchmark/`

### Experiment #005: Roll Spread 流动性因子（2026-03-25）

**方向**: D-009 roll_spread
**Agent**: ashare_rawdata_b
**结果**: 15 特征测试（3 bundle × 5 fields, 2 shortlist 全量评估），1 通过

| 特征 | |LS Sharpe| | LE Net | |IR(LS)| | w1 Mono | 状态 |
|------|-----------|--------|---------|---------|------|
| `reversal_ratio_full` | **1.09** | **+1.21** | **0.35** | **0.86** | **✅ pending** |
| `spread_to_vol_full` | 0.78 | +0.66 | 0.34 | 0.71 | ❌ LS Sharpe+LE |
| `zero_return_pct_full` | 0.43 | -0.56 | 0.37 | - | ❌ LS+LE |
| `roll_spread_bps_full` | 0.62 | +0.36 | 0.17 | - | ❌ IR+LS |
| `roll_impact_full` | 5.25 | -3.56 | 0.09 | - | ❌ LE(size proxy) |
| `reversal_ratio_0930_1030` | 0.22 | +0.77 | 0.28 | - | ❌ LS Sharpe |
| `zero_return_pct_0930_1030` | 0.65 | +0.37 | 0.36 | - | ❌ LS+LE |
| `roll_spread_bps_0930_1030` | 2.96 | -1.40 | 0.07 | - | ❌ IR+LE |
| `spread_to_vol_0930_1030` | 2.40 | -0.37 | 0.21 | - | ❌ LE |
| `roll_impact_0930_1030` | 9.13 | -7.59 | 0.21 | - | ❌ LE(size proxy) |
| `vol_weighted_zero_ret_0930_1030` | 0.68 | +0.52 | 0.35 | - | ❌ LS+LE |
| `abs_return_intensity_0930_1030` | 7.71 | -6.06 | 0.45 | - | ❌ LE |
| `small_trade_ratio_0930_1030` | 1.44 | +0.23 | 0.38 | - | ❌ LE |
| `return_concentration_0930_1030` | 5.21 | -3.78 | 0.18 | - | ❌ IR+LE |
| `reversal_asymmetry_0930_1030` | 6.10 | +0.53 | 0.01 | - | ❌ IR |

**关键发现**:
1. reversal_ratio_full 是本项目**首个全部通过自动筛选**的特征，突破了日内因子 Long Excess 瓶颈
2. 全天窗口（~237 bars）显著优于 1h 窗口（reversal_ratio 从 |Sharpe| 0.22→1.09），更多 bar 使反转频率估计更稳健
3. 中性化后信号增强（Sharpe 1.09→1.19），含独立于市值/行业的 alpha
4. 经典 Roll spread (bps) 表现差（IR 仅 0.07），离散化的反转频率远优于连续协方差
5. 2024 年信号衰减（Sharpe 0.13 vs 2022-2023 的 1.77-1.93）需关注

#### Related
- **报告**: `research/agent_reports/screening/2026-03-25_roll_spread_full_screening.md`
- **评估**: `.claude-output/evaluations/roll_spread/reversal_ratio_full/`
- **Pending**: `research/pending-rawdata/reversal_ratio_full/`

### Experiment #006: Corwin-Schultz Spread 全天窗口（2026-03-25）

**方向**: D-004 corwin_schultz_spread
**Agent**: ashare_rawdata_a
**结果**: 5 特征快筛 + 3 特征正式评估，2 通过

| 特征 | |Net Sharpe| (r/n) | |IR| (r/n) | LE (r/n) | w1 Mono (r/n) | 状态 |
|------|---------------------|-------------|----------|---------------|------|
| `cs_relative_spread_full` | 0.77/1.14 | 0.28/0.23 | +1.16/+1.18 | 0.71/0.57 | ✅ pending |
| `cs_spread_full` | 0.55/1.03 | 0.27/0.29 | +1.05/+1.06 | 0.71/0.43 | ✅ pending |
| `cs_spread_to_vol_full` | 0.54/1.07 | 0.28/0.31 | +1.09/+1.10 | 0.57/0.57 | ❌ Mono 不达标 |
| `cs_sigma_full` | 4.86 | 0.48 | -2.83 | - | ❌ LE 深度失败（波动率因子） |
| `cs_spread_trend_full` | 2.89 | 0.09 | +0.03 | - | ❌ IR 太低 |

**关键发现**:
1. CS spread 流动性字段中性化后信号增强（+48~87%），含独立于市值/行业的 alpha
2. 3 个流动性字段全部 LE > 0.7，二次验证流动性水平因子方向有效
3. cs_sigma 是纯波动率因子，alpha 集中在空头端，与 D-002 BPV 一致
4. 2024 年 neutral 信号衰减（Sharpe 0.16-0.45 vs 2022-2023 的 1.5-2.2）

#### Related
- **报告**: `research/agent_reports/screening/2026-03-25_cs_spread_full_screening.md`
- **评估**: `.claude-output/evaluations/corwin_schultz_spread/`
- **Pending**: `research/pending-rawdata/cs_relative_spread_full/`, `research/pending-rawdata/cs_spread_full/`

### Experiment #007: Volume Entropy 方向（2026-03-25）

**方向**: D-005 volume_entropy
**Agent**: ashare_rawdata_b
**结果**: 10 特征测试（2 bundle × 5 fields），1 通过

**Bundle 1: volume_microstructure_full（纯成交量分布）**

| 特征 | |LS Sharpe| | LE Sharpe | |IR(LS)| | 状态 |
|------|-----------|-----------|---------|------|
| `volume_entropy_full` | 2.41 | -0.75 | 0.12 | ❌ IR+LE |
| `volume_gini_full` | 2.45 | -1.67 | 0.17 | ❌ IR+LE |
| `high_vol_bar_ratio_full` | 1.46 | -0.24 | 0.27 | ❌ LS+LE |
| `volume_autocorr1_full` | 6.12 | -2.81 | 0.74 | ❌ LE深度失败 |
| `volume_dispersion_ratio_full` | 2.49 | -1.57 | 0.31 | ❌ LE失败 |

**Bundle 2: volume_informed_trading_full（量价交互）**

| 特征 | |LS Sharpe| | LE Sharpe | |IR(LS)| | w1 Mono (r/n) | 状态 |
|------|-----------|-----------|---------|---------------|------|
| `informed_trade_ratio_full` | 6.22 | -2.03 | 0.51 | - | ❌ LE深度失败 |
| `vol_return_sync_full` | 8.15 | -4.85 | 0.36 | - | ❌ LE深度失败 |
| `vol_weighted_return_std_full` | 7.09 | -5.41 | 0.52 | - | ❌ LE深度失败 |
| `vol_price_joint_entropy_full` | 0.27 | +1.10 | 0.24 | - | ❌ LS<0.9 |
| `vol_regime_transitions_full` | **2.48** | **+1.46** | **0.75** | **0.86/0.71** | **✅ pending** |

**关键发现**:
1. 纯成交量分布指标（熵/Gini/离散度/自相关）系统性失败在 LE，alpha 全部集中在空头端——与价格微观结构因子相同的失败模式
2. vol_regime_transitions_full（成交量 regime 切换频率）是 reversal_ratio_full 的量版本类比，二者共同验证"流动性质量"假设
3. volume_autocorr1 信号极强（|IR|=0.74, |LS Sharpe|=6.12）但 LE=-2.81，纯空头因子无 Long Excess
4. 离散化 regime 切换远优于连续分布统计（与 reversal_ratio >> Roll spread 一致）

#### Related
- **报告**: `research/agent_reports/screening/2026-03-25_volume_entropy_full_screening.md`
- **评估**: `.claude-output/evaluations/volume_entropy/vol_regime_transitions_full/`
- **Pending**: `research/pending-rawdata/vol_regime_transitions_full/`

### Experiment #008: Liquidity Impact 量价交互流动性因子（2026-03-26）

**方向**: D-006 high_volume_ratio
**Agent**: ashare_rawdata_a
**结果**: 5 特征快筛 + 1 特征正式评估，1 通过

| 特征 | |Net Sharpe| (r/n) | |IR| (r/n) | LE (r/n) | w1 Mono (r/n) | 状态 |
|------|---------------------|-------------|----------|---------------|------|
| `amihud_illiq_full` | 2.37/2.31 | 0.38/0.47 | +1.79/+1.78 | 0.86/0.57 | ✅ pending |
| `flow_toxicity_full` | 17.25 | 0.31 | -14.45 | - | ❌ LE 深度失败（趋势追踪→A股反转） |
| `large_trade_reversal_full` | 3.21 | 0.34 | -1.83 | - | ❌ LE 失败 |
| `vol_impact_ratio_full` | 7.47 | 0.42 | -5.17 | - | ❌ LE 深度失败（波动率代理） |
| `order_flow_imbalance_full` | 3.61 | 0.01 | -1.65 | - | ❌ IR 极低（方向性信号无效） |

**关键发现**:
1. Amihud 非流动性（|return|/amount）是继 CS spread 之后第二个基于不同方法的流动性因子，neutral 后 IR 增强 +24%
2. 2024 年 neutral Sharpe 1.62 远优于 CS spread 的 0.45，可能因为 Amihud 捕捉了更微观的价格冲击信息
3. raw Mono=0.86 vs neutral Mono=0.57：部分排序能力来自市值暴露（小市值→Amihud高），但核心信号独立
4. 信息流毒性（flow_toxicity）LE=-14.45，连续同方向=趋势追踪=A股反转效应，失败模式一致
5. 订单流失衡 IR=0.01，方向性信号在 A 股日频无效

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_amihud_illiq_full_screening.md`
- **评估**: `.claude-output/evaluations/high_volume_ratio/amihud_illiq_full/`
- **Pending**: `research/pending-rawdata/amihud_illiq_full/`

### Experiment #009: Volume Entropy 多维度 Regime Transition + 交易活动质量（2026-03-26）

**方向**: D-005 volume_entropy
**Agent**: ashare_rawdata_b
**结果**: 10 特征测试（2 bundle × 5 fields, 1 shortlist 正式评估），0 通过

**Bundle 1: regime_transitions_multi_full（多维度 regime transition）**

| 特征 | |LS Sharpe| | LE Sharpe | |IR(LS)| | w1 Mono (r/n) | 状态 |
|------|-----------|-----------|---------|---------------|------|
| `amount_regime_transitions_full` | **1.60** | **+1.14** | **0.66** | **0.57/0.43** | ⚠️ Mono 不达标 |
| `bar_range_regime_transitions_full` | 1.94 | +0.59 | 0.15 | - | ❌ IR+LE |
| `amihud_regime_transitions_full` | 2.52 | +0.30 | 0.13 | - | ❌ IR+LE |
| `body_ratio_transitions_full` | 4.65 | -0.87 | 0.35 | - | ❌ LE 深度失败 |
| `vwap_cross_transitions_full` | 2.87 | -0.06 | 0.22 | - | ❌ LE 失败 |

**Bundle 2: trade_activity_quality_full（交易活动质量）**

| 特征 | |LS Sharpe| | LE Sharpe | |IR(LS)| | 状态 |
|------|-----------|-----------|---------|------|
| `trade_size_transitions_full` | 2.96 | -0.16 | 0.20 | ❌ LE 失败 |
| `volume_accel_transitions_full` | 2.00 | +0.11 | 0.62 | ❌ LE 不达标 |
| `amount_weighted_reversal_full` | 4.43 | -0.77 | 0.12 | ❌ LE+IR |
| `cumret_zero_cross_full` | 4.57 | -0.64 | 0.03 | ❌ LE+IR |
| `vol_price_divergence_full` | 6.68 | -1.84 | 0.02 | ❌ LE+IR |

**关键发现**:
1. amount_regime_transitions_full 通过 LS/LE/IR/Coverage 但 Mono 仅 0.57（amount=price×volume，价格水平引入非线性干扰降低排序清晰度）
2. Regime transition 范式在 volume 维度最优，扩展到其他维度效果均下降
3. D-005 共测试 20 个特征（Exp#007+#009），仅 vol_regime_transitions_full 1 个全部通过，方向已充分探索

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_volume_entropy_regime_multi_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-020935/`, `.claude-output/evolve/20260326-022343/`
- **评估**: `.claude-output/evaluations/volume_entropy/amount_regime_transitions_full/`

### Experiment #010: Liquidity Level 2 + Advanced 批量快筛（2026-03-26）

**方向**: D-006 high_volume_ratio
**Agent**: ashare_rawdata_a
**结果**: 8 特征快筛 + 2 特征正式评估，1 通过

**Bundle 1: liquidity_level_2（3 特征）**

| 特征 | |Net Sharpe| (r/n) | |IR| (r/n) | LE (r/n) | w1 Mono (r/n) | 状态 |
|------|---------------------|-------------|----------|---------------|------|
| `high_vol_illiq_full` | 1.95/1.77 | 0.32/0.44 | +1.60/+1.44 | 1.00/0.86 | ✅ pending |
| `zero_return_ratio_full` | 0.78 (反向) | 0.35 | +0.79 (反向) | - | ❌ |LS|<0.9 |
| `illiq_variability_full` | 0.01 | 0.38 | 0.16 | - | ❌ 无信号 |

**Bundle 2: liquidity_advanced（5 特征）**

| 特征 | |Net Sharpe| (r/n) | |IR| (r/n) | LE | 状态 |
|------|---------------------|-------------|-----|------|
| `vw_hl_spread_full` | 6.78/3.91 (反向) | 0.60/0.62 | -6.60/-4.86 | ❌ 波动率代理，非流动性 |
| `kyle_lambda_full` | 4.68 (反向) | 0.52 | -4.36 | ❌ 波动率代理 |
| `effective_half_spread_full` | 3.99 (反向) | 0.50 | -2.91 | ❌ 波动率代理 |
| `high_vol_amihud_full` | 1.95 | 0.34 | 1.57 | 跳过（与 high_vol_illiq 重复） |
| `liquidity_resilience_full` | 0.13 | 0.38 | 1.21 | ❌ LS<0.9 |

**关键发现**:
1. high_vol_illiq_full（top-25% 量 bar Amihud）raw Mono=1.00（完美单调性），比 amihud_illiq_full 的 Mono=0.86 更优，隔离活跃期消除了安静期噪声
2. neutral IR 增强 +37%（0.32→0.44），强于 amihud_illiq_full 的 +24%，含更多独立 alpha
3. 零回报率方向反转：高零回报→低收益（"无人关注" ≠ "交易成本高"，Lesmond 1999 前提在 A 股 1m 数据不成立）
4. HL range 系列（vw_hl_spread/kyle_lambda/effective_half_spread）本质是波动率因子，中性化后仍强烈反向（low-vol premium），与 CS spread 的成功形成对比——Corwin-Schultz 用相邻 bar 差分分离了流动性成分，直接 HL/mid 没有
5. Amihud CV（illiq_variability）无信号：流动性的二阶矩不构成定价因子

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_liquidity_level2_advanced_screening.md`
- **评估**: `.claude-output/evaluations/high_volume_ratio/high_vol_illiq_full/`, `.claude-output/evaluations/high_volume_ratio/vw_hl_spread_full/`
- **Pending**: `research/pending-rawdata/high_vol_illiq_full/`


<!-- Agent append: 2026-03-26T03:03:27.959652 -->
### Experiment #011: Time-Segmented Momentum 时间分段收益模式（2026-03-26）

**方向**: D-012 time_segmented_momentum
**Agent**: ashare_rawdata_b
**结果**: 18 特征测试（2 bundle: 10+8 fields），0 通过

**Bundle 1: time_seg_momentum_full（纯收益时间分布，10 字段）**

| 特征 | |LS Sharpe| | LE Sharpe | |IR(LS)| | 状态 |
|------|-----------|-----------|---------|------|
| `return_hhi_full` | 11.20 | -5.44 | 0.14 | ❌ LE 深度失败 |
| `max_segment_share_full` | 10.46 | -4.05 | 0.23 | ❌ LE 深度失败 |
| `close_return_share_full` | 8.20 | -2.05 | 0.24 | ❌ LE 失败 |
| `segment_return_skew_full` | 7.47 | -3.02 | 0.14 | ❌ LE 失败 |
| `segment_reversal_ratio_full` | 7.01 | -1.25 | 0.12 | ❌ LE 失败 |
| `open_return_share_full` | 6.88 | -2.53 | 0.04 | ❌ LE+IR |
| `segment_autocorr1_full` | 5.90 | -1.13 | 0.04 | ❌ LE+IR |
| `segment_return_std_full` | 5.59 | -6.30 | 0.51 | ❌ LE 深度失败 |
| `am_pm_abs_ratio_full` | 4.77 | -1.64 | 0.06 | ❌ LE+IR |
| `return_path_roughness_full` | 1.46 | +0.27 | 0.06 | ❌ LE 不达标 |

**Bundle 2: vol_ret_timing_full（量价时间交互，8 字段）**

| 特征 | |LS Sharpe| | LE Sharpe | |IR(LS)| | 状态 |
|------|-----------|-----------|---------|------|
| `vol_am_pm_ratio_full` | 11.10 | -8.99 | 0.24 | ❌ LE 深度失败 |
| `vol_timing_hhi_full` | 9.97 | -6.39 | 0.59 | ❌ LE 深度失败 |
| `vol_ret_rank_corr_full` | 9.74 | -2.04 | 0.33 | ❌ LE 失败 |
| `high_vol_seg_ret_ratio_full` | 8.99 | -3.56 | 0.40 | ❌ LE 失败 |
| `vol_weighted_ret_hhi_full` | 8.66 | -3.35 | 0.37 | ❌ LE 失败 |
| `vol_ret_abs_corr_full` | 7.71 | -1.83 | 0.25 | ❌ LE 失败 |
| `vol_weighted_reversal_full` | 7.06 | -1.00 | 0.13 | ❌ LE+IR |
| `informed_ratio_full` | 1.89 | +0.19 | 0.32 | ❌ LE 不达标 |

**关键发现**:
1. 全部 18 字段 LE ≤ +0.27（阈值 0.7），alpha 全部集中在空头端（raw Sharpe 全负）
2. 段级别反转频率（segment_reversal_ratio, LE=-1.25）远不如 bar 级别（reversal_ratio_full, LE=+1.21）：30min 段反转捕捉中频趋势反转而非 bid-ask bounce
3. 添加 volume 维度（vol_weighted_reversal, vol_ret_rank_corr）无法改善 LE，量价时间交互与纯收益模式失败模式一致
4. D-012 方向已穷尽，与 D-001/D-002/D-003/D-011/D-013 相同的系统性失败模式

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_time_seg_momentum_full_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-025002/`

### Experiment #012: High-Volume Advanced 反转条件流动性探索（2026-03-26）

**方向**: D-006 high_volume_ratio
**Agent**: ashare_rawdata_a
**结果**: 4 特征快筛 + 2 特征正式评估，2 通过

| 特征 | |Net Sharpe| (r/n) | |IR| (r/n) | LE (r/n) | w1 Mono (r/n) | 状态 |
|------|---------------------|-------------|----------|---------------|------|
| `high_vol_reversal_amihud_full` | 1.85/1.54 | 0.38/0.46 | +1.56/+1.42 | 1.00/0.86 | ✅ pending |
| `reversal_amihud_full` | 1.49/1.39 | 0.39/0.44 | +1.20/+1.44 | 0.71/0.71 | ✅ pending |
| `high_vol_impact_ratio_full` | 6.60 (反向) | 0.38 | -7.16 | - | ❌ 波动率代理 |
| `amihud_session_diff_full` | 5.01 (反向) | 0.01 | -0.05 | - | ❌ 无信号 |

**关键发现**:
1. 反转条件 + 高量过滤构建了最纯粹的流动性供给成本度量，raw Mono=1.00 完美单调，neutral IR=0.46（所有 Amihud 变体最高）
2. Amihud 量比率（高/低）是波动率代理（|Sharpe|=6.60 反向），与 vw_hl_spread 一致
3. 日内 Amihud 差异 IR=0.01，A 股日内流动性演化模式高度同质
4. D-006 方向经 3 轮实验（#008/#010/#012）共测试 17 个特征，4 个通过，方向已充分探索

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_high_volume_advanced_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-030510/`
- **评估**: `.claude-output/evaluations/high_volume_ratio/reversal_amihud_full/`, `.claude-output/evaluations/high_volume_ratio/high_vol_reversal_amihud_full/`
- **Pending**: `research/pending-rawdata/reversal_amihud_full/`, `research/pending-rawdata/high_vol_reversal_amihud_full/`

### Experiment #013: Realized Quarticity 流动性视角尾部风险（2026-03-26）

**方向**: D-007 realized_quarticity
**Agent**: ashare_rawdata_b
**结果**: 8 特征快筛，1 通过正式评估

| 特征 | |Net Sharpe| (r/n) | |IR| (r/n) | LE (r/n) | w1 Mono (r/n) | 状态 |
|------|---------------------|-------------|----------|---------------|------|
| `extreme_amihud_full` | 1.47/1.26 | 0.39/0.45 | +1.19/+1.36 | 0.86/0.71 | ✅ pending |
| `realized_quarticity_full` | 10.76 | 0.625 | -10.63 | - | ❌ 波动率代理 |
| `kurtosis_ratio_full` | 11.61 | 0.446 | -7.33 | - | ❌ 波动率代理 |
| `quarticity_concentration_full` | 8.93 | 0.477 | -2.54 | - | ❌ LE 深负 |
| `tail_volume_share_full` | 6.95 | 0.087 | -1.36 | - | ❌ LE 负 |
| `extreme_bar_ratio_full` | 4.18 | 0.120 | +0.38 | - | ❌ IR 不足 |
| `extreme_amihud_ratio_full` | 4.12 | 0.065 | -0.81 | - | ❌ 信号弱 |
| `amihud_quarticity_full` | 1.21 | 0.001 | -0.45 | - | ❌ 无信号 |

**关键发现**:
1. 纯 quarticity（realized_quarticity/kurtosis_ratio）确认为波动率/市值代理，|LS Sharpe| 极高（>10）但 LE 深度负值，与结论#5（BPV 是市值代理）一致
2. extreme_amihud_full 本质是条件 Amihud（|r|>2×median(|r|) 的极端 bar），从"尾部风险"转化为"极端事件下的流动性"
3. Neutral 后 IR 增强（0.39→0.45），说明信号独立于市值/行业，与结论#12（CS spread 中性化增强）一致
4. r^4/amount（amihud_quarticity）IR 接近 0，说明 r^4 权重过度集中在极少数 bar，不如 |r|/amount 的条件选择稳健
5. 数据仅覆盖 2020-2023，2024 未评估；neutral Mono=0.71 边缘通过

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_realized_quarticity_full_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-031205/`
- **评估**: `.claude-output/evaluations/realized_quarticity/extreme_amihud_full/`
- **Pending**: `research/pending-rawdata/extreme_amihud_full/`

<!-- Agent append: 2026-03-26T03:45:00 -->
### Experiment #014: Amihud 二阶特征 — 流动性路径粗糙度（2026-03-26）

**方向**: D-006 high_volume_ratio
**Agent**: ashare_rawdata_a
**结果**: 3 特征快筛 + 1 特征正式评估，1 通过

| 特征 | |Net Sharpe| (r/n) | |IR| (r/n) | LE (r/n) | w1 Mono (r/n) | 状态 |
|------|---------------------|-------------|----------|---------------|------|
| `amihud_diff_mean_full` | 1.24/0.94 | 0.36/0.37 | +1.21/+1.03 | 1.00/0.71 | ✅ pending |
| `amihud_autocorr1_full` | 9.39 (反向) | 0.38 | -6.21 | - | ❌ LE 深度失败（波动率聚集代理） |
| `amihud_tail_ratio_full` | 0.43 | 0.39 | +0.79 | - | ❌ |LS|<0.9（信号太弱） |

**关键发现**:
1. Amihud 二阶属性（bar-to-bar 变化率）是独立于一阶属性（水平量）的有效因子维度
2. 流动性路径粗糙度 raw Mono=1.00 完美单调，比 amihud_illiq_full(0.86) 和 high_vol_illiq_full(1.00) 更优
3. Amihud 自相关 = 波动率聚集代理（|LS|=9.39, LE=-6.21），排除
4. Amihud 尾部比率方向正确（LE=0.79）但截面区分度不足（|LS|=0.43），可能需组合使用
5. D-006 方向经 4 轮实验（#008/#010/#012/#014）共测试 20 个特征，5 个通过。二阶属性成功拓展了 Amihud 因子族，方向仍有少量潜力但主要角度已探索完毕

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_amihud_second_order_full_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-033437/`
- **评估**: `.claude-output/evaluations/high_volume_ratio/amihud_diff_mean_full/`
- **Pending**: `research/pending-rawdata/amihud_diff_mean_full/`

### Experiment #015: Amihud 条件化变体 — 水平量聚合方式穷举（2026-03-26）

**方向**: D-006 high_volume_ratio
**Agent**: ashare_rawdata_a
**结果**: 5 特征快筛 + 3 特征正式评估，3 通过

| 特征 | |Net Sharpe| (r/n) | |IR| (r/n) | LE (r/n) | w1 Mono (r/n) | 2024 neutral | 状态 |
|------|---------------------|-------------|----------|---------------|-------------|------|
| `amihud_vol_accel_full` | 1.50/1.52 | 0.32/0.42 | +1.14/+1.16 | 1.00/0.86 | 0.62 | ✅ pending |
| `amihud_low_vol_full` | 1.50/1.52 | 0.35/0.43 | +1.05/+1.18 | 1.00/0.86 | 0.57 | ✅ pending |
| `amihud_return_weighted_full` | 1.43/1.46 | 0.36/0.43 | +1.04/+1.17 | 0.86/0.86 | 0.57 | ✅ pending |
| `amihud_hhi_full` | 0.69 | 0.38 | -0.51 | - | - | ❌ LE 负值（空头端集中） |
| `amihud_cv_full` | 0.01 | 0.38 | +0.16 | - | - | ❌ 无信号（分布形状消除水平量信息） |

**关键发现**:
1. 量增条件、低量条件、收益率加权三种新的 Amihud 聚合方式全部通过，但预计与已有 Amihud 特征高度相关
2. amihud_vol_accel_full raw Mono=1.00 完美单调，neutral IR=0.43 信号增强
3. 分布形状统计量（HHI/CV）再次失败，与 Exp#014 的 tail_ratio/autocorr 一致：Amihud 有效信号仅在水平量维度
4. D-006 方向经 5 轮实验（#008/#010/#012/#014/#015）共测试 25 个特征，8 个通过。Amihud 条件化的所有合理角度已穷尽
5. 建议方向 D-006 正式标记为 exhausted

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_amihud_conditioning_full_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-035433/`
- **评估**: `.claude-output/evaluations/high_volume_ratio/amihud_vol_accel_full/`, `.claude-output/evaluations/high_volume_ratio/amihud_low_vol_full/`, `.claude-output/evaluations/high_volume_ratio/amihud_return_weighted_full/`
- **Pending**: `research/pending-rawdata/amihud_vol_accel_full/`, `research/pending-rawdata/amihud_low_vol_full/`, `research/pending-rawdata/amihud_return_weighted_full/`

### Experiment #016: D-008 价格加速度（2026-03-26）

**方向**: D-008 price_acceleration
**Agent**: ashare_rawdata_b
**结果**: 8 特征测试，2 通过

| 特征 | Net Sharpe | w1 Mono | 状态 |
|------|-----------|---------|------|
| `high_vol_accel_illiq_full` | 1.93 | 1.00 | ✅ pending |
| `accel_illiq_full` | 1.67 | 0.71 | ✅ pending |
| `accel_kurtosis_full` | 10.88 | N/A | ❌ LE=-7.40 波动率代理 |
| `accel_skew_full` | 8.51 | N/A | ❌ LE=-3.22 |
| `accel_vol_corr_full` | 6.59 | N/A | ❌ LE=-4.58 波动率代理 |
| `accel_std_full` | 5.10 | N/A | ❌ LE=-4.89 波动率代理 |
| `abs_accel_mean_full` | 4.28 | N/A | ❌ LE=-3.91 波动率代理 |
| `accel_regime_trans_full` | 1.99 | N/A | ❌ LE=-0.22 |

**关键发现**:
1. Amihud 框架（|f(price)|/amount）从一阶（收益率）拓展到二阶（加速度）维度仍然有效：high_vol_accel_illiq_full raw Mono=1.00 完美单调
2. 纯加速度统计量（绝对值/标准差/峰度/偏度/相关性）全部是波动率代理（LE 深度负值），与 BPV/HL range 失败模式一致
3. 加速度 regime transition（符号切换频率 ~85%）截面区分度不足，基线太高导致差异被压缩
4. 两个通过特征中性化后信号增强（neutral IR > raw IR），含独立于市值/行业的流动性 alpha

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_price_accel_full_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-033927/`
- **评估**: `.claude-output/evaluations/price_acceleration/accel_illiq_full/`, `.claude-output/evaluations/price_acceleration/high_vol_accel_illiq_full/`
- **Pending**: `research/pending-rawdata/accel_illiq_full/`, `research/pending-rawdata/high_vol_accel_illiq_full/`

### Experiment #017: D-008 加速度 Amihud 条件化变体（2026-03-26）

**方向**: D-008 price_acceleration
**Agent**: ashare_rawdata_b
**结果**: 3 特征测试，3 通过

| 特征 | |Net Sharpe| (r/n) | |IR| (r/n) | LE (r/n) | w1 Mono (r/n) | 状态 |
|------|---------------------|-------------|----------|---------------|------|
| `reversal_accel_illiq_full` | 1.66/1.46 | 0.37/0.43 | +1.34/+1.39 | 0.71/0.71 | ✅ pending |
| `low_vol_accel_illiq_full` | 1.57/1.58 | 0.35/0.42 | +1.12/+1.41 | 0.71/0.86 | ✅ pending |
| `extreme_accel_illiq_full` | 1.49/1.35 | 0.39/0.44 | +1.16/+1.35 | 0.71/0.57 | ✅ pending |

**关键发现**:
1. D-006 的 Amihud 条件化模式（反转/极端/低量）完全迁移到加速度维度，三种方式全部通过
2. 中性化后信号增强模式一致（neutral IR +16%~20% vs raw），含独立于市值/行业的流动性 alpha
3. low_vol_accel_illiq_full neutral Mono=0.86 最高，低量时段价格曲率冲击分离更纯净的流动性信号
4. D-008 两轮实验共 11 个特征中 5 个通过，全部是 |accel|/amount 不同 bar 选择变体，条件化空间已饱和
5. 建议 D-008 标记为 exhausted

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_accel_conditioning_full_screening.md`
- **Evolve 产��**: `.claude-output/evolve/20260326-043526/`
- **评估**: `.claude-output/evaluations/price_acceleration/reversal_accel_illiq_full/`, `.claude-output/evaluations/price_acceleration/extreme_accel_illiq_full/`, `.claude-output/evaluations/price_acceleration/low_vol_accel_illiq_full/`
- **Pending**: `research/pending-rawdata/reversal_accel_illiq_full/`, `research/pending-rawdata/extreme_accel_illiq_full/`, `research/pending-rawdata/low_vol_accel_illiq_full/`

<!-- Agent append: 2026-03-26T06:00:00 -->
### Experiment #018: D-004 CS Spread 条件化变体（2026-03-26）

**方向**: D-004 corwin_schultz_spread
**Agent**: ashare_rawdata_a
**结果**: 5 特征快筛，0 通过

| 特征 | LS Sharpe | LE | IR(LS) | 状态 |
|------|-----------|-----|--------|------|
| `cs_high_vol_spread_full` | 0.43 | +0.52 | 0.30 | ❌ LS+LE 不达标 |
| `cs_reversal_spread_full` | -3.40 | -1.40 | 0.05 | ❌ 反向+IR极低 |
| `cs_vw_spread_full` | -0.79 | -1.47 | 0.28 | ❌ 反向 |
| `cs_spread_roughness_full` | -1.81 | -0.13 | 0.04 | ❌ IR极低 |
| `cs_high_vol_reversal_spread_full` | -4.94 | -2.13 | 0.02 | ❌ 反向+IR极低 |

**关键发现**:
1. Amihud 条件化范式不可迁移到 CS spread：CS 是 pair 级统计分解，H-L range 已隐式包含 bid-ask bounce 信息，条件化子选择 pair 只减少统计量不增加经济含义
2. cs_high_vol_spread_full 是唯一方向正确的特征（LS=0.43, LE=0.52, IR=0.30），但即使按原始 CS spread 的中性化增益（1.87x）也仅达 LS≈0.80，低于 0.9
3. 反转条件实际选出了 H-L range 更大的 pair（波动率偏差），导致信号反向
4. D-004 总计 2 轮实验（Exp#006+#018），10 个特征，2 个通过（均为 Exp#006 原始 CS spread）。条件化空间不可扩展，建议标记 exhausted

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_cs_spread_conditioned_full_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-055423/`

### Experiment #019: D-004 CS Spread 多尺度/混合变体（2026-03-26）

**方向**: D-004 corwin_schultz_spread
**Agent**: ashare_rawdata_a
**结果**: 4 特征快筛，0 通过

| 特征 | |LS Sharpe| | LE | IR(LS) | 状态 |
|------|-----------|------|--------|------|
| `cs_5m_spread_full` | 0.75 | -0.28 | 0.24 | ❌ LS+LE，5m聚合破坏微结构分解 |
| `cs_multiscale_ratio_full` | 1.91 | +0.11 | 0.23 | ❌ 空头端集中，尺度比率=波动率代理 |
| `cs_spread_per_amount_full` | 0.37 | +0.68 | 0.34 | ❌ LS太低，与Amihud冗余 |
| `cs_session_asymmetry_full` | 2.12 | +0.05 | 0.20 | ❌ 空头端集中，session差异截面区分度不足 |

**关键发现**:
1. CS spread 的有效性依赖于 1m 级别相邻 bar 的微小 H-L 差分；5m 聚合增大了波动率权重，破坏了 spread 分解有效性（与结论#22 一致）
2. 尺度比率和 session 非对称性都退化为波动率/市值代理
3. spread/amount 混合虽 LE=0.68 接近阈值，但完全被 amihud_illiq_full (LS=2.37, LE=1.79) 覆盖
4. D-004 三轮实验（#006/#018/#019），14 特征，2 通过（均为原始均值），方向确认 exhausted

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_cs_spread_multiscale_full_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-061024/`


<!-- Agent append: 2026-03-26T07:34:29.297347 -->
### Experiment #020: Hurst Exponent + Volume Roughness（2026-03-26）

**方向**: D-010 hurst_exponent
**Agent**: ashare_rawdata_a
**结果**: 6 特征测试，1 通过

| 特征 | LS Sharpe | LE Sharpe | IR | w1 Mono | 状态 |
|------|-----------|-----------|-----|---------|------|
| `vol_roughness_full` | 1.42 | 0.85 | 0.53 | 0.71 | ✅ pending |
| `hurst_volume_full` | -4.77 | -2.15 | -0.44 | 0.00 | ❌ 反向，波动率代理 |
| `hurst_return_full` | -3.90 | -1.43 | -0.24 | — | ❌ 反向（快筛） |
| `hurst_amount_full` | -4.97 | -2.93 | -0.47 | — | ❌ ≈hurst_volume |
| `hurst_range_full` | -5.69 | -3.22 | -0.41 | — | ❌ 波动率聚集代理 |
| `vol_var_ratio_full` | -5.64 | -4.11 | -0.67 | — | ❌ 方差比不迁移 |

**关键发现**:
1. Volume 路径粗糙度（mean|Δvol|/mean(vol)）是 amihud_diff_mean 在 volume 维度的成功延伸
2. R/S Hurst 在 237 bars 短序列上无法分离持续性与波动率，退化为波动率代理
3. 方差比从 returns→volume 不改变信号本质（仍是自相关代理）
4. 本方向可挖掘空间有限，建议标记为 explored（路径粗糙度已提取，Hurst 系列失败）

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_hurst_exponent_full_screening.md`
- **评估**: `.claude-output/evaluations/hurst_exponent/`
<!-- Agent append: 2026-03-26T08:20:00 -->
### Experiment #021: D-008 加速度 Amihud 正式评估（2020-2024 全覆盖）（2026-03-26）

**方向**: D-008 price_acceleration
**Agent**: ashare_rawdata_b
**结果**: 5 特征正式评估（2020-2024），5 通过

| 特征 | |Net Sharpe| (r/n) | |IR| (r/n) | LE (r/n) | w1 Mono (r/n) | 2024 Sharpe (r/n) | 状态 |
|------|---------------------|-------------|----------|---------------|-------------------|------|
| `high_vol_accel_illiq_full` | 1.56/1.74 | 0.32/0.44 | +1.12/+1.15 | 1.00/0.86 | 0.77/1.47 | ✅ pending (2024 confirmed) |
| `low_vol_accel_illiq_full` | 1.50/1.60 | 0.33/0.41 | +0.97/+1.17 | 0.86/0.86 | 1.32/1.64 | ✅ pending (2024 confirmed) |
| `accel_illiq_full` | 1.55/1.65 | 0.33/0.41 | +1.03/+1.18 | 0.71/0.86 | 1.25/1.65 | ✅ pending (2024 confirmed) |
| `reversal_accel_illiq_full` | 1.50/1.44 | 0.35/0.41 | +1.12/+1.15 | 0.86/0.86 | 1.10/1.31 | ✅ pending (2024 confirmed) |
| `extreme_accel_illiq_full` | 1.37/1.35 | 0.35/0.42 | +0.98/+1.12 | 1.00/0.71 | 1.06/1.31 | ✅ pending (2024 confirmed) |

**关键发现**:
1. 5 个加速度 Amihud 变体含 2024 后全部通过所有筛选阈值；2024 neutral Sharpe 1.31-1.65，远好于 CS spread 的 2024 衰减（Sharpe 0.45）
2. 中性化显著改善 2024 表现：raw 2024 Sharpe 0.77-1.32 → neutral 1.31-1.65，证明 2024 年的独立流动性 alpha 仍然稳健
3. 2020 年 neutral 表现转正（4/5 特征），说明疫情初期负收益主要来自市值暴露而非因子信号
4. D-008 正式确认 exhausted，建议清除当前方向分配新方向

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_accel_2024_formal_eval.md`
- **评估 (2024)**: `.claude-output/evaluations/price_acceleration/{feat}_2024/`
- **PKL**: `.claude-output/analysis/price_acceleration/`

<!-- Agent append: 2026-03-26T08:35:00 -->
### Experiment #022: Hurst Exponent 扩展粗糙度（最终轮）（2026-03-26）

**方向**: D-010 hurst_exponent
**Agent**: ashare_rawdata_a
**结果**: 3 特征测试，0 独立通过

| 特征 | LS Sharpe | LE Sharpe | IR | Mono(raw) | 状态 |
|------|-----------|-----------|-----|---------|------|
| `vol_accel_full` | 1.79 | 1.25 | 0.56 | 0.86 | ❌ corr=0.9948 与 vol_roughness |
| `log_vol_roughness_full` | 1.29 | 0.86 | 0.50 | 0.43 | ❌ Mono 失败 |
| `vol_change_asym_full` | -8.46 | -0.80 | 0.12 | — | ❌ 反向+IR |

**关键发现**:
1. vol_accel（二阶差分）通过所有指标阈值，但与 vol_roughness（一阶差分）截面相关性 0.9948，不提供独立信号
2. Log 变换压缩了粗糙度信号中的关键极值差异，反而破坏截面区分度（Mono 从 0.86→0.43）
3. D-010 方向两轮共 9 特征，仅 vol_roughness_full 独立有效，方向确认 exhausted

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_hurst_exponent_ext_full_screening.md`
- **评估**: `.claude-output/evaluations/hurst_exponent/vol_accel_full_screening/`, `log_vol_roughness_full_screening/`

<!-- Agent append: 2026-03-26T09:10:00 -->
### Experiment #023: D-014 日内动量/价格路径拓扑（2026-03-26）

**方向**: D-014 intraday_momentum
**Agent**: ashare_rawdata_b
**结果**: 2 轮 16 特征测试，4 通过正式评估

**Round 1: 路径拓扑 + 方向性 Amihud（8 特征）**

| 特征 | |LS Sharpe| | LE | |IR| | 状态 |
|------|-----------|------|------|------|
| `path_efficiency_full` | 8.23 | -5.36 | 0.095 | ❌ 波动率代理 |
| `vw_path_efficiency_full` | 6.78 | -2.05 | 0.074 | ❌ 波动率代理 |
| `max_excursion_ratio_full` | 3.86 | -1.72 | 0.087 | ❌ 波动率代理 |
| `up_amihud_full` | 1.58 | +1.28 | 0.374 | ✅ 方向性条件 Amihud |
| `down_amihud_full` | 1.47 | +1.14 | 0.379 | ✅ (高相关, 不独立进入 pending) |
| `amihud_directional_asym_full` | 7.84 | -0.48 | 0.121 | ❌ 方向性信号 |
| `macro_amihud_full` | 0.18 | +0.85 | 0.287 | ❌ |LS|<0.9 |
| `cumret_area_norm_full` | 5.64 | -5.33 | 0.379 | ❌ 波动率代理 |

**Round 2: Amount 归一化路径特征（8 特征）**

| 特征 | |LS Sharpe| | LE | |IR| | 状态 |
|------|-----------|------|------|------|
| `batch_amihud_full` | 2.12 | +1.63 | 0.365 | ✅ 最强，volume-weighted |
| `vw_amihud_full` | 2.09 | +1.63 | 0.359 | ✅ (≈batch, 不独立进入 pending) |
| `cumret_area_amihud_full` | 1.08 | +1.11 | 0.302 | ✅ 路径积分/amount |
| `max_excursion_amihud_full` | 1.53 | +1.35 | 0.295 | ✅ 最大偏移/amount |
| `am_amihud_full` | 1.62 | +1.19 | 0.354 | ✅ (session split, 不独立) |
| `pm_amihud_full` | 1.62 | +1.22 | 0.343 | ✅ (session split, 不独立) |
| `cumret_path_roughness_full` | 3.73 | -0.77 | 0.099 | ❌ IR 极低 |
| `session_amihud_ratio_full` | 7.05 | -4.21 | 0.047 | ❌ 比率=方向性信号 |

**正式评估 Shortlist（2020-2023, 含 Mono）**

| 特征 | |LS|(r/n) | LE(r/n) | |IR|(r/n) | Mono(r/n) | 状态 |
|------|---------|---------|---------|-----------|------|
| `batch_amihud_full` | 2.12/1.94 | +1.63/+1.49 | 0.36/0.47 | 1.00/0.86 | ✅ pending |
| `up_amihud_full` | 1.58/1.50 | +1.28/+1.45 | 0.37/0.44 | 1.00/0.71 | ✅ pending |
| `max_excursion_amihud_full` | 1.53/1.11 | +1.35/+1.18 | 0.29/0.43 | 0.86/0.86 | ✅ pending |
| `cumret_area_amihud_full` | 1.08/0.37 | +1.11/+0.92 | 0.30/0.44 | 0.86/0.71 | ✅ pending(raw通过) |

**关键发现**:
1. 纯路径拓扑特征（效率/面积/偏移比）全部是波动率代理，与 BPV/HL range/quarticity 失败模式一致
2. Amount 归一化成功挽救路径特征：cumret_area LE 从 -5.33→+1.11，max_excursion LE 从 -1.72→+1.35
3. batch_amihud（sum|ret|/sum(amount)）≈ amihud_illiq（mean(|ret|/amount)），volume-weighting 几乎不改变信号
4. 方向性 Amihud 各自有效但差值（非对称性）无效，买卖双方价格冲击截面排序一致
5. D-014 通过的 8 个特征全部是 Amihud 框架变体，未产生超越已有流动性框架的新因子类别
6. 2024 年数据覆盖待确认（screening preload 仅 2020-2023）

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_intraday_momentum_path_topology_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-083109/`, `.claude-output/evolve/20260326-083603/`
- **评估**: `.claude-output/evaluations/intraday_momentum/`
- **Pending**: `research/pending-rawdata/batch_amihud_full/`, `research/pending-rawdata/up_amihud_full/`, `research/pending-rawdata/max_excursion_amihud_full/`, `research/pending-rawdata/cumret_area_amihud_full/`

<!-- Agent append: 2026-03-26T09:15:00 -->
### Experiment #024: D-015 收益率分布高阶矩（2026-03-26）

**方向**: D-015 return_distribution
**Agent**: ashare_rawdata_a
**结果**: 2 轮 10 特征测试，0 通过

**Round 1: 连续分布矩（5 特征）**

| 特征 | |LS Sharpe| (r/n) | |IR| (r/n) | Mono (r/n) | 状态 |
|------|---------------------|-------------|-------------|------|
| `return_kurtosis_full` | 11.55/9.38 | 0.44/0.53 | 0.14/0.29 | ❌ Mono |
| `return_skewness_full` | 10.30/9.43 | 0.30/0.33 | 0.00/0.14 | ❌ Mono |
| `tail_asymmetry_full` | 5.97/6.50 | 0.27/0.31 | 0.14/0.57 | ❌ Mono |
| `downside_deviation_ratio_full` | 4.01/— | 0.07/— | —/— | ❌ IR |
| `amihud_skew_interaction_full` | 6.28/— | 0.04/— | —/— | ❌ IR |

**Round 2: 离散频率型（5 特征）**

| 特征 | |LS Sharpe| (r/n) | |IR| (r/n) | Mono (r/n) | 状态 |
|------|---------------------|-------------|-------------|------|
| `positive_extreme_freq_full` | 4.33/4.59 | 0.25/0.24 | 0.43/0.43 | ❌ Mono |
| `extreme_volume_ratio_full` | 4.18/5.35 | 0.26/0.31 | 0.43/0.29 | ❌ Mono |
| `extreme_asymmetry_freq_full` | 4.44/— | 0.15/— | —/— | ❌ IR |
| `extreme_return_freq_full` | 3.68/— | 0.20/— | —/— | ❌ 边缘IR |
| `extreme_amihud_ratio_full` | 2.40/— | 0.09/— | —/— | ❌ IR |

**关键发现**:
1. 收益分布矩信号真实存在（|LS|>9, neutral后IR增强0.44→0.53），但截面呈U型/非线性关系，Mono全部不达标
2. 离散化（频率型）仅带来边际Mono改善（0.29→0.43），无法克服根本的非线性问题
3. 收益分布形态不是A股日频有效的截面排序维度
4. D-015方向确认exhausted

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_return_distribution_full_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-083749/`, `.claude-output/evolve/20260326-090206/`
- **评估**: `.claude-output/evaluations/return_distribution/`


<!-- Agent append: 2026-03-26T09:56:35.698049 -->
<!-- Agent append: 2026-03-26T09:55:00 -->
### Experiment #025: D-016 VWAP 微观结构（2026-03-26）

**方向**: D-016 vwap_microstructure
**Agent**: ashare_rawdata_a
**结果**: 2 轮 8 特征测试，2 通过

**Round 1: 基础 VWAP 特征（5 特征）**

| 特征 | |LS Sharpe| | LE | |IR| | Mono | 状态 |
|------|-----------|------|------|------|------|
| `vwap_cross_freq_full` | 2.88 | -0.065 | 0.22 | 1.00 | ❌ LE 不达标 |
| `vwap_distance_full` | 5.23 | -5.68 | 0.42 | — | ❌ 波动率代理 |
| `vwap_distance_amihud_full` | 0.14 | +0.36 | 0.25 | — | ❌ LS 太低 |
| `high_vol_vwap_amihud_full` | 0.17 | +0.36 | 0.20 | — | ❌ LS 太低 |
| `vwap_tracking_error_full` | 5.24 | -5.99 | 0.49 | — | ❌ 波动率代理 |

**Round 2: VWAP 交叉事件 + Amihud（3 特征）**

| 特征 | |LS| (r/n) | LE (r/n) | |IR| (r/n) | Mono (r/n) | 状态 |
|------|----------|----------|-----------|------------|------|
| `high_vol_vwap_cross_amihud_full` | 1.26/0.82 | +1.31/+1.21 | 0.37/0.45 | 1.00/0.86 | ✅ pending |
| `vwap_cross_amihud_full` | 0.93/0.58 | +0.92/+1.12 | 0.38/0.43 | 0.71/0.86 | ✅ pending |
| `vwap_distance_roughness_full` | 4.59/— | -4.64/— | 0.56/— | — | ❌ 波动率代理 |

**关键发现**:
1. VWAP 穿越事件 + Amihud 是 Amihud 框架的有效扩展：事件触发器从「收益率反转」扩展到「价格穿越 VWAP」
2. high_vol_vwap_cross_amihud_full raw Mono=1.00（完美单调），年度趋势 2020:-0.93 到 2023:+3.30
3. vwap_cross_freq Mono=1.00 但 LE 近零：VWAP 穿越频率有截面排序但无多头 alpha
4. VWAP 距离/跟踪误差是波动率代理（与结论#22, #47 一致）
5. pkl 仅覆盖 2020-2023（preload 限制），2024 性能待补充

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_vwap_microstructure_full_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-092801/`, `.claude-output/evolve/20260326-094142/`
- **评估**: `.claude-output/evaluations/vwap_microstructure/`
- **Pending**: `research/pending-rawdata/vwap_cross_amihud_full/`, `research/pending-rawdata/high_vol_vwap_cross_amihud_full/`

<!-- Agent append: 2026-03-26T10:25:00.132988 -->
### Experiment #026: D-017 量价协调性 (pv_concordance)（2026-03-26）

**方向**: D-017 pv_concordance
**Agent**: ashare_rawdata_a
**结果**: 1 轮 5 特征测试，2 通过

| 特征 | |LS Sharpe| (r/n) | LE (r/n) | |IR| (r/n) | Mono (r/n) | 状态 |
|------|------------------|----------|-----------|------------|------|
| `pv_concordance_ratio_full` | 5.61/— | -3.99/— | 0.40/— | — | ❌ LE 深度负（空头端集中）|
| `pv_extreme_concordance_full` | 5.22/— | -2.41/— | 0.40/— | — | ❌ LE 负 |
| `pv_corr_full` | 7.22/— | -2.98/— | 0.79/— | — | ❌ 波动率代理模式 |
| `concordant_amihud_full` | 1.65/1.27 | +1.56/+1.41 | 0.35/0.52 | 1.00/0.71 | ✅ pending |
| `discordant_amihud_full` | 1.48/1.15 | +1.36/+1.45 | 0.37/0.53 | 0.86/0.57 | ✅ pending |

**关键发现**:
1. 量价协调性计数（concordance_ratio/extreme/corr）全部失败在 LE——高量价同步=投机/事件驱动=只识别坏股票
2. 联合事件选择 + Amihud 有效：concordant_amihud raw Mono=1.00，discordant_amihud raw Mono=0.86
3. Neutral 后 IR 增强（0.35→0.52, 0.37→0.53），信号独立于市值/行业；但 Mono 下降
4. 2020 年 raw 表现为负（-0.67/-0.93），2021-2023 逐年增强

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_pv_concordance_full_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-100922/`
- **评估**: `.claude-output/evaluations/pv_concordance/`
- **Pending**: `research/pending-rawdata/concordant_amihud_full/`, `research/pending-rawdata/discordant_amihud_full/`

<!-- Agent append: 2026-03-26T10:53:07.206458 -->
### Experiment #027: D-018 Amihud 价格冲击买卖不对称性（2026-03-26）

**方向**: D-018 amihud_asymmetry
**Agent**: ashare_rawdata_a
**结果**: 1 轮 5 特征测试，2 通过

| 特征 | |LS Sharpe| (r/n) | LE (r/n) | |IR| (r/n) | Mono (r/n) | 状态 |
|------|------------------|----------|-----------|------------|------|
| `down_amihud_full` | 1.42/1.36 | +1.14/+1.41 | 0.38/0.43 | 0.71/0.86 | ✅ pending |
| `high_vol_down_amihud_full` | 1.83/1.52 | +1.53/+1.43 | 0.38/0.44 | 1.00/1.00 | ✅ pending |
| `amihud_asymmetry_full` | 7.49/— | -0.30/— | 0.13/— | — | ❌ LE 负/IR 低 |
| `amihud_sell_ratio_full` | 2.59/— | -1.70/— | 0.30/— | — | ❌ LE 负 |
| `high_vol_amihud_asymmetry_full` | 6.77/— | -1.42/— | 0.12/— | — | ❌ LE 负/IR 低 |

**关键发现**:
1. 下行 Amihud（仅下跌 bar 的 |ret|/amount）是 Amihud 框架的有效扩展
2. high_vol_down_amihud_full raw 和 neutral 双 Mono=1.00（完美单调），年度 Sharpe 2021-2023 均正
3. Neutral 后 IR 增强（0.38→0.43, 0.38→0.44），信号独立于市值/行业
4. 不对称性比率类因子（asymmetry/sell_ratio）alpha 全集中空头端，与结论#6 一致
5. pkl 覆盖 2020-2023（preload 限制），2024 segment 无数据

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_amihud_asymmetry_full_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-103512/`
- **评估**: `.claude-output/evaluations/amihud_asymmetry/`
- **Pending**: `research/pending-rawdata/down_amihud_full/`, `research/pending-rawdata/high_vol_down_amihud_full/`
<!-- Agent append: 2026-03-26T11:30:00 -->
### Experiment #028: Price Absorption & Depth — Bar 微观结构（2026-03-26）

**方向**: D-019 price_absorption_depth
**Agent**: ashare_rawdata_a
**结果**: 15 特征测试（3 轮迭代），4 通过

| 特征 | Net Sharpe (best) | w1 Mono | 状态 |
|------|-------------------|---------|------|
| `absorption_freq_full` | |3.69| | - | ❌ LE=-0.27 空头端 |
| `zero_return_freq_full` | 0.78 | - | ❌ |LS|<0.9 |
| `depth_volume_ratio_full` | |2.93| | - | ❌ LE=-0.37 空头端 |
| `absorption_amihud_full` | 1.11 | - | ❌ IR 边缘+覆盖率低 |
| `impact_efficiency_full` | 2.09 | - | ❌ 与 batch_amihud 冗余 |
| `wick_ratio_full` | 1.43 | - | ❌ IR=0.17<0.2 |
| `wick_amihud_full` | 2.36(n) | 1.00(r)/0.86(n) | ✅ pending (neutral通过) |
| `high_vol_wick_amihud_full` | 2.15(n) | 0.86 | ✅ pending (neutral通过) |
| `bar_efficiency_full` | |3.65| | - | ❌ LE=-3.28 波动率代理 |
| `low_impact_amihud_full` | 0.01 | - | ❌ 无信号 |
| `wick_roughness_full` | 0.84(r)/2.51(n) | 0.86 | ❌ raw |LS|不达标, ntrl LE=0.12 |
| `doji_amihud_full` | 1.68(r) | 0.86 | ✅ pending (双组通过) |
| `high_vol_doji_amihud_full` | 1.78(r) | 0.86 | ✅ pending (双组通过) |
| `wick_regime_transitions_full` | |4.10| | - | ❌ LE=-1.03 |
| `rejection_intensity_full` | |4.63| | - | ❌ LE=-4.58 波动率代理 |

**关键发现**:
1. Bar 形态（doji 条件: wick > body）是 Amihud 框架的有效新事件选择器
2. Wick (H-L-|C-O|) 是 Amihud numerator 的有效新维度，neutral 后大幅增强
3. 离散频率计数（absorption_freq 类）在"吸收"维度失败在 LE
4. Wick regime transitions 失败，与结论#19（仅 volume 有效）一致
5. pkl 覆盖 2020-2023（preload 限制）

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_price_absorption_depth_full_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-110346/`, `.claude-output/evolve/20260326-110826/`, `.claude-output/evolve/20260326-111219/`
- **评估**: `.claude-output/evaluations/price_absorption/`
- **Pending**: `research/pending-rawdata/doji_amihud_full/`, `research/pending-rawdata/high_vol_doji_amihud_full/`, `research/pending-rawdata/wick_amihud_full/`, `research/pending-rawdata/high_vol_wick_amihud_full/`

### Experiment #029: D-014 Amihud 路径变体正式评估（2026-03-26）

**方向**: D-014 intraday_momentum
**Agent**: ashare_rawdata_b
**结果**: 4 特征正式评估（2020-2024），3 通过，1 失败

| 特征 | LS Sharpe (r/n) | LE (r/n) | IR (r/n) | Mono (r/n) | 状态 |
|------|----------------|----------|----------|------------|------|
| `batch_amihud_full` | 1.73/1.93 | 1.22/1.20 | 0.33/0.46 | 1.00/0.86 | ✅ pending |
| `up_amihud_full` | 1.45/1.47 | 1.08/1.17 | 0.35/0.42 | 1.00/0.71 | ✅ pending |
| `max_excursion_amihud_full` | 1.08/0.98 | 0.88/0.80 | 0.25/0.42 | 1.00/0.86 | ✅ pending |
| `cumret_area_amihud_full` | 0.66/0.18 | 0.64/0.52 | 0.26/0.42 | 0.86/0.71 | ❌ 2024衰减 |

**关键发现**: cumret_area_amihud_full 快筛通过（2020-2023 raw LS=1.08）但正式评估失败（2020-2024 raw LS=0.66），2024 年信号衰减 39%。累积收益路径积分对波动率环境变化更敏感，不具备时间稳定性。其余 3 个特征信号稳定，batch_amihud_full 2024 年仍有 Sharpe=0.95。

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_intraday_momentum_amihud_formal_eval.md`
- **评估**: `.claude-output/evaluations/intraday_momentum/{batch_amihud_full,up_amihud_full,max_excursion_amihud_full,cumret_area_amihud_full}/`
- **Pending**: `research/pending-rawdata/{batch_amihud_full,up_amihud_full,max_excursion_amihud_full}/`


<!-- Agent append: 2026-03-26T12:09:59.612012 -->
### Experiment #029: OHLC 微观结构分解（2026-03-26）

**方向**: D-020 ohlc_microstructure_decomposition
**Agent**: ashare_rawdata_a
**结果**: 5 特征测试，4 通过

| 特征 | LS Sharpe (r/n) | LE (r/n) | IR(LS) (r/n) | Mono (r/n) | 状态 |
|------|-----------------|----------|--------------|------------|------|
| `close_disp_amihud_full` | 1.05/1.55 | 0.61/1.28 | 0.44/0.46 | 0.75/0.89 | ✅ pending (neutral) |
| `high_vol_close_disp_amihud_full` | 1.01/1.13 | 0.67/1.16 | 0.42/0.45 | 0.79/0.82 | ✅ pending (neutral) |
| `upper_wick_amihud_full` | 1.26/2.18 | 0.74/1.37 | 0.46/0.48 | 0.86/0.86 | ✅ pending (both) |
| `lower_wick_amihud_full` | 1.10/2.16 | 0.60/1.36 | 0.48/0.49 | 0.79/0.86 | ✅ pending (neutral) |
| `close_disp_roughness_full` | -2.20/- | -0.27/- | 0.06/- | -/- | ❌ IR 极低 |

**关键发现**: Bar 内 OHLC 结构分解（close displacement = |C-midpoint|, upper/lower wick）归一化到 amount 后全部有效。中性化后信号大幅增强（LS +12%~+96%）。Upper/lower wick 几乎等强（neutral LS 2.18 vs 2.16），证明流动性溢价不依赖价格探索方向。

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_ohlc_microstructure_full_screening.md`
- **评估**: `.claude-output/evaluations/ohlc_microstructure/`
<!-- Agent append: 2026-03-26T12:25:00 -->
### Experiment #030: D-014 回撤路径 + 影线分解最终轮（2026-03-26）

**方向**: D-014 intraday_momentum
**Agent**: ashare_rawdata_b
**结果**: 6 特征测试，2 通过但全部冗余

| 特征 | |LS Sharpe| (r/n) | LE (r/n) | |IR| (r/n) | Mono (r/n) | 与 pending 相关性 | 状态 |
|------|---------------------|----------|-----------|------------|-------------------|------|
| `max_drawdown_amihud_full` | 1.89/1.75 | +1.53/+1.42 | 0.33/0.49 | 1.00/0.86 | 0.87 vs max_excursion | ✅ 通过但冗余 |
| `drawdown_area_amihud_full` | 1.76/- | +1.50/- | 0.27/- | -/- | 0.75 vs batch_amihud | ✅ 快筛通过，冗余 |
| `max_drawup_amihud_full` | 0.96/- | +1.04/- | 0.24/- | -/- | 0.89 vs max_excursion | ✅ 边缘，冗余 |
| `upper_wick_amihud_full` | 1.26/2.18 | +0.74/+1.37 | 0.46/0.48 | 0.86/0.71 | **0.98** vs wick_amihud | ✅ 已被 D-020 覆盖 |
| `lower_wick_amihud_full` | 1.10/- | +0.60/- | 0.48/- | -/- | 0.98 vs wick_amihud | ❌ LE<0.7 |
| `cumret_zero_cross_freq_full` | 4.60/- | -0.67/- | **0.005**/- | -/- | - | ❌ IR≈0 |

**关键发现**:
1. 回撤路径（peak-to-trough）与偏移路径（start-to-peak）截面相关 0.87-0.89，对随机游走路径近似等价
2. 上/下影线分离 Amihud 与总影线 wick_amihud 相关 0.98，分离不提供信息增量（上下影线自身相关 0.93）
3. 累积收益零穿越频率 IR=0.005，路径级别零穿越在 A 股无截面选股信号
4. D-014 三轮（#023/#029/#030）共 22 特征，3 pending + 4 冗余通过 + 15 失败。**方向确认 exhausted**

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_intraday_momentum_drawdown_final.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-120758/`
- **评估**: `.claude-output/evaluations/intraday_momentum_drawdown/`

<!-- Agent append: 2026-03-26T12:45:00 -->
### Experiment #031: D-021 日内价格区间发现动态（2026-03-26）

**方向**: D-021 range_discovery_dynamics
**Agent**: ashare_rawdata_a
**结果**: 5 特征测试，2 通过（neutral 组）

| 特征 | LS Sharpe (r/n) | LE (r/n) | IR(LS) (r/n) | Mono (r/n) | 状态 |
|------|-----------------|----------|--------------|------------|------|
| `body_amihud_full` | 0.98/1.34 | 0.59/1.24 | 0.43/0.45 | 0.71/0.86 | ✅ pending (neutral) |
| `open_disp_amihud_full` | 0.97/1.38 | 0.62/1.27 | 0.48/0.47 | 0.86/0.86 | ✅ pending (neutral) |
| `range_discovery_freq_full` | -2.91/- | -1.28/- | 0.11/- | -/- | ❌ 反向+IR 低(波动率代理) |
| `range_discovery_amihud_full` | 0.84/- | 0.19/- | 0.33/- | -/- | ❌ LS<0.9, 覆盖64% |
| `high_vol_body_amihud_full` | 0.80/- | 0.66/- | 0.34/- | -/- | ❌ LS<0.9 |

**关键发现**:
1. |C-O|/amount (body Amihud) 和 |O-midpoint|/amount (open disp Amihud) 是 Amihud 框架的有效新 numerator
2. 中性化后 body_amihud LS 从 0.98→1.34（+37%），open_disp 从 0.97→1.38（+42%），与 OHLC Amihud 系列一致
3. 区间发现频率（range_discovery_freq）是波动率代理——|LS|=2.91 强烈反向，IR=0.11 极低
4. 发现事件条件 Amihud 覆盖率仅 64%，样本量不足导致信号不稳定
5. 高量过滤反而削弱 body Amihud（LS 从 0.98→0.80），|C-O| 在高量 bar 上截面差异被压缩

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_range_discovery_full_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-122319/`
- **评估**: `.claude-output/evaluations/range_discovery/`
- **Pending**: `research/pending-rawdata/body_amihud_full/`, `research/pending-rawdata/open_disp_amihud_full/`

<!-- Agent append: 2026-03-26T13:15:00 -->
### Experiment #032: D-023 Multi-Bar Price Structure（2026-03-26）

**方向**: D-023 multi_bar_price_structure
**Agent**: ashare_rawdata_a
**结果**: 5 特征测试，3 通过（neutral）

| 特征 | Net Sharpe (neutral) | w1 Mono (neutral) | 状态 |
|------|-----------|---------|------|
| `high_vol_inside_amihud_full` | 1.35 | 0.86 | ✅ pending |
| `inside_bar_amihud_full` | 1.35 | 0.86 | ✅ pending |
| `engulfing_amihud_full` | 1.23 | 0.71 | ✅ pending |
| `inside_bar_freq_full` | 0.88 | 0.86 | ❌ LS<0.9 |
| `engulfing_freq_full` | 0.85 | 1.00 | ❌ LS<0.9 |

**关键发现**:
1. Multi-bar 结构模式（inside bar=range 包含, engulfing=range 扩张）是 Amihud 框架的有效新事件选择器，3 个变体全部通过。
2. 频率指标虽然 Mono 极高（0.86-1.00）且 LE 达标（~1.0），但 LS 略低于 0.9 阈值，截面区分度不如 Amihud 框架。
3. 高量+结构双条件（high_vol_inside_amihud）再次产生最强信号（raw Mono=1.00, neutral IR=0.47）。

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_multi_bar_structure_full_screening.md`
- **Evolve 产出**: `.claude-output/evolve/20260326-125702/`
- **评估**: `.claude-output/evaluations/multi_bar_structure/`
- **Pending**: `research/pending-rawdata/high_vol_inside_amihud_full/`, `research/pending-rawdata/inside_bar_amihud_full/`, `research/pending-rawdata/engulfing_amihud_full/`

<!-- Agent append: 2026-03-26T13:30:00 -->
### Experiment #033: D-022 微观结构噪声（2026-03-26）

**方向**: D-022 microstructure_noise
**Agent**: ashare_rawdata_b
**结果**: 12 特征测试，2 通过

| 特征 | |LS Sharpe| (快筛) | LE (快筛) | IR | Net Sharpe (w1) | Mono (w1) | 状态 |
|------|-------------------|----------|------|-----------------|-----------|------|
| `excess_bounce_amihud_full` | 1.50 | +1.26 | 0.38 | 1.29 | 0.86 | ✅ pending |
| `bar_pair_noise_amihud_full` | 1.10 | +1.07 | 0.23 | 0.91 | 0.86 | ✅ pending (边缘) |
| `high_vol_noise_amihud_full` | 4.90 | -0.05 | 0.13 | - | - | ❌ 空头端集中 |
| `noise_ratio_10_full` | 1.90 | +0.26 | 0.28 | - | - | ❌ LE<0.7 |
| `noise_ratio_5_full` | 1.40 | +0.35 | 0.32 | - | - | ❌ LE<0.7 |
| `noise_amihud_10_full` | 0.70 | +1.06 | 0.30 | - | - | ❌ LS<0.9 |
| `noise_amihud_5_full` | 0.36 | +1.10 | 0.33 | - | - | ❌ LS<0.9 |
| `high_vol_autocov_amihud_full` | 0.75 | +0.21 | 0.19 | - | - | ❌ LS<0.9, LE<0.7 |
| `neg_autocov_amihud_full` | 0.60 | +1.15 | 0.39 | - | - | ❌ LS<0.9 |
| `noise_amihud_product_full` | 0.52 | +1.19 | 0.42 | - | - | ❌ LS<0.9 |
| `autocov_amihud_full` | 0.55 | +0.99 | 0.28 | - | - | ❌ LS<0.9 |
| `noise_depth_full` | 0.13 | +1.31 | 0.43 | - | - | ❌ LS<0.9 |

**关键发现**:
1. Amount 归一化成功挽救了 variance_ratio/autocovariance 信号的 Long Excess（noise_ratio LE=0.26-0.35 → noise_amihud LE=1.06-1.10），结论#48 再次验证
2. Bar-pair 级别归一化（|r_i×r_{i+1}|/avg(amount), LS=1.10）优于聚合级别归一化（|autocov|/(n×mean_amt), LS=0.55）
3. Bounce 条件（前向反转）是有效的 Amihud 事件选择器，excess_bounce_amihud 与 reversal_amihud（后向反转）相关 0.82
4. 连续收益率乘积 |r_i×r_{i+1}|/amount 是新的 Amihud numerator 维度，衡量"微观结构噪声成本"

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_microstructure_noise_full_screening.md`
- **评估**: `.claude-output/evaluations/microstructure_noise/`
- **Pending**: `research/pending-rawdata/excess_bounce_amihud_full/`, `research/pending-rawdata/bar_pair_noise_amihud_full/`

<!-- Agent append: 2026-03-26T13:45:00 -->
### Experiment #034: D-024 Cross-Bar Stability Patterns（2026-03-26）

**方向**: D-024 cross_bar_stability
**Agent**: ashare_rawdata_a
**结果**: 5 特征测试，2 通过（neutral）

| 特征 | |LS| (r/n) | LE (r/n) | IR (r/n) | Mono (r/n) | 状态 |
|------|-----------|----------|----------|------------|------|
| `rs_amihud_full` | 1.82/1.77 | +1.34/+1.35 | 0.26/0.30 | **1.00**/0.86 | ✅ pending |
| `amount_roughness_full` | 1.46/1.04 | +1.00/+0.73 | 0.55/0.55 | 0.57/**0.71** | ✅ pending (neutral) |
| `range_roughness_full` | 1.01(反) | +0.49 | 0.18 | - | ❌ IR<0.2 |
| `body_roughness_full` | 0.37 | +0.75 | 0.45 | - | ❌ LS<0.9 |
| `joint_reversal_vol_full` | 0.54 | +0.97 | 0.04 | - | ❌ IR≈噪声 |

**关键发现**:
1. RS Amihud（OHLC 4点 Rogers-Satchell 方差/amount）raw Mono=1.00 完美单调，中性化后 LS 仅降 3%，是目前所有 Amihud 变体中排序最清晰的
2. Amount roughness 验证了粗糙度范式从 volume 到 amount 的泛化（IR=0.55 与 vol_roughness 0.53 高度一致），但部分信号来自市值（neutral 后 LS 降 29%）
3. 价格衍生指标的 roughness（range, body）退化为波动率代理，与 wick_roughness 一致
4. 复合离散事件（reversal × vol regime change）基线频率过低（~13%），截面变异不足

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_cross_bar_stability_full_screening.md`
- **评估**: `.claude-output/evaluations/cross_bar_stability/`
- **Pending**: `research/pending-rawdata/rs_amihud_full/`, `research/pending-rawdata/amount_roughness_full/`

<!-- Agent append: 2026-03-26T14:05:00 -->
### Experiment #035: Temporal Microstructure（2026-03-26）

**方向**: D-025 temporal_microstructure
**Agent**: ashare_rawdata_b
**结果**: 8 特征测试，1 通过

| 特征 | |LS Sharpe| (r/n) | LE (r/n) | IR_LS (r/n) | Mono (r/n) | 状态 |
|------|-------------------|----------|-------------|------------|------|
| `open_gap_amihud_full` | 1.34/1.80 | +0.77/+1.32 | 0.51/0.55 | 0.86/0.71 | ✅ pending |
| `volume_lead_return_freq_full` | 5.69 | -4.80 | 0.44 | - | ❌ 空头集中 |
| `ret_lead_volume_freq_full` | 5.63 | -4.92 | 0.46 | - | ❌ 空头集中 |
| `high_timing_full` | 5.20 | -2.34 | 0.23 | - | ❌ 空头集中 |
| `extremum_spread_full` | 4.26 | -0.79 | 0.07 | - | ❌ IR极低 |
| `gap_body_ratio_full` | 0.15 | +0.50 | 0.26 | - | ❌ LS极低 |
| `range_contraction_freq_full` | 1.65 | -0.19 | 0.03 | - | ❌ IR≈噪声 |
| `volume_return_lag_diff_full` | 7.18 | -0.14 | 0.29 | - | ❌ LE≈0 |

**关键发现**:
1. Inter-bar gap（|open_i - close_{i-1}|/amount）是有效的新 Amihud numerator，中性化后 LS 增强 34%（1.34→1.80），含独立于市值/行业的流动性 alpha
2. 日内时序结构特征（极值时点、lead-lag 频率、范围动态）本身缺乏截面选股能力；仅 Amihud 框架内的 gap 变体通过
3. Lead-lag 频率（vol→ret / ret→vol）|LS|>5 但 LE 深度负值，重复空头集中失败模式

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_temporal_microstructure_full_screening.md`
- **评估**: `.claude-output/evaluations/temporal_microstructure/open_gap_amihud_full/`
- **Pending**: `research/pending-rawdata/open_gap_amihud_full/`

<!-- Agent append: 2026-03-26T14:18:00 -->
### Experiment #036: Temporal Microstructure V2 — 离散计数范式迁移（2026-03-26）

**方向**: D-025 temporal_microstructure
**Agent**: ashare_rawdata_b
**结果**: 6 特征测试，0 通过。**D-025 方向 exhausted。**

| 特征 | |LS Sharpe| | LE Sharpe | IR_LS | 状态 |
|------|-----------|----------|-------|------|
| `gap_reversal_freq_full` | 10.43 | -2.04 | -0.09 | ❌ IR 噪声 + LE 深负 |
| `gap_sign_run_mean_full` | 9.26 | -1.76 | -0.06 | ❌ IR 噪声 + LE 深负 |
| `volume_accel_freq_full` | 11.14 | -1.02 | -0.22 | ❌ 纯空头集中 |
| `large_gap_vol_sync_full` | 3.58 | -4.27 | -0.44 | ❌ LE=-4.27 极差 |
| `price_path_efficiency_full` | 8.13 | -5.29 | -0.08 | ❌ LE=-5.29 最差 |
| `gap_cv_full` | 2.95 | -2.42 | +0.34 | ❌ LE 深负 |

**关键发现**:
1. Gap 符号反转频率无法复制 reversal_ratio 的成功——inter-bar gap 翻转缺乏 bid-ask bounce 的流动性含义
2. 6 个离散计数/路径特征全部 LE < -1.0，确认非 Amihud 时序结构在 A 股系统性无法产生正 LE
3. large_gap_vol_sync IR=-0.44（强信号）但 LE=-4.27，典型"事件驱动型坏股票识别器"
4. D-025 两轮合计 14 特征，仅 1 个 Amihud 变体有效，方向 exhausted

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_temporal_microstructure_v2_full_screening.md`
- **Evolve**: `.claude-output/evolve/20260326-140952/`

<!-- Agent append: 2026-03-26T14:30:00 -->
### Experiment #037: D-026 Robust Liquidity Estimators（2026-03-26）

**方向**: D-026 robust_liquidity_estimators
**Agent**: ashare_rawdata_a
**假设**: 标准 Amihud 的算术均值被极端冲击 bar 主导；不同聚合函数（sqrt/log/harmonic/median/trimmed mean）可能产生不同截面排序
**结果**: 5 特征测试，2 通过（pending），1 IR 失败，2 冗余

| 特征 | raw |LS| | raw LE | raw Mono | neutral |LS| | neutral Mono | vs std Amihud corr | 状态 |
|------|---------|--------|----------|------------|-------------|-------------------|------|
| `sqrt_impact_amihud_full` | 1.90 | 1.57 | 1.00 | 1.60 | 0.71 | ~0.97 | ❌ 与 log 相关 0.995 |
| `log_impact_amihud_full` | **2.11** | **1.67** | 0.86 | **1.83** | 0.86 | **0.974** | ✅ pending |
| `harmonic_amihud_full` | 1.85 | 1.61 | **1.00** | 1.59 | 0.86 | **0.945** | ✅ pending |
| `median_amihud_full` | 1.06 | 1.61 | - | - | - | - | ❌ IR(LS)≈0 |
| `trimmed_amihud_full` | 1.91 | 1.47 | 0.86 | 1.73 | 0.86 | ~0.97 | ❌ 与 log 相关 0.997 |

**关键发现**:
1. 算术均值 Amihud 是最优聚合函数：极端冲击 bar 携带最多截面信息，压缩极端值=丢失信号
2. Harmonic（调和均值）最独立（corr 0.945），由最小 Amihud bar 主导，捕捉"最优执行潜力"
3. Median 完全丢失空头信号（IR≈0），说明极端 bar 是空头端 alpha 的核心来源
4. sqrt/log/trimmed 彼此 0.99+，本质是同一信号

#### Related
- **报告**: `research/agent_reports/screening/2026-03-26_robust_liquidity_estimators_full_screening.md`
- **Evolve**: `.claude-output/evolve/20260326-135807/`
- **评估**: `.claude-output/evaluations/robust_liquidity_estimators/`

## 四、统计

| 指标 | 值 |
|------|-----|
| 总实验数 | 38 |
| 已测特征数 | 269 |
| 已注册 Bundle | 8 (pv_stats×4, volatility×4) |
| Pending | 48 (reversal_ratio_full, cs_relative_spread_full, cs_spread_full, vol_regime_transitions_full, amihud_illiq_full, high_vol_illiq_full, reversal_amihud_full, high_vol_reversal_amihud_full, extreme_amihud_full, amihud_diff_mean_full, amihud_vol_accel_full, amihud_low_vol_full, amihud_return_weighted_full, accel_illiq_full, high_vol_accel_illiq_full, reversal_accel_illiq_full, extreme_accel_illiq_full, low_vol_accel_illiq_full, vol_roughness_full, batch_amihud_full, up_amihud_full, max_excursion_amihud_full, vwap_cross_amihud_full, high_vol_vwap_cross_amihud_full, concordant_amihud_full, discordant_amihud_full, down_amihud_full, high_vol_down_amihud_full, doji_amihud_full, high_vol_doji_amihud_full, wick_amihud_full, high_vol_wick_amihud_full, close_disp_amihud_full, high_vol_close_disp_amihud_full, upper_wick_amihud_full, lower_wick_amihud_full, body_amihud_full, open_disp_amihud_full, high_vol_inside_amihud_full, inside_bar_amihud_full, engulfing_amihud_full, excess_bounce_amihud_full, bar_pair_noise_amihud_full, rs_amihud_full, amount_roughness_full, open_gap_amihud_full, log_impact_amihud_full, harmonic_amihud_full) |
| 已排除方向 | 10 (D-001, D-002, D-003, D-010, D-011, D-012, D-013, D-014, D-015, D-025) |
| 已验证结论 | 93 |

## 五、技术备忘

（暂无）
