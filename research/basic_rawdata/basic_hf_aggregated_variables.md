# 基础高频聚合 Raw-Data Variables 设计文档

> 状态：第一批已完成入库
> 创建日期：2026-03-18
> 最后更新：2026-03-19

## 1. 数据源概览

### 1.1 1m K线数据（主要输入）

- **Library**: `ashare@live@stock@kline@1m`
- **覆盖范围**: 5191 个 symbol，2020-01-02 起
- **每日 bar 数**: 240 根（09:30-11:30 120 根, 13:00-15:00 120 根）

可用字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `open` | float64 | 后复权开盘价 |
| `high` | float64 | 后复权最高价 |
| `low` | float64 | 后复权最低价 |
| `close` | float64 | 后复权收盘价 |
| `volume` | float64 | 成交量（股） |
| `amount` | float64 | 成交额（元） |
| `origin_open` | float64 | 未复权开盘价 |
| `origin_high` | float64 | 未复权最高价 |
| `origin_low` | float64 | 未复权最低价 |
| `origin_close` | float64 | 未复权收盘价 |

### 1.2 日线数据（辅助参考）

- **Library**: `ashare@live@stock@kline@1d`
- **字段**: 与 1m 相同的 OHLCVA + origin 系列
- **已知问题**: 近期日期的日线 high/low 可能仅反映上午数据（日线数据源更新时序问题），导致下午窗口的 twap/vwap 验证时出现越界。非计算错误。
- **框架限制**: `AShareRawDataDefinition` 仅支持 1m 输入，日线数据无法直接在 formula 中引用

---

## 2. Variable 清单

### 2.1 价格波动类（归入 volatility bundle）

| Variable | 输入字段 | 公式 | 说明 |
|----------|----------|------|------|
| `price_std` | close | `std(close)` | 窗口内收盘价标准差 |
| `return_std` | close | `std(log_returns)` | 1min log return 标准差 |
| `realized_vol` | close | `sqrt(sum(r²))` | 已实现波动率 |
| `upside_vol` | close | `sqrt(sum(r² where r>0))` | 上行波动率 |
| `downside_vol` | close | `sqrt(sum(r² where r<0))` | 下行波动率 |
| `vol_asymmetry` | close | `upside_vol - downside_vol` | 波动率不对称性 |
| `parkinson_vol` | high, low | `sqrt(sum(ln(H/L)²) / (4*n*ln2))` | Parkinson 波动率 |
| `garman_klass_vol` | open, high, low, close | GK formula | Garman-Klass 波动率 |
| `price_range` | high, low | `(max(high) - min(low)) / mean(close)` | 归一化价格振幅 |
| `bar_avg_range` | high, low, close | `mean((H-L)/C)` | 每根 bar 平均振幅 |

### 2.2 收益分布类（归入 volatility bundle）

| Variable | 输入字段 | 公式 | 说明 |
|----------|----------|------|------|
| `window_return` | close | `last_close / first_close - 1` | 窗口收益率 |
| `return_skew` | close | `skewness(log_returns)` | 收益率偏度 |
| `return_kurt` | close | `kurtosis(log_returns)` | 收益率峰度（excess kurtosis） |
| `max_return` | close | `max(log_returns)` | 最大单 bar 涨幅 |
| `min_return` | close | `min(log_returns)` | 最大单 bar 跌幅 |
| `max_drawdown` | close | 最大回撤 | 窗口内最大累计回撤 |

### 2.3 微观结构类（归入 volatility bundle）

| Variable | 输入字段 | 公式 | 说明 |
|----------|----------|------|------|
| `trend_strength` | close | `\|cum_return\| / sum(\|bar_return\|)` | 趋势强度（1=单边, 0=震荡） |
| `autocorr_1` | close | `autocorr(returns, lag=1)` | 收益率一阶自相关 |
| `sign_change_ratio` | close | 连续 return 符号交替频率 | 方向切换率 |
| `close_position` | open, high, low, close | `mean((C-L)/(H-L))` | 收盘价在 bar 范围内位置 |

### 2.4 量价关系类（归入 pv_stats bundle）

| Variable | 输入字段 | 公式 | 说明 |
|----------|----------|------|------|
| `twap` | close | `mean(close)` | 时间加权平均价 |
| `vwap` | close, volume | `sum(close*vol) / sum(vol)` | 成交量加权平均价 |
| `amihud` | close, amount | `mean(\|r\| / amount)` | Amihud 非流动性指标 |
| `price_volume_corr` | close, volume | `corr(close, volume)` | 价量相关系数 |
| `return_volume_corr` | close, volume | `corr(returns, volume)` | 收益-成交量相关系数 |
| `volume_imbalance` | close, volume | `sum(vol where r>0) / sum(vol) - 0.5` | 量的多空不平衡 |
| `amount_imbalance` | close, amount | `sum(amt where r>0) / sum(amt) - 0.5` | 额的多空不平衡 |
| `vwap_deviation` | close, volume | `(vwap - twap) / twap` | VWAP 相对 TWAP 偏离 |
| `kyle_lambda` | close, volume | `regression(\|Δprice\|, volume)` 斜率 | 价格冲击系数 |

### 2.5 成交量/额统计类（归入 pv_stats bundle）

| Variable | 输入字段 | 公式 | 说明 |
|----------|----------|------|------|
| `volume_std` | volume | `std(volume)` | 成交量标准差 |
| `volume_cv` | volume | `std(volume) / mean(volume)` | 成交量变异系数 |
| `volume_skew` | volume | `skewness(volume)` | 成交量偏度 |
| `volume_concentration` | volume | `max(volume) / sum(volume)` | 最大单 bar 成交量占比 |
| `volume_trend` | volume | `corr(bar_index, volume)` | 成交量时间趋势 |
| `amount_cv` | amount | `std(amount) / mean(amount)` | 成交额变异系数 |

---

## 3. 分组打包策略

两个 Bundle 类型，每个覆盖 4 个时间窗口，共 **8 个 Bundle、140 个 field**。

### Bundle 类型

| Bundle | 输入字段 | 每窗口 outputs |
|--------|---------|---------------|
| `volatility_{window}` | open, high, low, close | 20 |
| `pv_stats_{window}` | close, volume, amount | 15 |

### 时间窗口

| 窗口 | time_filter | expected_bars | slot | data_available_at | exec window |
|------|-------------|---------------|------|-------------------|-------------|
| `0930_1030` | 09:30-10:30 | 40 | midday | 1031 | 930-1030 |
| `0930_1130` | 09:30-11:30 | 80 | midday | 1131 | 930-1130 |
| `1300_1400` | 13:00-14:00 | 40 | evening | 1401 | 1300-1400 |
| `0930_1130_1300_1457` | 09:30-11:30 + 13:00-14:57 | 157 | evening | 1458 | 930-1457 |

**设计决策说明**:
- **expected_bars 取 2/3**：实盘 1m 数据可能缺少 1-2 根 bar，阈值设为窗口 bar 数的 2/3，低于此跳过该天（跳过的 cell 为 NaN，不影响 DataFrame 对齐）
- **收盘集合竞价排除**：A 股 14:57-15:00 为收盘集合竞价，数据特征与连续竞价不同，全天窗口截止到 14:57
- **两段式命名**：全天窗口用 `0930_1130_1300_1457` 而非 `0930_1500`，准确反映两段交易时间

---

## 4. 已入库 Bundle 一览

| Bundle | Fields | 入库日期 | 验证状态 |
|--------|--------|---------|---------|
| `pv_stats_0930_1030` | 15 | 2026-03-18 | ✓ 已验证 |
| `pv_stats_0930_1130` | 15 | 2026-03-18 | ✓ 已验证 |
| `pv_stats_1300_1400` | 15 | 2026-03-18 | ✓ 已验证 |
| `pv_stats_0930_1130_1300_1457` | 15 | 2026-03-18 | ✓ 已验证 |
| `volatility_0930_1030` | 20 | 2026-03-18 | ✓ 已验证 |
| `volatility_0930_1130` | 20 | 2026-03-18 | ✓ 已验证 |
| `volatility_1300_1400` | 20 | 2026-03-18 | ✓ 已验证 |
| `volatility_0930_1130_1300_1457` | 20 | 2026-03-18 | ✓ 已验证 |

**数据质量总结**:
- 零 inf/-inf
- 覆盖率 ≥ 98.85%（corr 类因方差为零时无法计算，缺失合理）
- twap/vwap 与 v1 版本 100% 精确一致
- 价格范围越界极少（上午窗口 < 0.001%），下午/全天窗口越界略多但已确认为日线数据源更新时序问题

---

## 5. 涨跌停标记（Pending）

需要日线数据（前收盘价）来计算涨跌停价，当前框架不支持混合日线输入。暂不实现。

---

## 6. 目录结构

```
research/basic_rawdata/
├── basic_hf_aggregated_variables.md     # 本文档
├── pv_stats/
│   ├── register_pv_stats_0930_1030.py
│   ├── register_pv_stats_0930_1130.py
│   ├── register_pv_stats_1300_1400.py
│   ├── register_pv_stats_0930_1130_1300_1457.py
│   └── validation_pv_stats_0930_1030.md
└── volatility/
    ├── register_volatility_0930_1030.py
    ├── register_volatility_0930_1130.py
    ├── register_volatility_1300_1400.py
    └── register_volatility_0930_1130_1300_1457.py

scripts/
└── validate-rawdata/
    ├── validate_rawdata_bundle.py        # 验证工具函数
    └── validation_guide.md               # 验证指南
```

---

## 7. 后续计划

1. **更多时间窗口**: 尾盘 14:00-14:57 等
2. **涨跌停标记**: 待框架支持日线辅助输入或独立 pipeline
3. **framework 改进**: field 级别 tag（当前 execution window 在 bundle 级别，twap/vwap 和非价格 field 共享同一设置）
4. **每日增量更新**: 接入定时任务自动更新
