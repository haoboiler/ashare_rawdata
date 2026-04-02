#!/usr/bin/env python3
"""Trade activity quality bundle for the full-day window.

Bundle: trade_activity_quality_full
- Input: close, volume, amount (from 1m bars, 09:30-11:30 + 13:00-14:57)
- Output: 5 variables measuring trade activity patterns as liquidity proxies.

Hypothesis: Building on the validated paradigm that discrete transition/frequency
measures capture liquidity quality better than continuous stats (conclusion #16),
this bundle explores 5 trade-activity dimensions:

1. Trade size (amount/volume) regime transitions
2. Volume acceleration (increasing vs decreasing) transitions
3. Amount-weighted price reversal ratio (enhanced reversal_ratio)
4. Intraday cumulative return zero-crossing frequency
5. Volume-price divergence frequency

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

NAME = "trade_activity_quality_full"

OUTPUT_NAMES = [
    "trade_size_transitions_full",         # Amount/volume crossing daily median
    "volume_accel_transitions_full",       # sign(Δvolume) flipping frequency
    "amount_weighted_reversal_full",       # Amount-weighted price reversal ratio
    "cumret_zero_cross_full",              # Intraday cumulative return zero-crossing frequency
    "vol_price_divergence_full",           # Volume-|return| divergence frequency
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

    # ---- Step 1: Compute returns and collect valid data ----
    n_ret = n - 1

    rets = np.empty(n_ret, dtype=np.float64)
    abs_rets = np.empty(n_ret, dtype=np.float64)
    vols = np.empty(n_ret, dtype=np.float64)
    amts = np.empty(n_ret, dtype=np.float64)
    trade_sizes = np.empty(n_ret, dtype=np.float64)
    valid_cnt = 0

    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        v1 = volume[i + 1]
        a1 = amount[i + 1]

        if (np.isnan(c0) or np.isnan(c1) or np.isnan(v1) or np.isnan(a1) or
            c0 <= 0.0 or c1 <= 0.0 or v1 <= 0.0 or a1 <= 0.0):
            continue

        r = np.log(c1 / c0)
        rets[valid_cnt] = r
        abs_rets[valid_cnt] = abs(r)
        vols[valid_cnt] = v1
        amts[valid_cnt] = a1
        trade_sizes[valid_cnt] = a1 / v1
        valid_cnt += 1

    if valid_cnt < 30:
        return out

    # ---- Step 2: Compute medians for trade size ----
    sorted_ts = np.empty(valid_cnt, dtype=np.float64)
    for i in range(valid_cnt):
        sorted_ts[i] = trade_sizes[i]
    sorted_ts = np.sort(sorted_ts)

    half = valid_cnt // 2
    if valid_cnt % 2 == 0:
        med_ts = (sorted_ts[half - 1] + sorted_ts[half]) / 2.0
    else:
        med_ts = sorted_ts[half]

    denom = float(valid_cnt - 1)

    # ---- 0: trade_size_transitions_full ----
    # Amount/volume = average price per share (actual yuan). Crossing daily
    # median measures stability of trade size. Frequent switching = diverse
    # participant mix (retail + institutional), better liquidity.
    trans = 0
    prev = trade_sizes[0] > med_ts
    for i in range(1, valid_cnt):
        curr = trade_sizes[i] > med_ts
        if curr != prev:
            trans += 1
        prev = curr
    out[0] = float(trans) / denom

    # ---- 1: volume_accel_transitions_full ----
    # Whether volume is increasing (vol[i] > vol[i-1]) flips frequently.
    # High switching = no sustained volume trends = no information cascade
    # = better liquidity.
    if valid_cnt < 3:
        pass
    else:
        trans = 0
        prev_inc = vols[1] > vols[0]
        for i in range(2, valid_cnt):
            curr_inc = vols[i] > vols[i - 1]
            if curr_inc != prev_inc:
                trans += 1
            prev_inc = curr_inc
        out[1] = float(trans) / float(valid_cnt - 2)

    # ---- 2: amount_weighted_reversal_full ----
    # Like reversal_ratio but each transition is weighted by the bar's amount.
    # Ratio = sum(amount on reversal bars) / total_amount.
    # This weights reversals by their economic significance. High ratio =
    # large-amount bars frequently reverse = deep market with strong mean-reversion.
    total_amt = 0.0
    reversal_amt = 0.0
    for i in range(valid_cnt):
        total_amt += amts[i]

    if valid_cnt >= 2 and total_amt > 0.0:
        prev_sign = rets[0] > 0.0
        for i in range(1, valid_cnt):
            curr_sign = rets[i] > 0.0
            if curr_sign != prev_sign:
                reversal_amt += amts[i]
            prev_sign = curr_sign
        out[2] = reversal_amt / total_amt

    # ---- 3: cumret_zero_cross_full ----
    # How often does the intraday cumulative return cross zero?
    # cumret[i] = sum(ret[0..i])
    # Frequent zero-crossing = strong intraday mean-reversion = high
    # liquidity depth (market makers keep price near opening level).
    if valid_cnt >= 2:
        cumret = 0.0
        trans = 0
        cumret += rets[0]
        prev_pos = cumret > 0.0
        for i in range(1, valid_cnt):
            cumret += rets[i]
            curr_pos = cumret > 0.0
            if curr_pos != prev_pos:
                trans += 1
            prev_pos = curr_pos
        out[3] = float(trans) / denom

    # ---- 4: vol_price_divergence_full ----
    # Fraction of bars where volume and |return| move in opposite directions.
    # divergence = (vol increases but |ret| decreases) or (vol decreases
    # but |ret| increases). High divergence = volume is not driven by
    # price moves alone = more diverse trading motives = better liquidity.
    if valid_cnt >= 2:
        diverge_cnt = 0
        for i in range(1, valid_cnt):
            vol_up = vols[i] > vols[i - 1]
            ret_up = abs_rets[i] > abs_rets[i - 1]
            if vol_up != ret_up:
                diverge_cnt += 1
        out[4] = float(diverge_cnt) / denom

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "volume", "amount"],
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
            "Trade activity quality bundle for full-day window "
            "(09:30-11:30 + 13:00-14:57). 5 metrics measuring trade activity "
            "patterns as liquidity proxies: trade size transitions, volume "
            "acceleration transitions, amount-weighted reversal ratio, "
            "cumulative return zero-crossing frequency, and volume-price "
            "divergence frequency."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the trade activity quality bundle"
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
