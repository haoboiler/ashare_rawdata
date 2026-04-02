#!/usr/bin/env python3
"""Register the liquidity impact bundle for the full-day window.

Bundle: liquidity_impact_0930_1130_1300_1457
- Input: close, volume, amount (from 1m bars)
- Output: 5 variables capturing liquidity impact and order flow characteristics.

Full-day window (237 bars) for stable estimates.

Physical hypothesis:
1. Amihud illiquidity (Amihud 2002): |return|/amount measures price impact per unit
   of trading activity. Higher values = less liquid = higher expected returns (liquidity premium).
   Uses amount (CNY) instead of volume (shares) to avoid market-cap scaling issues.
2. Flow toxicity: average run length of consecutive same-direction bars approximates
   VPIN (volume-synchronized probability of informed trading). Longer runs = more
   informed trading = higher adverse selection risk.
3. Large trade reversal: frequency of price direction reversal after high-volume bars
   measures market resilience/depth. Higher reversal = better depth = lower spread.
   Discrete counting method (validated by conclusions #16).
4. Volume impact ratio: ratio of mean |return| in high-vol bars to low-vol bars.
   Higher ratio = larger price impact from volume = less liquid market.
5. Order flow imbalance: sum(sign(r)*volume)/sum(volume). Net directional pressure.
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

NAME = "liquidity_impact_0930_1130_1300_1457"

OUTPUT_NAMES = [
    "amihud_illiq_full",            # Amihud illiquidity: mean(|return| / amount) * 1e9
    "flow_toxicity_full",           # Mean run length of consecutive same-direction bars
    "large_trade_reversal_full",    # Reversal frequency after high-volume bars
    "vol_impact_ratio_full",        # Price impact ratio: high-vol |r| / low-vol |r|
    "order_flow_imbalance_full",    # sum(sign(r)*volume) / sum(volume)
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]
    amount = inputs[2]

    n = close.size
    n_out = 5

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 10:
        return out

    # --- Pre-compute returns ---
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

    if valid_ret_count < 10:
        return out

    # --- 0: amihud_illiq_full ---
    # mean(|return_i| / amount_i) * 1e9
    amihud_sum = 0.0
    amihud_cnt = 0
    for i in range(n_ret):
        r = rets[i]
        a = amount[i + 1]  # amount of the bar whose return is rets[i]
        if not np.isnan(r) and not np.isnan(a) and a > 0.0:
            amihud_sum += abs(r) / a
            amihud_cnt += 1
    if amihud_cnt > 0:
        out[0] = (amihud_sum / amihud_cnt) * 1.0e9

    # --- 1: flow_toxicity_full ---
    # Average run length of consecutive same-direction bars
    run_lengths_sum = 0.0
    run_count = 0
    current_run = 1
    prev_sign = 0
    first_valid = True
    for i in range(n_ret):
        r = rets[i]
        if np.isnan(r):
            continue
        if r > 0.0:
            s = 1
        elif r < 0.0:
            s = -1
        else:
            s = 0
        if first_valid:
            prev_sign = s
            current_run = 1
            first_valid = False
        else:
            if s == prev_sign:
                current_run += 1
            else:
                run_lengths_sum += current_run
                run_count += 1
                current_run = 1
                prev_sign = s
    # Add last run
    if not first_valid:
        run_lengths_sum += current_run
        run_count += 1
    if run_count > 0:
        out[1] = run_lengths_sum / run_count

    # --- Compute median volume for features 2 and 3 ---
    valid_vols = np.empty(n, dtype=np.float64)
    valid_vol_cnt = 0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v) and v > 0.0:
            valid_vols[valid_vol_cnt] = v
            valid_vol_cnt += 1

    median_vol = 0.0
    has_median = False
    if valid_vol_cnt >= 10:
        sorted_vols = np.sort(valid_vols[:valid_vol_cnt])
        median_vol = sorted_vols[valid_vol_cnt // 2]
        has_median = True

    # --- 2: large_trade_reversal_full ---
    # Frequency of price direction reversal after high-volume bars
    if has_median:
        reversal_cnt = 0
        high_vol_cnt = 0
        for i in range(n_ret - 1):
            r_curr = rets[i]
            r_next = rets[i + 1]
            v = volume[i + 1]  # volume of bar producing rets[i]
            if np.isnan(r_curr) or np.isnan(r_next) or np.isnan(v):
                continue
            if v > median_vol:
                high_vol_cnt += 1
                # Check reversal: opposite signs
                if (r_curr > 0.0 and r_next < 0.0) or (r_curr < 0.0 and r_next > 0.0):
                    reversal_cnt += 1
        if high_vol_cnt > 5:
            out[2] = float(reversal_cnt) / float(high_vol_cnt)

    # --- 3: vol_impact_ratio_full ---
    # mean(|return|) for high-vol bars / mean(|return|) for low-vol bars
    if has_median:
        high_ret_sum = 0.0
        high_ret_cnt = 0
        low_ret_sum = 0.0
        low_ret_cnt = 0
        for i in range(n_ret):
            r = rets[i]
            v = volume[i + 1]
            if np.isnan(r) or np.isnan(v):
                continue
            ar = abs(r)
            if v > median_vol:
                high_ret_sum += ar
                high_ret_cnt += 1
            else:
                low_ret_sum += ar
                low_ret_cnt += 1
        if high_ret_cnt > 0 and low_ret_cnt > 0 and low_ret_sum > 0.0:
            out[3] = (high_ret_sum / high_ret_cnt) / (low_ret_sum / low_ret_cnt)

    # --- 4: order_flow_imbalance_full ---
    # sum(sign(return) * volume) / sum(volume)
    signed_vol_sum = 0.0
    total_vol_sum = 0.0
    for i in range(n_ret):
        r = rets[i]
        v = volume[i + 1]
        if np.isnan(r) or np.isnan(v) or v <= 0.0:
            continue
        if r > 0.0:
            signed_vol_sum += v
        elif r < 0.0:
            signed_vol_sum -= v
        total_vol_sum += v
    if total_vol_sum > 0.0:
        out[4] = signed_vol_sum / total_vol_sum

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
            "Liquidity impact factors for full trading day "
            "(09:30-11:30 + 13:00-14:57, excluding closing auction). "
            "Emits 5 variables: Amihud illiquidity, flow toxicity (run length), "
            "large trade reversal frequency, volume impact ratio, "
            "and order flow imbalance. "
            "237 bars for stable estimates."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the liquidity impact full-day bundle"
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
