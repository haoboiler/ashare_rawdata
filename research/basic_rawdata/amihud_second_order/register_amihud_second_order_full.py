#!/usr/bin/env python3
"""Register the Amihud second-order properties bundle for full-day window.

Bundle: amihud_second_order_0930_1130_1300_1457
- Input: close, amount (from 1m bars)
- Output: 3 variables capturing second-order properties of intraday Amihud distribution.

Full-day window (237 bars) for stable estimates.

Physical hypotheses:

1. amihud_autocorr1_full: Lag-1 autocorrelation of per-bar Amihud series.
   High autocorrelation = illiquidity is temporally clustered (a few illiquid
   episodes persist for multiple consecutive bars). Low autocorrelation = price
   impact is random/memoryless, consistent with continuous market-making.
   Different from Amihud LEVEL (which is the average) and from illiq_variability
   (which is overall dispersion). This captures the TEMPORAL STRUCTURE of liquidity.

2. amihud_tail_ratio_full: P90 / P50 of per-bar Amihud distribution.
   High tail ratio = occasional extreme price impact events ("flash illiquidity").
   A stock can have low mean Amihud but high tail ratio if liquidity is usually
   good but occasionally vanishes (e.g., during news events or large block trades).
   Different from CV (which measures symmetric dispersion) - this focuses specifically
   on the upper tail of the Amihud distribution.

3. amihud_diff_mean_full: Mean of |Amihud_t - Amihud_{t-1}| / mean(Amihud).
   Measures bar-to-bar liquidity instability. High = liquidity constantly changes
   (unreliable execution cost estimation). Different from autocorrelation (linear
   persistence) and tail ratio (extreme events). This captures the "roughness" of
   the liquidity path - inspired by how path roughness measures distinguish
   Brownian motion from fractional Brownian motion.
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

NAME = "amihud_second_order_0930_1130_1300_1457"

OUTPUT_NAMES = [
    "amihud_autocorr1_full",       # Lag-1 autocorrelation of per-bar Amihud
    "amihud_tail_ratio_full",      # P90/P50 of Amihud distribution
    "amihud_diff_mean_full",       # Mean |delta Amihud| / mean Amihud
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    amount = inputs[1]

    n = close.size
    n_out = 3

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 30:
        return out

    # --- Pre-compute returns (bar i -> bar i+1) ---
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0 or c1 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = c1 / c0 - 1.0

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

    # --- Collect valid Amihud values for statistics ---
    valid_ah = np.empty(valid_count, dtype=np.float64)
    vi = 0
    for i in range(n_ret):
        if not np.isnan(amihud_bars[i]):
            valid_ah[vi] = amihud_bars[i]
            vi += 1

    # Mean of valid Amihud
    ah_sum = 0.0
    for i in range(valid_count):
        ah_sum += valid_ah[i]
    ah_mean = ah_sum / valid_count

    if ah_mean <= 0.0:
        return out

    # --- 0: amihud_autocorr1_full (lag-1 autocorrelation) ---
    # Collect consecutive valid pairs
    sum_x = 0.0
    sum_y = 0.0
    sum_xx = 0.0
    sum_yy = 0.0
    sum_xy = 0.0
    pair_count = 0

    for i in range(n_ret - 1):
        ah_curr = amihud_bars[i]
        ah_next = amihud_bars[i + 1]
        if not np.isnan(ah_curr) and not np.isnan(ah_next):
            sum_x += ah_curr
            sum_y += ah_next
            sum_xx += ah_curr * ah_curr
            sum_yy += ah_next * ah_next
            sum_xy += ah_curr * ah_next
            pair_count += 1

    if pair_count >= 20:
        mean_x = sum_x / pair_count
        mean_y = sum_y / pair_count
        var_x = sum_xx / pair_count - mean_x * mean_x
        var_y = sum_yy / pair_count - mean_y * mean_y
        cov_xy = sum_xy / pair_count - mean_x * mean_y
        denom = var_x * var_y
        if denom > 0.0:
            out[0] = cov_xy / np.sqrt(denom)

    # --- 1: amihud_tail_ratio_full (P90/P50) ---
    sorted_ah = np.sort(valid_ah)
    p50_idx = int(valid_count * 0.50)
    p90_idx = int(valid_count * 0.90)
    if p50_idx >= valid_count:
        p50_idx = valid_count - 1
    if p90_idx >= valid_count:
        p90_idx = valid_count - 1
    p50 = sorted_ah[p50_idx]
    p90 = sorted_ah[p90_idx]
    if p50 > 0.0:
        out[1] = p90 / p50

    # --- 2: amihud_diff_mean_full (mean |delta Amihud| / mean Amihud) ---
    diff_sum = 0.0
    diff_count = 0
    for i in range(n_ret - 1):
        ah_curr = amihud_bars[i]
        ah_next = amihud_bars[i + 1]
        if not np.isnan(ah_curr) and not np.isnan(ah_next):
            diff_sum += abs(ah_next - ah_curr)
            diff_count += 1

    if diff_count >= 20:
        diff_mean = diff_sum / diff_count
        out[2] = diff_mean / ah_mean

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]),
        slot=RawDataSlot.EVENING,
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Second-order properties of intraday Amihud distribution for full trading day "
            "(09:30-11:30 + 13:00-14:57). "
            "Emits 3 variables: lag-1 autocorrelation of per-bar Amihud, "
            "P90/P50 tail ratio, "
            "and mean bar-to-bar Amihud change normalized by mean. "
            "237 bars for stable temporal structure estimation."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the Amihud second-order full-day bundle"
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
