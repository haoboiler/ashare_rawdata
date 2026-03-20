#!/usr/bin/env python3
"""Register batch2 pilot bundle for the 09:30-10:30 window.

Bundle: batch2_pilot_0930_1030
- Input: close, volume (from 1m bars)
- Output: 3 variables:
    1. smart_money_0930_1030: smart money factor (VWAP of high-S bars vs overall VWAP)
    2. variance_ratio_0930_1030: variance ratio (5m vs 1m, trend/mean-reversion indicator)
    3. volume_entropy_0930_1030: Shannon entropy of volume distribution

By default the script only prints the definition JSON for review.
Use ``--register`` to write it into the configured registry backend.
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

NAME = "batch2_pilot_0930_1030"

OUTPUT_NAMES = [
    "smart_money_0930_1030",
    "variance_ratio_0930_1030",
    "volume_entropy_0930_1030",
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]

    n = close.size
    n_out = 3

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 2:
        return out

    # ================================================================
    # 0: smart_money_0930_1030
    #    S_i = |return_i| / sqrt(volume_i) for each bar (using bar-to-bar returns)
    #    Sort bars by S descending, pick bars until cumulative volume >= 20% of total
    #    smart_money = VWAP(selected bars) / VWAP(all bars) - 1
    # ================================================================
    n_ret = n - 1

    # Compute overall VWAP first
    overall_wsum = 0.0
    overall_vsum = 0.0
    for i in range(n):
        c = close[i]
        v = volume[i]
        if np.isnan(c) or np.isnan(v) or v <= 0.0:
            continue
        overall_wsum += c * v
        overall_vsum += v

    if overall_vsum > 0.0 and n_ret > 0:
        overall_vwap = overall_wsum / overall_vsum
        vol_threshold = overall_vsum * 0.2

        # Compute S for each bar (using return from bar i to i+1, paired with volume[i+1])
        # We have n_ret return bars (index 0..n_ret-1), each associated with bar i+1
        s_vals = np.empty(n_ret, dtype=np.float64)
        bar_close = np.empty(n_ret, dtype=np.float64)
        bar_vol = np.empty(n_ret, dtype=np.float64)
        valid_count = 0

        for i in range(n_ret):
            c0 = close[i]
            c1 = close[i + 1]
            v1 = volume[i + 1]
            if np.isnan(c0) or np.isnan(c1) or np.isnan(v1) or c0 <= 0.0 or v1 <= 0.0:
                s_vals[i] = -1.0  # mark invalid
                bar_close[i] = np.nan
                bar_vol[i] = 0.0
            else:
                ret = abs(np.log(c1 / c0))
                s_vals[i] = ret / np.sqrt(v1)
                bar_close[i] = c1
                bar_vol[i] = v1
                valid_count += 1

        if valid_count > 0:
            # Sort indices by S descending (simple selection sort for numba compat)
            # Use argsort-like approach: build index array, sort by s_vals descending
            indices = np.empty(n_ret, dtype=np.int64)
            for i in range(n_ret):
                indices[i] = i

            # Bubble sort (small n, numba-compatible)
            for i in range(n_ret):
                for j in range(i + 1, n_ret):
                    if s_vals[indices[j]] > s_vals[indices[i]]:
                        tmp = indices[i]
                        indices[i] = indices[j]
                        indices[j] = tmp

            # Pick top bars until cumulative volume >= 20% of total
            smart_wsum = 0.0
            smart_vsum = 0.0
            for k in range(n_ret):
                idx = indices[k]
                if s_vals[idx] < 0.0:
                    break  # invalid entries
                c = bar_close[idx]
                v = bar_vol[idx]
                if np.isnan(c) or v <= 0.0:
                    continue
                smart_wsum += c * v
                smart_vsum += v
                if smart_vsum >= vol_threshold:
                    break

            if smart_vsum > 0.0 and overall_vwap > 0.0:
                smart_vwap = smart_wsum / smart_vsum
                out[0] = smart_vwap / overall_vwap - 1.0

    # ================================================================
    # 1: variance_ratio_0930_1030
    #    Merge consecutive 5 bars into 5m return
    #    VR = Var(5m returns) / (5 * Var(1m returns))
    # ================================================================
    # Compute 1m log returns
    rets_1m = np.empty(n_ret, dtype=np.float64)
    valid_1m = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            rets_1m[i] = np.nan
        else:
            rets_1m[i] = np.log(c1 / c0)
            valid_1m += 1

    if valid_1m >= 10:  # need enough data
        # Variance of 1m returns
        sum_1m = 0.0
        cnt_1m = 0
        for i in range(n_ret):
            if not np.isnan(rets_1m[i]):
                sum_1m += rets_1m[i]
                cnt_1m += 1
        if cnt_1m >= 2:
            mean_1m = sum_1m / cnt_1m
            ss_1m = 0.0
            for i in range(n_ret):
                if not np.isnan(rets_1m[i]):
                    d = rets_1m[i] - mean_1m
                    ss_1m += d * d
            var_1m = ss_1m / (cnt_1m - 1)

            # 5m returns: sum consecutive 5 non-nan 1m returns
            # Use non-overlapping blocks of 5 bars from the close series
            n_5m = n_ret // 5
            rets_5m = np.empty(n_5m, dtype=np.float64)
            cnt_5m = 0
            for blk in range(n_5m):
                start_idx = blk * 5
                c_start = close[start_idx]
                c_end = close[start_idx + 5]
                if np.isnan(c_start) or np.isnan(c_end) or c_start <= 0.0:
                    rets_5m[blk] = np.nan
                else:
                    rets_5m[blk] = np.log(c_end / c_start)
                    cnt_5m += 1

            if cnt_5m >= 2 and var_1m > 0.0:
                sum_5m = 0.0
                for blk in range(n_5m):
                    if not np.isnan(rets_5m[blk]):
                        sum_5m += rets_5m[blk]
                mean_5m = sum_5m / cnt_5m
                ss_5m = 0.0
                for blk in range(n_5m):
                    if not np.isnan(rets_5m[blk]):
                        d = rets_5m[blk] - mean_5m
                        ss_5m += d * d
                var_5m = ss_5m / (cnt_5m - 1)

                out[1] = var_5m / (5.0 * var_1m)

    # ================================================================
    # 2: volume_entropy_0930_1030
    #    p_i = volume_i / sum(volume), Shannon entropy = -sum(p_i * ln(p_i))
    # ================================================================
    vol_total = 0.0
    vol_valid = 0
    for i in range(n):
        v = volume[i]
        if np.isnan(v) or v <= 0.0:
            continue
        vol_total += v
        vol_valid += 1

    if vol_valid >= 2 and vol_total > 0.0:
        entropy = 0.0
        for i in range(n):
            v = volume[i]
            if np.isnan(v) or v <= 0.0:
                continue
            p = v / vol_total
            if p > 0.0:
                entropy -= p * np.log(p)
        out[2] = entropy

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "volume"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "10:30")]),
        slot=RawDataSlot.MIDDAY,
        data_available_at=1031,
        execution_start_at=930,
        execution_end_at=1030,
        expected_bars=40,
        description=(
            "Batch 2 pilot bundle for 09:30-10:30 window. "
            "Emits 3 variables: smart money factor (VWAP of high price-impact bars), "
            "variance ratio (5m vs 1m, trend/mean-reversion indicator), "
            "and volume entropy (Shannon entropy of volume distribution)."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the batch2 pilot 09:30-10:30 bundle"
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
