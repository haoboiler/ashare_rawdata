#!/usr/bin/env python3
"""Register a morning-session basics bundle for the 09:30-11:30 window.

Bundle: am_session_basics_0930_1130
- Input: high, low, close, volume, amount (from 1m bars)
- Output: 5 daily morning-session state variables intended for downstream
  models that start trading from the 13:00 afternoon session.

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

NAME = "am_session_basics_0930_1130"

OUTPUT_NAMES = [
    "am_close_0930_1130",
    "am_high_0930_1130",
    "am_low_0930_1130",
    "am_volume_sum_0930_1130",
    "am_amount_sum_0930_1130",
]

FORMULA = """@njit
def apply_func(inputs):
    high = inputs[0]
    low = inputs[1]
    close = inputs[2]
    volume = inputs[3]
    amount = inputs[4]

    n = close.size
    out = np.full(5, np.nan, dtype=np.float64)
    if n == 0:
        return out

    # ---- 0: am_close = last valid close in the morning window ----
    for i in range(n - 1, -1, -1):
        c = close[i]
        if not np.isnan(c):
            out[0] = c
            break

    # ---- 1: am_high = max(high) ----
    max_high = -np.inf
    for i in range(n):
        h = high[i]
        if np.isnan(h):
            continue
        if h > max_high:
            max_high = h
    if max_high > -np.inf:
        out[1] = max_high

    # ---- 2: am_low = min(low) ----
    min_low = np.inf
    for i in range(n):
        l = low[i]
        if np.isnan(l):
            continue
        if l < min_low:
            min_low = l
    if min_low < np.inf:
        out[2] = min_low

    # ---- 3: am_volume_sum = sum(volume) ----
    vol_sum = 0.0
    vol_cnt = 0
    for i in range(n):
        v = volume[i]
        if np.isnan(v):
            continue
        vol_sum += v
        vol_cnt += 1
    if vol_cnt > 0:
        out[3] = vol_sum

    # ---- 4: am_amount_sum = sum(amount) ----
    amt_sum = 0.0
    amt_cnt = 0
    for i in range(n):
        a = amount[i]
        if np.isnan(a):
            continue
        amt_sum += a
        amt_cnt += 1
    if amt_cnt > 0:
        out[4] = amt_sum

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["high", "low", "close", "volume", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30")]),
        slot=RawDataSlot.MIDDAY,
        data_available_at=1131,
        execution_start_at=930,
        execution_end_at=1130,
        expected_bars=80,
        description=(
            "Morning-session basics bundle for the 09:30-11:30 window. "
            "Emits last close, session high/low, and summed volume/amount "
            "for downstream models that trade from the 13:00 afternoon session."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the morning-session basics 09:30-11:30 bundle"
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
