#!/usr/bin/env python3
"""VWAP Cross Amihud bundle — full-day window (09:30-11:30, 13:00-14:57).

D-016 Round 2: Combine VWAP crossing events with Amihud framework.
Physical hypothesis: The price impact (|ret|/amount) specifically during
VWAP reversion events captures liquidity supply cost at mean-reversion points.
Stocks with high VWAP-crossing Amihud have poor liquidity at these critical
moments → higher execution cost → investors demand premium.

This follows the successful pattern of reversal_amihud_full (Exp#012)
but uses VWAP crossing as the event trigger instead of return sign change.

Features:
  1. vwap_cross_amihud_full      — |ret|/amount on VWAP crossing bars
  2. high_vol_vwap_cross_amihud_full — same but only high-volume crossing bars
  3. vwap_distance_roughness_full — mean|Δ(close/VWAP - 1)| (VWAP-relative path roughness)
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

NAME = "vwap_cross_amihud_full"

OUTPUT_NAMES = [
    "vwap_cross_amihud_full",
    "high_vol_vwap_cross_amihud_full",
    "vwap_distance_roughness_full",
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
    n_out = 3
    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 10:
        return out

    # ---- Compute cumulative VWAP at each bar ----
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

    # ---- Compute bar returns ----
    rets = np.empty(n, dtype=np.float64)
    rets[0] = np.nan
    for i in range(1, n):
        c0 = close[i - 1]
        c1 = close[i]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = np.log(c1 / c0)

    # ---- Identify VWAP crossing bars ----
    # A bar i is a VWAP crossing bar if sign(close[i-1] - vwap[i-1]) != sign(close[i] - vwap[i])
    is_cross = np.zeros(n, dtype=np.int64)
    for i in range(1, n):
        c_prev = close[i - 1]
        vw_prev = vwap_arr[i - 1]
        c_curr = close[i]
        vw_curr = vwap_arr[i]
        if np.isnan(c_prev) or np.isnan(vw_prev) or np.isnan(c_curr) or np.isnan(vw_curr):
            continue
        if vw_prev <= 0.0 or vw_curr <= 0.0:
            continue
        prev_sign = 1 if c_prev > vw_prev else -1
        curr_sign = 1 if c_curr > vw_curr else -1
        if prev_sign != curr_sign:
            is_cross[i] = 1

    # ---- Compute volume median for high-vol conditioning ----
    vol_valid = np.empty(n, dtype=np.float64)
    vol_valid_cnt = 0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v) and v > 0.0:
            vol_valid[vol_valid_cnt] = v
            vol_valid_cnt += 1

    vol_median = 0.0
    if vol_valid_cnt >= 4:
        vol_sorted = vol_valid[:vol_valid_cnt].copy()
        for i in range(1, vol_valid_cnt):
            key = vol_sorted[i]
            j = i - 1
            while j >= 0 and vol_sorted[j] > key:
                vol_sorted[j + 1] = vol_sorted[j]
                j -= 1
            vol_sorted[j + 1] = key
        vol_median = vol_sorted[vol_valid_cnt // 2]

    # ---- Feature 0: vwap_cross_amihud_full ----
    # mean(|ret| / amount) on VWAP crossing bars
    cross_amihud_sum = 0.0
    cross_amihud_cnt = 0
    for i in range(1, n):
        if is_cross[i] == 0:
            continue
        r = rets[i]
        a = amount[i]
        if np.isnan(r) or np.isnan(a) or a <= 0.0:
            continue
        cross_amihud_sum += abs(r) / a
        cross_amihud_cnt += 1
    if cross_amihud_cnt >= 3:
        out[0] = cross_amihud_sum / float(cross_amihud_cnt)

    # ---- Feature 1: high_vol_vwap_cross_amihud_full ----
    # mean(|ret| / amount) on high-volume VWAP crossing bars
    if vol_valid_cnt >= 4:
        hv_cross_sum = 0.0
        hv_cross_cnt = 0
        for i in range(1, n):
            if is_cross[i] == 0:
                continue
            v = volume[i]
            r = rets[i]
            a = amount[i]
            if np.isnan(v) or np.isnan(r) or np.isnan(a) or a <= 0.0:
                continue
            if v > vol_median:
                hv_cross_sum += abs(r) / a
                hv_cross_cnt += 1
        if hv_cross_cnt >= 3:
            out[1] = hv_cross_sum / float(hv_cross_cnt)

    # ---- Feature 2: vwap_distance_roughness_full ----
    # mean |Δ(close/VWAP - 1)| = path roughness of VWAP-relative price
    # Analogous to vol_roughness (mean|Δvol|/mean(vol)) but for price/VWAP ratio
    roughness_sum = 0.0
    roughness_cnt = 0
    prev_ratio = np.nan
    for i in range(n):
        c = close[i]
        vw = vwap_arr[i]
        if np.isnan(c) or np.isnan(vw) or vw <= 0.0:
            prev_ratio = np.nan
            continue
        cur_ratio = c / vw - 1.0
        if not np.isnan(prev_ratio):
            roughness_sum += abs(cur_ratio - prev_ratio)
            roughness_cnt += 1
        prev_ratio = cur_ratio
    if roughness_cnt > 0:
        out[2] = roughness_sum / float(roughness_cnt)

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
            "VWAP cross Amihud bundle for full-day window. "
            "Computes price impact (Amihud) specifically on bars where price "
            "crosses cumulative VWAP — capturing liquidity at mean-reversion "
            "events. Also includes high-volume conditioned variant and "
            "VWAP-relative path roughness."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the VWAP cross Amihud full-day bundle"
    )
    parser.add_argument(
        "--register", action="store_true",
        help="Write the definition into the configured registry backend",
    )
    parser.add_argument(
        "--skip-validate", action="store_true",
        help="Skip formula validation during registration",
    )
    parser.add_argument(
        "--print-json", action="store_true",
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
