#!/usr/bin/env python3
"""Register upper/lower limit masks for the 13:00-14:00 execution window.

Definitions:
  is_upper_limit_1300_1400 - 1.0 if >=60% of 1m bars at upper limit, else 0.0
  is_lower_limit_1300_1400 - 1.0 if >=60% of 1m bars at lower limit, else 0.0

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

# ---------- formulas ----------

_UPPER_LIMIT_FORMULA = """@njit
def apply_func(inputs, daily):
    origin_close = inputs[0]
    high_limited = daily[0]
    n = origin_close.size
    if n == 0 or high_limited <= 0.0:
        return (np.nan,)
    threshold = high_limited * (1.0 - 0.0005)
    count = 0
    valid = 0
    for i in range(n):
        v = origin_close[i]
        if v == v:
            valid += 1
            if v >= threshold:
                count += 1
    if valid == 0:
        return (np.nan,)
    if float(count) / float(valid) >= 0.6:
        return (1.0,)
    return (0.0,)
"""

_LOWER_LIMIT_FORMULA = """@njit
def apply_func(inputs, daily):
    origin_close = inputs[0]
    low_limited = daily[0]
    n = origin_close.size
    if n == 0 or low_limited <= 0.0:
        return (np.nan,)
    threshold = low_limited * (1.0 + 0.0005)
    count = 0
    valid = 0
    for i in range(n):
        v = origin_close[i]
        if v == v:
            valid += 1
            if v <= threshold:
                count += 1
    if valid == 0:
        return (np.nan,)
    if float(count) / float(valid) >= 0.6:
        return (1.0,)
    return (0.0,)
"""

# ---------- definitions ----------

DEFINITIONS = [
    AShareRawDataDefinition(
        name="is_upper_limit_1300_1400",
        formula=_UPPER_LIMIT_FORMULA,
        func_name="apply_func",
        input_names=["origin_close"],
        daily_input_names=["high_limited"],
        output_names=["is_upper_limit_1300_1400"],
        params=RawDataParams(input_time_filter=[("13:00", "14:00")]),
        slot=RawDataSlot.EVENING,
        data_available_at=1400,
        execution_start_at=1300,
        execution_end_at=1400,
        expected_bars=60,
        price_basis=PriceBasis.ORIGIN,
        description="涨停检测：13:00-14:00 时段内 >=60% 的 1m close 在涨停价 0.05% 以内",
    ),
    AShareRawDataDefinition(
        name="is_lower_limit_1300_1400",
        formula=_LOWER_LIMIT_FORMULA,
        func_name="apply_func",
        input_names=["origin_close"],
        daily_input_names=["low_limited"],
        output_names=["is_lower_limit_1300_1400"],
        params=RawDataParams(input_time_filter=[("13:00", "14:00")]),
        slot=RawDataSlot.EVENING,
        data_available_at=1400,
        execution_start_at=1300,
        execution_end_at=1400,
        expected_bars=60,
        price_basis=PriceBasis.ORIGIN,
        description="跌停检测：13:00-14:00 时段内 >=60% 的 1m close 在跌停价 0.05% 以内",
    ),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register upper/lower limit masks for 13:00-14:00",
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Write definitions into the configured registry backend",
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

    for definition in DEFINITIONS:
        if args.print_json or not args.register:
            print(json.dumps(definition.to_document(), indent=2, ensure_ascii=True))
            print()

        if args.register:
            upsert_definition(definition, validate=not args.skip_validate)
            print(f"registered: {definition.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
