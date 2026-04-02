#!/usr/bin/env python3
"""Register the closing volume ratio bundle for the full-day window.

Bundle: closing_volume_ratio
- Input: close, volume, amount (from 1m bars, full day)
- Output: 5 variables capturing intraday volume distribution patterns.

Physical hypothesis: stocks with higher closing-hour volume ratio tend to
have more institutional participation (institutions prefer to trade near
close to minimise impact cost and align with benchmark close prices).
Higher institutional presence may signal better stock quality and positive
future returns — a DIRECTIONAL hypothesis distinct from the microstructure
factors that previously failed on Long Excess.

Bar layout for full-day window [("09:30","11:30"),("13:00","14:57")]:
  - Total: 237 bars
  - AM session: bars 0-119 (120 bars, 09:30-11:30)
  - PM session: bars 120-236 (117 bars, 13:00-14:57)
  - Last hour (14:00-14:57): bars 180-236 (57 bars)
  - Last 30 min (14:27-14:57): bars 207-236 (30 bars)
  - First hour (09:30-10:30): bars 0-59 (60 bars)

All features use relative-position or fixed-position splits with NaN-aware
sums, so they work in both preload (fixed 237) and serial (variable length) modes.
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

NAME = "closing_volume_ratio"

OUTPUT_NAMES = [
    # --- Volume distribution (3) ---
    "vol_last_quarter_ratio_full",      # volume in last 25% bars / total volume
    "vol_center_of_mass_full",          # normalised weighted-avg position of volume
    "vol_back_half_ratio_full",         # volume in second half / total volume
    # --- Amount distribution (1) ---
    "amt_last_quarter_ratio_full",      # amount in last 25% bars / total amount
    # --- Close vs Open ratio (1) ---
    "close_open_vol_ratio_full",        # last-quarter volume / first-quarter volume
    # --- Directional closing features (3) ---
    "close_buy_pressure_full",          # net buy volume ratio in last quarter
    "close_vwap_return_full",           # volume-weighted return in last quarter
    "close_vol_momentum_full",          # vol-weighted mean return sign in last quarter
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]
    amount = inputs[2]

    n = close.size
    n_out = 8

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 4:
        return out

    # --- NaN-aware total volume and amount ---
    total_vol = 0.0
    total_amt = 0.0
    vol_count = 0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v) and v >= 0.0:
            total_vol += v
            vol_count += 1
        a = amount[i]
        if not np.isnan(a) and a >= 0.0:
            total_amt += a

    if vol_count < 10 or total_vol <= 0.0:
        return out

    # --- Quarter boundaries (relative positions) ---
    q1_end = n // 4          # end of first quarter
    q3_start = n - n // 4    # start of last quarter
    half = n // 2             # midpoint

    # --- 0: vol_last_quarter_ratio = sum(vol[q3:]) / total_vol ---
    vol_lq = 0.0
    for i in range(q3_start, n):
        v = volume[i]
        if not np.isnan(v) and v >= 0.0:
            vol_lq += v
    out[0] = vol_lq / total_vol

    # --- 1: vol_center_of_mass = sum(i * vol[i]) / ((n-1) * total_vol) ---
    weighted_pos = 0.0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v) and v >= 0.0:
            weighted_pos += float(i) * v
    if n > 1:
        out[1] = weighted_pos / (float(n - 1) * total_vol)

    # --- 2: vol_back_half_ratio = sum(vol[half:]) / total_vol ---
    vol_bh = 0.0
    for i in range(half, n):
        v = volume[i]
        if not np.isnan(v) and v >= 0.0:
            vol_bh += v
    out[2] = vol_bh / total_vol

    # --- 3: amt_last_quarter_ratio = sum(amt[q3:]) / total_amt ---
    if total_amt > 0.0:
        amt_lq = 0.0
        for i in range(q3_start, n):
            a = amount[i]
            if not np.isnan(a) and a >= 0.0:
                amt_lq += a
        out[3] = amt_lq / total_amt

    # --- 4: close_open_vol_ratio = vol_last_quarter / vol_first_quarter ---
    vol_fq = 0.0
    for i in range(0, q1_end):
        v = volume[i]
        if not np.isnan(v) and v >= 0.0:
            vol_fq += v
    if vol_fq > 0.0:
        out[4] = vol_lq / vol_fq

    # --- Pre-compute log returns for directional features ---
    n_ret = n - 1

    # --- 5: close_buy_pressure = (vol_up - vol_down) / vol_total in last quarter ---
    # Net buying pressure: positive = more volume on up-bars at close
    vol_up_lq = 0.0
    vol_down_lq = 0.0
    for i in range(q3_start, n):
        v = volume[i]
        if i == 0:
            continue
        c0 = close[i - 1]
        c1 = close[i]
        if np.isnan(v) or np.isnan(c0) or np.isnan(c1) or v < 0.0 or c0 <= 0.0:
            continue
        r = np.log(c1 / c0)
        if r > 0.0:
            vol_up_lq += v
        elif r < 0.0:
            vol_down_lq += v
    vol_total_lq = vol_up_lq + vol_down_lq
    if vol_total_lq > 0.0:
        out[5] = (vol_up_lq - vol_down_lq) / vol_total_lq

    # --- 6: close_vwap_return = sum(r_i * v_i) / sum(v_i) in last quarter ---
    # Volume-weighted average return at close; positive = price rising with volume
    rv_sum = 0.0
    v_sum = 0.0
    for i in range(q3_start, n):
        v = volume[i]
        if i == 0:
            continue
        c0 = close[i - 1]
        c1 = close[i]
        if np.isnan(v) or np.isnan(c0) or np.isnan(c1) or v < 0.0 or c0 <= 0.0:
            continue
        r = np.log(c1 / c0)
        rv_sum += r * v
        v_sum += v
    if v_sum > 0.0:
        out[6] = rv_sum / v_sum

    # --- 7: close_vol_momentum = close_buy_pressure * vol_last_quarter_ratio ---
    # Interaction: directional signal amplified by volume concentration at close
    if not np.isnan(out[5]) and not np.isnan(out[0]):
        out[7] = out[5] * out[0]

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "volume", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]),
        slot=RawDataSlot.EVENING,
        data_available_at=1457,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Closing volume ratio bundle for the full-day window. "
            "Emits 5 variables capturing intraday volume distribution: "
            "last-quarter volume/amount ratios, center of mass, "
            "back-half ratio, and close/open volume ratio. "
            "Hypothesis: higher closing volume ratio signals institutional "
            "participation and better stock quality."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the closing volume ratio bundle"
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
        from ashare_hf_variable.registry import upsert_definition
        upsert_definition(definition, validate=not args.skip_validate)
        print(f"registered: {definition.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
