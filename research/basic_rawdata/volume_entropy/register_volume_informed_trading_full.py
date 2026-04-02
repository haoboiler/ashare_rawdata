#!/usr/bin/env python3
"""Volume-informed trading bundle for the full-day window.

Bundle: volume_informed_trading_full
- Input: close, volume (from 1m bars, 09:30-11:30 + 13:00-14:57)
- Output: 5 variables measuring volume-price interaction as informed trading proxies.

Hypothesis: Stocks where volume is more synchronized with price movements have
higher adverse selection costs, leading to worse microstructure quality and a
liquidity premium. This complements the pure volume distribution metrics in
volume_microstructure_full by incorporating price information.

Key novelty vs existing pv_stats:
- pv_stats captures linear correlations (return_volume_corr, kyle_lambda)
- This captures nonlinear/distributional aspects (joint entropy, regime transitions,
  conditional concentration)

Uses full-day window (~237 bars) for stable estimation per conclusion #11.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path("/home/gkh/ashare")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ashare_hf_variable.models import AShareRawDataDefinition, RawDataParams, RawDataSlot

NAME = "volume_informed_trading_full"

OUTPUT_NAMES = [
    "informed_trade_ratio_full",       # Volume on large-|return| bars / total volume
    "vol_return_sync_full",            # Lift of P(high_vol & high_|ret|) over independence
    "vol_regime_transitions_full",     # Volume regime reversal frequency (analogue of reversal_ratio)
    "vol_price_joint_entropy_full",    # Normalized joint entropy of (vol_tercile, ret_sign)
    "vol_weighted_return_std_full",    # Volume-weighted return volatility
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]

    n = close.size
    n_out = 5

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 30:
        return out

    # ---- Compute log returns and collect valid (return, volume) pairs ----
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    abs_rets = np.empty(n_ret, dtype=np.float64)
    vols = np.empty(n_ret, dtype=np.float64)
    valid_cnt = 0

    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        v = volume[i + 1]
        if np.isnan(c0) or np.isnan(c1) or np.isnan(v) or c0 <= 0.0 or v <= 0.0:
            continue
        r = np.log(c1 / c0)
        rets[valid_cnt] = r
        abs_rets[valid_cnt] = abs(r)
        vols[valid_cnt] = v
        valid_cnt += 1

    if valid_cnt < 30:
        return out

    # ---- Compute medians via sorting ----
    # Sort abs_rets to find median
    sorted_abs_rets = np.empty(valid_cnt, dtype=np.float64)
    for i in range(valid_cnt):
        sorted_abs_rets[i] = abs_rets[i]
    sorted_abs_rets = np.sort(sorted_abs_rets)

    sorted_vols = np.empty(valid_cnt, dtype=np.float64)
    for i in range(valid_cnt):
        sorted_vols[i] = vols[i]
    sorted_vols = np.sort(sorted_vols)

    if valid_cnt % 2 == 0:
        median_abs_ret = (sorted_abs_rets[valid_cnt // 2 - 1] + sorted_abs_rets[valid_cnt // 2]) / 2.0
        median_vol = (sorted_vols[valid_cnt // 2 - 1] + sorted_vols[valid_cnt // 2]) / 2.0
    else:
        median_abs_ret = sorted_abs_rets[valid_cnt // 2]
        median_vol = sorted_vols[valid_cnt // 2]

    # ---- Find 75th percentile of abs_rets ----
    p75_idx = (3 * valid_cnt) // 4
    p75_abs_ret = sorted_abs_rets[p75_idx]

    total_vol = 0.0
    for i in range(valid_cnt):
        total_vol += vols[i]

    # ---- 0: informed_trade_ratio ----
    # Volume on bars with |return| > 75th percentile / total volume
    # High ratio = large trades cluster with big moves = adverse selection
    informed_vol = 0.0
    for i in range(valid_cnt):
        if abs_rets[i] > p75_abs_ret and p75_abs_ret > 1e-10:
            informed_vol += vols[i]
    if total_vol > 0.0:
        out[0] = informed_vol / total_vol

    # ---- 1: vol_return_sync ----
    # Lift = P(high_vol & high_|ret|) / (P(high_vol) * P(high_|ret|)) - 1
    # Positive lift = volume and returns are more synchronized than random
    high_vol_cnt = 0
    high_ret_cnt = 0
    both_high_cnt = 0
    for i in range(valid_cnt):
        hv = vols[i] > median_vol
        hr = abs_rets[i] > median_abs_ret
        if hv:
            high_vol_cnt += 1
        if hr:
            high_ret_cnt += 1
        if hv and hr:
            both_high_cnt += 1

    n_f = float(valid_cnt)
    p_hv = float(high_vol_cnt) / n_f
    p_hr = float(high_ret_cnt) / n_f
    p_both = float(both_high_cnt) / n_f
    expected = p_hv * p_hr
    if expected > 1e-10:
        out[1] = p_both / expected - 1.0

    # ---- 2: vol_regime_transitions ----
    # Fraction of bars where volume crosses median (volume reversal ratio)
    # Analogue of reversal_ratio for price direction
    # High transitions = no volume clustering = better liquidity
    transitions = 0
    prev_above = vols[0] > median_vol
    for i in range(1, valid_cnt):
        curr_above = vols[i] > median_vol
        if curr_above != prev_above:
            transitions += 1
        prev_above = curr_above

    if valid_cnt > 1:
        out[2] = float(transitions) / float(valid_cnt - 1)

    # ---- 3: vol_price_joint_entropy ----
    # Binned joint entropy: vol_tercile (3) x return_sign (3: neg/zero/pos) = 9 cells
    # Normalized by ln(9)
    # Find vol tercile thresholds
    t1_idx = valid_cnt // 3
    t2_idx = (2 * valid_cnt) // 3
    vol_t1 = sorted_vols[t1_idx]
    vol_t2 = sorted_vols[t2_idx]

    # Count 9 cells: vol_bin(0,1,2) x ret_sign(0=neg, 1=zero, 2=pos)
    counts = np.zeros(9, dtype=np.float64)
    for i in range(valid_cnt):
        v = vols[i]
        r = rets[i]
        if v <= vol_t1:
            vb = 0
        elif v <= vol_t2:
            vb = 1
        else:
            vb = 2
        if r < -1e-10:
            rs = 0
        elif r > 1e-10:
            rs = 2
        else:
            rs = 1
        idx = vb * 3 + rs
        counts[idx] += 1.0

    entropy = 0.0
    ln_9 = np.log(9.0)
    for i in range(9):
        p = counts[i] / n_f
        if p > 1e-15:
            entropy -= p * np.log(p)
    if ln_9 > 0.0:
        out[3] = entropy / ln_9

    # ---- 4: vol_weighted_return_std ----
    # sqrt(sum(v_i * r_i^2) / sum(v_i))
    # Measures volatility weighted by trading intensity
    vw_r2 = 0.0
    for i in range(valid_cnt):
        vw_r2 += vols[i] * rets[i] * rets[i]
    if total_vol > 0.0:
        out[4] = np.sqrt(vw_r2 / total_vol)

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "volume"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(
            input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]
        ),
        slot=RawDataSlot.EVENING,
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Volume-informed trading bundle for full-day window "
            "(09:30-11:30 + 13:00-14:57). 5 metrics measuring volume-price interaction "
            "as informed trading proxies: informed trade volume ratio, volume-return "
            "synchronization lift, volume regime transitions, joint entropy of "
            "volume-price bins, and volume-weighted return volatility."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the volume informed trading full-day bundle"
    )
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--skip-validate", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    definition = build_definition()
    if args.print_json or not args.register:
        print(json.dumps(definition.to_document(), indent=2, ensure_ascii=True))
    if args.register:
        from ashare_hf_variable.registry import upsert_definition
        upsert_definition(definition, validate=not args.skip_validate)
        print(f"registered: {definition.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
