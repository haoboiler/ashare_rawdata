#!/usr/bin/env python3
"""Acceleration Amihud conditioning variants for full-day window.

Bundle: accel_conditioning_full
- Input: close, volume, amount (from 1m bars, full day)
- Output: 3 features — conditioned |acceleration|/amount variants.

Physical basis:
  acceleration_t = ret_{t+1} - ret_t = log(c_{t+2}/c_{t+1}) - log(c_{t+1}/c_t)
  Each variant conditions on different bar subsets before computing mean(|accel|/amount).

  1. reversal_accel_illiq_full: Only bars where price direction reverses
     (ret[i] and ret[i+1] have opposite signs). Reversal bars represent
     "market-making" events; curvature impact at these points measures
     the cost of liquidity provision.

  2. extreme_accel_illiq_full: Only bars where |accel| > 2*median(|accel|).
     Extreme curvature events carry the most information about true
     illiquidity — analogous to extreme_amihud_full (Exp#013, conclusion #29).

  3. low_vol_accel_illiq_full: Only bottom-25% volume bars.
     During low-volume periods, price curvature impact amplifies,
     revealing latent illiquidity when the market is quiet.
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

NAME = "accel_conditioning_full"

OUTPUT_NAMES = [
    "reversal_accel_illiq_full",   # |accel|/amount on reversal bars only
    "extreme_accel_illiq_full",    # |accel|/amount on extreme |accel| bars only
    "low_vol_accel_illiq_full",    # |accel|/amount on bottom-25% volume bars only
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]
    amount = inputs[2]

    n = close.size
    n_out = 3

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 10:
        return out

    # ---- compute log returns ----
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0 or c1 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = np.log(c1 / c0)

    # ---- compute acceleration = ret[i+1] - ret[i] ----
    n_acc = n_ret - 1
    accel = np.empty(n_acc, dtype=np.float64)
    valid_acc = 0
    for i in range(n_acc):
        r0 = rets[i]
        r1 = rets[i + 1]
        if np.isnan(r0) or np.isnan(r1):
            accel[i] = np.nan
        else:
            accel[i] = r1 - r0
            valid_acc += 1

    if valid_acc < 10:
        return out

    # ---- Feature 0: reversal_accel_illiq_full ----
    # Only on bars where price direction reverses: ret[i] and ret[i+1] opposite signs
    # accel[i] = ret[i+1] - ret[i], so reversal means ret[i]*ret[i+1] < 0
    rev_sum = 0.0
    rev_cnt = 0
    for i in range(n_acc):
        a = accel[i]
        r0 = rets[i]
        r1 = rets[i + 1]
        if np.isnan(a) or np.isnan(r0) or np.isnan(r1):
            continue
        # Check reversal condition
        if r0 * r1 < 0.0:
            # avg amount for the two bars involved in the acceleration
            a1 = amount[i + 1]
            a2_idx = i + 2
            if a2_idx >= n:
                continue
            a2 = amount[a2_idx]
            if np.isnan(a1) or np.isnan(a2):
                continue
            avg_amt = (a1 + a2) * 0.5
            if avg_amt > 0.0:
                rev_sum += abs(a) / avg_amt
                rev_cnt += 1
    if rev_cnt > 0:
        out[0] = rev_sum / rev_cnt

    # ---- Pre-compute |accel| for median calculation (Feature 1) ----
    abs_accel_vals = np.empty(valid_acc, dtype=np.float64)
    abs_cnt = 0
    for i in range(n_acc):
        a = accel[i]
        if not np.isnan(a):
            abs_accel_vals[abs_cnt] = abs(a)
            abs_cnt += 1

    # ---- Feature 1: extreme_accel_illiq_full ----
    # Only bars where |accel| > 2 * median(|accel|)
    if abs_cnt >= 4:
        # Sort to find median
        for ii in range(abs_cnt):
            for jj in range(ii + 1, abs_cnt):
                if abs_accel_vals[jj] < abs_accel_vals[ii]:
                    tmp = abs_accel_vals[ii]
                    abs_accel_vals[ii] = abs_accel_vals[jj]
                    abs_accel_vals[jj] = tmp
        if abs_cnt % 2 == 0:
            median_abs = (abs_accel_vals[abs_cnt // 2 - 1] + abs_accel_vals[abs_cnt // 2]) * 0.5
        else:
            median_abs = abs_accel_vals[abs_cnt // 2]
        threshold = 2.0 * median_abs

        ext_sum = 0.0
        ext_cnt = 0
        for i in range(n_acc):
            a = accel[i]
            if np.isnan(a):
                continue
            if abs(a) > threshold:
                a1 = amount[i + 1]
                a2_idx = i + 2
                if a2_idx >= n:
                    continue
                a2 = amount[a2_idx]
                if np.isnan(a1) or np.isnan(a2):
                    continue
                avg_amt = (a1 + a2) * 0.5
                if avg_amt > 0.0:
                    ext_sum += abs(a) / avg_amt
                    ext_cnt += 1
        if ext_cnt > 0:
            out[1] = ext_sum / ext_cnt

    # ---- Feature 2: low_vol_accel_illiq_full ----
    # Only bottom-25% volume bars
    vol_vals = np.empty(n, dtype=np.float64)
    vol_cnt = 0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v):
            vol_vals[vol_cnt] = v
            vol_cnt += 1
    if vol_cnt >= 4:
        # Sort to find 25th percentile
        for ii in range(vol_cnt):
            for jj in range(ii + 1, vol_cnt):
                if vol_vals[jj] < vol_vals[ii]:
                    tmp = vol_vals[ii]
                    vol_vals[ii] = vol_vals[jj]
                    vol_vals[jj] = tmp
        p25_idx = int(vol_cnt * 0.25)
        if p25_idx >= vol_cnt:
            p25_idx = vol_cnt - 1
        vol_threshold = vol_vals[p25_idx]

        lv_sum = 0.0
        lv_cnt = 0
        for i in range(n_acc):
            a = accel[i]
            idx2 = i + 2
            if idx2 >= n:
                continue
            v2 = volume[idx2]
            if np.isnan(a) or np.isnan(v2):
                continue
            if v2 <= vol_threshold:
                a1 = amount[i + 1]
                a2 = amount[idx2]
                if np.isnan(a1) or np.isnan(a2):
                    continue
                avg_amt = (a1 + a2) * 0.5
                if avg_amt > 0.0:
                    lv_sum += abs(a) / avg_amt
                    lv_cnt += 1
        if lv_cnt > 0:
            out[2] = lv_sum / lv_cnt

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "volume", "amount"],
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
            "Acceleration Amihud conditioning variants for full-day window. "
            "Tests three bar-selection strategies applied to |acceleration|/amount: "
            "(1) reversal bars only, (2) extreme |accel| bars only, "
            "(3) low-volume bars only. Validates whether D-006 Amihud conditioning "
            "patterns transfer to the acceleration dimension."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the acceleration conditioning full-day bundle"
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
