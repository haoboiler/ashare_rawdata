#!/usr/bin/env python3
"""Register Amihud conditioning variants bundle for full-day window.

Bundle: amihud_conditioning_0930_1130_1300_1457
- Input: close, volume, amount (from 1m bars)
- Output: 5 variables exploring NEW Amihud conditioning / aggregation methods.

Full-day window (237 bars) for stable estimates.

Physical hypotheses:

1. amihud_vol_accel_full: Amihud on volume-acceleration bars (volume_i > volume_{i-1}).
   When volume is increasing, new demand is entering the market. The price impact
   during these demand surges captures "reactive liquidity cost" - how expensive it
   is to trade when others are also rushing in. Different from high_vol_illiq (which
   uses static top-25% threshold) because this captures the DYNAMIC of volume growth.

2. amihud_hhi_full: Herfindahl-Hirschman Index of per-bar Amihud contributions.
   HHI = sum((amihud_i / sum_amihud)^2). High HHI = illiquidity comes in rare extreme
   bursts (flash illiquidity). Low HHI = uniformly distributed cost. Different from
   tail_ratio (P90/P50 percentile-based) and diff_mean (consecutive-bar path-based).
   This is a full-distribution concentration measure.

3. amihud_low_vol_full: Amihud on bottom-25% volume bars. The COMPLEMENT of high_vol_illiq
   (which computes on top-25%). Low-volume periods reveal structural/baseline illiquidity
   when the market is quiet. If high_vol_illiq measures "stress liquidity cost", this
   measures "quiet-period structural cost".

4. amihud_cv_full: Coefficient of variation (std/mean) of per-bar Amihud.
   Directly measures execution cost UNPREDICTABILITY. A stock with high Amihud level
   but low CV has consistent (predictable) spread; high CV = unreliable cost estimation.
   Different from diff_mean (which measures consecutive-bar changes, i.e., temporal
   roughness) and tail_ratio (which only looks at upper tail).

5. amihud_return_weighted_full: sum(|r_i|^2 / amount_i) / sum(|r_i|).
   Weights each bar's Amihud by its return magnitude (continuous weighting).
   Bars with larger price moves contribute more. Different from extreme_amihud
   (which uses a discrete threshold |r|>2*median) - this uses smooth weighting.
   Captures "how expensive is it to trade during volatile episodes" without
   arbitrary threshold selection.
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

NAME = "amihud_conditioning_0930_1130_1300_1457"

OUTPUT_NAMES = [
    "amihud_vol_accel_full",        # Amihud on volume-acceleration bars
    "amihud_hhi_full",              # Herfindahl concentration of bar-level Amihud
    "amihud_low_vol_full",          # Amihud on bottom-25% volume bars
    "amihud_cv_full",               # Coefficient of variation of per-bar Amihud
    "amihud_return_weighted_full",  # Return-magnitude weighted Amihud
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]
    amount = inputs[2]

    n = close.size
    n_out = 5

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 30:
        return out

    # --- Pre-compute returns (bar i -> bar i+1) ---
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    valid_ret_count = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0 or c1 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = c1 / c0 - 1.0
            valid_ret_count += 1

    if valid_ret_count < 30:
        return out

    # --- Pre-compute per-bar Amihud: |return_i| / amount_i ---
    amihud_bars = np.empty(n_ret, dtype=np.float64)
    valid_count = 0
    for i in range(n_ret):
        r = rets[i]
        a = amount[i + 1]
        if not np.isnan(r) and not np.isnan(a) and a > 0.0:
            amihud_bars[i] = abs(r) / a
            valid_count += 1
        else:
            amihud_bars[i] = np.nan

    if valid_count < 30:
        return out

    # --- Collect valid Amihud values and compute basic stats ---
    valid_ah = np.empty(valid_count, dtype=np.float64)
    vi = 0
    for i in range(n_ret):
        if not np.isnan(amihud_bars[i]):
            valid_ah[vi] = amihud_bars[i]
            vi += 1

    ah_sum = 0.0
    for i in range(valid_count):
        ah_sum += valid_ah[i]
    ah_mean = ah_sum / valid_count

    if ah_mean <= 0.0:
        return out

    # --- Find volume percentiles for conditioning ---
    valid_volumes = np.empty(n, dtype=np.float64)
    valid_vol_cnt = 0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v) and v > 0.0:
            valid_volumes[valid_vol_cnt] = v
            valid_vol_cnt += 1

    vol_p25 = 0.0
    vol_p75 = 0.0
    if valid_vol_cnt >= 10:
        sorted_vols = np.sort(valid_volumes[:valid_vol_cnt])
        p25_idx = int(valid_vol_cnt * 0.25)
        p75_idx = int(valid_vol_cnt * 0.75)
        if p25_idx >= valid_vol_cnt:
            p25_idx = valid_vol_cnt - 1
        if p75_idx >= valid_vol_cnt:
            p75_idx = valid_vol_cnt - 1
        vol_p25 = sorted_vols[p25_idx]
        vol_p75 = sorted_vols[p75_idx]

    # === 0: amihud_vol_accel_full ===
    # Amihud on bars where volume increased vs previous bar
    accel_sum = 0.0
    accel_cnt = 0
    for i in range(n_ret):
        ah = amihud_bars[i]
        if np.isnan(ah):
            continue
        # volume[i+1] is the bar whose return is rets[i]
        v_curr = volume[i + 1]
        v_prev = volume[i]
        if np.isnan(v_curr) or np.isnan(v_prev) or v_curr <= 0.0 or v_prev <= 0.0:
            continue
        if v_curr > v_prev:
            accel_sum += ah
            accel_cnt += 1
    if accel_cnt >= 10:
        out[0] = (accel_sum / accel_cnt) * 1.0e9

    # === 1: amihud_hhi_full ===
    # Herfindahl concentration: sum((ah_i / sum_ah)^2)
    if ah_sum > 0.0:
        hhi = 0.0
        for i in range(valid_count):
            share = valid_ah[i] / ah_sum
            hhi += share * share
        out[1] = hhi

    # === 2: amihud_low_vol_full ===
    # Amihud on bottom-25% volume bars (complement of high_vol_illiq)
    if valid_vol_cnt >= 10 and vol_p25 > 0.0:
        low_sum = 0.0
        low_cnt = 0
        for i in range(n_ret):
            ah = amihud_bars[i]
            v = volume[i + 1]
            if not np.isnan(ah) and not np.isnan(v) and v > 0.0:
                if v <= vol_p25:
                    low_sum += ah
                    low_cnt += 1
        if low_cnt >= 5:
            out[2] = (low_sum / low_cnt) * 1.0e9

    # === 3: amihud_cv_full ===
    # Coefficient of variation: std / mean
    ah_sq_sum = 0.0
    for i in range(valid_count):
        ah_sq_sum += valid_ah[i] * valid_ah[i]
    ah_var = ah_sq_sum / valid_count - ah_mean * ah_mean
    if ah_var > 0.0:
        ah_std = np.sqrt(ah_var)
        out[3] = ah_std / ah_mean

    # === 4: amihud_return_weighted_full ===
    # sum(|r_i|^2 / amount_i) / sum(|r_i|) = sum(|r_i| * amihud_i) / sum(|r_i|)
    # Each bar's Amihud weighted by its |return| magnitude
    rw_num = 0.0
    rw_den = 0.0
    for i in range(n_ret):
        r = rets[i]
        ah = amihud_bars[i]
        if not np.isnan(r) and not np.isnan(ah):
            ar = abs(r)
            rw_num += ar * ah
            rw_den += ar
    if rw_den > 0.0:
        out[4] = (rw_num / rw_den) * 1.0e9

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
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Amihud conditioning variants for full trading day "
            "(09:30-11:30 + 13:00-14:57). "
            "Emits 5 variables: volume-acceleration conditioned Amihud, "
            "Herfindahl concentration of bar-level Amihud, "
            "low-volume bar Amihud, "
            "coefficient of variation of Amihud, "
            "and return-magnitude weighted Amihud. "
            "237 bars for stable estimates."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the Amihud conditioning full-day bundle"
    )
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--skip-validate", action="store_true")
    parser.add_argument("--print-json", action="store_true")
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
