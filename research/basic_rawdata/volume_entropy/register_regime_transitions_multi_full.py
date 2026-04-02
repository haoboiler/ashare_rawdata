#!/usr/bin/env python3
"""Multi-dimension regime transition bundle for the full-day window.

Bundle: regime_transitions_multi_full
- Input: close, open, high, low, volume, amount (basic6)
- Output: 5 variables measuring regime transition frequency across different
  market dimensions as liquidity quality proxies.

Hypothesis: Regime transition frequency (how often a per-bar metric crosses its
daily median) captures liquidity quality better than continuous distribution
statistics (entropy, Gini, etc.). This is validated by vol_regime_transitions_full
(Exp#007, conclusion #16). We extend this paradigm to 5 new dimensions:

1. Amount (trading value) regime transitions
2. Bar range (intraday spread proxy) regime transitions
3. Amihud (price impact) regime transitions
4. Candlestick body ratio regime transitions
5. VWAP cross transitions (price vs running VWAP)

Each feature discretizes a different per-bar metric into above/below median,
then counts the transition frequency. Discretization eliminates absolute
magnitude (avoiding market-cap proxy), while transition frequency captures
time-series microstructure behavior.

Uses full-day window (~237 bars) for stable estimation per conclusion #11.
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

NAME = "regime_transitions_multi_full"

OUTPUT_NAMES = [
    "amount_regime_transitions_full",      # Amount crossing daily median frequency
    "bar_range_regime_transitions_full",   # (High-Low)/Close crossing daily median frequency
    "amihud_regime_transitions_full",      # |return|/amount crossing daily median frequency
    "body_ratio_transitions_full",         # |Close-Open|/(High-Low+eps) crossing daily median frequency
    "vwap_cross_transitions_full",         # Close crossing running VWAP frequency
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
    if n < 30:
        return out

    # ---- Step 1: Compute per-bar metrics for bars with valid return ----
    n_ret = n - 1

    amounts_arr = np.empty(n_ret, dtype=np.float64)
    ranges_arr = np.empty(n_ret, dtype=np.float64)
    amihud_arr = np.empty(n_ret, dtype=np.float64)
    body_arr = np.empty(n_ret, dtype=np.float64)
    valid_cnt = 0

    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        o1 = open_[i + 1]
        h1 = high[i + 1]
        l1 = low[i + 1]
        a1 = amount[i + 1]

        if (np.isnan(c0) or np.isnan(c1) or np.isnan(o1) or
            np.isnan(h1) or np.isnan(l1) or np.isnan(a1) or
            c0 <= 0.0 or c1 <= 0.0 or a1 <= 0.0):
            continue

        abs_ret = abs(np.log(c1 / c0))
        bar_range = (h1 - l1) / c1
        amihud_val = abs_ret / a1
        shadow = h1 - l1
        if shadow > 1e-10:
            body_ratio = abs(c1 - o1) / shadow
        else:
            body_ratio = 0.0

        amounts_arr[valid_cnt] = a1
        ranges_arr[valid_cnt] = bar_range
        amihud_arr[valid_cnt] = amihud_val
        body_arr[valid_cnt] = body_ratio
        valid_cnt += 1

    if valid_cnt < 30:
        return out

    # ---- Step 2: Sort to find medians ----
    sorted_amounts = np.empty(valid_cnt, dtype=np.float64)
    sorted_ranges = np.empty(valid_cnt, dtype=np.float64)
    sorted_amihud = np.empty(valid_cnt, dtype=np.float64)
    sorted_body = np.empty(valid_cnt, dtype=np.float64)

    for i in range(valid_cnt):
        sorted_amounts[i] = amounts_arr[i]
        sorted_ranges[i] = ranges_arr[i]
        sorted_amihud[i] = amihud_arr[i]
        sorted_body[i] = body_arr[i]

    sorted_amounts = np.sort(sorted_amounts)
    sorted_ranges = np.sort(sorted_ranges)
    sorted_amihud = np.sort(sorted_amihud)
    sorted_body = np.sort(sorted_body)

    half = valid_cnt // 2
    if valid_cnt % 2 == 0:
        med_amount = (sorted_amounts[half - 1] + sorted_amounts[half]) / 2.0
        med_range = (sorted_ranges[half - 1] + sorted_ranges[half]) / 2.0
        med_amihud = (sorted_amihud[half - 1] + sorted_amihud[half]) / 2.0
        med_body = (sorted_body[half - 1] + sorted_body[half]) / 2.0
    else:
        med_amount = sorted_amounts[half]
        med_range = sorted_ranges[half]
        med_amihud = sorted_amihud[half]
        med_body = sorted_body[half]

    denom = float(valid_cnt - 1)

    # ---- 0: amount_regime_transitions_full ----
    # Amount crossing daily median. Amount = volume * price (yuan), so it
    # captures trading VALUE rather than share count. Frequent switching
    # means no value-clustering, indicating distributed liquidity.
    trans = 0
    prev = amounts_arr[0] > med_amount
    for i in range(1, valid_cnt):
        curr = amounts_arr[i] > med_amount
        if curr != prev:
            trans += 1
        prev = curr
    out[0] = float(trans) / denom

    # ---- 1: bar_range_regime_transitions_full ----
    # (High-Low)/Close crossing daily median. Bar range is a proxy for
    # bid-ask spread. High transition freq = spread is evenly distributed
    # across the day = stable microstructure quality.
    trans = 0
    prev = ranges_arr[0] > med_range
    for i in range(1, valid_cnt):
        curr = ranges_arr[i] > med_range
        if curr != prev:
            trans += 1
        prev = curr
    out[1] = float(trans) / denom

    # ---- 2: amihud_regime_transitions_full ----
    # |return|/amount crossing daily median. Discretized Amihud illiquidity.
    # High transition freq = price impact is not persistent across bars =
    # better execution quality, no sustained information asymmetry.
    trans = 0
    prev = amihud_arr[0] > med_amihud
    for i in range(1, valid_cnt):
        curr = amihud_arr[i] > med_amihud
        if curr != prev:
            trans += 1
        prev = curr
    out[2] = float(trans) / denom

    # ---- 3: body_ratio_transitions_full ----
    # |Close-Open|/(High-Low+eps) crossing daily median. Candlestick body
    # ratio measures directional conviction within a bar. Frequent regime
    # switching = no persistent micro-trend = competitive market making.
    trans = 0
    prev = body_arr[0] > med_body
    for i in range(1, valid_cnt):
        curr = body_arr[i] > med_body
        if curr != prev:
            trans += 1
        prev = curr
    out[3] = float(trans) / denom

    # ---- 4: vwap_cross_transitions_full ----
    # Close crossing running VWAP. Running VWAP = cumsum(close*vol) /
    # cumsum(vol) in hfq space. Frequent crossing = price mean-reverts to
    # fair value = high liquidity depth.
    cum_pv = 0.0
    cum_v = 0.0
    trans_vwap = 0
    first_valid = True
    prev_above = False
    vwap_bars = 0

    for i in range(n):
        c = close[i]
        v = volume[i]
        if np.isnan(c) or np.isnan(v) or c <= 0.0 or v <= 0.0:
            continue
        cum_pv += c * v
        cum_v += v
        vwap_bars += 1
        if cum_v > 0.0:
            vwap_val = cum_pv / cum_v
            curr_above = c > vwap_val
            if first_valid:
                first_valid = False
            else:
                if curr_above != prev_above:
                    trans_vwap += 1
            prev_above = curr_above

    if vwap_bars > 1:
        out[4] = float(trans_vwap) / float(vwap_bars - 1)

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
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Multi-dimension regime transition bundle for full-day window "
            "(09:30-11:30 + 13:00-14:57). Extends the validated regime transition "
            "frequency paradigm (vol_regime_transitions_full) to 5 new dimensions: "
            "amount, bar range, Amihud illiquidity, candlestick body ratio, and "
            "VWAP crossing. Each feature discretizes a per-bar metric and counts "
            "transition frequency as a liquidity quality proxy."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the multi-dimension regime transition bundle"
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
