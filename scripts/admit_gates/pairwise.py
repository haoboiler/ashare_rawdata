"""
Pairwise ρ Gate — 基于 PnL 相关性的冗余检测

对 rawdata 因子的 PnL 与 alpha 侧 official cache 中所有已入库 alpha 做 pairwise 相关性检查。
直接读取 alpha 侧 official cache (bundle.pkl)，不维护自己的 cache。

阈值从 evaluation.yaml → corr_gate.pairwise 读取。
"""

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from . import GateResult


def _load_alpha_cache(alpha_project_root: str, composite_root: str, bucket: str):
    """
    加载 alpha 侧 official cache。

    Returns:
        dict with keys: pnl_df, pnl_ls_df, ic_df, metadata
        或 None（cache 不存在）
    """
    import pickle

    cache_dir = Path(alpha_project_root) / composite_root / bucket
    bundle_path = cache_dir / 'bundle.pkl'

    if not bundle_path.exists():
        return None

    with open(bundle_path, 'rb') as f:
        data = pickle.load(f)

    return data


def _max_abs_corr(new_series: pd.Series, pool_df: pd.DataFrame) -> tuple[float, str]:
    """计算新序列与 pool 中所有列的 max |pearson ρ|"""
    if pool_df.empty:
        return 0.0, ''

    # 对齐索引
    combined = pool_df.copy()
    combined['__new__'] = new_series
    combined = combined.dropna(subset=['__new__'])

    if len(combined) < 30:
        return 0.0, '(insufficient overlap)'

    corrs = combined.drop(columns=['__new__']).corrwith(combined['__new__'])
    abs_corrs = corrs.abs()

    if abs_corrs.empty:
        return 0.0, ''

    max_idx = abs_corrs.idxmax()
    return float(abs_corrs[max_idx]), str(max_idx)


def check_gate(
    rawdata_pnl: pd.Series,
    rawdata_pnl_ls: Optional[pd.Series],
    *,
    ls_threshold: float,
    lb_threshold: float,
    alpha_project_root: str,
    composite_root: str,
    bucket: str,
) -> GateResult:
    """
    执行 pairwise ρ gate 检查。

    Args:
        rawdata_pnl: Raw-data 因子的 Long-Benchmark PnL 序列
        rawdata_pnl_ls: Raw-data 因子的 Long-Short PnL 序列（可选）
        ls_threshold: LS PnL max |ρ| 上限
        lb_threshold: Long-Benchmark PnL max |ρ| 上限
        alpha_project_root: alpha 项目根目录
        composite_root: official cache 相对路径
        bucket: 'am' 或 'pm'

    Returns:
        GateResult
    """
    cache = _load_alpha_cache(alpha_project_root, composite_root, bucket)

    if cache is None:
        return GateResult(
            admitted=True,
            reason=f"Alpha cache 不存在 ({bucket})，跳过相关性检查",
            metrics={'num_compared': 0, 'cache_exists': False},
        )

    pnl_df = cache.get('pnl_df', pd.DataFrame())
    pnl_ls_df = cache.get('pnl_ls_df', pd.DataFrame())
    n_alphas = len(pnl_df.columns)

    if n_alphas == 0:
        return GateResult(
            admitted=True,
            reason="Alpha pool 为空，跳过相关性检查",
            metrics={'num_compared': 0, 'cache_exists': True},
        )

    metrics = {'num_compared': n_alphas, 'cache_exists': True}

    # L2b: Long-Benchmark PnL
    max_rho_lb, most_similar_lb = _max_abs_corr(rawdata_pnl, pnl_df)
    metrics['max_rho_lb'] = round(max_rho_lb, 4)
    metrics['most_similar_lb'] = most_similar_lb
    metrics['lb_threshold'] = lb_threshold

    lb_passed = max_rho_lb < lb_threshold

    # L2a: LS PnL（如果提供）
    ls_passed = True
    if rawdata_pnl_ls is not None and not pnl_ls_df.empty:
        max_rho_ls, most_similar_ls = _max_abs_corr(rawdata_pnl_ls, pnl_ls_df)
        metrics['max_rho_ls'] = round(max_rho_ls, 4)
        metrics['most_similar_ls'] = most_similar_ls
        metrics['ls_threshold'] = ls_threshold
        ls_passed = max_rho_ls < ls_threshold

    admitted = lb_passed and ls_passed

    if admitted:
        reason = f"通过: max|ρ_LB|={max_rho_lb:.3f}<{lb_threshold}"
        if rawdata_pnl_ls is not None:
            reason += f", max|ρ_LS|={metrics.get('max_rho_ls', 0):.3f}<{ls_threshold}"
    else:
        reasons = []
        if not lb_passed:
            reasons.append(f"max|ρ_LB|={max_rho_lb:.3f}>={lb_threshold} (most_similar: {most_similar_lb})")
        if not ls_passed:
            reasons.append(f"max|ρ_LS|={metrics.get('max_rho_ls', 0):.3f}>={ls_threshold} (most_similar: {metrics.get('most_similar_ls', '')})")
        reason = f"冗余: {'; '.join(reasons)}"

    return GateResult(admitted=admitted, reason=reason, metrics=metrics)
