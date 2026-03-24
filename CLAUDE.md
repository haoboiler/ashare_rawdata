# AShare RawData — A 股高频聚合原始数据挖掘项目

## 项目概要

从 **A 股 1 分钟 K 线数据** (`ashare@stock@kline@1m`, 5191 symbols, 2020 年起) 挖掘日度 Raw-Data 因子，入库到 `ashare@stock@raw_value@1d`，为下游 `ashare_alpha` 提供原料。

## 硬约束

- **Numba 强制**：所有 formula 必须 `@njit` 兼容，纯 numpy，显式 NaN 处理
- **可解释性强制**：每个 Raw-Data 必须有清晰物理含义
- **禁止自行注册**：入库必须经用户审批（`docs/ASHARE_ADMISSION.md`）
- **后复权强制**：因子计算使用 `open/high/low/close`（hfq），禁止 `origin_*`（仅用于涨跌停判断）
- **产出索引**：写入 `.claude-output/` 后必须更新 `index.md`

## 评估标准

> 详见 `docs/evaluation-standards.md` 和 `docs/BACKTEST.md`

| 指标 | 阈值 |
|------|------|
| LS Sharpe (`sharpe_abs_net`) | > 0.9 |
| IR(LS) | > 0.2 |
| Long Excess Net Sharpe | > 0.7 |
| Mono (8 组) | > 0.7 |
| 数据覆盖率 | > 30% |

回测参数：`--mode long_short --num-groups 8 --post-process-method comp --execution-price-field twap_1300_1400 --benchmark-index csi1000 --commission-rate 0.0001 --neutralize`

## 核心工作流

```
物理假设 → Numba 实现 → compute_rawdata_local.py → evaluate.py → admission_corr_check.py → 入库审批
```

- **本地计算**: `python scripts/compute_rawdata_local.py --formula-file {script.py} --quick -o .claude-output/analysis/`
- **回测评估**: 见 `docs/BACKTEST.md`（必须用 `gkh-ashare` 环境 python + mock_packages）
- **相关性检测**: `python scripts/admission_corr_check.py --factors {pkl} --cache .claude-output/pnl_cache/pnl_cache.pkl`
- **入库流程**: 见 `docs/ASHARE_ADMISSION.md`

## 运行环境

- **Python**: `/home/b0qi/anaconda3/envs/gkh-ashare/bin/python`
- **casimir**: `sys.path.insert(0, '/home/gkh/ashare/casimir_ashare')`
- **.env**: 从项目根目录运行（`CA_AES_256_KEY_PATH`, `CA_IV_PATH`）
- **mock**: 需要 `.claude-tmp/mock_packages/bookdisco_ml/`

## 知识检索（三层架构）

启动研究时按 Layer 0 → 1 → 2 递进阅读。详见 `docs/THREE-LAYER-GUIDE.md`

| 层级 | 文件 | 说明 |
|------|------|------|
| L0 | `research/KNOWLEDGE-BASE.md` | 已注册 RawData + 结论 + 方向池 |
| L1 | `research/EXPERIMENT-LOG.md` | 实验记录 + 已排除方向 |
| L2 | `.claude-output/` | 原始评估数据（按需读取） |

**规则**: 已排除方向**绝对不重复研究**。

## 研究纪律

1. **假设驱动**，不做无意义数学变换
2. **单变量迭代**，一次只改一个维度
3. **必须做分组回测**（不能只看 IC）
4. **连续 2 个失败必须停下反思**
5. 失败特征必须写诊断（特征/假设/实际/诊断/结论/下一步）

## 文件产出位置

| 类型 | 位置 |
|------|------|
| 因子值 pkl | `.claude-output/analysis/` |
| 评估报告 | `.claude-output/evaluations/` |
| 研究报告 | `.claude-output/reports/` |
| 临时文件 | `.claude-tmp/` |

## 关键路径

| 资源 | 路径 |
|------|------|
| casimir_ashare | `/home/gkh/ashare/casimir_ashare` |
| ashare_hf_variable | `/home/gkh/ashare/ashare_hf_variable` |
| evaluate.py | `/home/gkh/claude_tasks/ashare_alpha/backtest/evaluate.py`（**不要修改**） |
| 1m 数据指南 | `docs/HFT-DATA-GUIDE.md` |
| 回测参数 | `docs/BACKTEST.md` |
| 入库流程 | `docs/ASHARE_ADMISSION.md` |
