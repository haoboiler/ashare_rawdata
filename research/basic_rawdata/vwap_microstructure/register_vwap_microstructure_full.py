#!/usr/bin/env python3
"""VWAP Microstructure bundle — full-day window (09:30-11:30, 13:00-14:57).

D-016: VWAP-based microstructure factors.
Physical hypothesis: The bar-by-bar relationship between price and cumulative
VWAP captures trading orderliness and liquidity quality — a dimension orthogonal
to Amihud (price impact level) and reversal_ratio (direction switching).

Features:
  1. vwap_cross_freq_full   — frequency of price crossing cumulative VWAP (discrete)
  2. vwap_distance_full     — mean |close - VWAP| / VWAP (relative deviation level)
  3. vwap_distance_amihud_full — mean |close - VWAP| / mean(amount) (Amihud form)
  4. high_vol_vwap_amihud_full — above-median-volume bars only (conditioned Amihud)
  5. vwap_tracking_error_full — std(close/VWAP - 1) (volatility diagnostic)
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
from ashare_hf_variable.registry import upsert_definition

NAME = "vwap_microstructure_full"

OUTPUT_NAMES = [
    "vwap_cross_freq_full",
    "vwap_distance_full",
    "vwap_distance_amihud_full",
    "high_vol_vwap_amihud_full",
    "vwap_tracking_error_full",
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    open_ = inputs[1]
    high = inputs[2]
    low = inputs[3]
    volume = inputs[4]
    amount = inputs[5]

    n = close.size
    n_out = 5
    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 10:
        return out

    # ---- Compute cumulative VWAP at each bar ----
    # Use close as price (consistent with pv_stats VWAP definition)
    cum_pv = 0.0
    cum_v = 0.0
    vwap_arr = np.empty(n, dtype=np.float64)
    for i in range(n):
        c = close[i]
        v = volume[i]
        if np.isnan(c) or np.isnan(v) or v <= 0.0 or c <= 0.0:
            vwap_arr[i] = np.nan
            continue
        cum_pv += c * v
        cum_v += v
        if cum_v > 0.0:
            vwap_arr[i] = cum_pv / cum_v
        else:
            vwap_arr[i] = np.nan

    # ---- Feature 0: vwap_cross_freq_full ----
    # Count transitions of sign(close - VWAP)
    cross_count = 0
    prev_sign = 0
    valid_transitions = 0
    for i in range(n):
        c = close[i]
        vw = vwap_arr[i]
        if np.isnan(c) or np.isnan(vw) or vw <= 0.0:
            continue
        cur_sign = 1 if c > vw else -1
        if prev_sign != 0:
            valid_transitions += 1
            if cur_sign != prev_sign:
                cross_count += 1
        prev_sign = cur_sign
    if valid_transitions > 0:
        out[0] = float(cross_count) / float(valid_transitions)

    # ---- Feature 1: vwap_distance_full ----
    # mean(|close - VWAP| / VWAP)
    dist_sum = 0.0
    dist_cnt = 0
    for i in range(n):
        c = close[i]
        vw = vwap_arr[i]
        if np.isnan(c) or np.isnan(vw) or vw <= 0.0:
            continue
        dist_sum += abs(c - vw) / vw
        dist_cnt += 1
    if dist_cnt > 0:
        out[1] = dist_sum / float(dist_cnt)

    # ---- Feature 2: vwap_distance_amihud_full ----
    # mean(|close - VWAP|) / mean(amount)
    abs_dist_sum = 0.0
    abs_dist_cnt = 0
    amt_sum = 0.0
    amt_cnt = 0
    for i in range(n):
        c = close[i]
        vw = vwap_arr[i]
        a = amount[i]
        if np.isnan(c) or np.isnan(vw):
            continue
        abs_dist_sum += abs(c - vw)
        abs_dist_cnt += 1
        if not np.isnan(a) and a > 0.0:
            amt_sum += a
            amt_cnt += 1
    if abs_dist_cnt > 0 and amt_cnt > 0 and amt_sum > 0.0:
        out[2] = (abs_dist_sum / float(abs_dist_cnt)) / (amt_sum / float(amt_cnt))

    # ---- Feature 3: high_vol_vwap_amihud_full ----
    # Same as vwap_distance_amihud but only for above-median-volume bars
    # First compute volume median
    vol_valid = np.empty(n, dtype=np.float64)
    vol_valid_cnt = 0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v) and v > 0.0:
            vol_valid[vol_valid_cnt] = v
            vol_valid_cnt += 1

    if vol_valid_cnt >= 4:
        vol_sorted = vol_valid[:vol_valid_cnt].copy()
        # Simple insertion sort for median (Numba-compatible)
        for i in range(1, vol_valid_cnt):
            key = vol_sorted[i]
            j = i - 1
            while j >= 0 and vol_sorted[j] > key:
                vol_sorted[j + 1] = vol_sorted[j]
                j -= 1
            vol_sorted[j + 1] = key
        vol_median = vol_sorted[vol_valid_cnt // 2]

        hv_dist_sum = 0.0
        hv_amt_sum = 0.0
        hv_cnt = 0
        for i in range(n):
            c = close[i]
            vw = vwap_arr[i]
            v = volume[i]
            a = amount[i]
            if np.isnan(c) or np.isnan(vw) or np.isnan(v) or np.isnan(a):
                continue
            if v > vol_median and a > 0.0:
                hv_dist_sum += abs(c - vw)
                hv_amt_sum += a
                hv_cnt += 1
        if hv_cnt > 0 and hv_amt_sum > 0.0:
            out[3] = (hv_dist_sum / float(hv_cnt)) / (hv_amt_sum / float(hv_cnt))

    # ---- Feature 4: vwap_tracking_error_full ----
    # std(close / VWAP - 1)
    ratio_sum = 0.0
    ratio_cnt = 0
    for i in range(n):
        c = close[i]
        vw = vwap_arr[i]
        if np.isnan(c) or np.isnan(vw) or vw <= 0.0:
            continue
        ratio_sum += c / vw - 1.0
        ratio_cnt += 1
    if ratio_cnt >= 2:
        ratio_mean = ratio_sum / float(ratio_cnt)
        ss = 0.0
        for i in range(n):
            c = close[i]
            vw = vwap_arr[i]
            if np.isnan(c) or np.isnan(vw) or vw <= 0.0:
                continue
            d = c / vw - 1.0 - ratio_mean
            ss += d * d
        out[4] = np.sqrt(ss / float(ratio_cnt - 1))

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "open", "high", "low", "volume", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(
            input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]
        ),
        slot=RawDataSlot.EVENING,
        data_available_at=1500,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "VWAP microstructure bundle for full-day window. "
            "Measures bar-by-bar price-VWAP dynamics: crossing frequency, "
            "relative distance, Amihud-normalized distance, "
            "high-volume conditioned Amihud, and tracking error."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the VWAP microstructure full-day bundle"
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Write the definition into the configured registry backend",
    )
    parser.add_argument(
        "--skip-validate",
        action="store_true",
        help="Skip formula validation during registration",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print the definition JSON payload",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    definition = build_definition()

    if args.print_json or not args.register:
        print(json.dumps(definition.to_document(), indent=2, ensure_ascii=True))

    if args.register:
        upsert_definition(definition, validate=not args.skip_validate)
        print(f"registered: {definition.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
