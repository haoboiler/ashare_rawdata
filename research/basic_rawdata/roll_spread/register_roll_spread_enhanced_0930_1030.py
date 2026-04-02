#!/usr/bin/env python3
"""Enhanced liquidity features for the 09:30-10:30 window.

Bundle: roll_spread_enhanced_0930_1030
- Input: close, volume, amount (from 1m bars)
- Output: 5 enhanced liquidity variables.

Based on quick-eval insights:
- zero_return_pct showed strongest IR (0.36) and first positive LE (+0.37)
- reversal_ratio showed first LE above threshold (+0.77) but weak Sharpe

Enhanced features explore:
1. Volume-weighted zero return — weights by volume to reduce noise
2. Absolute return intensity — average |return|, inversely related to liquidity
3. Small-trade ratio — proportion of low-volume bars (retail proxy)
4. Return concentration — Herfindahl of |returns| (information clustering)
5. Neg reversal asymmetry — down→up vs up→down reversal ratio (sell pressure)
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

NAME = "roll_spread_enhanced_0930_1030"

OUTPUT_NAMES = [
    "vol_weighted_zero_ret_0930_1030",    # Volume-weighted zero-return score
    "abs_return_intensity_0930_1030",      # mean(|log_return|) — trade activity
    "small_trade_ratio_0930_1030",         # Fraction of bars with volume < median
    "return_concentration_0930_1030",      # Herfindahl of |returns| (info clustering)
    "reversal_asymmetry_0930_1030",        # (down→up reversals) / (up→down reversals)
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]
    amount = inputs[2]

    n = close.size
    n_out = 5

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 5:
        return out

    # ---- Pre-compute log returns ----
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    valid_ret_count = 0

    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = np.log(c1 / c0)
            valid_ret_count += 1

    if valid_ret_count < 5:
        return out

    # ---- 0: vol_weighted_zero_ret ----
    # Volume-weighted proportion of zero-return bars
    # Weight each bar's zero-return indicator by its volume
    vw_zero_sum = 0.0
    vw_total = 0.0
    for i in range(n_ret):
        r = rets[i]
        v = volume[i + 1]
        if np.isnan(r) or np.isnan(v) or v <= 0.0:
            continue
        vw_total += v
        if abs(r) < 1e-12:
            vw_zero_sum += v
    if vw_total > 0.0:
        out[0] = vw_zero_sum / vw_total * 100.0

    # ---- 1: abs_return_intensity ----
    # mean(|log_return|) — lower = more liquid / less volatile
    abs_ret_sum = 0.0
    abs_ret_cnt = 0
    for i in range(n_ret):
        r = rets[i]
        if not np.isnan(r):
            abs_ret_sum += abs(r)
            abs_ret_cnt += 1
    if abs_ret_cnt > 0:
        out[1] = abs_ret_sum / abs_ret_cnt

    # ---- 2: small_trade_ratio ----
    # Fraction of bars with volume below median
    # First find median volume
    vol_vals = np.empty(n, dtype=np.float64)
    vol_cnt = 0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v) and v > 0.0:
            vol_vals[vol_cnt] = v
            vol_cnt += 1

    if vol_cnt >= 5:
        # Simple median: sort and take middle
        for i in range(vol_cnt):
            for j in range(i + 1, vol_cnt):
                if vol_vals[j] < vol_vals[i]:
                    tmp = vol_vals[i]
                    vol_vals[i] = vol_vals[j]
                    vol_vals[j] = tmp
        median_vol = vol_vals[vol_cnt // 2]

        # Count bars below median
        below_cnt = 0
        for i in range(vol_cnt):
            if vol_vals[i] < median_vol:
                below_cnt += 1
        out[2] = float(below_cnt) / float(vol_cnt)

    # ---- 3: return_concentration ----
    # Herfindahl index of |returns|: sum((|r_i| / sum(|r|))^2)
    # High = returns concentrated in few bars (information clustering)
    if abs_ret_sum > 1e-15 and abs_ret_cnt >= 5:
        hhi = 0.0
        for i in range(n_ret):
            r = rets[i]
            if not np.isnan(r):
                share = abs(r) / abs_ret_sum
                hhi += share * share
        out[3] = hhi

    # ---- 4: reversal_asymmetry ----
    # Ratio of down→up reversals to up→down reversals
    # > 1 means more buying pressure after drops (recovery)
    # < 1 means more selling pressure after rises (distribution)
    du_cnt = 0  # down → up
    ud_cnt = 0  # up → down
    for i in range(1, n_ret):
        r0 = rets[i - 1]
        r1 = rets[i]
        if np.isnan(r0) or np.isnan(r1):
            continue
        if abs(r0) < 1e-12 or abs(r1) < 1e-12:
            continue
        if r0 < 0.0 and r1 > 0.0:
            du_cnt += 1
        elif r0 > 0.0 and r1 < 0.0:
            ud_cnt += 1

    if ud_cnt >= 3:
        out[4] = float(du_cnt) / float(ud_cnt)

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "volume", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "10:30")]),
        slot=RawDataSlot.MIDDAY,
        data_available_at=1031,
        execution_start_at=930,
        execution_end_at=1030,
        expected_bars=40,
        description=(
            "Enhanced liquidity features for 09:30-10:30. "
            "Volume-weighted zero-return, absolute return intensity, "
            "small-trade ratio, return concentration (HHI), "
            "and reversal asymmetry."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register enhanced Roll spread 09:30-10:30 bundle"
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
