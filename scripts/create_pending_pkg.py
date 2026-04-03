#!/usr/bin/env python3
"""
create_pending_pkg.py — 自动打包 pending-rawdata

将通过筛选的因子自动打包到 research/pending-rawdata/{feature_name}/，
替代 researcher prompt 中的手动 bash 命令。

Usage:
    python scripts/create_pending_pkg.py \
        --feature-name extreme_amihud_full \
        --pkl .claude-output/analysis/direction/extreme_amihud_full.pkl \
        --eval-dir .claude-output/evaluations/direction/extreme_amihud_full/ \
        --report research/agent_reports/screening/report.md \
        --direction "D-042 (realized_quarticity)" \
        --agent-id ashare_rawdata_a

    # 带 --check 自动执行筛选检查
    python scripts/create_pending_pkg.py \
        --feature-name extreme_amihud_full \
        --pkl ... --eval-dir ... --report ... \
        --check
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PENDING_DIR = PROJECT_ROOT / 'research' / 'pending-rawdata'


def find_charts(eval_dir: Path) -> list[tuple[str, Path]]:
    """查找评估图表"""
    charts = []
    for variant_dir in eval_dir.iterdir():
        if not variant_dir.is_dir():
            continue
        charts_dir = variant_dir / 'charts'
        if not charts_dir.exists():
            continue
        prefix = 'w1'
        for chart in sorted(charts_dir.glob('*.png')):
            label = f"{prefix}_{chart.stem}"
            charts.append((label, chart))
    return charts


def create_package(
    feature_name: str,
    pkl_path: Path,
    eval_dir: Path,
    report_path: Path = None,
    direction: str = '',
    agent_id: str = '',
    screening_result: dict = None,
) -> Path:
    """
    创建 pending package 目录。

    Returns:
        pending package 目录路径
    """
    pkg_dir = PENDING_DIR / feature_name
    charts_dir = pkg_dir / 'eval_charts'

    if pkg_dir.exists():
        print(f"[pending] 警告: {pkg_dir} 已存在，将覆盖")
        shutil.rmtree(pkg_dir)

    pkg_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    # 1. 符号链接因子 pkl
    pkl_link = pkg_dir / 'factor_values.pkl'
    pkl_abs = pkl_path.resolve()
    if pkl_abs.exists():
        pkl_link.symlink_to(pkl_abs)
        print(f"[pending] pkl → {pkl_abs}")

    # 2. 复制报告
    if report_path and report_path.exists():
        shutil.copy2(report_path, pkg_dir / 'report.md')
        print(f"[pending] report → {pkg_dir / 'report.md'}")

    # 3. 复制评估图表
    charts = find_charts(eval_dir)
    for label, chart_path in charts:
        dst = charts_dir / f"{label}.png"
        shutil.copy2(chart_path, dst)
    if charts:
        print(f"[pending] {len(charts)} 张图表 → {charts_dir}")

    # 4. 复制 stats.json 和 group_analysis.json
    for variant_dir in eval_dir.iterdir():
        if not variant_dir.is_dir():
            continue
        for fname in ['stats.json', 'group_analysis.json']:
            src = variant_dir / fname
            if src.exists():
                dst_name = f"{variant_dir.name}_{fname}"
                shutil.copy2(src, pkg_dir / dst_name)

    # 5. 写 screening_result.json（如果有）
    if screening_result:
        with open(pkg_dir / 'screening_result.json', 'w') as f:
            json.dump(screening_result, f, ensure_ascii=False, indent=2, default=str)

    # 6. 写 package_info.yaml
    info = {
        'feature_name': feature_name,
        'direction': direction,
        'agent_id': agent_id,
        'created_at': datetime.now().isoformat(),
        'pkl_path': str(pkl_abs) if pkl_abs.exists() else str(pkl_path),
        'eval_dir': str(eval_dir),
        'report_path': str(report_path) if report_path else None,
        'screening_passed': screening_result['passed'] if screening_result else None,
        'num_charts': len(charts),
    }
    import yaml
    with open(pkg_dir / 'package_info.yaml', 'w') as f:
        yaml.dump(info, f, default_flow_style=False, allow_unicode=True)

    print(f"[pending] ✅ Package 创建完成: {pkg_dir}")
    return pkg_dir


def main():
    parser = argparse.ArgumentParser(description='创建 pending-rawdata package')
    parser.add_argument('--feature-name', required=True, help='特征名')
    parser.add_argument('--pkl', required=True, help='因子 pkl 路径')
    parser.add_argument('--eval-dir', required=True, help='评估输出目录')
    parser.add_argument('--report', default=None, help='筛选报告路径')
    parser.add_argument('--direction', default='', help='方向（如 D-042 (name)）')
    parser.add_argument('--agent-id', default='', help='Agent ID')
    parser.add_argument('--check', action='store_true',
                        help='先运行 check_screening，通过才打包')
    args = parser.parse_args()

    pkl_path = Path(args.pkl).resolve()
    eval_dir = Path(args.eval_dir).resolve()
    report_path = Path(args.report).resolve() if args.report else None

    if not eval_dir.exists():
        print(f"评估目录不存在: {eval_dir}", file=sys.stderr)
        sys.exit(2)

    screening_result = None
    if args.check:
        from check_screening import check_screening
        screening_result = check_screening(eval_dir, pkl_path)
        if not screening_result['passed']:
            print(f"[pending] ❌ 筛选未通过: {screening_result['summary']}")
            sys.exit(1)
        print(f"[pending] ✅ 筛选通过: {screening_result['summary']}")

    pkg_dir = create_package(
        feature_name=args.feature_name,
        pkl_path=pkl_path,
        eval_dir=eval_dir,
        report_path=report_path,
        direction=args.direction,
        agent_id=args.agent_id,
        screening_result=screening_result,
    )

    sys.exit(0)


if __name__ == '__main__':
    main()
