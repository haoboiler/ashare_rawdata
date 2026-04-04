#!/usr/bin/env python3
"""
admit_rawdata.py — 统一入库入口

参照 ashare_alpha 的 admit_alpha.py 设计：
  1. Performance gate (check_screening.py)
  2. Correlation gate (可插拔: pairwise | incremental_sharpe)
  3. 打包 / 报告 / TG 通知

直接读取 alpha 侧 official cache 做相关性检查，不维护自己的 PnL cache。
所有阈值从 evaluation.yaml (SSOT) 读取。

Usage:
    # 完整流程：筛选 + 相关性检查 + 打包
    python scripts/admit_rawdata.py \
        --feature-name extreme_amihud_full \
        --pkl .claude-output/analysis/direction/extreme_amihud_full.pkl \
        --eval-dir .claude-output/evaluations/direction/extreme_amihud_full/ \
        --direction "D-042 (realized_quarticity)" \
        --agent-id ashare_rawdata_a

    # 只做相关性检查（跳过筛选）
    python scripts/admit_rawdata.py \
        --feature-name extreme_amihud_full \
        --eval-dir ... \
        --skip-screening --gate-only

    # 指定 gate 类型
    python scripts/admit_rawdata.py ... --gate incremental_sharpe

    # dry-run（不打包，只报告）
    python scripts/admit_rawdata.py ... --dry-run

    # JSON 输出
    python scripts/admit_rawdata.py ... --json

Return codes:
    0 — 通过（筛选 + gate 都通过）
    1 — 未通过（筛选或 gate 失败）
    2 — 错误
"""

import argparse
import json
import os
import pickle
import sys
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_YAML_PATH = PROJECT_ROOT / 'docs' / 'params' / 'evaluation.yaml'

sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))


def load_config() -> dict:
    """从 evaluation.yaml 加载完整配置"""
    with open(EVAL_YAML_PATH, 'r') as f:
        return yaml.safe_load(f)


def _execution_price_to_bucket(execution_price_field: str) -> str:
    """执行价字段 → cache bucket"""
    if '0930' in execution_price_field or '1030' in execution_price_field:
        return 'am'
    return 'pm'


def _load_rawdata_pnl_pool() -> pd.DataFrame:
    """加载 rawdata 内部 LS PnL pool（来自 .claude-output/pnl_cache/pnl_cache.pkl）"""
    cache_path = PROJECT_ROOT / '.claude-output' / 'pnl_cache' / 'pnl_cache.pkl'
    if not cache_path.exists():
        return pd.DataFrame()
    with open(cache_path, 'rb') as f:
        data = pickle.load(f)
    if isinstance(data, dict):
        return data.get('ls_pnl', pd.DataFrame())
    return pd.DataFrame()


def _load_alpha_pnl_pool(alpha_root: str, composite_root: str, bucket: str) -> pd.DataFrame:
    """加载 alpha 侧 official cache 的 LS PnL pool（pnl_ls_df）"""
    bundle_path = Path(alpha_root) / composite_root / bucket / 'bundle.pkl'
    if not bundle_path.exists():
        return pd.DataFrame()
    with open(bundle_path, 'rb') as f:
        data = pickle.load(f)
    if isinstance(data, dict):
        return data.get('pnl_ls_df', pd.DataFrame())
    return pd.DataFrame()


def _load_pnl_from_eval(eval_dir: Path) -> tuple:
    """
    从评估产出中加载 PnL 序列。

    evaluate.py 不输出 admission_data.pkl（那是 alpha 侧的），
    但会输出 pnl_curve.pkl 或在 stats.json 旁边的序列数据。

    Returns:
        (pnl_series, pnl_ls_series) — 可能为 None
    """
    pnl = None
    pnl_ls = None

    # 查找各变体中的 PnL 数据
    for variant_dir in eval_dir.iterdir():
        if not variant_dir.is_dir():
            continue

        # 尝试读取 pnl_curve.pkl（如果 evaluate.py 输出了的话）
        for fname in ['pnl_curve.pkl', 'pnl_series.pkl', 'pnl.pkl']:
            path = variant_dir / fname
            if path.exists():
                with open(path, 'rb') as f:
                    data = pickle.load(f)
                if isinstance(data, pd.Series):
                    pnl = data
                elif isinstance(data, dict):
                    pnl = data.get('pnl', data.get('long_excess'))
                    pnl_ls = data.get('pnl_ls', data.get('long_short'))
                break

        # 尝试 admission_data.pkl（ashare_alpha 格式）
        adm_path = variant_dir / 'admission_data.pkl'
        if adm_path.exists():
            with open(adm_path, 'rb') as f:
                adm = pickle.load(f)
            pnl = adm.get('pnl')
            pnl_ls = adm.get('pnl_ls')
            break

        if pnl is not None:
            break

    return pnl, pnl_ls


def run_screening(eval_dir: Path, pkl_path: Path = None) -> dict:
    """运行 check_screening"""
    from check_screening import check_screening
    return check_screening(eval_dir, pkl_path)


def run_gate(
    eval_dir: Path,
    gate_type: str,
    config: dict,
) -> 'GateResult':
    """
    运行相关性 gate（两层，均为硬性 gate，LS PnL only）。

    pairwise gate 两层：
      Layer 1 — vs rawdata pool: 内部去重 (rawdata_ls_threshold)
      Layer 2 — vs alpha pool:   跨池硬性 gate (alpha_ls_threshold)

    任一层失败则整体 rejected。

    Args:
        eval_dir: 评估输出目录
        gate_type: 'pairwise' 或 'incremental_sharpe'
        config: evaluation.yaml 的完整配置

    Returns:
        GateResult（combined，包含两层 metrics）
    """
    from admit_gates import GateResult

    corr_config = config.get('corr_gate', {})
    alpha_cache_config = config.get('alpha_official_cache', {})
    alpha_root = alpha_cache_config.get('project_root', '')
    composite_root = alpha_cache_config.get('composite_root', '')
    bucket = _execution_price_to_bucket(config.get('execution_price_field', 'twap_1300_1400'))

    # 加载候选因子的 LS PnL
    _, pnl_ls = _load_pnl_from_eval(eval_dir)

    if pnl_ls is None:
        return GateResult(
            admitted=True,
            reason="评估产出中无 LS PnL 序列，跳过相关性检查",
            metrics={'pnl_ls_available': False},
        )

    if gate_type == 'incremental_sharpe':
        from admit_gates.incremental_sharpe import check_gate
        threshold = corr_config.get('incremental_sharpe', {}).get('threshold', 0.30)
        if not alpha_root or not Path(alpha_root).exists():
            return GateResult(
                admitted=True,
                reason=f"Alpha 项目不存在 ({alpha_root})，跳过增量 Sharpe 检查",
                metrics={'alpha_project_exists': False},
            )
        return check_gate(
            rawdata_pnl_ls=pnl_ls,
            threshold=threshold,
            alpha_project_root=alpha_root,
            composite_root=composite_root,
            bucket=bucket,
        )

    elif gate_type == 'pairwise':
        from admit_gates.pairwise import check_gate
        pw_config = corr_config.get('pairwise', {})
        rawdata_threshold = pw_config.get('rawdata_ls_threshold', 0.60)
        alpha_threshold = pw_config.get('alpha_ls_threshold', 0.70)

        combined_metrics = {}

        # Layer 1: vs rawdata pool (内部去重)
        rawdata_pool = _load_rawdata_pnl_pool()
        r1 = check_gate(
            candidate_pnl_ls=pnl_ls,
            pool_df=rawdata_pool,
            threshold=rawdata_threshold,
            gate_label='rawdata_pool',
        )
        combined_metrics['layer1_rawdata'] = r1.metrics
        if not r1.admitted:
            return GateResult(
                admitted=False,
                reason=f"Layer1 {r1.reason}",
                metrics=combined_metrics,
            )

        # Layer 2: vs alpha pool (跨池硬性 gate)
        if not alpha_root or not Path(alpha_root).exists():
            combined_metrics['layer2_alpha'] = {'skipped': True, 'reason': f'alpha_root不存在: {alpha_root}'}
            return GateResult(
                admitted=True,
                reason=f"Layer1 {r1.reason} | Layer2 skipped (alpha_root不存在)",
                metrics=combined_metrics,
            )

        alpha_pool = _load_alpha_pnl_pool(alpha_root, composite_root, bucket)
        r2 = check_gate(
            candidate_pnl_ls=pnl_ls,
            pool_df=alpha_pool,
            threshold=alpha_threshold,
            gate_label='alpha_pool',
        )
        combined_metrics['layer2_alpha'] = r2.metrics

        admitted = r2.admitted
        reason = f"Layer1 {r1.reason} | Layer2 {r2.reason}"
        return GateResult(admitted=admitted, reason=reason, metrics=combined_metrics)

    else:
        return GateResult(
            admitted=False,
            reason=f"未知 gate 类型: {gate_type}",
        )


def admit_rawdata(
    feature_name: str,
    pkl_path: Path,
    eval_dir: Path,
    report_path: Path = None,
    direction: str = '',
    agent_id: str = '',
    gate_type: str = None,
    skip_screening: bool = False,
    gate_only: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    统一入库流程。

    Returns:
        {
            'status': 'passed' | 'rejected' | 'dry_run' | 'error',
            'feature_name': str,
            'screening': {...} | None,
            'gate': {...} | None,
            'package_dir': str | None,
            'summary': str,
        }
    """
    config = load_config()

    if gate_type is None:
        gate_type = config.get('corr_gate', {}).get('default_gate', 'pairwise')

    result = {
        'status': 'error',
        'feature_name': feature_name,
        'screening': None,
        'gate': None,
        'package_dir': None,
    }

    # Step 1: Performance gate (check_screening)
    if not skip_screening:
        screening = run_screening(eval_dir, pkl_path)
        result['screening'] = screening

        if not screening['passed']:
            result['status'] = 'rejected'
            result['summary'] = f"筛选未通过: {screening['summary']}"
            return result
    else:
        result['screening'] = {'passed': True, 'summary': 'skipped'}

    # Step 2: Correlation gate
    gate_result = run_gate(eval_dir, gate_type, config)
    result['gate'] = {
        'gate_type': gate_type,
        'admitted': gate_result.admitted,
        'reason': gate_result.reason,
        'metrics': gate_result.metrics,
    }

    if not gate_result.admitted:
        result['status'] = 'rejected'
        result['summary'] = f"Gate 未通过 ({gate_type}): {gate_result.reason}"
        return result

    # Step 3: 打包
    if gate_only or dry_run:
        result['status'] = 'dry_run' if dry_run else 'passed'
        result['summary'] = f"通过 (gate={gate_type}): {gate_result.reason}"
        return result

    from create_pending_pkg import create_package
    pkg_dir = create_package(
        feature_name=feature_name,
        pkl_path=pkl_path,
        eval_dir=eval_dir,
        report_path=report_path,
        direction=direction,
        agent_id=agent_id,
        screening_result=result.get('screening'),
    )
    result['package_dir'] = str(pkg_dir)
    result['status'] = 'passed'
    result['summary'] = f"通过并打包: {pkg_dir}"

    return result


def main():
    parser = argparse.ArgumentParser(description='Raw-Data 统一入库入口')
    parser.add_argument('--feature-name', required=True)
    parser.add_argument('--pkl', default=None, help='因子 pkl 路径')
    parser.add_argument('--eval-dir', required=True, help='评估输出目录')
    parser.add_argument('--report', default=None, help='筛选报告路径')
    parser.add_argument('--direction', default='')
    parser.add_argument('--agent-id', default='')
    parser.add_argument('--gate', default=None,
                        choices=['pairwise', 'incremental_sharpe'],
                        help='Gate 类型（默认从 evaluation.yaml 读取）')
    parser.add_argument('--skip-screening', action='store_true',
                        help='跳过 performance gate')
    parser.add_argument('--gate-only', action='store_true',
                        help='只做 gate 检查，不打包')
    parser.add_argument('--dry-run', action='store_true',
                        help='干跑，不实际打包')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    args = parser.parse_args()

    eval_dir = Path(args.eval_dir).resolve()
    pkl_path = Path(args.pkl).resolve() if args.pkl else None

    if not eval_dir.exists():
        print(f"评估目录不存在: {eval_dir}", file=sys.stderr)
        sys.exit(2)

    result = admit_rawdata(
        feature_name=args.feature_name,
        pkl_path=pkl_path,
        eval_dir=eval_dir,
        report_path=Path(args.report).resolve() if args.report else None,
        direction=args.direction,
        agent_id=args.agent_id,
        gate_type=args.gate,
        skip_screening=args.skip_screening,
        gate_only=args.gate_only,
        dry_run=args.dry_run,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        status_emoji = {'passed': '✅', 'rejected': '❌', 'dry_run': '🔍', 'error': '⚠️'}
        emoji = status_emoji.get(result['status'], '?')

        print(f"\n{'='*60}")
        print(f"  {emoji} {result['status'].upper()}: {args.feature_name}")
        print(f"{'='*60}")

        if result.get('screening') and result['screening'].get('summary') != 'skipped':
            s = result['screening']
            print(f"\n  Performance Gate: {'✅' if s['passed'] else '❌'} {s.get('summary', '')}")

        if result.get('gate'):
            g = result['gate']
            print(f"  Correlation Gate ({g['gate_type']}): {'✅' if g['admitted'] else '❌'} {g['reason']}")
            if g.get('metrics'):
                for layer_key in ('layer1_rawdata', 'layer2_alpha'):
                    layer = g['metrics'].get(layer_key)
                    if layer and isinstance(layer, dict):
                        label = 'rawdata_pool' if 'rawdata' in layer_key else 'alpha_pool'
                        skip = layer.get('skipped') or layer.get('pool_empty')
                        rho = layer.get('max_rho_ls', '')
                        thr = layer.get('threshold', '')
                        sim = layer.get('most_similar', '')
                        if skip:
                            print(f"    {label}: skipped")
                        else:
                            print(f"    {label}: max|ρ|={rho}, threshold={thr}, most_similar={sim}")

        if result.get('package_dir'):
            print(f"\n  Package: {result['package_dir']}")

        print(f"\n  {result.get('summary', '')}\n")

    sys.exit(0 if result['status'] in ('passed', 'dry_run') else 1)


if __name__ == '__main__':
    main()
