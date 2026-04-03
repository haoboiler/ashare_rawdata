#!/usr/bin/env python3
"""
check_screening.py — 自动化筛选 pass/fail 判定

读取 evaluation.yaml (SSOT) 中的阈值，对评估产出 (stats.json + group_analysis.json)
进行自动化 pass/fail 判定。参照 ashare_alpha 的 check_pool_criteria.py。

Usage:
    # 检查单个评估目录
    python scripts/check_screening.py \
        --eval-dir .claude-output/evaluations/direction/feature/

    # 检查单个 pkl（自动寻找对应评估目录）
    python scripts/check_screening.py \
        --pkl .claude-output/analysis/direction/feature.pkl \
        --eval-dir .claude-output/evaluations/direction/feature/

    # 输出 JSON（供 pipeline 集成）
    python scripts/check_screening.py --eval-dir ... --json

Return codes:
    0 — 通过（至少 raw 或 neutralized 一组通过所有指标）
    1 — 未通过
    2 — 错误（文件缺失等）
"""

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_YAML_PATH = PROJECT_ROOT / 'docs' / 'params' / 'evaluation.yaml'


def load_thresholds() -> dict:
    """从 evaluation.yaml (SSOT) 加载阈值"""
    with open(EVAL_YAML_PATH, 'r') as f:
        params = yaml.safe_load(f)
    return {
        'sharpe_abs_net_min': params['sharpe_abs_net_min'],
        'ir_ls_min': params['ir_ls_min'],
        'long_excess_net_sharpe_min': params['long_excess_net_sharpe_min'],
        'mono_min': params['mono_min'],
        'coverage_min': params['coverage_min'],
    }


def find_eval_variants(eval_dir: Path) -> list[Path]:
    """发现评估目录下的所有变体（raw / neutralized）"""
    variants = []
    for d in sorted(eval_dir.iterdir()):
        if d.is_dir() and (d / 'stats.json').exists():
            variants.append(d)
    # 如果 eval_dir 本身就有 stats.json（无变体子目录）
    if not variants and (eval_dir / 'stats.json').exists():
        variants.append(eval_dir)
    return variants


def check_variant(variant_dir: Path, thresholds: dict) -> dict:
    """检查单个变体是否通过所有阈值"""
    stats_path = variant_dir / 'stats.json'
    group_path = variant_dir / 'group_analysis.json'

    with open(stats_path, 'r') as f:
        stats = json.load(f)

    # Monotonicity 来自 group_analysis.json
    mono_score = None
    if group_path.exists():
        with open(group_path, 'r') as f:
            group = json.load(f)
        mono_score = group.get('monotonicity_score')

    # 覆盖率需要从 pkl 计算（此处仅检查 stats 中是否有）
    # evaluate.py 不输出覆盖率，需单独计算
    coverage = stats.get('coverage', None)

    # 取绝对值（因子方向可能相反）
    sharpe_abs_net = abs(stats.get('sharpe_abs_net', 0))
    ir_ls = abs(stats.get('ir_ls', 0))
    long_excess = abs(stats.get('sharpe_long_excess_net', 0))

    checks = {
        'sharpe_abs_net': {
            'value': sharpe_abs_net,
            'threshold': thresholds['sharpe_abs_net_min'],
            'passed': sharpe_abs_net >= thresholds['sharpe_abs_net_min'],
            'field': 'sharpe_abs_net',
        },
        'ir_ls': {
            'value': ir_ls,
            'threshold': thresholds['ir_ls_min'],
            'passed': ir_ls >= thresholds['ir_ls_min'],
            'field': 'ir_ls',
        },
        'long_excess_net_sharpe': {
            'value': long_excess,
            'threshold': thresholds['long_excess_net_sharpe_min'],
            'passed': long_excess >= thresholds['long_excess_net_sharpe_min'],
            'field': 'sharpe_long_excess_net',
        },
        'mono': {
            'value': mono_score,
            'threshold': thresholds['mono_min'],
            'passed': (mono_score is not None and mono_score >= thresholds['mono_min']),
            'field': 'group_analysis.monotonicity_score',
        },
    }

    # 覆盖率：如果 stats 中没有，标记为 skip（需要从 pkl 单独计算）
    if coverage is not None:
        checks['coverage'] = {
            'value': coverage,
            'threshold': thresholds['coverage_min'],
            'passed': coverage >= thresholds['coverage_min'],
            'field': 'coverage',
        }
    else:
        checks['coverage'] = {
            'value': None,
            'threshold': thresholds['coverage_min'],
            'passed': None,  # 无法判定，需单独计算
            'field': 'coverage (需从 pkl 计算)',
        }

    all_passed = all(
        c['passed'] is True
        for c in checks.values()
        if c['passed'] is not None  # 跳过无法判定的
    )

    return {
        'variant': variant_dir.name,
        'variant_path': str(variant_dir),
        'all_passed': all_passed,
        'checks': checks,
    }


def check_coverage_from_pkl(pkl_path: Path, threshold: float) -> dict:
    """从 pkl 文件计算覆盖率"""
    import pandas as pd
    try:
        df = pd.read_pickle(pkl_path)
        total = df.size
        non_nan = df.notna().sum().sum()
        coverage = non_nan / total if total > 0 else 0
        return {
            'value': round(coverage, 4),
            'threshold': threshold,
            'passed': coverage >= threshold,
        }
    except Exception as e:
        return {
            'value': None,
            'threshold': threshold,
            'passed': None,
            'error': str(e),
        }


def check_screening(eval_dir: Path, pkl_path: Path = None) -> dict:
    """
    主筛选函数。

    Returns:
        {
            'passed': bool,
            'pkl_path': str | None,
            'eval_dir': str,
            'thresholds_source': str,
            'variants': [...],
            'coverage': {...} | None,
            'summary': str,
        }
    """
    thresholds = load_thresholds()
    variants = find_eval_variants(eval_dir)

    if not variants:
        return {
            'passed': False,
            'eval_dir': str(eval_dir),
            'thresholds_source': str(EVAL_YAML_PATH),
            'variants': [],
            'summary': f'无评估产出: {eval_dir}',
        }

    variant_results = []
    for v in variants:
        result = check_variant(v, thresholds)
        variant_results.append(result)

    # 覆盖率（从 pkl 计算，如果提供）
    coverage_result = None
    if pkl_path and pkl_path.exists():
        coverage_result = check_coverage_from_pkl(pkl_path, thresholds['coverage_min'])

    # 判定：任一变体（raw 或 neutralized）通过 + 覆盖率通过 → overall pass
    any_variant_passed = any(v['all_passed'] for v in variant_results)
    coverage_ok = (coverage_result is None or coverage_result.get('passed', False))

    overall_passed = any_variant_passed and coverage_ok

    # 生成摘要
    passed_variants = [v['variant'] for v in variant_results if v['all_passed']]
    failed_variants = [v['variant'] for v in variant_results if not v['all_passed']]

    if overall_passed:
        summary = f"PASSED — 通过变体: {', '.join(passed_variants)}"
    else:
        # 列出失败原因
        reasons = []
        for v in variant_results:
            failed_checks = [
                f"{name}={c['value']}<{c['threshold']}"
                for name, c in v['checks'].items()
                if c['passed'] is False
            ]
            if failed_checks:
                reasons.append(f"{v['variant']}: {', '.join(failed_checks)}")
        if coverage_result and not coverage_result.get('passed', True):
            reasons.append(f"coverage={coverage_result['value']}<{coverage_result['threshold']}")
        summary = f"FAILED — {'; '.join(reasons)}"

    return {
        'passed': overall_passed,
        'pkl_path': str(pkl_path) if pkl_path else None,
        'eval_dir': str(eval_dir),
        'thresholds_source': str(EVAL_YAML_PATH),
        'variants': variant_results,
        'coverage': coverage_result,
        'summary': summary,
    }


def main():
    parser = argparse.ArgumentParser(description='Raw-Data 自动筛选 pass/fail')
    parser.add_argument('--eval-dir', required=True, help='评估输出目录')
    parser.add_argument('--pkl', default=None, help='因子 pkl 文件（用于计算覆盖率）')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    args = parser.parse_args()

    eval_dir = Path(args.eval_dir).resolve()
    pkl_path = Path(args.pkl).resolve() if args.pkl else None

    if not eval_dir.exists():
        print(f"评估目录不存在: {eval_dir}", file=sys.stderr)
        sys.exit(2)

    result = check_screening(eval_dir, pkl_path)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"\n{'='*60}")
        print(f"  筛选结果: {'✅ PASSED' if result['passed'] else '❌ FAILED'}")
        print(f"  阈值来源: {result['thresholds_source']}")
        print(f"{'='*60}")

        for v in result['variants']:
            status = '✅' if v['all_passed'] else '❌'
            print(f"\n  {status} {v['variant']}:")
            for name, c in v['checks'].items():
                check_status = '✅' if c['passed'] else ('❌' if c['passed'] is False else '⚠️')
                val = f"{c['value']:.4f}" if isinstance(c['value'], float) else str(c['value'])
                print(f"    {check_status} {name}: {val} (>= {c['threshold']})")

        if result.get('coverage'):
            c = result['coverage']
            status = '✅' if c.get('passed') else '❌'
            val = f"{c['value']:.4f}" if c.get('value') is not None else '?'
            print(f"\n  {status} coverage: {val} (>= {c['threshold']})")

        print(f"\n  {result['summary']}\n")

    sys.exit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
