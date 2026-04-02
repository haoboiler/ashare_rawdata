# AShare RawData — A 股高频聚合原始数据挖掘项目

从 A 股 1 分钟 K 线数据（`ashare@live@stock@kline@1m`, 5191 symbols, 2020 年起）挖掘日度 Raw-Data 因子，入库到 `ashare@live@stock@raw_value@1d`，为下游 `ashare_alpha` 提供原料。

## 快速导航

- **当前任务**: → FOCUS.md
- **硬约束**: → .claude/rules/hard-constraints.md
- **工作流程**: → .claude/rules/workflow.md
- **环境配置**: → .claude/rules/environment.md
- **项目管理**: → .claude/rules/project-local.md
- **评估参数 (SSOT)**: → docs/params/evaluation.yaml
- **参考文档**: → docs/INDEX.md
- **知识库**: → research/KNOWLEDGE-BASE.md
- **产出索引**: → .claude-output/index.md

## 核心约束（不可遗忘）

1. **Numba 强制** — 所有 formula 必须 `@njit` 兼容，纯 numpy
2. **可解释性强制** — 每个 Raw-Data 必须有清晰物理含义
3. **禁止自行注册** — 入库必须经用户审批
4. **后复权强制** — 使用 hfq 字段，禁止 `origin_*`
5. **已排除方向绝对不重复研究**

详见 .claude/rules/hard-constraints.md

## 新会话启动顺序

1. 读本文件 → FOCUS.md → research/KNOWLEDGE-BASE.md
2. 确认当前工作不重复已排除方向（查 EXPERIMENT-LOG.md）
3. 工作完成后更新 FOCUS.md 和 .claude-output/index.md
