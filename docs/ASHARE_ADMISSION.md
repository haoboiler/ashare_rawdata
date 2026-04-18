# AShare RawData Admission Guide

本文档面向 agent，说明在当前新版本架构下，如何把一个新的 A 股 generated rawdata 接入系统。

这里的“新版本”指：

- 定义存在 registry，而不是硬编码在老的聚合脚本里
- 公式以 `formula string + numba` 形式注册
- 底层输入仍然来自 `ashare@live@stock@kline@1m`
- 正式输出统一写入 `ashare@live@stock@raw_value@1d`
- 更新器采用 `symbol chunk -> staging -> canonical publish`

典型例子：

- `twap_0930_1030_v1`
- `vwap_0930_1030_v1`
- 一个函数同时产出多个同窗口字段

## 1. 先记住现在的架构

> **迁移提示**（2026-03-18 起）：生产 rawdata 包已从 `ashare_hf_variable`
> 迁到 `casimir.core.ashare_rawdata`。旧包 `/home/gkh/ashare/ashare_hf_variable/`
> 是 dead code，**不要再改它**，改动也不会影响 cron。所有 import 都用
> `from casimir.core.ashare_rawdata import …`，CLI 用
> `/home/gkh/ashare/ashare_update/scripts/aggregate/update_ashare_rawdata.py`。

### 1.1 输入、定义、输出分别在哪里

- canonical source raw:
  - `ashare@live@stock@kline@1m`
- generated rawdata registry:
  - `casimir.core.ashare_rawdata` 包（在 `casimir_ashare` 仓库中）
  - 当前默认 registry backend 可以是 JSON fallback，也可以是 Mongo
- canonical generated rawdata:
  - `ashare@live@stock@raw_value@1d`
- staging library:
  - `ashare@live@stock@raw_value_staging@1d`

### 1.2 物理形状

- `ashare@live@stock@kline@1m` 是 `per-symbol`
  - `symbol = 股票代码`
  - `columns = open/high/low/close/volume/...`
- `ashare@live@stock@raw_value@1d` 是 `per-field`
  - `symbol = 字段名`
  - `columns = 股票代码`
  - `index = trade date`

### 1.3 读路径

`casimir_ashare` 现在会优先把 `ashare@live@stock@raw_value@1d` 当作 daily raw source，所以：

- 试验字段建议先加 `_v1`
- 不要一开始就覆盖 legacy 同名字段

相关代码：

- `/home/gkh/ashare/casimir_ashare/casimir/core/ashare_rawdata/updater.py`
- `/home/gkh/ashare/ashare_update/scripts/aggregate/update_ashare_rawdata.py`（生产 CLI 入口）
- `/home/gkh/ashare/casimir_ashare/casimir/core/market/ashare.py`

## 2. 什么时候适合做成 generated rawdata

适合的字段通常满足：

- 输入只依赖单只股票的 `1m` raw
- 输出是日度矩阵
- 下游会频繁通过 `get_raw_value()` 读取
- 可以明确写出 `data_available_at`
- 可以明确写出输入时间窗，例如 `09:30-10:30`

适合例子：

- `twap_0930_1030`
- `vwap_0930_1030`
- `sum_amount_0930_1000`
- `ret_0945_1105`

不适合直接走这套 admission 的：

- 长表结果
- cross-sectional 依赖很重的字段
- 不是 daily 输出的字段
- 还没有稳定 source raw 的字段

## 3. admission 前必须先定好的 8 件事

### 3.1 字段名

规则：

- 全小写
- ASCII only
- 时间窗用 `HHMM_HHMM`
- 试验版先加 `_v1`

推荐：

- `twap_0930_1030_v1`
- `vwap_0930_1030_v1`

不要用：

- `twap-0930-1030`
- `TWAP_0930_1030`

### 3.2 slot

只能选：

- `midday`
- `evening`
- `full`

规则：

- 只依赖上午窗口的字段，通常放 `midday`
- 涉及下午窗口的字段，放 `evening`
- 首次全量回填用 `full-history` 命令，不是新建一个 slot

### 3.3 `data_available_at`

必须人工填写，不做自动推导。

例子：

- `09:30-10:30` 窗口的字段，通常写 `1030`
- `13:00-14:00` 窗口的字段，通常写 `1400`

### 3.4 `execution_start_at` / `execution_end_at`

如果这个字段是执行价或 close-family 字段，就明确填写。

如果不是执行价字段，可以都设成 `null`。

当前版本不再使用：

- `timing_tag`
- `close_tag`

### 3.5 `input_time_filter`

这是 admission 里最关键的参数之一。它决定传入公式函数的 `1m` 数据时间范围。

例如：

```yaml
params:
  input_time_filter:
    - ["09:30", "10:30"]
```

表示：

- 每个交易日只把 `09:30 <= t < 10:30` 的 `1m` bar 传给函数

如果要上午和下午两段一起传：

```yaml
params:
  input_time_filter:
    - ["09:30", "11:30"]
    - ["13:00", "15:00"]
```

### 3.6 `expected_bars`

如果要求完整窗口，就明确写。

例子：

- `09:30-10:30` 写 `60`
- `13:00-14:00` 写 `60`
- `09:45-11:05` 写 `80`

默认逻辑是：

- `completeness_policy = strict_full_window`
- 不足 `expected_bars` 就跳过该日，不写半成品

### 3.7 `price_basis`

常见取值：

- `hfq`
- `origin`

规则：

- 因子研究和日度对齐，通常用 `hfq`
- 更接近真实成交价的口径，才考虑 `origin`

### 3.8 `history_days` / `pad_mode` / `max_bars`（历史窗口字段）

默认都不用管 —— `history_days=0`，`pad_mode="none"`，公式签名还是 `apply_func(inputs)`，`inputs[i]` 是当日 1D 分钟数组。

如果字段计算需要**过去 N 日历史**（N ≤ 25），就设：

```python
history_days=20,               # 过去 20 天 + 当天 = 21 行
pad_mode="slot_aligned",       # 或 "packed"
max_bars=240,                  # slot_aligned 必须等于 input_time_filter 的总分钟数
```

此时框架给公式传的 `inputs[i]` 是 `(history_days+1, max_bars)` 的 2D numpy，行 0 最老，行 N 当天；缺失 bar 是 `NaN`。历史天里 invalid（bar 不足 `expected_bars`）整行填 NaN，但不跳过目标日 —— 公式自己按最小有效天数判断；当日 invalid 则跳过整个目标日。

`pad_mode` 两个合法值：

| 值 | 语义 | 何时用 |
|---|---|---|
| `packed` | 有效 bar 压到前排，末尾 NaN 补齐 | 日内顺序/累积算法（cummax、cumsum），不关心 slot 对齐 |
| `slot_aligned` | 按分钟 slot 索引填位置，缺位 NaN | 跨日同分钟 slot 聚合（例如过去 20 日同一 slot 的 amount 均值/方差） |

约束：
- `history_days > 0` → `pad_mode` 必须是 `packed` / `slot_aligned`（不能 `none`）
- `pad_mode="slot_aligned"` → 必须有 `input_time_filter`，且 `max_bars` == window 的理论 bar 数
- `history_days > 0` 时**不允许** `daily_input_names`（两套契约尚未合并）

参考实现：

- `research/basic_rawdata/hf_pv_corr_illiq_20d/register_hf_pv_corr_illiq_20d.py`（`history_days=20`，`slot_aligned`）
- `research/basic_rawdata/hf_longshort_battle/register_hf_longshort_battle.py`（`history_days=0`，`none`）

### 3.9 是否需要一个函数产出多个字段

如果多个字段：

- 共享同一个输入窗口
- 共享同一个 source raw
- 共享同一个 slot

那么推荐用一个函数一起产出。

例如：

- `twap_0930_1030_v1`
- `vwap_0930_1030_v1`

就应该用一个 definition，一次扫描 minute bars，同时返回两个输出。

## 4. 公式函数必须满足什么要求

当前版本是 crypto 同构模式：

- registry 里存 `formula` 字符串
- 入库前要通过 numba 校验
- 执行时由 updater 编译后调用

### 4.1 scope 里默认已有这些名字

formula string 里可以直接使用：

- `np`
- `njit`
- `prange`

所以通常不需要自己写：

```python
import numpy as np
from numba import njit
```

### 4.2 固定函数签名

推荐固定成：

```python
@njit
def apply_func(inputs):
    ...
    return np.array([...], dtype=np.float64)
```

其中：

- `inputs` 是 tuple
- `inputs[i]` 对应 `input_names[i]`
- 返回值长度必须等于 `output_names`

### 4.3 一个最小例子

```python
@njit
def apply_func(inputs):
    close = inputs[0]

    if close.size == 0:
        return np.array([np.nan], dtype=np.float64)

    return np.array([np.nanmean(close)], dtype=np.float64)
```

### 4.4 一个双输出例子

```python
@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]

    twap = np.nan
    vwap = np.nan

    if close.size == 0:
        return np.array([twap, vwap], dtype=np.float64)

    twap = np.nanmean(close)

    weighted_sum = 0.0
    volume_sum = 0.0
    for i in range(close.size):
        c = close[i]
        v = volume[i]
        if np.isnan(c) or np.isnan(v):
            continue
        weighted_sum += c * v
        volume_sum += v

    if volume_sum > 0.0:
        vwap = weighted_sum / volume_sum

    return np.array([twap, vwap], dtype=np.float64)
```

## 5. 标准 admission 流程

### 5.1 写一个注册脚本

推荐把 admission 脚本放在：

- `/home/gkh/claude_tasks/ashare_rawdata/research/`

不要一开始就改生产 registry 文件。

可以参考现成例子：

- `/home/gkh/claude_tasks/ashare_rawdata/research/register_pilot_twap_vwap_0930_1030_v1.py`

### 5.2 在脚本里构造 definition

最小模板如下：

```python
from casimir.core.ashare_rawdata.models import AShareRawDataDefinition, RawDataParams, RawDataSlot
from casimir.core.ashare_rawdata.registry import upsert_definition

definition = AShareRawDataDefinition(
    name="pilot_twap_vwap_0930_1030_v1",
    formula=FORMULA_STRING,
    func_name="apply_func",
    input_names=["close", "volume"],
    output_names=["twap_0930_1030_v1", "vwap_0930_1030_v1"],
    params=RawDataParams(input_time_filter=[("09:30", "10:30")]),
    slot=RawDataSlot.MIDDAY,
    data_available_at=1030,
    execution_start_at=None,
    execution_end_at=None,
    expected_bars=60,
    description="Pilot bundle for 09:30-10:30 TWAP/VWAP.",
)
```

### 5.3 默认先 `print-json`

脚本默认应该先把 definition 打印出来供检查。

这是 admission 前的第一步。

### 5.4 注册到 registry

Python 必须使用：

```bash
/home/b0qi/anaconda3/envs/gkh-ashare/bin/python
```

注册命令示例：

```bash
/home/b0qi/anaconda3/envs/gkh-ashare/bin/python \
  /home/gkh/claude_tasks/ashare_rawdata/research/register_pilot_twap_vwap_0930_1030_v1.py \
  --register
```

如果只是先跳过校验入库：

```bash
... --register --skip-validate
```

但正常 admission 不建议跳过校验。

## 6. 更新器怎么跑

入口脚本：

- `/home/gkh/ashare/ashare_update/scripts/aggregate/update_ashare_rawdata.py`

### 6.1 小范围 smoke run

先跑少量 symbol，确认：

- registry 可读
- numba 编译正常
- staging / publish 正常
- 值写到了 `raw_value@1d`

例如：

```bash
/home/b0qi/anaconda3/envs/gkh-ashare/bin/python \
  /home/gkh/ashare/ashare_update/scripts/aggregate/update_ashare_rawdata.py \
  --slot midday \
  --fields pilot_twap_vwap_0930_1030_v1 \
  --symbols 000001.SZ 000002.SZ 000004.SZ 000006.SZ \
  --num-days 30 \
  --batch-size 2 \
  --max-workers 2
```

### 6.2 全量回填

确认 smoke run 正常后，再跑全市场全历史：

```bash
/home/b0qi/anaconda3/envs/gkh-ashare/bin/python \
  /home/gkh/ashare/ashare_update/scripts/aggregate/update_ashare_rawdata.py \
  --slot midday \
  --fields pilot_twap_vwap_0930_1030_v1 \
  --full-history \
  --batch-size 100 \
  --max-workers 4
```

### 6.3 常用参数说明

- `--fields`
  - 传 definition `name`，不是 output field name
- `--symbols`
  - 只更新指定股票
- `--num-days`
  - 增量更新时读取最近一段自然日
- `--full-history`
  - 全历史回填
- `--batch-size`
  - 每个 symbol chunk 的大小
- `--max-workers`
  - 外层并行 worker 数
- `--run-id`
  - 手工指定本次运行的 staging run id
- `--keep-staging`
  - 保留 staging 分片，方便排障

## 7. 更新器的发布语义

这是新版最容易搞错的地方。

### 7.1 不是边算边写正式字段

更新器流程是：

1. 按 symbol chunk 并行计算
2. 每个 chunk 先写 `staging library`
3. 所有 chunk 成功后，才 publish 到 `ashare@live@stock@raw_value@1d`

### 7.2 为什么这么设计

为了避免：

- 一半 symbol 已写，一半还没写
- 下游读到半成品 canonical field
- 中断后正式字段变脏

### 7.3 publish 的 gate

只要出现下面任意一种情况，就不发布 canonical field：

- `failed_chunks > 0`
- `failed_symbols > 0`

这意味着：

- staging 里可能有分片
- 但正式字段不会被更新

### 7.4 full-history 和 incremental 的区别

- `full-history`
  - 正式字段走 `replace`
  - 用完整新矩阵替换旧矩阵
- `incremental`
  - 正式字段走宽表 merge
  - 只覆盖这次更新的日期和 symbol
  - 未触达的旧 symbol 列会保留

## 8. admission 之后如何验证

### 8.1 看 raw_value 库里有没有正式字段

```python
import arcticdb

ac = arcticdb.Arctic("s3://192.168.2.180:arctic?access=bookdisco&secret=bookdiscono1&port=8122")
lib = ac.get_library("ashare@live@stock@raw_value@1d", create_if_missing=False)
print("twap_0930_1030_v1" in lib.list_symbols())
```

### 8.2 看实际形状

```python
df = lib.read("twap_0930_1030_v1").data
print(df.shape)
print(df.index.min(), df.index.max())
```

### 8.3 用 provider 回读

用 `AShareProvider` 或 `get_raw_value()` 回读，确认下游能拿到。

### 8.4 如果有 legacy 同名字段，就做值对比

当前例子里已有 compare 脚本：

- `/home/gkh/claude_tasks/ashare_rawdata/research/compare_pilot_twap_vwap_0930_1030_v1.py`

原则：

- 先用 `_v1` 名称跑新版本
- 和 legacy 字段比值
- 确认一致后，再考虑切正式名字

## 9. agent admission checklist

每次 admission 前，agent 都应逐项确认：

- 字段命名是否规范
- `slot` 是否正确
- `data_available_at` 是否人工填写正确
- `execution_*` 是否需要填写
- `input_time_filter` 是否正确
- `expected_bars` 是否正确
- `price_basis` 是否明确
- `formula` 是否符合 numba 约束
- `output_names` 数量是否和返回向量长度一致
- 是否先用 `_v1` 名称灰度
- 是否先做小范围 smoke run
- 是否在全量回填前完成值校验

## 10. 当前推荐的 admission 策略

对一个新字段，推荐顺序固定如下：

1. 先写 research 注册脚本
2. `print-json` 自查 metadata
3. 正常校验后入 registry
4. 跑少量 symbol 的 smoke run
5. 检查 `raw_value@1d`
6. 如果有 legacy 字段，做 compare
7. 再跑全市场全历史
8. 确认稳定后，再决定是否去掉 `_v1`

一句话总结：

- A 股 rawdata admission 现在不是“去老聚合脚本里加一个 field”
- 而是“注册一个 numba formula definition，然后通过并行 staging/publish updater 生成 canonical raw_value 字段”
