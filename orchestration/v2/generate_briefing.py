#!/usr/bin/env python3
"""
Briefing Generator — 用 Sonnet 生成 cycle-specific 研究 briefing

将 KB、EXPERIMENT-LOG、feedback 等大文件浓缩为 ~200 行的精简上下文，
注入 researcher lean prompt，避免 Opus 每次重新读取全文。

Usage:
    python orchestration/v2/generate_briefing.py \
        --agent ashare_rawdata_a \
        --task-card "mode=research; direction_id=D-042; direction_name=vwap_micro; ..." \
        --output orchestration/state/briefings/ashare_rawdata_a_cycle5.md
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KB_PATH = os.path.join(PROJECT_DIR, 'research', 'KNOWLEDGE-BASE.md')
EXPERIMENT_LOG_PATH = os.path.join(PROJECT_DIR, 'research', 'EXPERIMENT-LOG.md')
POOL_PATH = os.path.join(PROJECT_DIR, 'orchestration', 'state', 'direction_pool.yaml')


EVAL_YAML_PATH = os.path.join(PROJECT_DIR, 'docs', 'params', 'evaluation.yaml')


def _load_eval_thresholds_summary() -> str:
    """从 evaluation.yaml (SSOT) 动态加载阈值，生成 Markdown 表格"""
    try:
        import yaml
        with open(EVAL_YAML_PATH, 'r') as f:
            params = yaml.safe_load(f) or {}
        lines = [
            "| 指标 | 阈值 |",
            "|------|------|",
            f"| LS Sharpe | > {params.get('sharpe_abs_net_min', '?')} |",
            f"| IR(LS) | > {params.get('ir_ls_min', '?')} |",
            f"| Long Excess Net Sharpe | > {params.get('long_excess_net_sharpe_min', '?')} |",
            f"| Mono | > {params.get('mono_min', '?')} |",
            f"| 覆盖率 | > {int(params.get('coverage_min', 0.3) * 100)}% |",
        ]
        return '\n'.join(lines)
    except Exception:
        return "→ 阈值见 docs/params/evaluation.yaml"


def parse_task_card(task_card: str) -> dict:
    """解析 task_card 字符串为字典"""
    result = {}
    for part in task_card.split(';'):
        part = part.strip()
        if '=' in part:
            key, value = part.split('=', 1)
            result[key.strip()] = value.strip()
    return result


def extract_kb_section(direction_name: str) -> str:
    """从 KNOWLEDGE-BASE.md 中提取与方向相关的结论"""
    if not os.path.exists(KB_PATH):
        return "(KB 文件不存在)"

    with open(KB_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取已注册因子列表（前 30 行概述区域）
    lines = content.split('\n')
    registered_section = []
    in_registered = False
    for line in lines[:150]:
        if '已注册' in line or 'registered' in line.lower() or '## 一' in line:
            in_registered = True
        if in_registered:
            registered_section.append(line)
            if len(registered_section) > 50:
                break
        if in_registered and line.startswith('## ') and '一' not in line:
            break

    # 提取与方向名相关的结论
    relevant_conclusions = []
    for i, line in enumerate(lines):
        if direction_name.lower() in line.lower() or direction_name.replace('_', ' ') in line.lower():
            start = max(0, i - 2)
            end = min(len(lines), i + 5)
            relevant_conclusions.extend(lines[start:end])
            relevant_conclusions.append('---')

    # 提取已排除方向列表
    excluded_section = []
    in_excluded = False
    for line in lines:
        if '排除' in line or 'exhausted' in line.lower():
            in_excluded = True
        if in_excluded:
            excluded_section.append(line)
            if len(excluded_section) > 40:
                break
        if in_excluded and line.startswith('## ') and '排除' not in line:
            break

    parts = []
    if registered_section:
        parts.append("### 已注册因子\n" + '\n'.join(registered_section[:30]))
    if relevant_conclusions:
        parts.append("### 与当前方向相关的结论\n" + '\n'.join(relevant_conclusions[:30]))
    if excluded_section:
        parts.append("### 已排除方向\n" + '\n'.join(excluded_section[:30]))

    return '\n\n'.join(parts) if parts else "(无相关 KB 内容)"


def extract_experiments(direction_name: str, direction_id: str = '') -> str:
    """从 EXPERIMENT-LOG.md 中提取与方向相关的历史实验"""
    if not os.path.exists(EXPERIMENT_LOG_PATH):
        return "(实验日志不存在)"

    with open(EXPERIMENT_LOG_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # 按 Experiment 块切分
    blocks = re.split(r'(?=### Experiment #)', content)
    relevant = []
    for block in blocks:
        if (direction_name.lower() in block.lower() or
                (direction_id and direction_id in block)):
            # 取每个 block 的前 20 行
            block_lines = block.strip().split('\n')[:20]
            relevant.append('\n'.join(block_lines))

    if relevant:
        return '\n\n---\n\n'.join(relevant[-5:])  # 最多 5 个最近的
    return "(无相关实验记录)"


def read_feedback(feedback_path: str) -> str:
    """读取 feedback 文件内容"""
    if not feedback_path or not os.path.exists(feedback_path):
        return ""
    try:
        with open(feedback_path, 'r', encoding='utf-8') as f:
            return f.read()[:1000]  # 最多 1000 字符
    except Exception:
        return ""


def get_direction_pool_summary() -> str:
    """获取方向池概要"""
    if not os.path.exists(POOL_PATH):
        return "(方向池不存在)"

    from scripts.utils.state_manager import read_state
    pool = read_state(POOL_PATH)
    directions = pool.get('directions', [])

    available = [d for d in directions if d.get('status') == 'available']
    claimed = [d for d in directions if d.get('status') == 'claimed']
    exhausted_count = len([d for d in directions if d.get('status') == 'exhausted'])

    lines = [f"可用: {len(available)} | 进行中: {len(claimed)} | 已穷尽: {exhausted_count}"]
    for d in available[:5]:
        lines.append(f"  - {d['id']} {d['name']} (priority: {d.get('priority', '?')})")

    return '\n'.join(lines)


def build_briefing_without_llm(agent_id: str, task_card_dict: dict) -> str:
    """
    纯 Python 构建 briefing（不调用 LLM）。

    当 Sonnet 不可用或为了节省 token 时使用此路径。
    实际上大部分 briefing 信息都可以通过 grep/parse 获得。
    """
    direction_name = task_card_dict.get('direction_name', 'unknown')
    direction_id = task_card_dict.get('direction_id', '')
    mode = task_card_dict.get('mode', 'research')
    description = task_card_dict.get('description', '')
    prev_notes = task_card_dict.get('prev_notes', '')
    feedback_path = task_card_dict.get('feedback_path', '')

    kb_section = extract_kb_section(direction_name)
    experiment_history = extract_experiments(direction_name, direction_id)
    feedback = read_feedback(feedback_path)
    pool_summary = get_direction_pool_summary()

    briefing_parts = [
        f"# Cycle Briefing — {agent_id}",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 当前任务",
        f"- **方向**: {direction_id} ({direction_name})",
        f"- **模式**: {mode}",
        f"- **描述**: {description}" if description else "",
        "",
    ]

    if prev_notes:
        briefing_parts.extend([
            "## 上轮笔记",
            prev_notes,
            "",
        ])

    if feedback:
        briefing_parts.extend([
            "## 反馈（来自上轮审阅）",
            feedback,
            "",
        ])

    briefing_parts.extend([
        "## 知识库摘要",
        kb_section,
        "",
        "## 相关实验历史",
        experiment_history,
        "",
        "## 方向池概况",
        pool_summary,
        "",
        "## 评估检查清单",
        _load_eval_thresholds_summary(),
        "",
        "## 提醒",
        "- 禁止重复已排除方向",
        "- 假设驱动，不做无意义数学变换",
        "- 单变量迭代，一次只改一个维度",
        "- 连续 2 个失败必须停下反思",
        f"- 方向研究完毕时，状态文件中设 current_direction: null + current_direction_id: null",
    ])

    return '\n'.join(briefing_parts)


def build_briefing_with_sonnet(agent_id: str, task_card_dict: dict, raw_context: str) -> str:
    """
    用 Sonnet 压缩 raw_context 为精简 briefing。

    仅在 raw_context 超过阈值时使用，否则直接用 Python 构建的版本。
    """
    prompt = f"""你是 A 股 RawData 研究 briefing 生成器。将以下原始上下文压缩为不超过 150 行的精简 briefing。

要求：
1. 保留所有关键数值（Sharpe、IC、Mono 等）
2. 保留已排除方向列表（防止重复）
3. 保留已失败的变体和原因
4. 保留 feedback 的具体要求
5. 删除通用说明和重复信息
6. 使用中文

Agent: {agent_id}
方向: {task_card_dict.get('direction_name', 'unknown')}

=== 原始上下文 ===
{raw_context}
=== 结束 ===

输出精简 briefing（Markdown 格式）:"""

    try:
        result = subprocess.run(
            ['claude', '--print', '-p', prompt, '--model', 'sonnet', '--max-turns', '1'],
            capture_output=True, text=True, timeout=120,
            cwd=PROJECT_DIR,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        print(f"[briefing] Sonnet 调用失败: {e}，回退到 Python 构建", file=sys.stderr)

    return None


def generate_briefing(agent_id: str, task_card: str, output_path: str,
                      use_sonnet: bool = True, sonnet_threshold: int = 3000):
    """
    生成 briefing 的主流程。

    1. 用 Python 收集 raw context（零 AI token）
    2. 如果 context 过长且 use_sonnet=True，用 Sonnet 压缩
    3. 否则直接使用 Python 构建的 briefing
    """
    task_card_dict = parse_task_card(task_card)

    # Step 1: Python 构建基础 briefing
    briefing = build_briefing_without_llm(agent_id, task_card_dict)

    # Step 2: 如果 briefing 过长，考虑 Sonnet 压缩
    line_count = len(briefing.split('\n'))
    if use_sonnet and line_count > sonnet_threshold // 20:
        compressed = build_briefing_with_sonnet(agent_id, task_card_dict, briefing)
        if compressed:
            briefing = compressed
            print(f"[briefing] Sonnet 压缩: {line_count} 行 → {len(compressed.split(chr(10)))} 行")

    # Step 3: 写入文件
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(briefing)

    print(f"[briefing] 生成完毕: {output_path} ({len(briefing.split(chr(10)))} 行)")
    return output_path


def main():
    parser = argparse.ArgumentParser(description='Briefing Generator')
    parser.add_argument('--agent', required=True, help='Agent ID')
    parser.add_argument('--task-card', required=True, help='Task card 字符串')
    parser.add_argument('--output', required=True, help='输出文件路径')
    parser.add_argument('--no-sonnet', action='store_true',
                        help='不使用 Sonnet 压缩，纯 Python 构建')
    args = parser.parse_args()

    generate_briefing(
        agent_id=args.agent,
        task_card=args.task_card,
        output_path=args.output,
        use_sonnet=not args.no_sonnet,
    )


if __name__ == '__main__':
    main()
