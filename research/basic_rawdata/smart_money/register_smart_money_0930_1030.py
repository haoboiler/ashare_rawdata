#!/usr/bin/env python3
"""Register the smart money bundle for the 09:30-10:30 window.

Bundle: smart_money_0930_1030
- Input: open, high, low, close, volume
- Output: 5 variables covering smart money flow, direction, concentration, and BVC OIB

Physical hypothesis:
  Informed traders ("smart money") generate high price impact per unit volume.
  S_i = |return_i| / sqrt(volume_i) identifies bars with disproportionate information content.
  Selecting bars with highest S until 20% cumulative volume is reached isolates "smart" trades.
  The VWAP of these bars vs overall VWAP reveals smart money's directional bias.

Reference: 广发证券 Smart Money Factor
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

NAME = "smart_money_0930_1030"

OUTPUT_NAMES = [
    # --- Core Smart Money (2) ---
    "smart_money_0930_1030",            # (smart_vwap - full_vwap) / full_vwap
    "smart_money_direction_0930_1030",  # vol-weighted avg return of smart bars
    # --- Concentration (2) ---
    "smart_money_bar_ratio_0930_1030",  # #smart_bars / #valid_bars
    "smart_money_s_ratio_0930_1030",    # sum(S_smart) / sum(S_all)
    # --- BVC Order Imbalance (1) ---
    "bulk_volume_oib_0930_1030",        # (buy_vol - sell_vol) / total_vol
]

FORMULA = """@njit
def apply_func(inputs):
    open_price = inputs[0]
    high = inputs[1]
    low = inputs[2]
    close = inputs[3]
    volume = inputs[4]

    n = close.size
    n_out = 5

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 5:
        return out

    # ---- Pre-compute log returns ----
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    valid_ret = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = np.log(c1 / c0)
            valid_ret += 1

    if valid_ret < 5:
        return out

    # ---- Compute S_i = |r_i| / sqrt(volume[i+1]) ----
    s_scores = np.empty(n_ret, dtype=np.float64)
    total_volume = 0.0
    vol_valid_count = 0

    for i in range(n_ret):
        r = rets[i]
        v = volume[i + 1]
        if np.isnan(r) or np.isnan(v) or v <= 0.0:
            s_scores[i] = np.nan
        else:
            s_scores[i] = abs(r) / np.sqrt(v)
            total_volume += v
            vol_valid_count += 1

    if vol_valid_count < 5 or total_volume <= 0.0:
        return out

    # ---- Sort indices by S descending (selection sort, n<=60 so O(n^2) is fine) ----
    indices = np.empty(vol_valid_count, dtype=np.int64)
    k = 0
    for i in range(n_ret):
        if not np.isnan(s_scores[i]):
            indices[k] = i
            k += 1

    # Selection sort descending by s_scores
    for i in range(k):
        max_idx = i
        for j in range(i + 1, k):
            if s_scores[indices[j]] > s_scores[indices[max_idx]]:
                max_idx = j
        if max_idx != i:
            tmp = indices[i]
            indices[i] = indices[max_idx]
            indices[max_idx] = tmp

    # ---- Select smart bars: cumulative volume >= 20% of total ----
    target_volume = total_volume * 0.2
    cum_vol = 0.0
    n_smart = 0
    smart_mask = np.zeros(n_ret, dtype=np.int64)

    for m in range(k):
        idx = indices[m]
        v = volume[idx + 1]
        smart_mask[idx] = 1
        cum_vol += v
        n_smart += 1
        if cum_vol >= target_volume:
            break

    if n_smart == 0:
        return out

    # ---- Compute Smart VWAP vs Full VWAP ----
    smart_vwap_num = 0.0
    smart_vwap_den = 0.0
    full_vwap_num = 0.0
    full_vwap_den = 0.0
    smart_ret_sum = 0.0
    smart_ret_vol = 0.0
    smart_s_sum = 0.0
    full_s_sum = 0.0

    for i in range(n_ret):
        c = close[i + 1]
        v = volume[i + 1]
        r = rets[i]
        s = s_scores[i]

        if np.isnan(c) or np.isnan(v) or v <= 0.0:
            continue

        full_vwap_num += c * v
        full_vwap_den += v

        if not np.isnan(s):
            full_s_sum += s

        if smart_mask[i] == 1:
            smart_vwap_num += c * v
            smart_vwap_den += v
            if not np.isnan(r):
                smart_ret_sum += r * v
                smart_ret_vol += v
            if not np.isnan(s):
                smart_s_sum += s

    # [0] smart_money: (smart_vwap - full_vwap) / full_vwap
    if full_vwap_den > 0.0 and smart_vwap_den > 0.0:
        full_vwap = full_vwap_num / full_vwap_den
        smart_vwap = smart_vwap_num / smart_vwap_den
        if full_vwap > 0.0:
            out[0] = (smart_vwap - full_vwap) / full_vwap

    # [1] smart_money_direction: vol-weighted avg return of smart bars
    if smart_ret_vol > 0.0:
        out[1] = smart_ret_sum / smart_ret_vol

    # [2] smart_money_bar_ratio: n_smart / vol_valid_count
    out[2] = float(n_smart) / float(vol_valid_count)

    # [3] smart_money_s_ratio: smart S / total S
    if full_s_sum > 0.0:
        out[3] = smart_s_sum / full_s_sum

    # ---- [4] bulk_volume_oib: BVC order imbalance ----
    buy_vol = 0.0
    sell_vol = 0.0
    for i in range(n):
        o = open_price[i]
        h = high[i]
        l = low[i]
        c = close[i]
        v = volume[i]
        if np.isnan(o) or np.isnan(h) or np.isnan(l) or np.isnan(c) or np.isnan(v):
            continue
        rng = h - l
        if rng <= 0.0:
            buy_vol += v * 0.5
            sell_vol += v * 0.5
        else:
            tau = (c - l) / rng
            buy_vol += tau * v
            sell_vol += (1.0 - tau) * v

    total_bvc = buy_vol + sell_vol
    if total_bvc > 0.0:
        out[4] = (buy_vol - sell_vol) / total_bvc

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["open", "high", "low", "close", "volume"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "10:30")]),
        slot=RawDataSlot.MIDDAY,
        data_available_at=1031,
        execution_start_at=930,
        execution_end_at=1030,
        expected_bars=40,
        description=(
            "Smart Money bundle for 09:30-10:30 window. "
            "Identifies informed trading bars via S = |return|/sqrt(volume), "
            "selects bars with cumulative volume = 20% of total (highest S first), "
            "computes smart VWAP premium, directional signal, concentration metrics, "
            "and BVC-based order imbalance."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the smart money 09:30-10:30 bundle"
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
        upsert_definition(definition, validate=not args.skip_validate)
        print(f"registered: {definition.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
