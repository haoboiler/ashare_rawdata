#!/usr/bin/env python3
"""Register the batch2b bundle for the full-day window (excl. closing auction).

Bundle: batch2b_0930_1130_1300_1457
- Input: high, close, volume (from 1m bars)
- Output: 4 variables:
    1. apm_factor — Afternoon-minus-Morning return differential
    2. closing_volume_ratio — Last 15 bars volume / total volume
    3. high_time — Normalized time of intraday high
    4. price_volume_divergence — Mean absolute deviation between normalized
       cumulative return and cumulative volume curves
- Window: 09:30-11:30 + 13:00-14:57 (excludes 14:57-15:00 closing auction)

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

NAME = "batch2b_0930_1130_1300_1457"

OUTPUT_NAMES = [
    "apm_factor_0930_1130_1300_1457",
    "closing_volume_ratio_0930_1130_1300_1457",
    "high_time_0930_1130_1300_1457",
    "price_volume_divergence_0930_1130_1300_1457",
]

FORMULA = """@njit
def apply_func(inputs):
    high = inputs[0]
    close = inputs[1]
    volume = inputs[2]

    n = close.size
    n_out = 4

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 2:
        return out

    # ---- 0: apm_factor = return_first_half - return_second_half ----
    half = n // 2
    c_first_start = close[0]
    c_first_end = close[half - 1]
    c_second_start = close[half]
    c_second_end = close[n - 1]

    if (not np.isnan(c_first_start) and not np.isnan(c_first_end)
            and not np.isnan(c_second_start) and not np.isnan(c_second_end)
            and c_first_start > 0.0 and c_second_start > 0.0):
        ret_first = c_first_end / c_first_start - 1.0
        ret_second = c_second_end / c_second_start - 1.0
        out[0] = ret_first - ret_second

    # ---- 1: closing_volume_ratio = sum(volume[-15:]) / sum(volume) ----
    tail_len = 15
    if n < tail_len:
        tail_len = n
    tail_start = n - tail_len

    vol_total = 0.0
    vol_tail = 0.0
    for i in range(n):
        v = volume[i]
        if np.isnan(v):
            continue
        vol_total += v
        if i >= tail_start:
            vol_tail += v
    if vol_total > 0.0:
        out[1] = vol_tail / vol_total

    # ---- 2: high_time = argmax(high) / (n - 1) ----
    max_high = -np.inf
    max_idx = 0
    valid_high = False
    for i in range(n):
        h = high[i]
        if np.isnan(h):
            continue
        if h > max_high:
            max_high = h
            max_idx = i
            valid_high = True
    if valid_high and n > 1:
        out[2] = float(max_idx) / float(n - 1)

    # ---- 3: price_volume_divergence ----
    # cumulative return curve
    c0 = close[0]
    if not np.isnan(c0) and c0 > 0.0 and vol_total > 0.0:
        cum_ret = np.empty(n, dtype=np.float64)
        cum_vol = np.empty(n, dtype=np.float64)

        running_vol = 0.0
        ret_min = np.inf
        ret_max = -np.inf
        all_valid = True

        for i in range(n):
            c = close[i]
            v = volume[i]
            if np.isnan(c) or np.isnan(v):
                cum_ret[i] = np.nan
                cum_vol[i] = np.nan
                all_valid = False
                continue
            cr = c / c0 - 1.0
            cum_ret[i] = cr
            running_vol += v
            cum_vol[i] = running_vol / vol_total
            if cr < ret_min:
                ret_min = cr
            if cr > ret_max:
                ret_max = cr

        ret_range = ret_max - ret_min
        if ret_range > 0.0:
            div_sum = 0.0
            div_cnt = 0
            for i in range(n):
                if np.isnan(cum_ret[i]) or np.isnan(cum_vol[i]):
                    continue
                norm_ret = (cum_ret[i] - ret_min) / ret_range
                div_sum += abs(norm_ret - cum_vol[i])
                div_cnt += 1
            if div_cnt > 0:
                out[3] = div_sum / div_cnt

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["high", "close", "volume"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]),
        slot=RawDataSlot.EVENING,
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Batch 2B bundle for the full-day window "
            "(09:30-11:30 + 13:00-14:57, excludes closing auction). "
            "Emits 4 variables: APM factor (AM vs PM return differential), "
            "closing volume ratio (last 15 bars volume share), "
            "high time (normalized position of intraday high), "
            "and price-volume divergence (deviation between cumulative "
            "return and cumulative volume curves)."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the batch2b full-day bundle"
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
