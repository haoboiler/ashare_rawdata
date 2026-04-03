#!/usr/bin/env python3
"""
方向池管理工具 — 添加/列出/移除方向

Usage:
    # 列出方向池
    python orchestration/v2/scripts/pool_manage.py --list

    # 添加方向
    python orchestration/v2/scripts/pool_manage.py --add \
        --name "realized_semi_var" \
        --desc "Realized Semi-Variance 分解" \
        --priority high

    # 标记方向为 exhausted
    python orchestration/v2/scripts/pool_manage.py --exhaust D-042

    # 释放被 claim 的方向
    python orchestration/v2/scripts/pool_manage.py --release D-042
"""

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from scripts.utils.state_manager import read_state, write_state, release_direction

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
POOL_PATH = os.path.join(PROJECT_DIR, 'orchestration', 'state', 'direction_pool.yaml')


def list_pool():
    """列出方向池"""
    pool = read_state(POOL_PATH)
    directions = pool.get('directions', [])

    status_counts = {}
    for d in directions:
        s = d.get('status', '?')
        status_counts[s] = status_counts.get(s, 0) + 1

    print(f"\n方向池: {len(directions)} 个方向")
    print(f"  状态: {', '.join(f'{k}={v}' for k, v in sorted(status_counts.items()))}")
    print()

    for status_filter in ['available', 'claimed', 'exhausted']:
        filtered = [d for d in directions if d.get('status') == status_filter]
        if not filtered:
            continue

        emoji = {'available': '🟢', 'claimed': '🔵', 'exhausted': '⚫'}.get(status_filter, '?')
        print(f"  {emoji} {status_filter} ({len(filtered)}):")
        for d in filtered:
            line = f"    {d['id']:<8} {d.get('name', '?'):<30} priority={d.get('priority', '?')}"
            if d.get('claimed_by'):
                line += f"  claimed_by={d['claimed_by']}"
            print(line)
        print()


def add_direction(name: str, description: str, priority: str = 'medium',
                  source: str = '用户添加', prereq: str = ''):
    """添加新方向"""
    pool = read_state(POOL_PATH)
    directions = pool.get('directions', [])

    # 生成新 ID
    max_num = 0
    for d in directions:
        did = d.get('id', '')
        if did.startswith('D-'):
            try:
                num = int(did.split('-')[1])
                max_num = max(max_num, num)
            except ValueError:
                pass
    new_id = f"D-{max_num + 1:03d}"

    new_dir = {
        'id': new_id,
        'name': name,
        'description': description,
        'priority': priority,
        'status': 'available',
        'source': source,
    }
    if prereq:
        new_dir['prerequisite_reading'] = prereq

    directions.append(new_dir)
    pool['directions'] = directions
    write_state(POOL_PATH, pool)

    print(f"✅ 添加方向: {new_id} {name} (priority={priority})")
    return new_id


def exhaust_direction(direction_id: str):
    """标记方向为 exhausted"""
    release_direction(POOL_PATH, direction_id, 'exhausted')
    print(f"⚫ {direction_id} 标记为 exhausted")


def release_dir(direction_id: str):
    """释放方向回 available"""
    release_direction(POOL_PATH, direction_id, 'available')
    print(f"🟢 {direction_id} 释放为 available")


def main():
    parser = argparse.ArgumentParser(description='方向池管理')
    parser.add_argument('--list', action='store_true', help='列出方向池')
    parser.add_argument('--add', action='store_true', help='添加方向')
    parser.add_argument('--name', help='方向名')
    parser.add_argument('--desc', help='方向描述')
    parser.add_argument('--priority', default='medium', choices=['highest', 'high', 'medium', 'low'])
    parser.add_argument('--source', default='用户添加')
    parser.add_argument('--prereq', default='', help='前置阅读路径')
    parser.add_argument('--exhaust', metavar='DIR_ID', help='标记方向 exhausted')
    parser.add_argument('--release', metavar='DIR_ID', help='释放方向为 available')

    args = parser.parse_args()

    if args.list:
        list_pool()
    elif args.add:
        if not args.name or not args.desc:
            print("--add 需要 --name 和 --desc")
            sys.exit(1)
        add_direction(args.name, args.desc, args.priority, args.source, args.prereq)
    elif args.exhaust:
        exhaust_direction(args.exhaust)
    elif args.release:
        release_dir(args.release)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
