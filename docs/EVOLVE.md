# Raw-Data Evolve Driver

> 本文档说明 `scripts/evolve_rawdata.py` 的用途、边界和基本用法。

## 什么时候用

适合：
- 你已经有一批 raw-data 候选，想批量跑 `compute + quick-eval + 排名`
- 你想做多轮 mutation / top-K 保留，但不想每次手工敲命令
- 你想复用当前 `--use-preload` 热路径，把候选探索做成一个稳定 driver

不适合：
- 只算 1 个 raw-data：直接用 `scripts/compute_rawdata_local.py`
- 只做正式评估：直接用 `scripts/evaluate_rawdata.py`
- shortlist 之后的最终落盘和完整评估：还是回到 `compute_rawdata_local.py` + `evaluate_rawdata.py`

一句话：`evolve_rawdata.py` 是探索 driver，不是最终生产入口。

## 快筛策略（强制）

- 快筛必须保留**全市场横截面**
- 快筛**禁止**使用小股票池抽样（如 `--symbols`、`--quick --quick-size N`）
- 快筛允许缩短时间窗，但评估窗口至少要有 **2 年**
- 当前默认快筛窗口是 `2020-01-01` 到 `2023-12-31`
- 当前默认 field preset 是 `basic6`：`close/open/high/low/volume/amount`
- 正式 `evaluate_rawdata.py` 的截止日仍是 `2024-12-31`；不要把 screening 快筛窗口和 formal evaluate 截止日混用

这样做的原因是：缩短时间窗主要牺牲的是跨阶段稳定性检验；缩小股票池则会直接引入 universe bias，扭曲行业结构、流动性分布和容量判断。

## 设计边界

它不会自己实现第二套 compute/backtest 逻辑，而是直接复用：
- `scripts/compute_rawdata_local.py` 的 compute
- `scripts/compute_rawdata_local.py` 的 in-memory quick-eval
- `scripts/evaluate_rawdata.py` 作为 shortlist 之后的正式评估入口

这保证 evolve 用的口径和你平时单独跑 raw-data 的口径尽量一致。

## 产出

每次 run 会在 `.claude-output/evolve/{run_name or timestamp}/` 下写：
- `run_manifest.json`
- `summary.json`
- `generations/generation_000/leaderboard.csv`
- `generations/generation_000/field_scores.csv`
- 每个 candidate 的 `definition.json`
- 每个 candidate 的 quick-eval report

排序默认按：
- `score_metric=sharpe_abs_net`
- `score_transform=abs`

也就是默认按“绝对值后的 LS Sharpe”排，负号强的因子也会被保留下来，后续可以再决定是否翻符号。

## 模式一：固定候选批量跑

适合你已经写好了几个注册脚本，只想批量比较。

```bash
python scripts/evolve_rawdata.py \
  --formula-file research/basic_rawdata/variance_ratio/register_variance_ratio_0930_1030.py \
  --formula-file research/basic_rawdata/pv_stats/register_pv_stats_0930_1030.py \
  --use-preload --num-workers 32 \
  --eval-start 2020-01-01 --eval-end 2023-12-31
```

如果只是先 smoke 一下：

```bash
python scripts/evolve_rawdata.py \
  --formula-file research/basic_rawdata/variance_ratio/register_variance_ratio_0930_1030.py \
  --formula-file research/basic_rawdata/pv_stats/register_pv_stats_0930_1030.py \
  --fast --num-workers 16 \
  --start-date 2020-01-01 --end-date 2023-12-31 \
  --eval-start 2020-01-01 --eval-end 2023-12-31
```

## 模式二：generator 驱动的多代 evolve

适合你想把 mutation 逻辑放到单独模块里，让 driver 负责执行循环。

```bash
python scripts/evolve_rawdata.py \
  --generator-file my_generator.py \
  --seed-formula-file research/basic_rawdata/variance_ratio/register_variance_ratio_0930_1030.py \
  --generations 5 \
  --population-size 12 \
  --top-k 4 \
  --use-preload --num-workers 32
```

### generator 接口

`my_generator.py` 里定义：

```python
def generate_candidates(seed_definition, generation, parents, rng, population_size):
    ...
    return candidates
```

driver 只会传入你的函数真正声明过的参数，所以可以只收你需要的那几个。

返回值支持两种：

1. 直接返回 `AShareRawDataDefinition`
2. 返回 dict

```python
{
    "label": "candidate_alias",
    "definition": definition,
    "metadata": {"note": "optional"},
    "only_fields": ["field_a", "field_b"],  # optional
}
```

`parents` 是上一代 top-K 的结果，里面至少会带：
- `candidate_label`
- `candidate_name`
- `fitness`
- `best_field`
- `definition`
- `field_rows`

所以 generator 可以直接基于上一代胜者继续变异。

## 常用参数

| 参数 | 说明 |
|------|------|
| `--use-preload` | 推荐，直接复用 preload actor |
| `--fast` | 不用 preload 的 Ray 模式 |
| `--field-preset` | 快筛默认 `basic6`，更接近同事那套轻量 preload 口径 |
| `--start-date/--end-date` | 非 preload 模式下的计算窗口，至少 2 年 |
| `--eval-start/--eval-end` | 快筛评估窗口，至少 2 年 |
| `--score-metric` | 排名指标，比如 `sharpe_abs_net` / `sharpe_long_excess_net` / `ir_ls` |
| `--score-transform raw/abs` | 是否按绝对值排名 |
| `--top-k` | 每代保留多少候选 |
| `--only-fields` | 只看指定 output fields |

## 推荐工作流

1. 先用全市场 + 2 年窗口跑一轮轻量 smoke，确认 generator/候选没有明显坏掉
2. 再切到 `--use-preload` 跑全市场热启动 evolve
3. 从 leaderboard 里挑 shortlist
4. 对 shortlist 单独跑：
   - `scripts/compute_rawdata_local.py`
   - `scripts/evaluate_rawdata.py`
   - `scripts/admission_corr_check.py`

## 当前限制

- 这是第一版 driver，重点是把“执行循环”稳定下来，不是把 mutation 策略写死
- shortlist 导出 pkl / 正式 evaluate 仍建议单独跑，不建议把所有重流程都塞进 evolve 热路径
- 如果 preload actor 重启了，需要先重新 `python scripts/compute_rawdata_local.py --preload`
- 如果想让 2-4 年快筛整体更快，最好单独准备一个 `2020-01-01 ~ 2023-12-31 + basic6` 的 preload actor；只缩短 `eval-start/end` 不一定明显降低 compute wall time
- 当前不支持把快筛阶段裁掉的 symbols 自动“拼回”正式结果；shortlist 必须重新跑一次正式 compute / evaluate
