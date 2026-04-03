# Workflow

## 进度管理 (FOCUS.md)

- 每次启动读 `FOCUS.md`，了解当前进度和下一步
- 任务完成后询问用户：「是否需要更新 FOCUS.md？」（勾选完成项、新增待办）
- 不得未经确认自行修改 FOCUS.md

## 核心流程
```
物理假设 → Numba 实现 → compute_rawdata_local.py → evaluate.py → admit_rawdata.py → 入库审批
```

- **本地计算**: `docs/COMPUTE.md`（推荐 Ray 加速 `--use-preload`，需先 `--preload`）
- **回测评估**: `docs/BACKTEST.md`（必须用 `gkh-ashare` 环境 python + mock_packages）
- **统一入库**: `python scripts/admit_rawdata.py --feature-name {name} --pkl {pkl} --eval-dir {dir}`（含自动筛选 + 相关性 gate + 打包）
- **入库流程**: `docs/ASHARE_ADMISSION.md`

## 知识检索（三层架构）
启动研究时按 Layer 0 → 1 → 2 递进阅读。详见 `docs/THREE-LAYER-GUIDE.md`

| 层级 | 文件 | 说明 |
|------|------|------|
| L0 | `research/KNOWLEDGE-BASE.md` | 已注册 RawData + 结论 + 方向池 |
| L1 | `research/EXPERIMENT-LOG.md` | 实验记录 + 已排除方向 |
| L2 | `.claude-output/` | 原始评估数据（按需读取） |

**规则**: 已排除方向绝对不重复研究。
