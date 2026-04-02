#!/usr/bin/env python3
"""Price-Volume Concordance bundle — full-day window (09:30-11:30, 13:00-14:57).

D-017: Intraday price-volume concordance (日内量价协调性).

Physical hypothesis:
  In stocks with better market quality, price changes are closely tied to volume
  (Kyle's informed trading model). High concordance = orderly price discovery.
  The ratio of "concordant events" (high |ret| + high vol) to "discordant events"
  (high |ret| + low vol) captures the information quality of trading.

  This is a JOINT measure of volume and return behavior — fundamentally different
  from existing features that look at each dimension independently (Amihud = ratio,
  reversal_ratio = return signs only, vol_regime_transitions = volume levels only).

Features:
  1. pv_concordance_ratio_full     — fraction of bars where both |ret| and vol
                                      exceed their within-day medians
  2. pv_extreme_concordance_full   — fraction of bars where |ret| > 2×median AND
                                      vol > 2×median (extreme info events)
  3. pv_corr_full                  — Pearson correlation of |ret| and volume
  4. concordant_amihud_full        — Amihud on concordant bars only
  5. discordant_amihud_full        — Amihud on discordant bars (high |ret|, low vol)
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

NAME = "pv_concordance_full"

OUTPUT_NAMES = [
    "pv_concordance_ratio_full",
    "pv_extreme_concordance_full",
    "pv_corr_full",
    "concordant_amihud_full",
    "discordant_amihud_full",
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
            abs_rets[i] = np.nan
            vols[i] = np.nan
            amts[i] = np.nan
            continue
        abs_rets[i] = abs(np.log(c1 / c0))
        vols[i] = v
        amts[i] = a
        valid[i] = 1
        valid_cnt += 1

    if valid_cnt < 20:
        return out

    # ---- Compute median of abs_rets and volume (insertion sort) ----
    ar_sorted = np.empty(valid_cnt, dtype=np.float64)
    vol_sorted = np.empty(valid_cnt, dtype=np.float64)
    idx = 0
    for i in range(1, n):
        if valid[i] == 1:
            ar_sorted[idx] = abs_rets[i]
            vol_sorted[idx] = vols[i]
            idx += 1

    # Sort abs_rets
    for i in range(1, valid_cnt):
        key = ar_sorted[i]
        j = i - 1
        while j >= 0 and ar_sorted[j] > key:
            ar_sorted[j + 1] = ar_sorted[j]
            j -= 1
        ar_sorted[j + 1] = key

    # Sort volume
    for i in range(1, valid_cnt):
        key = vol_sorted[i]
        j = i - 1
        while j >= 0 and vol_sorted[j] > key:
            vol_sorted[j + 1] = vol_sorted[j]
            j -= 1
        vol_sorted[j + 1] = key

    ar_median = ar_sorted[valid_cnt // 2]
    vol_median = vol_sorted[valid_cnt // 2]

    if ar_median <= 0.0 or vol_median <= 0.0:
        return out

    # ---- Classify bars into quadrants and compute features ----
    # HH: high |ret| + high vol (concordant / information events)
    # HL: high |ret| + low vol (discordant / noise trading)
    # LH: low |ret| + high vol (passive flow / liquidity absorption)
    # LL: low |ret| + low vol (quiet)
    hh_count = 0
    extreme_hh_count = 0
    concordant_amihud_sum = 0.0
    concordant_amihud_cnt = 0
    discordant_amihud_sum = 0.0
    discordant_amihud_cnt = 0

    # For Pearson correlation
    sum_ar = 0.0
    sum_vol = 0.0
    sum_ar2 = 0.0
    sum_vol2 = 0.0
    sum_ar_vol = 0.0
    corr_cnt = 0

    ar_2x_median = 2.0 * ar_median
    vol_2x_median = 2.0 * vol_median

    for i in range(1, n):
        if valid[i] == 0:
            continue

        ar = abs_rets[i]
        v = vols[i]
        a = amts[i]

        # Pearson correlation accumulators
        sum_ar += ar
        sum_vol += v
        sum_ar2 += ar * ar
        sum_vol2 += v * v
        sum_ar_vol += ar * v
        corr_cnt += 1

        high_ret = ar > ar_median
        high_vol = v > vol_median

        if high_ret and high_vol:
            # Concordant (HH)
            hh_count += 1
            concordant_amihud_sum += ar / a
            concordant_amihud_cnt += 1

            # Check extreme concordance
            if ar > ar_2x_median and v > vol_2x_median:
                extreme_hh_count += 1

        elif high_ret and not high_vol:
            # Discordant (HL) — noise trading
            discordant_amihud_sum += ar / a
            discordant_amihud_cnt += 1

    # ---- Feature 0: pv_concordance_ratio_full ----
    out[0] = float(hh_count) / float(valid_cnt)

    # ---- Feature 1: pv_extreme_concordance_full ----
    out[1] = float(extreme_hh_count) / float(valid_cnt)

    # ---- Feature 2: pv_corr_full ----
    if corr_cnt >= 20:
        mean_ar = sum_ar / float(corr_cnt)
        mean_vol = sum_vol / float(corr_cnt)
        var_ar = sum_ar2 / float(corr_cnt) - mean_ar * mean_ar
        var_vol = sum_vol2 / float(corr_cnt) - mean_vol * mean_vol
        if var_ar > 0.0 and var_vol > 0.0:
            cov = sum_ar_vol / float(corr_cnt) - mean_ar * mean_vol
            out[2] = cov / (var_ar ** 0.5 * var_vol ** 0.5)

    # ---- Feature 3: concordant_amihud_full ----
    if concordant_amihud_cnt >= 3:
        out[3] = concordant_amihud_sum / float(concordant_amihud_cnt)

    # ---- Feature 4: discordant_amihud_full ----
    if discordant_amihud_cnt >= 3:
        out[4] = discordant_amihud_sum / float(discordant_amihud_cnt)

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
            "Price-volume concordance bundle for full-day window. "
            "Measures the joint behavior of |return| and volume at bar level: "
            "concordance ratio (fraction of bars where both are above median), "
            "extreme concordance, Pearson correlation, and conditional Amihud "
            "on concordant vs discordant bars."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the PV concordance full-day bundle"
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
