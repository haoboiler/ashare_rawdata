#!/usr/bin/env python3
"""
Auto-Dispatch — 零 AI token 的任务路由器

读取 agent 状态 → 决定下一个任务 → 更新状态 + 生成 task_card。
由 worker_wrapper 在每个 cycle 的 dispatch 阶段调用。

Return codes:
    0 — 任务已分配/继续，wrapper 应启动 AI 会话
    1 — 需要人工干预
    2 — 方向池空，等待补充
    3 — 错误

Usage:
    python orchestration/v2/auto_dispatch.py --agent ashare_rawdata_a
    python orchestration/v2/auto_dispatch.py --agent ashare_rawdata_a --allow-stopped
"""

import argparse
import glob
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.utils.state_manager import (
    claim_direction,
    read_state,
    release_direction,
    update_state,
)

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_DIR = os.path.join(PROJECT_DIR, 'orchestration', 'state')
AGENT_STATES_DIR = os.path.join(STATE_DIR, 'agent_states')
POOL_PATH = os.path.join(STATE_DIR, 'direction_pool.yaml')
FEEDBACK_DIR = os.path.join(PROJECT_DIR, 'research', 'agent_reports', 'feedback')

MAX_CONSECUTIVE_FAILURES = 3


def find_latest_feedback(direction_name: str) -> str:
    """查找与方向相关的最新 feedback 文件路径"""
    if not os.path.isdir(FEEDBACK_DIR):
        return ''
    candidates = []
    for f in os.listdir(FEEDBACK_DIR):
        if direction_name in f and f.endswith('.md'):
            full = os.path.join(FEEDBACK_DIR, f)
            candidates.append((os.path.getmtime(full), full))
    if not candidates:
        return ''
    candidates.sort(reverse=True)
    return candidates[0][1]


def build_task_card(direction: dict, state: dict, feedback_path: str = '') -> str:
    """构建 task_card 字符串，wrapper 用 grep -oP 解析"""
    parts = [
        f"mode=research",
        f"direction_id={direction['id']}",
        f"direction_name={direction['name']}",
        f"priority={direction.get('priority', 'medium')}",
        f"max_formulas=5",
        f"cycle={state.get('cycle_count', 0) + 1}",
        f"eval_start=2020-01-01",
        f"eval_end=2023-12-31",
        f"field_preset=basic6",
    ]
    if direction.get('prerequisite_reading'):
        parts.append(f"prereq={direction['prerequisite_reading']}")
    if feedback_path:
        parts.append(f"feedback_path={feedback_path}")
    desc = direction.get('description', '')
    if desc:
        # 截断到 120 字符，避免 task_card 过长
        parts.append(f"description={desc[:120]}")
    return "; ".join(parts)


def build_task_card_continue(state: dict) -> str:
    """为继续当前方向构建 task_card"""
    parts = [
        f"mode=research_continue",
        f"direction_id={state.get('current_direction_id', '')}",
        f"direction_name={state.get('current_direction', '')}",
        f"cycle={state.get('cycle_count', 0) + 1}",
        f"eval_start=2020-01-01",
        f"eval_end=2023-12-31",
        f"field_preset=basic6",
    ]
    # 注入上轮的 notes 摘要（前 200 字符）
    notes = state.get('notes', '')
    if notes and notes != '初始化':
        summary = notes.replace('\n', ' ').strip()[:200]
        parts.append(f"prev_notes={summary}")
    feedback_path = find_latest_feedback(state.get('current_direction', ''))
    if feedback_path:
        parts.append(f"feedback_path={feedback_path}")
    return "; ".join(parts)


def dispatch(agent_id: str, allow_stopped: bool = False) -> int:
    """
    主调度逻辑。

    Returns:
        0 — 任务已分配
        1 — 需要干预
        2 — 方向池空
        3 — 错误
    """
    state_path = os.path.join(AGENT_STATES_DIR, f'{agent_id}.yaml')
    state = read_state(state_path)

    if not state:
        print(f"[dispatch] 状态文件不存在或为空: {state_path}", file=sys.stderr)
        return 3

    status = state.get('status', 'idle')

    # stopped 状态检查
    if status == 'stopped' and not allow_stopped:
        print(f"[dispatch] {agent_id} 状态为 stopped，跳过（使用 --allow-stopped 强制）")
        return 1

    # 1. 连续失败升级
    failures = state.get('consecutive_failures', 0)
    if failures >= MAX_CONSECUTIVE_FAILURES:
        direction_id = state.get('current_direction_id')
        direction_name = state.get('current_direction', 'unknown')
        if direction_id:
            print(f"[dispatch] {agent_id} 连续 {failures} 次失败，"
                  f"方向 {direction_name} ({direction_id}) 标记 exhausted")
            release_direction(POOL_PATH, direction_id, 'exhausted')
        update_state(state_path, {
            'consecutive_failures': 0,
            'current_direction': None,
            'current_direction_id': None,
            'current_experiment_id': None,
        })
        state['current_direction'] = None
        state['current_direction_id'] = None

    # 2. 是否需要新方向?
    if state.get('current_direction') is None:
        direction = claim_direction(POOL_PATH, agent_id)
        if direction is None:
            print(f"[dispatch] 方向池空，{agent_id} 等待补充")
            update_state(state_path, {
                'status': 'idle',
                'runtime_phase': 'pool_empty',
            })
            return 2

        feedback_path = find_latest_feedback(direction['name'])
        task_card = build_task_card(direction, state, feedback_path)

        update_state(state_path, {
            'status': 'assigned',
            'current_direction': direction['name'],
            'current_direction_id': direction['id'],
            'current_experiment_id': None,
            'task_type': 'research',
            'task_card': task_card,
        })
        print(f"[dispatch] {agent_id} 认领方向: {direction['name']} ({direction['id']})")
        print(f"[dispatch] task_card: {task_card}")
        return 0

    # 3. 继续当前方向
    task_card = build_task_card_continue(state)
    update_state(state_path, {
        'status': 'assigned',
        'task_card': task_card,
    })
    print(f"[dispatch] {agent_id} 继续方向: {state['current_direction']}")
    print(f"[dispatch] task_card: {task_card}")
    return 0


def main():
    parser = argparse.ArgumentParser(description='Auto-Dispatch: 零 token 任务路由器')
    parser.add_argument('--agent', required=True, help='Agent ID')
    parser.add_argument('--allow-stopped', action='store_true',
                        help='允许为 stopped 状态的 agent 分配任务')
    args = parser.parse_args()

    rc = dispatch(args.agent, args.allow_stopped)
    sys.exit(rc)


if __name__ == '__main__':
    main()
