#!/usr/bin/env python3
"""APM Momentum bundle for the 09:30-11:30 window (midday slot).

Physical Hypothesis:
Morning-session directional momentum captures overnight information
absorption and early institutional activity. AM return and close location
predict same-day afternoon returns (t_plus_n=0 with twap_1300_1400).

Bundle: apm_momentum_0930_1130
- Input: close, high, low, volume (from 1m bars, 09:30-11:30)
- Output: 5 directional momentum variables
- Slot: midday (data_available_at=1131, t_plus_n=0 with twap_1300_1400)
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

NAME = "apm_momentum_0930_1130"

OUTPUT_NAMES = [
    # --- 方向性动量 (3) ---
    "am_return_0930_1130",           # AM session return
    "am_late_return_0930_1130",      # Late AM return (second half)
    "am_acceleration_0930_1130",     # Late return minus early return
    # --- 收盘位置 (1) ---
    "am_close_loc_0930_1130",        # Close location in AM range [0,1]
    # --- 量价方向 (1) ---
    "am_vw_avg_return_0930_1130",    # Volume-weighted average return
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    high = inputs[1]
    low = inputs[2]
    volume = inputs[3]

    n = close.size
    n_out = 5

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 4:
        return out

    # ---- Find first and last valid close ----
    first_close = np.nan
    last_close = np.nan
    first_idx = -1
    last_idx = -1
    for i in range(n):
        c = close[i]
        if not np.isnan(c) and c > 0.0:
            if first_idx == -1:
                first_close = c
                first_idx = i
            last_close = c
            last_idx = i

    if first_idx == -1 or first_idx == last_idx:
        return out

    # ---- 0: am_return = log(last_close / first_close) ----
    out[0] = np.log(last_close / first_close)

    # ---- 1 & 2: late return and acceleration ----
    mid = (first_idx + last_idx) // 2
    mid_close = np.nan
    best_dist = n
    for i in range(first_idx, last_idx + 1):
        c = close[i]
        if not np.isnan(c) and c > 0.0:
            dist = abs(i - mid)
            if dist < best_dist:
                best_dist = dist
                mid_close = c

    if not np.isnan(mid_close) and mid_close > 0.0:
        early_ret = np.log(mid_close / first_close)
        late_ret = np.log(last_close / mid_close)

        # 1: am_late_return
        out[1] = late_ret

        # 2: am_acceleration = late - early
        out[2] = late_ret - early_ret

    # ---- 3: am_close_loc = (last_close - window_low) / (window_high - window_low) ----
    window_high = -1e18
    window_low = 1e18
    for i in range(n):
        h = high[i]
        l = low[i]
        if not np.isnan(h) and h > window_high:
            window_high = h
        if not np.isnan(l) and l > 0.0 and l < window_low:
            window_low = l

    range_hl = window_high - window_low
    if range_hl > 0.0 and window_low > 0.0:
        out[3] = (last_close - window_low) / range_hl

    # ---- 4: am_vw_avg_return = sum(ret_i * vol_i) / sum(vol_i) ----
    vw_sum = 0.0
    vol_sum = 0.0
    for i in range(first_idx, last_idx):
        c0 = close[i]
        c1 = close[i + 1]
        v = volume[i + 1]
        if np.isnan(c0) or np.isnan(c1) or np.isnan(v) or c0 <= 0.0 or v <= 0.0:
            continue
        ret = np.log(c1 / c0)
        vw_sum += ret * v
        vol_sum += v
    if vol_sum > 0.0:
        out[4] = vw_sum / vol_sum

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "high", "low", "volume"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30")]),
        slot=RawDataSlot.MIDDAY,
        data_available_at=1131,
        execution_start_at=930,
        execution_end_at=1130,
        expected_bars=80,
        description=(
            "APM (Afternoon-to-PM) Momentum bundle for the 09:30-11:30 window. "
            "Captures directional momentum signals in the morning session: "
            "AM return, late-session return, acceleration, close location, "
            "and volume-weighted directional signal. Midday slot enables "
            "same-day afternoon execution (t_plus_n=0)."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the APM momentum 09:30-11:30 bundle"
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
