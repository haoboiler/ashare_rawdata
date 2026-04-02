#!/usr/bin/env python3
"""Amihud Asymmetry bundle — full-day window (09:30-11:30, 13:00-14:57).

D-018: Amihud price-impact buy/sell asymmetry (日内价格冲击买卖不对称性).

Physical hypothesis:
  Adverse selection theory: if selling has more price impact than buying
  (down_amihud >> up_amihud), the stock faces informed selling / distribution
  pressure. This asymmetry is a cross-sectional risk factor — stocks with
  high sell-side impact should command a liquidity premium.

  We already have up_amihud_full (pending). This bundle adds the sell-side
  counterpart and their ratios to explore the asymmetry dimension.

Features:
  1. down_amihud_full              — Amihud on down-return bars only
  2. amihud_asymmetry_full         — (up - down) / (up + down), signed asymmetry
  3. high_vol_down_amihud_full     — Down-return Amihud on high-volume bars
  4. amihud_sell_ratio_full        — down_amihud / total_amihud
  5. high_vol_amihud_asymmetry_full — Asymmetry using high-volume bars only
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

NAME = "amihud_asymmetry_full"

OUTPUT_NAMES = [
    "down_amihud_full",
    "amihud_asymmetry_full",
    "high_vol_down_amihud_full",
    "amihud_sell_ratio_full",
    "high_vol_amihud_asymmetry_full",
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
    n_out = 5
    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 20:
        return out

    # ---- Compute bar returns and collect valid bars ----
    rets = np.empty(n, dtype=np.float64)
    abs_rets = np.empty(n, dtype=np.float64)
    vols = np.empty(n, dtype=np.float64)
    amts = np.empty(n, dtype=np.float64)
    valid = np.zeros(n, dtype=np.int64)
    valid_cnt = 0

    for i in range(1, n):
        c0 = close[i - 1]
        c1 = close[i]
        v = volume[i]
        a = amount[i]
        if (np.isnan(c0) or np.isnan(c1) or c0 <= 0.0 or c1 <= 0.0 or
                np.isnan(v) or v <= 0.0 or np.isnan(a) or a <= 0.0):
            rets[i] = np.nan
            abs_rets[i] = np.nan
            vols[i] = np.nan
            amts[i] = np.nan
            continue
        r = np.log(c1 / c0)
        rets[i] = r
        abs_rets[i] = abs(r)
        vols[i] = v
        amts[i] = a
        valid[i] = 1
        valid_cnt += 1

    if valid_cnt < 20:
        return out

    # ---- Compute median volume (insertion sort) ----
    vol_sorted = np.empty(valid_cnt, dtype=np.float64)
    idx = 0
    for i in range(1, n):
        if valid[i] == 1:
            vol_sorted[idx] = vols[i]
            idx += 1

    for i in range(1, valid_cnt):
        key = vol_sorted[i]
        j = i - 1
        while j >= 0 and vol_sorted[j] > key:
            vol_sorted[j + 1] = vol_sorted[j]
            j -= 1
        vol_sorted[j + 1] = key

    vol_median = vol_sorted[valid_cnt // 2]

    # ---- Accumulate Amihud by direction and volume filter ----
    # All bars
    total_amihud_sum = 0.0
    total_amihud_cnt = 0

    # Up bars (ret > 0)
    up_amihud_sum = 0.0
    up_amihud_cnt = 0

    # Down bars (ret < 0)
    down_amihud_sum = 0.0
    down_amihud_cnt = 0

    # High-vol up bars
    hv_up_amihud_sum = 0.0
    hv_up_amihud_cnt = 0

    # High-vol down bars
    hv_down_amihud_sum = 0.0
    hv_down_amihud_cnt = 0

    for i in range(1, n):
        if valid[i] == 0:
            continue

        ar = abs_rets[i]
        r = rets[i]
        a = amts[i]
        v = vols[i]

        amihud_val = ar / a
        total_amihud_sum += amihud_val
        total_amihud_cnt += 1

        is_high_vol = v > vol_median

        if r > 0.0:
            up_amihud_sum += amihud_val
            up_amihud_cnt += 1
            if is_high_vol:
                hv_up_amihud_sum += amihud_val
                hv_up_amihud_cnt += 1
        elif r < 0.0:
            down_amihud_sum += amihud_val
            down_amihud_cnt += 1
            if is_high_vol:
                hv_down_amihud_sum += amihud_val
                hv_down_amihud_cnt += 1

    # ---- Feature 0: down_amihud_full ----
    if down_amihud_cnt >= 5:
        out[0] = down_amihud_sum / float(down_amihud_cnt)

    # ---- Feature 1: amihud_asymmetry_full ----
    if up_amihud_cnt >= 5 and down_amihud_cnt >= 5:
        up_avg = up_amihud_sum / float(up_amihud_cnt)
        down_avg = down_amihud_sum / float(down_amihud_cnt)
        denom = up_avg + down_avg
        if denom > 0.0:
            out[1] = (up_avg - down_avg) / denom

    # ---- Feature 2: high_vol_down_amihud_full ----
    if hv_down_amihud_cnt >= 3:
        out[2] = hv_down_amihud_sum / float(hv_down_amihud_cnt)

    # ---- Feature 3: amihud_sell_ratio_full ----
    if down_amihud_cnt >= 5 and total_amihud_cnt >= 10:
        down_avg = down_amihud_sum / float(down_amihud_cnt)
        total_avg = total_amihud_sum / float(total_amihud_cnt)
        if total_avg > 0.0:
            out[3] = down_avg / total_avg

    # ---- Feature 4: high_vol_amihud_asymmetry_full ----
    if hv_up_amihud_cnt >= 3 and hv_down_amihud_cnt >= 3:
        hv_up_avg = hv_up_amihud_sum / float(hv_up_amihud_cnt)
        hv_down_avg = hv_down_amihud_sum / float(hv_down_amihud_cnt)
        hv_denom = hv_up_avg + hv_down_avg
        if hv_denom > 0.0:
            out[4] = (hv_up_avg - hv_down_avg) / hv_denom

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
            "Amihud price-impact buy/sell asymmetry bundle for full-day window. "
            "Measures the difference in price impact (|return|/amount) between "
            "up-return and down-return bars. Captures adverse selection and "
            "distribution pressure as cross-sectional risk factors."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the Amihud asymmetry full-day bundle"
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
