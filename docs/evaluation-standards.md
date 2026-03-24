# A 股 RawData 评估标准

> 最后更新：2026-03-24

## 自动筛选阈值（硬性要求，全部通过才进入 pending）

| 指标 | 阈值 | 来源字段 | 说明 |
|------|------|---------|------|
| LS Sharpe | > 0.9 | `stats.json → sharpe_abs_net` | 多空绝对 Sharpe（扣费后） |
| IR(LS) | > 0.2 | `stats.json → ir_ls` | IC 的信息比率（IC_mean / IC_std） |
| Long Excess Net Sharpe | > 0.7 | `stats.json → sharpe_long_excess_net` | 多头端对冲 CSI1000 TWAP 的超额 Sharpe（扣费后） |
| Mono | > 0.7 | 分组回测输出 | 8 组分组回测的单调性评分 |
| 数据覆盖率 | > 30% | 因子 pkl 非 NaN 占比 | 允许较低覆盖率（部分因子只在特定条件下有值） |

## 回测参数（与 ashare_alpha 保持一致）

| 参数 | 值 |
|------|-----|
| `--mode` | `long_short` |
| `--num-groups` | `8` |
| `--post-process-method` | `comp` |
| `--execution-price-field` | `twap_1300_1400` |
| `--benchmark-index` | `csi1000` |
| `--commission-rate` | `0.0001`（万1 单边） |
| `--stamp-tax-rate` | `0.0` |
| `--start` | `2020-01-01` |
| `--end` | `2024-12-31` |
| `--neutralize` | 启用（同时输出 raw 和 neutralized 两组） |

详见 `docs/BACKTEST.md`。

## 主指标说明

- **LS Sharpe (`sharpe_abs_net`)**: 多空组合的绝对收益 Sharpe。反映因子在多空两端的综合选股能力
- **Long Excess Net Sharpe (`sharpe_long_excess_net`)**: 多头端收益减去 CSI1000 TWAP benchmark 后的 Sharpe。这是最终考核指标——多头端能否跑赢基准
- **IR(LS) (`ir_ls`)**: IC 的均值除以标准差。衡量信号的稳定性
- **Mono**: 分组回测中，从 G1（因子值最高）到 G8（因子值最低）的收益是否单调递减。1.0 = 完美单调

## 筛选流程

```
compute_rawdata_local.py → evaluate.py → 提取 stats.json →
→ 检查 5 个硬指标 → 全部通过 → 进入 pending-rawdata/
→ 任一不通过 → 写失败诊断到 screening report
```

## 注意事项

1. **raw 和 neutralized 两组都要看**：neutralized 版本剥离了行业+市值暴露，更能反映因子的"纯信号"
2. **取绝对值判断 IC 方向**：因子方向可能与预期相反，|IR| > 0.2 即可，方向可以在入库时翻转
3. **Mono 评分需要完整评估**（不能用 `--quick`）：`--quick` 跳过分组分析
4. **覆盖率 30% 是最低要求**：低覆盖率因子可能在特定条件下（如高波动日）才有值，这是可以接受的
