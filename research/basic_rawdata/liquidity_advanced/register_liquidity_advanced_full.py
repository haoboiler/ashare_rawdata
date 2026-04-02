#!/usr/bin/env python3
"""Register the advanced liquidity estimators bundle for the full-day window.

Bundle: liquidity_advanced_0930_1130_1300_1457
- Input: close, high, low, volume, amount (from 1m bars)
- Output: 5 variables capturing different aspects of intraday liquidity.

Full-day window (237 bars) for stable estimates.

Physical hypotheses:
1. kyle_lambda_full: Correlation between |return| and log(amount) across bars.
   Measures how strongly trading activity moves prices (scale-free price impact).
   Positive correlation = more illiquid. Unlike Amihud (simple mean ratio),
   this captures the ASSOCIATION between volume and price movement.

2. high_vol_amihud_full: Amihud illiquidity measured ONLY on high-volume bars
   (above daily median volume). During active trading, if price impact remains
   high, it indicates that large orders are moving prices adversely (informed
   trading). If price impact is low during high volume, the market efficiently
   absorbs flow. Connects to D-006 "high volume ratio" theme.

3. vw_hl_spread_full: Volume-weighted (high-low) spread:
   sum(volume_i * (high_i - low_i) / mid_i) / sum(volume_i).
   Different estimator from CS spread (adjacent-bar based). Volume weighting
   gives more importance to actively traded bars.

4. effective_half_spread_full: mean(|close_i - (high_i+low_i)/2| / close_i).
   Proxy for effective half-spread: how far does the closing trade deviate from
   the bar's midpoint? Larger deviation = higher transaction costs. Captures
   the "realized cost" of the marginal trade in each bar.

5. liquidity_resilience_full: After a high-illiquidity bar (|return|/amount >
   daily mean), fraction of subsequent bars where illiquidity returns to below
   mean. Higher resilience = faster recovery from liquidity shocks = better
   market quality. Discrete counting approach (validated by conclusions #16).
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

NAME = "liquidity_advanced_0930_1130_1300_1457"

OUTPUT_NAMES = [
    "kyle_lambda_full",             # Corr(|return|, log(amount)) - price impact association
    "high_vol_amihud_full",         # Amihud on high-volume bars only * 1e9
    "vw_hl_spread_full",            # Volume-weighted (high-low)/mid spread
    "effective_half_spread_full",   # mean(|close - HL_mid| / close)
    "liquidity_resilience_full",    # Recovery rate after illiquid bars
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    high = inputs[1]
    low = inputs[2]
    volume = inputs[3]
    amount = inputs[4]

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

    # --- 0: kyle_lambda_full ---
    # Pearson correlation between |return_i| and log(amount_i)
    # Scale-free measure of price impact association
    sum_x = 0.0
    sum_y = 0.0
    sum_xx = 0.0
    sum_yy = 0.0
    sum_xy = 0.0
    corr_cnt = 0
    for i in range(n_ret):
        r = rets[i]
        a = amount[i + 1]
        if not np.isnan(r) and not np.isnan(a) and a > 0.0:
            x = np.log(a)
            y = abs(r)
            sum_x += x
            sum_y += y
            sum_xx += x * x
            sum_yy += y * y
            sum_xy += x * y
            corr_cnt += 1
    if corr_cnt > 10:
        mean_x = sum_x / corr_cnt
        mean_y = sum_y / corr_cnt
        var_x = sum_xx / corr_cnt - mean_x * mean_x
        var_y = sum_yy / corr_cnt - mean_y * mean_y
        if var_x > 0.0 and var_y > 0.0:
            cov_xy = sum_xy / corr_cnt - mean_x * mean_y
            out[0] = cov_xy / np.sqrt(var_x * var_y)

    # --- Compute median volume for feature 1 ---
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

    # --- 1: high_vol_amihud_full ---
    # Amihud illiquidity measured ONLY on bars with volume > median
    if has_median:
        hv_amihud_sum = 0.0
        hv_amihud_cnt = 0
        for i in range(n_ret):
            r = rets[i]
            a = amount[i + 1]
            v = volume[i + 1]
            if not np.isnan(r) and not np.isnan(a) and not np.isnan(v) and a > 0.0:
                if v > median_vol:
                    hv_amihud_sum += abs(r) / a
                    hv_amihud_cnt += 1
        if hv_amihud_cnt > 5:
            out[1] = (hv_amihud_sum / hv_amihud_cnt) * 1.0e9

    # --- 2: vw_hl_spread_full ---
    # Volume-weighted (high-low)/mid spread across all bars
    vw_spread_sum = 0.0
    vw_total_vol = 0.0
    for i in range(n):
        h = high[i]
        l = low[i]
        v = volume[i]
        if np.isnan(h) or np.isnan(l) or np.isnan(v):
            continue
        if v <= 0.0 or h <= 0.0 or l <= 0.0:
            continue
        mid = (h + l) / 2.0
        if mid > 0.0:
            spread = (h - l) / mid
            vw_spread_sum += v * spread
            vw_total_vol += v
    if vw_total_vol > 0.0:
        out[2] = vw_spread_sum / vw_total_vol

    # --- 3: effective_half_spread_full ---
    # mean(|close_i - (high_i + low_i)/2| / close_i)
    eff_sum = 0.0
    eff_cnt = 0
    for i in range(n):
        c = close[i]
        h = high[i]
        l = low[i]
        if np.isnan(c) or np.isnan(h) or np.isnan(l) or c <= 0.0:
            continue
        mid = (h + l) / 2.0
        eff_sum += abs(c - mid) / c
        eff_cnt += 1
    if eff_cnt > 0:
        out[3] = eff_sum / eff_cnt

    # --- 4: liquidity_resilience_full ---
    # After a high-illiquidity bar (|r|/amount > mean), fraction of next bars
    # where illiquidity returns to below mean (recovery)
    # First compute bar-level illiquidity and mean
    bar_illiq = np.full(n_ret, np.nan, dtype=np.float64)
    illiq_sum = 0.0
    illiq_cnt = 0
    for i in range(n_ret):
        r = rets[i]
        a = amount[i + 1]
        if not np.isnan(r) and not np.isnan(a) and a > 0.0:
            val = abs(r) / a
            bar_illiq[i] = val
            illiq_sum += val
            illiq_cnt += 1

    if illiq_cnt >= 10:
        mean_illiq = illiq_sum / illiq_cnt
        shock_cnt = 0
        recovery_cnt = 0
        for i in range(n_ret - 1):
            if not np.isnan(bar_illiq[i]) and bar_illiq[i] > mean_illiq:
                shock_cnt += 1
                if not np.isnan(bar_illiq[i + 1]) and bar_illiq[i + 1] <= mean_illiq:
                    recovery_cnt += 1
        if shock_cnt > 5:
            out[4] = float(recovery_cnt) / float(shock_cnt)

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "high", "low", "volume", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]),
        slot=RawDataSlot.EVENING,
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Advanced liquidity estimators for full trading day "
            "(09:30-11:30 + 13:00-14:57, excluding closing auction). "
            "Emits 5 variables: Kyle's lambda (price-volume correlation), "
            "high-volume Amihud illiquidity, volume-weighted HL spread, "
            "effective half-spread, and liquidity resilience. "
            "237 bars for stable estimates."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the advanced liquidity full-day bundle"
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
