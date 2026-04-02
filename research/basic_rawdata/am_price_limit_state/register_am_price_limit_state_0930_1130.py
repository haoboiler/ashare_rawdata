#!/usr/bin/env python3
"""Register the morning price-limit state bundle for the 09:30-11:30 window.

Bundle: am_price_limit_state_0930_1130
- 1m Input: origin_close, origin_high, origin_low (from 1m bars, 09:30-11:30)
- Daily Input: high_limited, low_limited, pre_close (from morning bundle)
- Output: 5 daily fields covering limit-price gap, touch count, lock ratio,
  and reopen (炸板) count.

By default the script only prints the definition JSON for review.
Use ``--register`` to write it into the configured registry backend.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CASIMIR_ROOT = Path("/home/gkh/ashare/casimir_ashare")
if str(CASIMIR_ROOT) not in sys.path:
    sys.path.insert(0, str(CASIMIR_ROOT))

from casimir.core.ashare_rawdata.models import (
    AShareRawDataDefinition,
    PriceBasis,
    RawDataParams,
    RawDataSlot,
)
from casimir.core.ashare_rawdata.registry import upsert_definition

NAME = "am_price_limit_state_0930_1130"

OUTPUT_NAMES = [
    "am_up_limit_gap_pct_0930_1130",      # 0: distance to upper limit
    "am_down_limit_gap_pct_0930_1130",     # 1: distance to lower limit
    "am_limit_touch_count_0930_1130",      # 2: bars touching any limit
    "am_limit_lock_ratio_0930_1130",       # 3: fraction of bars locked at limit
    "am_limit_reopen_count_0930_1130",     # 4: locked->unlocked transitions
]

FORMULA = """@njit
def apply_func(inputs, daily):
    origin_close = inputs[0]
    origin_high = inputs[1]
    origin_low = inputs[2]
    high_lim = daily[0]
    low_lim = daily[1]
    pre_close = daily[2]

    N_OUT = 5
    out = np.full(N_OUT, np.nan, dtype=np.float64)

    n = origin_close.size
    if n == 0 or pre_close <= 0.0 or high_lim <= 0.0 or low_lim <= 0.0:
        return out

    tol_up = high_lim * 0.0005
    tol_down = low_lim * 0.0005
    up_threshold = high_lim - tol_up
    down_threshold = low_lim + tol_down

    # --- last valid origin_close ---
    last_oc = np.nan
    for i in range(n - 1, -1, -1):
        v = origin_close[i]
        if v == v and v > 0.0:
            last_oc = v
            break

    # --- bar-by-bar scan ---
    touch_count = 0
    n_valid_close = 0
    lock_count = 0
    prev_locked = -1  # -1 = unknown
    reopen_count = 0

    for i in range(n):
        oc = origin_close[i]
        oh = origin_high[i]
        ol = origin_low[i]

        # touch count: origin_high or origin_low hits limit
        touched = False
        if oh == oh and oh >= up_threshold:
            touched = True
        if ol == ol and ol <= down_threshold:
            touched = True
        if touched:
            touch_count += 1

        # lock ratio & reopen count: based on origin_close
        if oc == oc and oc > 0.0:
            n_valid_close += 1
            is_locked = (oc >= up_threshold) or (oc <= down_threshold)
            if is_locked:
                lock_count += 1
            if prev_locked == 1 and not is_locked:
                reopen_count += 1
            prev_locked = 1 if is_locked else 0

    # --- outputs ---
    if last_oc != last_oc:
        return out

    # 0: am_up_limit_gap_pct_0930_1130
    out[0] = (high_lim - last_oc) / pre_close

    # 1: am_down_limit_gap_pct_0930_1130
    out[1] = (last_oc - low_lim) / pre_close

    # 2: am_limit_touch_count_0930_1130
    if n_valid_close > 0 or touch_count > 0:
        out[2] = float(touch_count)

    # 3: am_limit_lock_ratio_0930_1130
    if n_valid_close > 0:
        out[3] = float(lock_count) / float(n_valid_close)

    # 4: am_limit_reopen_count_0930_1130
    if n_valid_close > 0:
        out[4] = float(reopen_count)

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["origin_close", "origin_high", "origin_low"],
        daily_input_names=["high_limited", "low_limited", "pre_close"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30")]),
        slot=RawDataSlot.MIDDAY,
        data_available_at=1131,
        execution_start_at=930,
        execution_end_at=1130,
        expected_bars=120,
        price_basis=PriceBasis.ORIGIN,
        description=(
            "上午涨跌停状态特征：距涨停/跌停价距离、触板次数、封板分钟占比、炸板次数"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the am_price_limit_state 09:30-11:30 bundle",
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
