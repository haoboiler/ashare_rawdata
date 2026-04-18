# Environment

- **Python**: `/home/b0qi/anaconda3/envs/gkh-ashare/bin/python`
- **casimir**: `sys.path.insert(0, '/home/gkh/ashare/casimir_ashare')`
- **.env**: 从项目根目录运行（`CA_AES_256_KEY_PATH`, `CA_IV_PATH`）
- **mock**: 需要 `.claude-tmp/mock_packages/bookdisco_ml/`

## 关键外部路径

| 资源 | 路径 |
|------|------|
| casimir_ashare | `/home/gkh/ashare/casimir_ashare` |
| rawdata package | `casimir.core.ashare_rawdata`（在 casimir_ashare 仓库内；2026-03-18 从 `ashare_hf_variable` 迁入，旧包已废弃） |
| rawdata updater CLI | `/home/gkh/ashare/ashare_update/scripts/aggregate/update_ashare_rawdata.py` |
| evaluate.py | `/home/gkh/claude_tasks/ashare_alpha/backtest/evaluate.py`（**不要修改**） |

**废弃目录**：`/home/gkh/ashare/ashare_hf_variable/`（dead code，cron 不会读）；`/home/gkh/ashare/ashare_hf_variable_v2/`（本轮 PoC 分支副本）；`/home/gkh/ashare/ashare_hf_variable.bak.*/`（合入前备份）。
