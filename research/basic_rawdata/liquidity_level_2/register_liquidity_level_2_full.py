#!/usr/bin/env python3
"""Register the liquidity level batch 2 bundle for the full-day window.

Bundle: liquidity_level_2_0930_1130_1300_1457
- Input: close, amount (from 1m bars)
- Output: 3 variables capturing different aspects of intraday liquidity.

Full-day window (237 bars) for stable estimates.

Physical hypothesis:
1. Zero-return ratio (Lesmond et al. 1999): Fraction of bars with exactly zero return.
   When transaction costs exceed informed traders' signal, no trade occurs → price doesn't
   move → zero return. Higher zero-return ratio = less liquid stock = liquidity premium.
   Discrete counting method (validated by conclusion #16).

2. Illiquidity variability: Coefficient of variation (std/mean) of per-bar Amihud values
   (|return_i| / amount_i). Captures CONSISTENCY of liquidity rather than its level.
   High CV = unpredictable liquidity = higher risk premium. Uses amount (CNY) to avoid
   market-cap scaling (validated by conclusion #17).

3. High-volume illiquidity: Amihud illiquidity computed only during the top-quartile
   volume bars. Separates "active period price impact" from "quiet period price impact".
   If even high-volume bars show large price impact → truly illiquid (informed trading).
   Different from regular Amihud which averages across all activity levels.
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

NAME = "liquidity_level_2_0930_1130_1300_1457"

OUTPUT_NAMES = [
    "zero_return_ratio_full",       # Fraction of bars with zero return
    "illiq_variability_full",       # CV of per-bar Amihud illiquidity
    "high_vol_illiq_full",          # Amihud illiquidity on top-quartile volume bars only
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    amount = inputs[1]

    n = close.size
    n_out = 3

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 10:
        return out

    # --- Pre-compute returns ---
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    valid_ret_count = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0 or c1 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = c1 / c0 - 1.0
            valid_ret_count += 1

    if valid_ret_count < 10:
        return out

    # --- 0: zero_return_ratio_full ---
    # Fraction of valid bars with exactly zero return (|r| < 1e-10)
    zero_count = 0
    for i in range(n_ret):
        r = rets[i]
        if not np.isnan(r):
            if abs(r) < 1.0e-10:
                zero_count += 1
    if valid_ret_count > 0:
        out[0] = float(zero_count) / float(valid_ret_count)

    # --- Pre-compute per-bar Amihud: |return_i| / amount_i ---
    amihud_bars = np.empty(n_ret, dtype=np.float64)
    amihud_valid_count = 0
    for i in range(n_ret):
        r = rets[i]
        a = amount[i + 1]
        if not np.isnan(r) and not np.isnan(a) and a > 0.0:
            amihud_bars[i] = abs(r) / a
            amihud_valid_count += 1
        else:
            amihud_bars[i] = np.nan

    # --- 1: illiq_variability_full ---
    # CV = std(amihud_bar) / mean(amihud_bar)
    if amihud_valid_count >= 10:
        amihud_sum = 0.0
        for i in range(n_ret):
            if not np.isnan(amihud_bars[i]):
                amihud_sum += amihud_bars[i]
        amihud_mean = amihud_sum / amihud_valid_count

        if amihud_mean > 0.0:
            var_sum = 0.0
            for i in range(n_ret):
                if not np.isnan(amihud_bars[i]):
                    diff = amihud_bars[i] - amihud_mean
                    var_sum += diff * diff
            amihud_std = np.sqrt(var_sum / amihud_valid_count)
            out[1] = amihud_std / amihud_mean

    # --- 2: high_vol_illiq_full ---
    # Amihud on top-quartile amount bars only
    # First find the 75th percentile of amount
    valid_amounts = np.empty(n, dtype=np.float64)
    valid_amt_cnt = 0
    for i in range(n):
        a = amount[i]
        if not np.isnan(a) and a > 0.0:
            valid_amounts[valid_amt_cnt] = a
            valid_amt_cnt += 1

    if valid_amt_cnt >= 10:
        sorted_amounts = np.sort(valid_amounts[:valid_amt_cnt])
        # 75th percentile index
        p75_idx = int(valid_amt_cnt * 0.75)
        if p75_idx >= valid_amt_cnt:
            p75_idx = valid_amt_cnt - 1
        amount_p75 = sorted_amounts[p75_idx]

        # Compute Amihud only for bars where amount > p75
        high_vol_sum = 0.0
        high_vol_cnt = 0
        for i in range(n_ret):
            r = rets[i]
            a = amount[i + 1]
            if not np.isnan(r) and not np.isnan(a) and a > amount_p75:
                high_vol_sum += abs(r) / a
                high_vol_cnt += 1
        if high_vol_cnt > 0:
            out[2] = (high_vol_sum / high_vol_cnt) * 1.0e9

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]),
        slot=RawDataSlot.EVENING,
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Liquidity level factors batch 2 for full trading day "
            "(09:30-11:30 + 13:00-14:57). "
            "Emits 3 variables: zero-return ratio (Lesmond 1999), "
            "Amihud illiquidity CV (consistency), "
            "and high-volume-bar Amihud (informed trading). "
            "237 bars for stable estimates."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the liquidity level batch 2 full-day bundle"
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
