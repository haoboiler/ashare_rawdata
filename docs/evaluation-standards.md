# A 股 RawData 评估标准

> 最后更新：2026-04-03

## 自动筛选阈值（硬性要求，全部通过才进入 pending）

<!-- SSOT: docs/params/evaluation.yaml — 阈值数值只在 YAML 中定义 -->
→ **阈值数值见 `docs/params/evaluation.yaml`**

| 指标 | YAML key | 来源字段 | 说明 |
|------|----------|---------|------|
| LS Sharpe | `sharpe_abs_net_min` | `stats.json → sharpe_abs_net` | 多空绝对 Sharpe（扣费后） |
| IR(LS) | `ir_ls_min` | `stats.json → ir_ls` | IC 的信息比率（IC_mean / IC_std） |
| Long Excess Net Sharpe | `long_excess_net_sharpe_min` | `stats.json → sharpe_long_excess_net` | 多头端对冲 CSI1000 TWAP 的超额 Sharpe（扣费后） |
| Mono | `mono_min` | 分组回测输出 | 8 组分组回测的单调性评分 |
| 数据覆盖率 | `coverage_min` | 因子 pkl 非 NaN 占比 | 允许较低覆盖率（部分因子只在特定条件下有值） |

## 回测参数（与 ashare_alpha 保持一致）

<!-- SSOT: docs/params/evaluation.yaml — 参数值只在 YAML 中定义 -->
→ **参数数值见 `docs/params/evaluation.yaml`**

| 参数 | YAML key | 说明 |
|------|----------|------|
| `--mode` | `mode` | 多空模式 |
| `--num-groups` | `num_groups` | 横截面分组数 |
| `--post-process-method` | `post_process_method` | 截面处理方法 |
| `--execution-price-field` | `execution_price_field` | 执行价字段 |
| `--benchmark-index` | `benchmark_index` | 基准指数 |
| `--commission-rate` | `commission_rate` | 单边佣金 |
| `--stamp-tax-rate` | — | 无印花税 |
| `--start` | — | 2020-01-01 |
| `--end` | — | 2024-12-31 |
| `--neutralize` | `neutralize` | 行业 + 市值中性化 |

详见 `docs/BACKTEST.md`。

## 主指标说明

- **LS Sharpe (`sharpe_abs_net`)**: 多空组合的绝对收益 Sharpe。反映因子在多空两端的综合选股能力
- **Long Excess Net Sharpe (`sharpe_long_excess_net`)**: 多头端收益减去 CSI1000 TWAP benchmark 后的 Sharpe。这是最终考核指标——多头端能否跑赢基准
- **IR(LS) (`ir_ls`)**: IC 的均值除以标准差。衡量信号的稳定性
- **Mono**: 分组回测中，从 G1（因子值最高）到 G8（因子值最低）的收益是否单调递减。1.0 = 完美单调

## 筛选流程

```
compute/evolve → evaluate_rawdata.py → stats.json + group_analysis.json
    ↓
check_screening.py (自动 pass/fail，读 evaluation.yaml)
    ↓
admit_rawdata.py (统一入口：筛选 + 相关性 gate + 自动打包)
    ├── admit_gates/pairwise.py        (读 alpha 侧 official cache)
    └── admit_gates/incremental_sharpe.py (OLS 增量 Sharpe)
    ↓
research/pending-rawdata/{feature}/ → 人工审批 (approve.py)
```

**自动化命令**:
```bash
python scripts/admit_rawdata.py --feature-name {name} --pkl {pkl} --eval-dir {dir}
```

## 注意事项

1. **raw 和 neutralized 两组都要看**：neutralized 版本剥离了行业+市值暴露，更能反映因子的"纯信号"
2. **取绝对值判断 IC 方向**：因子方向可能与预期相反，|IR| 达标即可，方向可以在入库时翻转
3. **Mono 评分需要完整评估**（不能用 `--quick`）：`--quick` 跳过分组分析
4. **覆盖率是最低要求**：低覆盖率因子可能在特定条件下（如高波动日）才有值，这是可以接受的
