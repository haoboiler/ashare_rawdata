# Crypto HF Variable 迁移审计

> 审计日期: 2026-03-31
> 来源: `/home/gkh/bp_data/data_project/` (crypto HF variables by zhusm)
> 目标: 从 crypto 已有因子库中筛选可用 A 股 1m OHLCV 实现的方向

## 一、Crypto HF 因子库全貌

Crypto 因子库共 **36 个 HF variable groups**，产出 **370 个变量**，存储在 `binance@futures@hf_value@15m`。

### 1.1 按数据源分类

| 数据源 | 字段 | Groups | 总变量数 | A 股可用性 |
|--------|------|--------|----------|-----------|
| `norm_book_5` (5 档行情快照) | `bids/asks_[0-4]_price/amount`, `close`, `volume`, `quote_volume`, `funding_rate` | 23 | ~220 | **不可用** — A 股 1m K 线无盘口数据 |
| `trades` (逐笔成交) | `price`, `qty`, `is_buyer_maker`, `quote_qty` | 11 | ~120 | **不可用** — 无逐笔数据，无买卖方向标识 |
| `agg_trades` (聚合成交) | `open`, `close`, `is_buyer_maker`, `quote_qty`, `count`, `qty` | 2 | ~63 | **不可用** — 同上 |

### 1.2 已注册 Groups 清单

#### norm_book_5 类 (23 groups)

| Group | 变量数 | Offset | 核心概念 |
|-------|--------|--------|----------|
| hf_corr | 6 | 1 | 价格-成交量/成交笔数相关性 |
| hf_mom | 7 | 1 | 收益率分布矩 (mean/std/skew/kurt) |
| hf_wspread | 4 | 1 | 5 档加权价差 |
| wbook | 5 | 1 | 加权盘口特征 |
| dbook | 5 | 1 | 盘口深度特征 |
| hf_cv | 9 | 1 | 价格/量变异系数 (std/skew/kurt) |
| hf_rsj | 9 | 1 | 已实现半方差分解 + 趋势效率 |
| hf_ratio | 8 | 1 | 盘口各档价量比率 |
| hf_elatricity_trading | 6 | 1 | 价格弹性 (Δvol/Δprice) |
| hf_soir | 9 | 1 | 堆叠订单不平衡率 (5 档) |
| hf_mpc | 8 | 1 | 中间价变动特征 |
| hf_feph | 4 | 4 | 前瞻性瞬态价格 |
| hf_tide | 3 | 16 | 量潮价格行为 |
| hf_basic_close | 4 | 1 | 基础收盘/中间/量特征 |
| hf_corr_16 | 6 | 16 | 相关性 (4h 窗口) |
| hf_soir_16 | 9 | 16 | SOIR (4h 窗口) |
| hf_bid_ask_imbalance_l1 | 5 | 1 | L1 买卖不平衡 |
| hf_bid_ask_imbalance_l1_debug | 5 | 1 | L1 不平衡 (debug) |
| hf_bid_ask_imbalance_l5 | 8 | 1 | L5 买卖不平衡 |
| hf_orderbookshape_1 | 2 | 4 | 盘口形状 |
| hf_mid_prx_L0 | 2 | 1 | 中间价 L0 |
| hf_fundrate | 3 | 1 | 资金费率 (close/TWAP/std) |
| hf_estimated_quote_volume | 3 | 4 | 估算成交额 |

#### trades 类 (11 groups)

| Group | 变量数 | Offset | 核心概念 |
|-------|--------|--------|----------|
| HCVOL | 1 | 1 | 高于收盘价的买入量占比 |
| LCVOL | 1 | 1 | 低于收盘价的卖出量占比 |
| HCP | 1 | 1 | 高于收盘价买入的 VWAP |
| LCP | 1 | 1 | 低于收盘价卖出的 VWAP |
| hf_tick_size | 33 | 1 | 逐笔成交大小分布 |
| hf_ohlcv | 34 | 1 | 从 tick 聚合的 OHLCV 微观结构 |
| HCVOL_16 | 1 | 16 | HCVOL (4h 窗口) |
| LCVOL_16 | 1 | 16 | LCVOL (4h 窗口) |
| HCP_16 | 1 | 16 | HCP (4h 窗口) |
| LCP_16 | 1 | 16 | LCP (4h 窗口) |
| hf_trade_zsm001 | 15 | 1 | 量价分布分位数回归 |

#### agg_trades 类 (2 groups)

| Group | 变量数 | Offset | 核心概念 |
|-------|--------|--------|----------|
| hf_taker_tick_size | 35 | 1 | Taker 成交大小分布 |
| hf_taker_orders | 28 | 1 | Taker 订单流特征 |

### 1.3 zsm 系列研究 Notebooks (zsm001-007)

均位于 `/home/gkh/bp_data/data_project/hf_trade_zsm*/`，使用 `trades` 数据源。

| Notebook | 核心概念 | 变量数 | 数据需求 |
|----------|----------|--------|----------|
| zsm001 | 量价分位数函数多项式拟合 | 15 | tick: price, qty, is_buyer_maker, quote_qty |
| zsm002 | 按价格水平聚合的量价分布矩 | 15 | tick: 同上 |
| zsm003 | 成交量 Benford 定律偏离度 | 28 | tick: 同上 |
| zsm004 | 价格变动 regime 条件下的成交笔数 | 24 | tick: 同上 |
| zsm005 | 大单条件分布矩 (regime × buyer/maker) | 76 | tick: 同上 |
| zsm006 | 3 秒子 bar 聚合统计的时序矩 | 24 | tick + datetime |
| zsm007 | 3 秒子 bar 聚合统计的两两相关性 | 42 | tick + datetime |

**结论**: zsm001-007 全部依赖逐笔成交的 `is_buyer_maker` 方向标识和单笔 `qty`/`price`，**无一可从 1m OHLCV 复现**。

## 二、概念层面迁移评估

虽然原始数据源不可用，但部分因子的**核心思想**可以用 1m bar 的 close/volume/amount 近似实现。

### 2.1 逐组评估

#### hf_rsj — 已实现半方差分解 ✅ 可迁移

**原始实现**: 从 bid/ask 加权价格计算 bar 间收益率，分解为上行/下行半方差。

**9 个输出变量**:

| 变量 | 公式 | 迁移可行性 | 与 ashare 已有工作重叠 |
|------|------|-----------|----------------------|
| `ratio_realupvar` | std(ret where ret>0) / std(ret) | ✅ 可算 | **新概念** |
| `ratio_realdownvar` | std(ret where ret<0) / std(ret) | ✅ 可算 | **新概念** |
| `trendratio` | mean(ret) / mean(\|ret\|) | ✅ 可算 | **新概念** (效率比) |
| `vret` | volume-weighted return | ✅ 可算 | **新概念** |
| `illiquidity` | mean(\|ret\| / quote_volume) | ✅ 可算 | ⚠️ = Amihud (已有 48 pending) |
| `ret_h1` | mean(ret of first 15% bars) | ✅ 可算 | ⚠️ ≈ pv_stats 时段分解 |
| `ret_t1` | mean(ret of last 15% bars) | ✅ 可算 | ⚠️ ≈ pv_stats 时段分解 |
| `volume_h1` | sum(vol of first 15% bars) / total | ✅ 可算 | ⚠️ ≈ pv_stats 时段分解 |
| `volume_t1` | sum(vol of last 15% bars) / total | ✅ 可算 | ⚠️ ≈ pv_stats 时段分解 |

**迁移结论**: 聚焦 `ratio_realupvar`, `ratio_realdownvar`, `trendratio`, `vret` 这 4 个新字段。A 股实现: `ret = log(close[i]/close[i-1])` on 1m bars。

#### hf_tide — 量潮价格行为 ✅ 可迁移

**原始实现**: 将 30 秒 bar 按 rolling window 检测成交量高峰，分析量潮上升/下降阶段的价格变化率。

**3 个输出变量**:

| 变量 | 公式 | 物理含义 |
|------|------|----------|
| `cxyz` | 全量潮周期价格变化率 / 持续时间 | 量潮期间整体价格效率 |
| `qscxyz` | 量潮上升期价格变化率 | 放量阶段价格方向 |
| `rscxyz` | 量潮下降期价格变化率 | 缩量阶段价格方向 |

**迁移方案**: 用 1m bar 原生精度替代 30 秒重采样。在日内 ~237 bars 上用 6-bar rolling sum(volume) 检测 peak，向前/后找 trough 划分量潮周期。

#### hf_elatricity_trading — 价格弹性 ⚠️ 部分可迁移

**原始实现**: 在 30 秒和 1 分钟间隔上计算 Δamount/Δprice，取 mean/std/skew。

**迁移限制**: 原版在秒级快照上计算，30 秒变体不可复现。1 分钟变体可直接用 1m bar 实现：`elasticity[i] = Δamount[i] / Δclose[i]`，取日内 mean/std/skew (3 个变量)。

**注意**: 概念上是 Amihud 的逆 (`Δvol/Δprice` vs `|Δprice|/volume`)，需验证相关性。

#### hf_mom — 收益率矩 ❌ 已证伪

7 个变量 (ret mean/std/skew/kurt/max/min/normalized) 全部可从 1m close 计算。

**但**: ashare 项目中 D-015 (return_distribution) 已排除 — 两轮 10 特征全部 Mono 不达标，收益分布形态在截面上呈 U 型非线性关系。**不再重复研究。**

#### hf_cv — 变异系数 ❌ 已证伪

价格 std/skew/kurt = D-015 已排除；volume std/skew/kurt = D-005 (volume_entropy) / D-013 (closing_volume_ratio) 已排除 — 日内成交量分布截面区分度不足。

#### hf_corr — 价格-量相关性 ⚠️ 在研

`corr_pv` (价格-量相关) 和 `corr_rv` (收益-量相关) 可从 1m bar 计算，但 D-017 (pv_concordance) 已被认领，概念高度重叠。

#### HCVOL/LCVOL/HCP/LCP — 方向性成交量 ❌ 不可实现

需要逐笔 `is_buyer_maker` 方向标识，1m OHLCV 无法提供。

### 2.2 汇总矩阵

| Crypto 因子组 | 总变量 | 可迁移 | 新增(去重后) | 状态 |
|---|---|---|---|---|
| hf_rsj | 9 | 9 | **4** (semi-var + trend + vret) | ✅ 待实现 |
| hf_tide | 3 | 3 | **3** | ✅ 待实现 |
| hf_elatricity | 6 | 3 | **3** (需验证与 Amihud 冗余) | ⚠️ 待验证 |
| hf_corr | 6 | 2 | 0 (D-017 在研) | — |
| hf_mom | 7 | 7 | 0 (D-015 已证伪) | ❌ |
| hf_cv | 9 | 4 | 0 (D-005/013/015 已证伪) | ❌ |
| HCVOL 系列 | 4 | 0 | 0 | ❌ |
| zsm001-007 | 224 | 0 | 0 | ❌ |
| 其余 book/tick 类 | ~100 | 0 | 0 | ❌ |
| **合计** | **370** | **28** | **10** | — |

## 三、可执行方向

### D-RSJ: Realized Semi-Variance 分解 (优先级 P0)

**假设**: 日内上行波动占比高的股票，买方力量主导，隐含方向性流动性信息，这一维度与 Amihud (流动性水平) 正交。

**核心字段**:
- `ratio_realupvar`: 上行半方差占总方差比例 → 买方主导度
- `ratio_realdownvar`: 下行半方差占总方差比例 → 卖方主导度
- `trendratio`: 净收益/总绝对收益 → 日内趋势效率
- `vret`: 成交量加权收益 → 放量方向

**实现**: `ret[i] = log(close[i] / close[i-1])` on 全天 1m bars → 分离 ret>0 和 ret<0 分别求 std → 归一化

**预期与 ashare 结论的关系**:
- 与 Amihud 系列 (流动性**水平**) 低相关 — RSJ 衡量流动性**方向性**
- 与 volatility bundle (已注册) 有一定相关 — 但 RSJ 的信息在于 up/down 分解而非总量
- 符合「流动性因子有效」的大结论 (结论 #10, #13, #17)

### D-TIDE: Volume Climax 价格行为 (优先级 P0)

**假设**: 日内成交量存在明显高峰期 (量潮)，高峰前后的价格行为不对称性反映了知情交易者 vs 噪声交易者的博弈结果。

**核心字段**:
- `cxyz`: 量潮全程价格效率
- `qscxyz`: 量潮上升期价格变化率 (放量阶段)
- `rscxyz`: 量潮下降期价格变化率 (缩量阶段)

**实现**: 1m volume → 6-bar rolling sum → 找 peak → 前后 trough 划分三段 → 各段 Δprice/Δtime

**A 股特殊性**: A 股日内成交量有固定 U 型分布 (开盘/收盘活跃)，量潮检测需要去除这一固定模式，否则每只股票的 peak 都在开盘附近，截面区分度消失。

### D-ELAST: 价格弹性 (优先级 P1)

**假设**: 成交额对价格变动的敏感度 (弹性) 是流动性的另一个维度，与 Amihud (价格冲击/成交额) 互补。

**核心字段**:
- `elasticity_mean`: 日内弹性均值
- `elasticity_std`: 日内弹性波动
- `elasticity_skew`: 日内弹性偏度

**实现**: `elast[i] = Δamount[i] / Δclose[i]` per 1m bar → 日内 mean/std/skew

**风险**: 数学上 `Δamount/Δprice` ≈ `1 / (|Δprice|/amount)` ≈ `1/Amihud`，可能与 Amihud 高度相关。需先验证 corr < 0.8 再全面评估。

## 四、不可迁移但有概念启发的方向

以下 crypto 因子虽然数据层面不可复现，但其思路可能启发新的 1m bar 因子设计：

| Crypto 概念 | 启发 | 可能的 1m bar 近似 |
|---|---|---|
| zsm003 Benford 偏离 | 成交量首位数字分布异常 → 人为操纵信号 | 可对 1m bar volume 序列做 Benford 检验 |
| zsm004 Regime 条件统计 | 按价格变动幅度分 regime | 类似 ashare 已有的 regime transition (D-005 变体) |
| zsm006 子 bar 时序矩 | 更细粒度的 bar 内统计 | 我们已有 1m bar 日内矩 (volatility bundle) |
| HCVOL/LCVOL 方向性量 | 价格上方/下方的成交量分布 | 可用 1m bar 的 close vs prev_close 近似方向: 涨 bar 量 vs 跌 bar 量 |

> 注: 「涨 bar 量 vs 跌 bar 量」本质上是 RSJ 中 `vret` 的离散化版本，已包含在 D-RSJ 方向中。
