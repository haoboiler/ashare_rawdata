# A 股 RawData 回测默认参数

> **强制**：所有 Agent 在执行评估/回测之前，**必须先阅读本文件**，确保使用正确的默认参数。
> 本文件定义的参数优先级高于 evaluate.py 自身默认值。

## 默认参数一览

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--benchmark-index` | `csi1000` | 基准指数，使用中证 1000 |
| `--neutralize` | **启用** | 行业 + 市值中性化 |
| `--neutralize-factors` | `industry,size` | 中性化因子（evaluate.py 默认值已是此项） |
| `--start` | `2020-01-01` | 评估起始日期 |
| `--window` | `1` | 持仓周期（1 天） |
| `--num-groups` | `5` | 横截面分组数 |
| `--execution-price-field` | `twap_1300_1400` | 执行价字段 |

## 股票池

- **全 A 股**：不限制 `--index-code`（默认全 A）
- **排除 ST**：默认行为（不加 `--allow-st`）
- **排除退市股**：默认行为（`AShareStockPool` 硬编码过滤）
- **排除涨跌停**：默认行为（不加 `--include-price-limit`）

## 标准评估命令

```bash
# ⭐ RawData 标准评估命令（从项目根目录运行）
cd /home/gkh/claude_tasks/ashare_rawdata
python /home/gkh/claude_tasks/ashare_alpha/backtest/evaluate.py \
    --file .claude-output/analysis/{feature_name}.pkl \
    --start 2020-01-01 \
    --window 1 \
    --num-groups 5 \
    --execution-price-field twap_1300_1400 \
    --benchmark-index csi1000 \
    --neutralize \
    --output-dir .claude-output/evaluations/{direction}/{feature_name}/
```

## 快速评估命令

```bash
# 快速模式（跳过分组和时段分析，用于快速迭代）
cd /home/gkh/claude_tasks/ashare_rawdata
python /home/gkh/claude_tasks/ashare_alpha/backtest/evaluate.py \
    --file .claude-output/analysis/{feature_name}.pkl \
    --start 2020-01-01 \
    --window 1 \
    --num-groups 5 \
    --execution-price-field twap_1300_1400 \
    --benchmark-index csi1000 \
    --neutralize \
    --quick \
    --output-dir .claude-output/evaluations/{direction}/{feature_name}/
```

## 注意事项

1. **必须从项目根目录运行**（确保 `.env` 生效）
2. **不要修改 evaluate.py**（共享文件，修改需与 ashare_alpha 协调）
3. 因子值 pickle 格式：`index=trade_date(DatetimeIndex, tz=Asia/Shanghai)`, `columns=symbols(str)`, `values=factor_value(float64)`
4. `--neutralize` 会同时输出 raw 和 neutralized 两组结果，方便对比
5. **不使用** `--post-process-method`（与 ashare_alpha 保持一致）
