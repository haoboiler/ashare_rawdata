"""
Pairwise ρ Gate — LS PnL 相关性检查（通用）

只比较 Long-Short PnL（benchmark 无关），用于两个场景：
  Layer 1 — vs rawdata pool: 内部去重，阈值 rawdata_ls_threshold (default 0.60)
  Layer 2 — vs alpha pool:   跨池硬性 gate，阈值 alpha_ls_threshold (default 0.70)

阈值从 evaluation.yaml → corr_gate.pairwise 读取。
"""

import pandas as pd

from . import GateResult


def _max_abs_corr(new_series: pd.Series, pool_df: pd.DataFrame) -> tuple[float, str]:
    """计算新序列与 pool 中所有列的 max |pearson ρ|"""
    if pool_df.empty:
        return 0.0, ''

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
    candidate_pnl_ls: pd.Series,
    pool_df: pd.DataFrame,
    *,
    threshold: float,
    gate_label: str = '',
) -> GateResult:
    """
    执行 pairwise ρ gate 检查（LS PnL only）。

    Args:
        candidate_pnl_ls: 候选因子的 Long-Short PnL 序列
        pool_df: pool 中所有已入库因子的 LS PnL (columns=因子名, index=日期)
        threshold: max |ρ| 上限，超过则拒绝
        gate_label: 日志标签，用于区分 'rawdata_pool' 或 'alpha_pool'

    Returns:
        GateResult
    """
    label = f"[{gate_label}] " if gate_label else ""

    if pool_df.empty:
        return GateResult(
            admitted=True,
            reason=f"{label}Pool 为空，跳过相关性检查",
            metrics={'num_compared': 0, 'pool_empty': True, 'gate_label': gate_label},
        )

    max_rho, most_similar = _max_abs_corr(candidate_pnl_ls, pool_df)
    n = len(pool_df.columns)

    metrics = {
        'gate_label': gate_label,
        'num_compared': n,
        'max_rho_ls': round(max_rho, 4),
        'most_similar': most_similar,
        'threshold': threshold,
    }

    admitted = max_rho < threshold

    if admitted:
        reason = f"{label}通过: max|ρ_LS|={max_rho:.3f} < {threshold} (n={n})"
    else:
        reason = (
            f"{label}冗余: max|ρ_LS|={max_rho:.3f} >= {threshold}"
            f" (most_similar: {most_similar}, n={n})"
        )

    return GateResult(admitted=admitted, reason=reason, metrics=metrics)
