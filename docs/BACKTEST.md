# A 股 RawData 回测默认参数

> **强制**：所有 Agent 在执行评估/回测之前，**必须先阅读本文件**，确保使用正确的默认参数。
> 本文件定义的参数优先级高于 evaluate.py 自身默认值。
> 筛选阈值见 `docs/evaluation-standards.md`。

## 默认参数一览

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--mode` | `long_short` | 多空模式 |
| `--benchmark-index` | `csi1000` | 基准指数（合成 TWAP benchmark） |
| `--execution-price-field` | `twap_1300_1400` | 执行价字段 |
| `--num-groups` | `8` | 横截面分组数 |
| `--post-process-method` | `comp` | 截面减中位数 + booksize 归一化 |
| `--neutralize` | **启用** | 行业 + 市值中性化（同时输出 raw + neutralized） |
| `--commission-rate` | `0.0001` | 万1 单边佣金 |
| `--stamp-tax-rate` | `0.0` | 无印花税 |
| `--start` | `2020-01-01` | 评估起始日期 |
| `--end` | `2024-12-31` | RawData 回测截止日期 |

## Python 环境

因为 `compute_rawdata_local.py` 用 `gkh-ashare` 环境（numpy 2.x）生成 pkl，而共享 `evaluate.py` 也必须用同一环境读取，所以本项目统一通过 wrapper 调用：

```bash
python scripts/evaluate_rawdata.py ...
```

wrapper 会自动：
- 使用正确的 `gkh-ashare` python 调起共享 `evaluate.py`
- 注入 `.claude-tmp/mock_packages/`
- 从 `*.meta.json` sidecar 或 registry 补 raw-data timing metadata，并对齐 `t_plus_n`

## 股票池

- **全 A 股**：不限制 `--index-code`（默认全 A）
- **排除 ST**：默认行为（不加 `--allow-st`）
- **排除退市股**：默认行为
- **涨跌停约束**：由 positive/negative trade mask 自动处理

## 标准评估命令

```bash
# ⭐ RawData 标准评估命令（从项目根目录运行）
cd /home/gkh/claude_tasks/ashare_rawdata
python scripts/evaluate_rawdata.py \
    --file .claude-output/analysis/{feature_name}.pkl \
    --start 2020-01-01 --end 2024-12-31 \
    --neutralize \
    --output-dir .claude-output/evaluations/{direction}/{feature_name}/
```

## 快速评估命令

```bash
# 快速模式（跳过分组和时段分析，用于快速迭代）
# 注意：--quick 跳过 Mono 评分，最终提交前必须跑完整评估
cd /home/gkh/claude_tasks/ashare_rawdata
python scripts/evaluate_rawdata.py \
    --file .claude-output/analysis/{feature_name}.pkl \
    --start 2020-01-01 --end 2024-12-31 \
    --neutralize \
    --quick \
    --output-dir .claude-output/evaluations/{direction}/{feature_name}/
```

## 主指标（详见 evaluation-standards.md）

| 指标 | stats.json 字段 | 阈值 |
|------|----------------|------|
| LS Sharpe | `sharpe_abs_net` | > 0.9 |
| IR(LS) | `ir_ls` | > 0.2 |
| Long Excess Net Sharpe | `sharpe_long_excess_net` | > 0.7 |
| Mono | 分组输出 | > 0.7 |

## 注意事项

1. **必须从项目根目录运行**（确保 `.env` 生效）
2. **不要修改 evaluate.py**（共享文件，修改需与 ashare_alpha 协调）
3. `compute_rawdata_local.py` 导出的每个 `pkl` 旁边会有一个 `*.meta.json`，wrapper 会优先读取它来推断 raw-data 的 `t_plus_n`
4. 因子值 pickle 格式：`index=trade_date(DatetimeIndex, tz=Asia/Shanghai)`, `columns=symbols(str)`, `values=factor_value(float64)`
5. `--neutralize` 会同时输出 raw 和 neutralized 两组结果，方便对比
6. `--end` 固定为 `2024-12-31`，RawData 不需要回测到最新日期
7. 最后的 `update_output_index` 报错（跨项目路径）可忽略，不影响结果
