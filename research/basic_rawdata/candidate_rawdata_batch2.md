# 第二批 Raw-Data 候选清单

> 日期：2026-03-19
> 目的：从中挑选入库，需考虑计算成本（全天窗口 vs 子窗口）

## 分组原则

- **A 组（子窗口可算）**: 不依赖全天数据，可以在任意时间窗口（如 0930-1030）内计算，与第一批 bundle 机制一致
- **B 组（需要全天窗口）**: 需要全天 240 bars 或跨时段信息（如上午 vs 下午对比、尾盘占比等）

---

## A 组：子窗口可算

这些因子可以在任意窗口内计算，可与现有 4 个时间窗口复用。

### A1. 聪明钱因子 (Smart Money Factor)

- **计算**: 每根 bar 算 S = |return| / sqrt(volume)，按 S 从高到低排序，取累计 volume 达到总量 20% 的 bars，算这些 bars 的 VWAP vs 整体 VWAP
- **逻辑**: 大单低买高卖的行为信号，S 高 = 少量成交引起大价格变动 = 知情交易
- **来源**: 广发证券
- **输入**: close, volume

### A2. 跳跃变差 (Jump Variation)

- **计算**:
  - Bipower variation: BV = (π/2) × sum(|r_i| × |r_{i-1}|)
  - Jump variation: JV = max(RV - BV, 0)
  - 正跳/负跳分离
- **逻辑**: 区分连续波动和突发信息冲击
- **来源**: Li et al. 2017, PLOS ONE
- **输入**: close

### A3. 方差比 (Variance Ratio)

- **计算**: 将连续 5 根 1m bar 合并为 5m return，Var(5m) / (5 × Var(1m))
- **逻辑**: VR>1 = 趋势（知情交易），VR<1 = 均值回复（噪声）
- **来源**: 中信建投
- **输入**: close

### A4. Corwin-Schultz Spread

- **计算**: 用相邻两根 bar 的 high/low 估算 bid-ask spread
  - β = E[ln(H/L)²], γ = ln(H₂/L₂)²（其中 H₂, L₂ 为两根 bar 合并的 high/low）
  - S = 2(e^α - 1) / (1 + e^α), α = f(β, γ)
- **逻辑**: 比 Amihud 更精确的流动性/交易成本代理
- **来源**: Corwin & Schultz 2012, JF
- **输入**: high, low

### A5. 成交量熵 (Volume Entropy)

- **计算**: 每根 bar 的 volume 占总 volume 的比例 p_i，Shannon 熵 = -sum(p_i × ln(p_i))
- **逻辑**: 低熵 = 成交集中 = 可能有知情交易者；高熵 = 均匀分布 = 正常交易
- **来源**: 长江证券 2024
- **输入**: volume

### A6. 高量成交占比 (High Volume Ratio)

- **计算**: 窗口内 volume > 2 × mean(volume) 的 bar 数量 / 总 bar 数
- **逻辑**: 异常放量频率，代理机构激进交易行为
- **来源**: 2024 A股有效因子
- **输入**: volume

### A7. 已实现四次变差 (Realized Quarticity)

- **计算**: (n/3) × sum(r_i⁴)
- **逻辑**: 尾部风险度量，刻画极端价格跳跃的频率和幅度
- **来源**: Barndorff-Nielsen & Shephard
- **输入**: close

### A8. 价格加速度 (Price Acceleration)

- **计算**: 将窗口分前半和后半，acceleration = return_后半 - return_前半
- **逻辑**: 二阶动量，捕捉加速/减速趋势。2/3 测试中优于一阶动量
- **输入**: close

### A9. BVC 多空分类 (Bulk Volume Classification)

- **计算**: 每根 bar 的买入占比 τ = (close - open) / (high - low)，归一化到 [0,1]
  - buy_volume = τ × volume, sell_volume = (1-τ) × volume
  - OIB = (buy - sell) / (buy + sell)
- **逻辑**: 不需要 orderbook 的委买委卖近似，Lee-Ready 分类的 OHLC 版本
- **来源**: Easley, López de Prado & O'Hara (VPIN)
- **输入**: open, high, low, close, volume

### A10. Roll Spread

- **计算**: Roll = 2 × sqrt(-Cov(Δp_t, Δp_{t-1}))，若 Cov > 0 则设为 0
- **逻辑**: 从价格序列的负自协方差估算有效 bid-ask spread
- **来源**: Roll 1984
- **输入**: close

### A11. 价格重心 (Price Center of Gravity)

- **计算**: sum(close_i × i) / (sum(close_i) × n)，i 为 bar index，归一化到 [0,1]
- **逻辑**: 接近 1 = 价格重心靠后（尾盘拉升），接近 0 = 价格重心靠前（冲高回落）
- **输入**: close

### A12. Hurst 指数（R/S 法）

- **计算**: 将窗口内 return 序列做 R/S 分析，log(R/S) vs log(n) 的斜率
- **逻辑**: H > 0.5 趋势性，H < 0.5 均值回复，H = 0.5 随机游走
- **注意**: njit 内实现需要简化版本（如用固定分段数）
- **输入**: close

### A13. Illiquidity 持续性

- **计算**: 每根 bar 算 mini-Amihud = |r_i| / amount_i，然后算这个序列的自相关系数
- **逻辑**: 非流动性的持续性越高，说明市场微观结构越差
- **输入**: close, amount

### A14. 价格振幅集中度 (Range Concentration)

- **计算**: max(|r_i|) / sum(|r_i|)，类似 volume_concentration 但用于 return
- **逻辑**: 高集中度 = 振幅来自单根 bar 的跳跃；低集中度 = 振幅来自持续波动
- **输入**: close

---

## B 组：需要全天窗口

这些因子需要全天数据或跨时段对比，只能在全天窗口 `0930_1130_1300_1457` 中计算。

### B1. 上午-下午动量差 (APM Factor)

- **计算**: return_AM - return_PM（上午收益 - 下午收益）
- **逻辑**: AM/PM 收益差异刻画机构 vs 散户行为差异，IR 2.89，胜率 80.5%
- **来源**: A股研报
- **输入**: close（需区分上午/下午）

### B2. 分时段动量 (Time-Segmented Momentum)

- **计算**: 将全天拆为 4-6 段，分别算各段 return，加权组合
- **逻辑**: 不同时段有不同的 reversal/momentum 特性，13:00-14:00 反转最强（RankIC 5.99%）
- **来源**: 东吴证券，IR=2.30
- **输入**: close（需按时间段切分）

### B3. 尾盘成交占比 (Closing Volume Ratio)

- **计算**: 最后 15 分钟（14:42-14:57）的 volume / 全天 volume
- **逻辑**: 高尾盘占比 = 散户跟风 = 负面信号，IC 约 -5.65%
- **来源**: 中信建投
- **输入**: volume（需要全天数据来算占比）

### B4. 日内动量 (Intraday Momentum)

- **计算**: 前 30 分钟 return 用于预测最后 30 分钟 return
- **逻辑**: 开盘信息逐步扩散到收盘，Sharpe 0.87-1.73
- **来源**: Gao et al., SSRN
- **输入**: close

### B5. 隔夜缺口回补率 (Overnight Gap Fill Ratio)

- **计算**: overnight_gap = open_0930 - close_prev，intraday_fill = close_1457 - open_0930
  - fill_ratio = -intraday_fill / overnight_gap（若 gap ≠ 0）
- **逻辑**: 缺口回补率高 = 隔夜信息被市场消化/反转
- **输入**: close（需要当天第一根和最后一根 bar）
- **注意**: 还需要前一天的收盘价，当前框架单日计算，可用当天第一根 bar 的 open 近似

### B6. 最高价出现时间 (High Time)

- **计算**: 日内最高价出现在第几根 bar / 总 bar 数，归一化到 [0,1]
- **逻辑**: 靠近 0 = 冲高回落，靠近 1 = 尾盘拉升，刻画资金行为模式
- **输入**: high

### B7. 上午-下午成交量熵差 (Volume Entropy Gradient)

- **计算**: entropy_AM - entropy_PM
- **逻辑**: 上下午交易模式变化的非对称性
- **输入**: volume（需拆上下午分别算）

### B8. 时段成交量比 (Time-Segment Volume Ratio)

- **计算**: 特定时段（如 10:00-11:00）volume / 全天 volume
- **逻辑**: 10-11点成交占比正 IC (~0.040)，尾盘占比负 IC (~-0.057)
- **来源**: 券商研报
- **输入**: volume

### B9. 价量背离 (Price-Volume Divergence)

- **计算**: 累计 return 曲线和累计 volume 曲线的面积差
- **逻辑**: 量价背离 = 趋势可能反转
- **输入**: close, volume（需要全天序列）

### B10. VPIN (Volume-Synchronized Probability of Informed Trading)

- **计算**: 用 BVC 分类将每根 bar 拆为买卖量，按固定 volume bucket 聚合，计算 |buy-sell| / bucket_size 的移动平均
- **逻辑**: 知情交易概率的高频估计
- **来源**: Easley, López de Prado & O'Hara 2012
- **输入**: open, high, low, close, volume
- **注意**: volume bucket 聚合逻辑较复杂，但可简化为固定 bar 数版本

### B11. 改进反转因子 (Improved Reversal)

- **计算**: 月度 return - overnight return - 首小时 return
- **逻辑**: 剔除隔夜和开盘冲击后的"纯日内反转"更干净，年化 L/S 27.6%
- **来源**: academic
- **输入**: close（需要跨日，可能超出当前单日框架）

---

## 成本对比

| | A 组（子窗口可算） | B 组（全天窗口） |
|--|-------------------|----------------|
| 因子数量 | 14 | 11 |
| 计算窗口 | 可复用 4 个现有窗口 | 仅 0930_1130_1300_1457 |
| 入库成本 | 每窗口 ~50 分钟 | ~50 分钟（1 个窗口） |
| Bundle 策略 | 可按输入字段分组 | 单独一个全天 bundle |

**A 组如果 4 个窗口全做**: 14 factors × 4 windows = 56 fields，约 4 × 50 min = 200 min
**A 组如果只做 1 个窗口**: 14 factors × 1 window = 14 fields，约 50 min
**B 组**: 11 factors × 1 window = 11 fields，约 50 min
