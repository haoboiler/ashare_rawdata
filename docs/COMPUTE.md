# Raw-Data 因子计算指南

> 本文档是 `scripts/compute_rawdata_local.py` 的完整使用说明。
> 所有 Agent 在计算因子值时必须参考本文件。

## 概览

`compute_rawdata_local.py` 从 1m K线数据计算因子值，导出为 pkl 文件，不入库。

三种模式：

| 模式 | 命令 | 速度 | 适用场景 |
|------|------|------|---------|
| 串行 | 默认 | ~30-60 分钟 | 无 Ray 环境时 |
| 快速验证 | `--quick` | ~1-2 分钟 | 100 个 symbol 快速排除 |
| **Ray 加速** | `--use-preload` | **~18 分钟** | 推荐，需先 preload |

另外，脚本现在支持 **内存内 quick-eval 热路径**：
- `--quick-eval`：计算后直接复用共享 `evaluate.py` helper 做 Tier 1 快评
- `--skip-export`：不写 pkl，只输出 quick-eval report
- `--use-preload + --quick-eval`：会复用 preload actor 内缓存的 quick-eval backtest context

如果你要批量比较一组候选，或做多代 mutate → quick-eval → top-K，见 `docs/EVOLVE.md` 和 `scripts/evolve_rawdata.py`。

## Ray 加速模式（推荐）

### 前置条件：启动 Ray head + 预加载数据

只需做一次，Ray head 存活期间不用重跑。

```bash
# 1. 启动 dedicated-user preload Ray（由 gkh_ray 维护）
bash orchestration/start_rawdata_preload_ray_gkh_ray.sh

# 2. 预加载 1m 数据到 Ray 内存（首次较慢，后续同区间默认复用）
cd /home/gkh/claude_tasks/ashare_rawdata
bash orchestration/build_rawdata_preload_gkh_ray.sh --start-date 2020-01-01 --end-date 2023-12-31

# 研究快筛推荐口径：2020-01-01 ~ 2023-12-31 + basic6
bash orchestration/build_rawdata_preload_gkh_ray.sh \
    --start-date 2020-01-01 \
    --end-date 2023-12-31 \
    --field-preset basic6 --symbol-source cache
```

说明：
- 如果同一个 preload actor 已经以相同区间成功加载，重复执行 `--preload` 会**直接复用**
- 如果 actor 正在加载相同区间，命令会**等待已有加载完成**
- preload Ray 当前运行在 `gkh_ray` 用户下的专用 runtime 目录，默认不会写到 `/tmp/ray/ray_current_cluster`
- 普通 researcher 会通过 wrapper 自动 source 的 `orchestration/researcher_runtime_env.sh` 连接 `gkh_ray` preload bridge
- 不要硬编码 `RAY_ADDRESS`
- `--field-preset basic6` 会只 preload `close/open/high/low/volume/amount`
- `--symbol-source cache` 会优先使用当前 symbol cache，和非 preload 的默认 universe 保持一致
- screening preload 当前默认窗口是 `2020-01-01 ~ 2023-12-31`
- 正式 `evaluate_rawdata.py` 截止日仍是 `2024-12-31`，两者不是同一个口径
- 如果你明确确认当前没有 researcher 在用 preload，才允许：

```bash
python scripts/compute_rawdata_local.py --preload --start-date 2020-01-01 --end-date 2023-12-31 --force-preload-rebuild
```

验证 preload 是否存活：
```bash
bash orchestration/status_rawdata_preload_ray_bridge.sh
```

### 计算因子

```bash
cd /home/gkh/claude_tasks/ashare_rawdata

# 全量计算（所有 outputs）
python scripts/compute_rawdata_local.py \
    --formula-file {your_script.py} \
    --use-preload --num-workers 32 \
    -o .claude-output/analysis/{direction}/

# 只算特定 fields（更快）
python scripts/compute_rawdata_local.py \
    --formula-file {your_script.py} \
    --use-preload --num-workers 32 \
    --only-fields smart_money_0930_1030 volume_entropy_0930_1030 \
    -o .claude-output/analysis/{direction}/
```

### 计算后直接 quick-eval（不走外部 evaluate.py）

```bash
cd /home/gkh/claude_tasks/ashare_rawdata

# 热路径：算完后直接在内存里做 Tier 1 快评，不落 pkl
python scripts/compute_rawdata_local.py \
    --formula-file {your_script.py} \
    --use-preload --num-workers 32 \
    --only-fields {field_name} \
    --quick-eval --skip-export \
    --eval-start 2020-01-01 --eval-end 2023-12-31
```

输出：
- 控制台直接打印核心指标（coverage / sharpe_abs / sharpe_long_excess / ir_ls / ic_ls）
- JSON report 落到 `.claude-output/reports/quick_eval/`

说明：
- quick-eval 复用共享 `/home/gkh/claude_tasks/ashare_alpha/backtest/evaluate.py` 的 Tier 1 helper
- 仍建议 shortlist 之后再跑一次标准 `evaluate.py` 完整评估

### 如果 preload actor 失效

Ray head 重启、服务器重启后需要重新 preload：
```bash
bash orchestration/start_rawdata_preload_ray_gkh_ray.sh
bash orchestration/build_rawdata_preload_gkh_ray.sh --start-date 2020-01-01 --end-date 2023-12-31
```

新行为说明：
- 如果命名 actor 存在但**不响应**，默认 `--preload` 会**直接报错并拒绝自动 kill**
- 原因是立即 kill + rebuild 很容易在 50GB object store 上触发二次内存压力，导致新 actor 再次被杀
- 只有在确认**没有其他 researcher 正在使用 preload** 时，才应使用 `--force-preload-rebuild`
- 当前 preload 运行状态会写到：
  - `.claude-tmp/preload/ashare_rawdata_preload_state.json`

当 actor 还在加载时，`--use-preload` 现在会 fail-fast：
- 直接报 `Preload actor is still loading data`
- 不再像以前那样长时间挂住研究员会话

## 串行模式

不需要 Ray，直接运行：

```bash
cd /home/gkh/claude_tasks/ashare_rawdata

# 全量计算（~30-60 分钟）
python scripts/compute_rawdata_local.py \
    --formula-file {your_script.py} \
    -o .claude-output/analysis/{direction}/

# 从 registry 加载已注册 bundle
python scripts/compute_rawdata_local.py \
    --bundle pv_stats_0930_1030 \
    -o .claude-output/analysis/{direction}/
```

## 快速验证模式

100 个随机 symbol，用于快速排除无效因子：

```bash
python scripts/compute_rawdata_local.py \
    --formula-file {your_script.py} \
    --quick \
    -o .claude-output/analysis/{direction}/
```

## 参数一览

| 参数 | 说明 |
|------|------|
| `--formula-file` | 注册脚本路径（含 `build_definition()`） |
| `--bundle` | 从 registry 加载已注册 bundle（与 --formula-file 二选一） |
| `--use-preload` | 使用 Ray 预加载数据（需先 `--preload`） |
| `--preload` | 预加载 1m 数据到 Ray（一次性） |
| `--force-preload-rebuild` | 强制重建 detached preload actor（仅在确认无人使用时） |
| `--num-workers` | Ray worker 数量（默认 32） |
| `--quick` | 100 个随机 symbol 快速验证 |
| `--quick-eval` | 计算后直接做内存内 Tier 1 快评 |
| `--skip-export` | 不导出 pkl（通常和 `--quick-eval` 一起用） |
| `--only-fields` | 只导出指定 output fields |
| `--symbols` | 指定 symbol 列表 |
| `--start-date` | 数据起始日期（默认全量） |
| `-o, --output-dir` | pkl 输出目录 |

quick-eval 相关参数：
- `--eval-start`, `--eval-end`
- `--eval-execution-price-field`
- `--eval-benchmark-index`
- `--eval-post-process-method`
- `--eval-commission-rate`, `--eval-stamp-tax-rate`

## 输出格式

每个 output field 会生成两份文件：
- `{field}.pkl`
- `{field}.meta.json`

其中 pkl 内容：
- `index`: DatetimeIndex (tz=Asia/Shanghai)
- `columns`: symbol codes (str)
- `values`: float64

其中 sidecar metadata 会记录：
- `definition_name`
- `output_name`
- `data_available_at`
- `execution_start_at` / `execution_end_at`

评估时建议走 `python scripts/evaluate_rawdata.py --file {field}.pkl`，wrapper 会优先读取 sidecar 来对齐 raw-data 的 `t_plus_n`。

## Formula 脚本格式

必须包含 `build_definition()` 函数，返回 `AShareRawDataDefinition`。参考：
- `research/basic_rawdata/pv_stats/register_pv_stats_0930_1030.py`
- `research/basic_rawdata/volatility/register_volatility_0930_1030.py`

数据字段说明见 `docs/HFT-DATA-GUIDE.md`。

## Ray 配置

| 参数 | 值 |
|------|-----|
| Ray head 地址 | dedicated-user bridge `127.0.0.1:43680`（由 `orchestration/researcher_runtime_env.sh` 注入） |
| Namespace | `ashare_rawdata_preload` |
| Object store | 200 GB |
| Preload actor | `ashare_rawdata_preload` |
| temp dir | `/home/gkh_ray/rp` |
| 预加载数据量 | screening 口径推荐 `2020-01-01 ~ 2023-12-31 + basic6` |
