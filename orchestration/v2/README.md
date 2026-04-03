# Agent Mining v2 — Quick Start

## 架构

```
Supervisor (shell, 0 token)
  ├── Worker A (wrapper → dispatch → briefing → Opus → postprocess)
  ├── Worker B (同上)
  └── hourly_report (shell)

CLI 工具 (取代 Lead Agent):
  ├── status.py    — 查看系统状态
  ├── approve.py   — 审批 pending 特征
  └── pool_manage.py — 管理方向池
```

## 启动

```bash
cd /home/gkh/claude_tasks/ashare_rawdata

# 一键启动（supervisor 会自动启动 workers + hourly report）
tmux new-session -d -s supervisor \
  "bash orchestration/v2/supervisor.sh ashare_rawdata_a ashare_rawdata_b 2>&1 | tee orchestration/logs/supervisor.log"
```

## 常用操作

```bash
# 查看状态
python orchestration/v2/scripts/status.py

# 查看待审核
python orchestration/v2/scripts/approve.py --list

# 通过审批
python orchestration/v2/scripts/approve.py feat1 feat2

# 拒绝
python orchestration/v2/scripts/approve.py --reject feat1 --reason WEAK_SIGNAL --note "说明"

# 方向池管理
python orchestration/v2/scripts/pool_manage.py --list
python orchestration/v2/scripts/pool_manage.py --add --name "xxx" --desc "描述" --priority high

# 停止
touch orchestration/state/SUPERVISOR_STOP            # 停止 supervisor
touch orchestration/state/agent_states/xxx_STOP      # 停止单个 worker
```

## 与 v1 的区别

| 项目 | v1 | v2 |
|------|----|----|
| 协调 | Lead Agent (Opus 会话) | Supervisor (shell, 0 token) |
| 方向认领 | AI 会话内 Python | auto_dispatch.py (0 token) |
| Prompt | 370 行全量 | ~100 行 lean + briefing |
| 上下文 | 每次读 KB/LOG 全文 | Sonnet/Python 生成精简 briefing |
| 审批 | 对话式 (lead Agent) | CLI 工具 (approve.py) |
| 模型 | 全部 Opus | 研究 Opus, 批量/scout Sonnet |
