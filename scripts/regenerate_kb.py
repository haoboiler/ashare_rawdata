#!/usr/bin/env python3
"""
A-Share RawData 知识库自动生成器

从以下数据源合成 KNOWLEDGE-BASE.md (Layer 0, ≤300行):
1. EXPERIMENT-LOG.md — 已验证结论 + 已排除方向 + 统计
2. direction_pool.yaml — 方向池状态
3. 已注册 bundle 信息（从 research/basic_rawdata/ 下的文档提取）

Usage:
    python scripts/regenerate_kb.py
"""

import os
import re
import sys
import yaml
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_KB_LINES = 300
MAX_CONCLUSIONS = 20

# 已注册 bundle 的静态信息（从 basic_hf_aggregated_variables.md 提取）
REGISTERED_BUNDLES = [
    {'name': 'pv_stats_0930_1030', 'fields': 15, 'window': '09:30-10:30', 'slot': 'midday', 'status': 'validated'},
    {'name': 'pv_stats_0930_1130', 'fields': 15, 'window': '09:30-11:30', 'slot': 'midday', 'status': 'validated'},
    {'name': 'pv_stats_1300_1400', 'fields': 15, 'window': '13:00-14:00', 'slot': 'evening', 'status': 'validated'},
    {'name': 'pv_stats_0930_1130_1300_1457', 'fields': 15, 'window': '全天', 'slot': 'evening', 'status': 'validated'},
    {'name': 'volatility_0930_1030', 'fields': 20, 'window': '09:30-10:30', 'slot': 'midday', 'status': 'validated'},
    {'name': 'volatility_0930_1130', 'fields': 20, 'window': '09:30-11:30', 'slot': 'midday', 'status': 'validated'},
    {'name': 'volatility_1300_1400', 'fields': 20, 'window': '13:00-14:00', 'slot': 'evening', 'status': 'validated'},
    {'name': 'volatility_0930_1130_1300_1457', 'fields': 20, 'window': '全天', 'slot': 'evening', 'status': 'validated'},
]


def parse_experiment_log() -> dict:
    """解析 EXPERIMENT-LOG.md，提取 §一、§二、§四。"""
    log_path = PROJECT_ROOT / 'research' / 'EXPERIMENT-LOG.md'
    if not log_path.exists():
        return {'conclusions': [], 'excluded': [], 'stats': '*实验日志不存在*'}

    content = log_path.read_text()

    # §一 已验证结论
    conclusions = []
    m = re.search(r'## 一、已验证结论(.*?)## 二、', content, re.DOTALL)
    if m:
        section = m.group(1)
        for line in section.strip().split('\n'):
            line = line.strip()
            if re.match(r'^\d+\.', line):
                conclusions.append(line)

    # §二 已排除方向
    excluded = []
    m = re.search(r'## 二、已排除方向(.*?)## 三、', content, re.DOTALL)
    if m:
        section = m.group(1)
        for line in section.strip().split('\n'):
            if line.startswith('|') and not line.startswith('| 方向') and not line.startswith('|---'):
                excluded.append(line)

    # §四 统计
    stats = '*统计区域未找到*'
    m = re.search(r'## 四、统计(.*?)(?:## 五、|$)', content, re.DOTALL)
    if m:
        stats = m.group(1).strip()

    return {
        'conclusions': conclusions[:MAX_CONCLUSIONS],
        'excluded': excluded,
        'stats': stats,
    }


def load_direction_pool() -> list:
    """读取 direction_pool.yaml 状态。"""
    pool_path = PROJECT_ROOT / 'orchestration' / 'state' / 'direction_pool.yaml'
    if not pool_path.exists():
        return []

    with open(pool_path) as f:
        pool = yaml.safe_load(f) or {}

    return pool.get('directions', [])


def render_kb(log_data: dict, directions: list) -> str:
    """渲染 KNOWLEDGE-BASE.md 内容。"""
    lines = []
    lines.append(f'# AShare RawData Knowledge Base')
    lines.append(f'')
    lines.append(f'> 自动生成: {datetime.now().strftime("%Y-%m-%d %H:%M")} | 由 `scripts/regenerate_kb.py` 生成')
    lines.append(f'> Layer 0 入口 — 研究员启动时必读')
    lines.append(f'')

    # §1 已注册 RawData
    lines.append(f'## §一 已注册 RawData')
    lines.append(f'')
    total_fields = sum(b['fields'] for b in REGISTERED_BUNDLES)
    lines.append(f'| Bundle | 字段数 | 时间窗口 | Slot | 状态 |')
    lines.append(f'|--------|--------|----------|------|------|')
    for b in REGISTERED_BUNDLES:
        status = '✅ ' + b['status']
        lines.append(f"| {b['name']} | {b['fields']} | {b['window']} | {b['slot']} | {status} |")
    lines.append(f'')
    lines.append(f'共计: {len(REGISTERED_BUNDLES)} bundles, {total_fields} fields')
    lines.append(f'')

    # §2 已验证结论
    lines.append(f'## §二 已验证结论（Top {MAX_CONCLUSIONS}）')
    lines.append(f'')
    if log_data['conclusions']:
        for c in log_data['conclusions']:
            lines.append(c)
    else:
        lines.append('_尚无已验证结论_')
    lines.append(f'')

    # §3 已排除方向
    lines.append(f'## §三 已排除方向')
    lines.append(f'')
    if log_data['excluded']:
        lines.append('| 方向 | 原因 | 来源 |')
        lines.append('|------|------|------|')
        for e in log_data['excluded']:
            lines.append(e)
    else:
        lines.append('_尚无已排除方向_')
    lines.append(f'')

    # §4 研究方向池
    lines.append(f'## §四 研究方向池')
    lines.append(f'')
    if directions:
        lines.append('| ID | 名称 | 优先级 | 状态 | 认领者 |')
        lines.append('|----|------|--------|------|--------|')
        for d in directions:
            claimed = d.get('claimed_by', '-')
            lines.append(f"| {d.get('id','-')} | {d.get('name','-')} | {d.get('priority','-')} | {d.get('status','-')} | {claimed} |")
    else:
        lines.append('_方向池未初始化_')
    lines.append(f'')

    # §5 统计
    lines.append(f'## §五 实验统计')
    lines.append(f'')
    lines.append(log_data['stats'])
    lines.append(f'')

    # 截断到 MAX_KB_LINES
    result = '\n'.join(lines)
    result_lines = result.split('\n')
    if len(result_lines) > MAX_KB_LINES:
        result_lines = result_lines[:MAX_KB_LINES]
        result_lines.append('')
        result_lines.append(f'> ⚠️ 已截断至 {MAX_KB_LINES} 行。完整数据请查看 Layer 1。')
    return '\n'.join(result_lines)


def main():
    print("=== A-Share RawData KB Generator ===")

    # 1. 解析实验日志
    log_data = parse_experiment_log()
    print(f"  结论: {len(log_data['conclusions'])} 条")
    print(f"  排除方向: {len(log_data['excluded'])} 个")

    # 2. 加载方向池
    directions = load_direction_pool()
    available = sum(1 for d in directions if d.get('status') == 'available')
    exhausted = sum(1 for d in directions if d.get('status') == 'exhausted')
    print(f"  方向池: {len(directions)} 总, {available} 可用, {exhausted} 已穷尽")

    # 3. 渲染 KB
    kb_content = render_kb(log_data, directions)
    kb_lines = kb_content.count('\n')
    print(f"  KB 行数: {kb_lines}")

    # 4. 写入
    kb_path = PROJECT_ROOT / 'research' / 'KNOWLEDGE-BASE.md'
    kb_path.write_text(kb_content)
    print(f"  写入: {kb_path}")
    print("=== Done ===")


if __name__ == '__main__':
    main()
