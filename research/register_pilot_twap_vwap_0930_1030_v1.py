#!/usr/bin/env python3
"""Register the first A-share raw-data pilot bundle.

This script defines one registry item that computes two generated raw-data fields
from the same 09:30-10:30 1m window:

- twap_0930_1030_v1
- vwap_0930_1030_v1

Rationale:
- The two outputs share the same input window and source columns.
- It is cheaper and clearer to scan the minute bars once and emit both values.

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


PILOT_NAME = "pilot_twap_vwap_0930_1030_v1"

PILOT_FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]

    twap = np.nan
    vwap = np.nan

    if close.size == 0:
        return np.array([twap, vwap], dtype=np.float64)

    twap = np.nanmean(close)

    weighted_sum = 0.0
    volume_sum = 0.0
    for i in range(close.size):
        c = close[i]
        v = volume[i]
        if np.isnan(c) or np.isnan(v):
            continue
        weighted_sum += c * v
        volume_sum += v

    if volume_sum > 0.0:
        vwap = weighted_sum / volume_sum

    return np.array([twap, vwap], dtype=np.float64)
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=PILOT_NAME,
        formula=PILOT_FORMULA,
        func_name="apply_func",
        input_names=["close", "volume"],
        output_names=["twap_0930_1030_v1", "vwap_0930_1030_v1"],
        params=RawDataParams(input_time_filter=[("09:30", "10:30")]),
        slot=RawDataSlot.MIDDAY,
        data_available_at=1031,
        execution_start_at=None,
        execution_end_at=None,
        expected_bars=60,
        description=(
            "Pilot bundle for the 09:30-10:30 window. "
            "Emits twap_0930_1030_v1 and vwap_0930_1030_v1 from one function."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the pilot A-share TWAP/VWAP 09:30-10:30 bundle"
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
