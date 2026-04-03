#!/usr/bin/env python3
"""
系统状态查看工具 — 取代 lead Agent 的状态查询

Usage:
    python orchestration/v2/scripts/status.py
"""

import os
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from scripts.utils.state_manager import read_state

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
AGENT_STATES_DIR = os.path.join(PROJECT_DIR, 'orchestration', 'state', 'agent_states')
COST_TRACKER = os.path.join(PROJECT_DIR, 'orchestration', 'state', 'cost_tracker.yaml')
POOL_PATH = os.path.join(PROJECT_DIR, 'orchestration', 'state', 'direction_pool.yaml')
PENDING_DIR = os.path.join(PROJECT_DIR, 'research', 'pending-rawdata')


def get_tmux_sessions():
    """获取所有 tmux 会话"""
    try:
        result = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'],
                                capture_output=True, text=True)
        if result.returncode == 0:
            return set(result.stdout.strip().split('\n'))
    except FileNotFoundError:
        pass
    return set()


def main():
    tmux_sessions = get_tmux_sessions()

    # --- Agents ---
    print("\n=== Agent 状态 ===\n")
    agents = []
    for f in sorted(os.listdir(AGENT_STATES_DIR)):
        if f.endswith('.yaml') and not f.endswith('.lock'):
            agents.append(f.replace('.yaml', ''))

    for agent in agents:
        state = read_state(os.path.join(AGENT_STATES_DIR, f'{agent}.yaml'))
        tmux_alive = '🟢' if agent in tmux_sessions else '🔴'
        status = state.get('status', '?')
        direction = state.get('current_direction', 'null')
        direction_id = state.get('current_direction_id', '')
        cycle = state.get('cycle_count', 0)
        failures = state.get('consecutive_failures', 0)
        phase = state.get('runtime_phase', '?')
        last_at = state.get('last_cycle_at', '?')

        print(f"  {tmux_alive} {agent}")
        print(f"    status={status} | phase={phase} | cycle={cycle} | failures={failures}")
        print(f"    direction={direction} ({direction_id})")
        print(f"    last_cycle_at={last_at}")
        if state.get('pending_features'):
            print(f"    pending_features={state['pending_features']}")
        print()

    # --- 预算 ---
    print("=== 预算 ===\n")
    try:
        cost = read_state(COST_TRACKER)
    except Exception:
        # cost_tracker may have inline YAML issues from v1 sed-based writes
        import re
        cost = {}
        try:
            with open(COST_TRACKER, 'r') as f:
                for line in f:
                    m = re.match(r'^(weekly_budget_usd|week_total_usd|week_start):\s*(.+)', line)
                    if m:
                        cost[m.group(1)] = m.group(2).strip().strip('"')
        except Exception:
            pass
    spent = float(cost.get('week_total_usd', 0))
    budget = float(cost.get('weekly_budget_usd', 500))
    week_start = cost.get('week_start', '?')
    pct = (spent / budget * 100) if budget > 0 else 0
    emoji = '✅' if pct < 80 else ('⚠️' if pct < 100 else '🔴')
    print(f"  {emoji} ${spent:.2f} / ${budget} ({pct:.0f}%) | 周起始: {week_start}\n")

    # --- 方向池 ---
    print("=== 方向池 ===\n")
    pool = read_state(POOL_PATH)
    directions = pool.get('directions', [])
    available = len([d for d in directions if d.get('status') == 'available'])
    claimed = len([d for d in directions if d.get('status') == 'claimed'])
    exhausted = len([d for d in directions if d.get('status') == 'exhausted'])
    print(f"  可用: {available} | 进行中: {claimed} | 已穷尽: {exhausted} | 总计: {len(directions)}\n")

    # --- Pending ---
    print("=== 待审核 ===\n")
    if os.path.isdir(PENDING_DIR):
        pending = [d for d in os.listdir(PENDING_DIR) if os.path.isdir(os.path.join(PENDING_DIR, d))]
        if pending:
            for p in sorted(pending):
                print(f"  📋 {p}")
            print(f"\n  共 {len(pending)} 个待审核。")
        else:
            print("  无待审核特征。")
    else:
        print("  无待审核特征。")

    # --- Supervisor ---
    print("\n=== 基础设施 ===\n")
    sv = '🟢' if 'supervisor' in tmux_sessions else '🔴'
    hr = '🟢' if 'ashare_rawdata_hourly_report' in tmux_sessions else '🔴'
    print(f"  {sv} supervisor")
    print(f"  {hr} hourly_report")
    print()


if __name__ == '__main__':
    main()
