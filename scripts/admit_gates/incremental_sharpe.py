"""
Incremental Sharpe Gate — 基于 OLS 回归残差 Sharpe 的增量价值检测

参照 ashare_alpha 的 incremental_sharpe gate：
  new_pnl = β₀ + Σ βᵢ·pool_factor_i_pnl + ε
  incr_sharpe = β₀ / std(ε) × √252

直接读取 alpha 侧 official cache (bundle.pkl)。
阈值从 evaluation.yaml → corr_gate.incremental_sharpe 读取。
"""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from . import GateResult


def _load_alpha_cache(alpha_project_root: str, composite_root: str, bucket: str):
    """加载 alpha 侧 official cache"""
    import pickle

    cache_dir = Path(alpha_project_root) / composite_root / bucket
    bundle_path = cache_dir / 'bundle.pkl'

    if not bundle_path.exists():
        return None

    with open(bundle_path, 'rb') as f:
        return pickle.load(f)


def _compute_incremental_sharpe(
    new_series: pd.Series,
    pool_df: pd.DataFrame,
    annualize_factor: float = np.sqrt(252),
) -> dict:
    """
    OLS 回归计算增量 Sharpe。

    new = β₀ + Σ βᵢ·poolᵢ + ε
    incr_sharpe = (β₀ / std(ε)) × √252

    Returns:
        {'incr_sharpe': float, 'alpha_daily': float, 'r_squared': float, 'n_obs': int}
    """
    # 对齐索引
    combined = pool_df.copy()
    combined['__new__'] = new_series
    combined = combined.dropna()

    if len(combined) < 60:
        return {
            'incr_sharpe': float('nan'),
            'alpha_daily': float('nan'),
            'r_squared': float('nan'),
            'n_obs': len(combined),
            'error': 'insufficient observations (<60)',
        }

    y = combined['__new__'].values
    X = combined.drop(columns=['__new__']).values

    # 添加截距
    n = len(y)
    X_with_const = np.column_stack([np.ones(n), X])

    # OLS: (X'X)^{-1} X'y
    try:
        # 使用 ridge 正则化防止多重共线性
        lam = 1e-6
        XtX = X_with_const.T @ X_with_const
        XtX += lam * np.eye(XtX.shape[0])
        betas = np.linalg.solve(XtX, X_with_const.T @ y)
    except np.linalg.LinAlgError:
        return {
            'incr_sharpe': float('nan'),
            'alpha_daily': float('nan'),
            'r_squared': float('nan'),
            'n_obs': n,
            'error': 'singular matrix',
        }

    alpha_daily = betas[0]  # 截距 = Jensen's alpha
    residuals = y - X_with_const @ betas
    resid_std = residuals.std()

    if resid_std < 1e-12:
        incr_sharpe = 0.0
    else:
        incr_sharpe = (alpha_daily / resid_std) * annualize_factor

    # R²
    ss_res = (residuals ** 2).sum()
    ss_tot = ((y - y.mean()) ** 2).sum()
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return {
        'incr_sharpe': float(incr_sharpe),
        'alpha_daily': float(alpha_daily),
        'r_squared': float(r_squared),
        'n_obs': n,
    }


def check_gate(
    rawdata_pnl_ls: pd.Series,
    *,
    threshold: float,
    alpha_project_root: str,
    composite_root: str,
    bucket: str,
) -> GateResult:
    """
    执行 incremental Sharpe gate 检查。

    Args:
        rawdata_pnl_ls: Raw-data 因子的 LS PnL 序列
        threshold: 增量 Sharpe 下限
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
            reason=f"Alpha cache 不存在 ({bucket})，跳过增量 Sharpe 检查",
            metrics={'num_compared': 0, 'cache_exists': False},
        )

    pnl_ls_df = cache.get('pnl_ls_df', pd.DataFrame())
    n_alphas = len(pnl_ls_df.columns)

    if n_alphas == 0:
        return GateResult(
            admitted=True,
            reason="Alpha pool 为空，跳过增量 Sharpe 检查",
            metrics={'num_compared': 0, 'cache_exists': True},
        )

    result = _compute_incremental_sharpe(rawdata_pnl_ls, pnl_ls_df)

    metrics = {
        'num_compared': n_alphas,
        'cache_exists': True,
        'incr_sharpe': round(result['incr_sharpe'], 4) if not np.isnan(result['incr_sharpe']) else None,
        'alpha_daily_bps': round(result['alpha_daily'] * 10000, 2) if not np.isnan(result['alpha_daily']) else None,
        'r_squared': round(result['r_squared'], 4) if not np.isnan(result['r_squared']) else None,
        'n_obs': result['n_obs'],
        'threshold': threshold,
    }

    if result.get('error'):
        return GateResult(
            admitted=False,
            reason=f"计算失败: {result['error']}",
            metrics=metrics,
        )

    admitted = result['incr_sharpe'] >= threshold

    if admitted:
        reason = (
            f"通过: incr_sharpe={result['incr_sharpe']:.3f}>={threshold}, "
            f"alpha={result['alpha_daily']*10000:.1f}bps/day, R²={result['r_squared']:.3f}"
        )
    else:
        reason = (
            f"增量不足: incr_sharpe={result['incr_sharpe']:.3f}<{threshold}, "
            f"alpha={result['alpha_daily']*10000:.1f}bps/day, R²={result['r_squared']:.3f}"
        )

    return GateResult(admitted=admitted, reason=reason, metrics=metrics)
