#!/usr/bin/env python3
"""Register the high-volume advanced liquidity bundle for the full-day window.

Bundle: high_volume_advanced_0930_1130_1300_1457
- Input: close, volume, amount (from 1m bars)
- Output: 4 variables exploring advanced high-volume liquidity conditioning.

Full-day window (237 bars) for stable estimates.

Physical hypotheses:
1. Reversal Amihud: Price impact measured ONLY on bars where price reversed from
   the previous bar's direction. When price reverses, a liquidity provider absorbed
   flow against the prevailing trend. The Amihud on these bars captures the "cost
   of providing liquidity" rather than the "cost of consuming liquidity".
   Different from regular Amihud (all bars) or high_vol_illiq (volume filter only).

2. High-volume Impact Ratio: Ratio of mean Amihud on top-25% volume bars to mean
   Amihud on bottom-75% volume bars. Measures price impact convexity/nonlinearity.
   If ratio > 1, even high-volume bars have disproportionate price impact → market
   lacks depth. If ratio < 1 (normal), high-volume bars absorb impact efficiently.
   This ratio is fundamentally different from the LEVEL of Amihud.

3. Amihud Session Diff: Amihud in the afternoon session minus morning session.
   Morning = first 120 bars (09:30-11:30), afternoon = remaining bars (13:00-14:57).
   Stocks whose liquidity deteriorates intraday face higher execution risk for
   afternoon/closing trades. Captures time-of-day liquidity dynamics.

4. High-volume Reversal Amihud: Amihud on bars satisfying BOTH conditions:
   (a) volume in top-25% quartile, AND (b) price reversed from previous bar.
   This is the purest measure of "cost of absorbing flow during active market-making".
   Combines the proven effectiveness of high-volume filtering (conclusion #21) with
   the reversal-conditioning logic of feature #1.
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

NAME = "high_volume_advanced_0930_1130_1300_1457"

OUTPUT_NAMES = [
    "reversal_amihud_full",            # Amihud on reversal bars only
    "high_vol_impact_ratio_full",      # Amihud ratio: high-vol / low-vol bars
    "amihud_session_diff_full",        # Afternoon Amihud - Morning Amihud
    "high_vol_reversal_amihud_full",   # Amihud on high-vol AND reversal bars
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]
    amount = inputs[2]

    n = close.size
    n_out = 4

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 20:
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

    if valid_ret_count < 20:
        return out

    # --- Pre-compute per-bar Amihud: |return_i| / amount_i ---
    amihud_bars = np.empty(n_ret, dtype=np.float64)
    for i in range(n_ret):
        r = rets[i]
        a = amount[i + 1]
        if not np.isnan(r) and not np.isnan(a) and a > 0.0:
            amihud_bars[i] = abs(r) / a
        else:
            amihud_bars[i] = np.nan

    # --- Find volume 75th percentile for high-volume filtering ---
    valid_volumes = np.empty(n, dtype=np.float64)
    valid_vol_cnt = 0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v) and v > 0.0:
            valid_volumes[valid_vol_cnt] = v
            valid_vol_cnt += 1

    vol_p75 = 0.0
    if valid_vol_cnt >= 10:
        sorted_vols = np.sort(valid_volumes[:valid_vol_cnt])
        p75_idx = int(valid_vol_cnt * 0.75)
        if p75_idx >= valid_vol_cnt:
            p75_idx = valid_vol_cnt - 1
        vol_p75 = sorted_vols[p75_idx]

    # --- 0: reversal_amihud_full ---
    # Amihud only on bars where price reversed from previous bar direction
    # A reversal bar: ret[i] and ret[i-1] have opposite signs (one positive, one negative)
    rev_sum = 0.0
    rev_cnt = 0
    for i in range(1, n_ret):
        r_prev = rets[i - 1]
        r_curr = rets[i]
        ah = amihud_bars[i]
        if not np.isnan(r_prev) and not np.isnan(r_curr) and not np.isnan(ah):
            # Reversal: signs differ and both non-zero
            if r_prev * r_curr < 0.0:
                rev_sum += ah
                rev_cnt += 1
    if rev_cnt >= 5:
        out[0] = (rev_sum / rev_cnt) * 1.0e9

    # --- 1: high_vol_impact_ratio_full ---
    # Ratio of mean Amihud on high-vol bars to mean Amihud on low-vol bars
    if valid_vol_cnt >= 10 and vol_p75 > 0.0:
        high_sum = 0.0
        high_cnt = 0
        low_sum = 0.0
        low_cnt = 0
        for i in range(n_ret):
            ah = amihud_bars[i]
            v = volume[i + 1]
            if not np.isnan(ah) and not np.isnan(v) and v > 0.0:
                if v > vol_p75:
                    high_sum += ah
                    high_cnt += 1
                else:
                    low_sum += ah
                    low_cnt += 1
        if high_cnt >= 5 and low_cnt >= 5:
            high_mean = high_sum / high_cnt
            low_mean = low_sum / low_cnt
            if low_mean > 0.0:
                out[1] = high_mean / low_mean

    # --- 2: amihud_session_diff_full ---
    # Morning session: first 120 bars (indices 0..119)
    # Afternoon session: remaining bars (indices 120..n-1)
    # But n_ret = n-1, so morning rets are indices 0..118, afternoon 119..n_ret-1
    morning_end = min(119, n_ret)  # 120 bars -> 119 returns (0-based inclusive)
    am_sum = 0.0
    am_cnt = 0
    for i in range(morning_end):
        ah = amihud_bars[i]
        if not np.isnan(ah):
            am_sum += ah
            am_cnt += 1

    pm_sum = 0.0
    pm_cnt = 0
    for i in range(morning_end, n_ret):
        ah = amihud_bars[i]
        if not np.isnan(ah):
            pm_sum += ah
            pm_cnt += 1

    if am_cnt >= 10 and pm_cnt >= 10:
        am_mean = am_sum / am_cnt
        pm_mean = pm_sum / pm_cnt
        # Positive = afternoon less liquid; normalize by overall mean to avoid scale bias
        overall_mean = (am_sum + pm_sum) / (am_cnt + pm_cnt)
        if overall_mean > 0.0:
            out[2] = (pm_mean - am_mean) / overall_mean

    # --- 3: high_vol_reversal_amihud_full ---
    # Amihud on bars that are BOTH high-volume AND reversal
    if valid_vol_cnt >= 10 and vol_p75 > 0.0:
        hvr_sum = 0.0
        hvr_cnt = 0
        for i in range(1, n_ret):
            r_prev = rets[i - 1]
            r_curr = rets[i]
            ah = amihud_bars[i]
            v = volume[i + 1]
            if (not np.isnan(r_prev) and not np.isnan(r_curr)
                    and not np.isnan(ah) and not np.isnan(v)):
                if r_prev * r_curr < 0.0 and v > vol_p75:
                    hvr_sum += ah
                    hvr_cnt += 1
        if hvr_cnt >= 3:
            out[3] = (hvr_sum / hvr_cnt) * 1.0e9

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
            "Advanced high-volume liquidity conditioning for full trading day "
            "(09:30-11:30 + 13:00-14:57). "
            "Emits 4 variables: reversal-conditioned Amihud, "
            "high/low volume impact ratio, "
            "afternoon-morning Amihud session diff, "
            "and high-volume reversal Amihud. "
            "237 bars for stable estimates."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the high-volume advanced full-day bundle"
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
