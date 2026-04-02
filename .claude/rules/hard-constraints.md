# Hard Constraints

## 实现约束
- **Numba 强制**：所有 formula 必须 `@njit` 兼容，纯 numpy，显式 NaN 处理
- **可解释性强制**：每个 Raw-Data 必须有清晰物理含义
- **禁止自行注册**：入库必须经用户审批（`docs/ASHARE_ADMISSION.md`）
- **后复权强制**：因子计算使用 `open/high/low/close`（hfq），禁止 `origin_*`（仅用于涨跌停判断）
- **产出索引**：写入 `.claude-output/` 后必须更新 `index.md`

## 评估标准
参数值定义 → `docs/params/evaluation.yaml`（SSOT）
详细说明 → `docs/evaluation-standards.md` 和 `docs/BACKTEST.md`
