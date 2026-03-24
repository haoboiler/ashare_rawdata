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

## Ray 加速模式（推荐）

### 前置条件：启动 Ray head + 预加载数据

只需做一次，Ray head 存活期间不用重跑。

```bash
# 1. 启动 Ray head（如果还没启动）
ray start --head --port 26380 --include-dashboard false --object-store-memory 50000000000

# 2. 预加载 1m 数据到 Ray 内存（~3 分钟，5090 symbols）
cd /home/gkh/claude_tasks/ashare_rawdata
python scripts/compute_rawdata_local.py --preload --start-date 2020-01-01
```

验证 preload 是否存活：
```bash
python -c "
import ray
ray.init(address='192.168.0.107:26380', namespace='ashare_rawdata')
store = ray.get_actor('ashare_rawdata_preload', namespace='ashare_rawdata')
print(ray.get(store.get_stats.remote()))
"
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

### 如果 preload actor 失效

Ray head 重启、服务器重启后需要重新 preload：
```bash
ray start --head --port 26380 --include-dashboard false --object-store-memory 50000000000
python scripts/compute_rawdata_local.py --preload --start-date 2020-01-01
```

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
| `--num-workers` | Ray worker 数量（默认 32） |
| `--quick` | 100 个随机 symbol 快速验证 |
| `--only-fields` | 只导出指定 output fields |
| `--symbols` | 指定 symbol 列表 |
| `--start-date` | 数据起始日期（默认全量） |
| `-o, --output-dir` | pkl 输出目录 |

## 输出格式

每个 output field 一个 pkl 文件：
- `index`: DatetimeIndex (tz=Asia/Shanghai)
- `columns`: symbol codes (str)
- `values`: float64

与 `evaluate.py --file` 直接兼容。

## Formula 脚本格式

必须包含 `build_definition()` 函数，返回 `AShareRawDataDefinition`。参考：
- `research/basic_rawdata/pv_stats/register_pv_stats_0930_1030.py`
- `research/basic_rawdata/volatility/register_volatility_0930_1030.py`

数据字段说明见 `docs/HFT-DATA-GUIDE.md`。

## Ray 配置

| 参数 | 值 |
|------|-----|
| Ray head 地址 | `192.168.0.107:26380` |
| Namespace | `ashare_rawdata` |
| Object store | 50 GB |
| Preload actor | `ashare_rawdata_preload` |
| 预加载数据量 | ~5090 symbols, 2020-01-01 ~ 2024-12-31 |
