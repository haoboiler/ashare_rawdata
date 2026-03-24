#!/usr/bin/env python3
"""Register the batch2a bundle for the 09:30-10:30 window.

Bundle: batch2a_0930_1030
- Input: open, high, low, close, volume, amount (from 1m bars)
- Output: 8 variables covering microstructure, liquidity, and price dynamics.

By default the script only prints the definition JSON for review.
Use ``--register`` to write it into the configured registry backend.
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

NAME = "batch2a_0930_1030"

OUTPUT_NAMES = [
    "smart_money_0930_1030",
    "jump_variation_0930_1030",
    "corwin_schultz_spread_0930_1030",
    "high_volume_ratio_0930_1030",
    "bvc_order_imbalance_0930_1030",
    "roll_spread_0930_1030",
    "price_center_of_gravity_0930_1030",
    "range_concentration_0930_1030",
]

FORMULA = """@njit
def apply_func(inputs):
    open_ = inputs[0]
    high = inputs[1]
    low = inputs[2]
    close = inputs[3]
    volume = inputs[4]
    amount = inputs[5]

    n = close.size
    n_out = 8

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 2:
        return out

    # ---- pre-compute returns ----
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = c1 / c0 - 1.0

    # ================================================================
    # 0: smart_money_0930_1030
    #    S_i = |return_i| / sqrt(volume_i)
    #    Sort by S desc, take bars until cumulative volume >= 20% total
    #    smart_vwap of those bars vs overall_vwap
    # ================================================================
    # overall vwap
    overall_cv_sum = 0.0
    overall_v_sum = 0.0
    for i in range(n):
        c = close[i]
        v = volume[i]
        if np.isnan(c) or np.isnan(v) or v <= 0.0:
            continue
        overall_cv_sum += c * v
        overall_v_sum += v
    if overall_v_sum > 0.0:
        overall_vwap = overall_cv_sum / overall_v_sum

        # Compute S for each bar that has a return (bars 1..n-1)
        # We use bar index i+1 for return i
        n_candidates = 0
        s_vals = np.empty(n_ret, dtype=np.float64)
        bar_idx = np.empty(n_ret, dtype=np.int64)
        for i in range(n_ret):
            r = rets[i]
            v = volume[i + 1]
            if np.isnan(r) or np.isnan(v) or v <= 0.0:
                continue
            s_vals[n_candidates] = abs(r) / np.sqrt(v)
            bar_idx[n_candidates] = i + 1
            n_candidates += 1

        if n_candidates > 0:
            # sort by S descending (simple insertion sort for numba compat)
            for i in range(n_candidates - 1):
                for j in range(i + 1, n_candidates):
                    if s_vals[j] > s_vals[i]:
                        s_vals[i], s_vals[j] = s_vals[j], s_vals[i]
                        bar_idx[i], bar_idx[j] = bar_idx[j], bar_idx[i]

            threshold = 0.2 * overall_v_sum
            cum_vol = 0.0
            smart_cv = 0.0
            smart_v = 0.0
            for k in range(n_candidates):
                bi = bar_idx[k]
                v = volume[bi]
                c = close[bi]
                smart_cv += c * v
                smart_v += v
                cum_vol += v
                if cum_vol >= threshold:
                    break
            if smart_v > 0.0:
                smart_vwap = smart_cv / smart_v
                out[0] = smart_vwap / overall_vwap - 1.0

    # ================================================================
    # 1: jump_variation_0930_1030
    #    RV = sum(r_i^2), BV = (pi/2)*sum(|r_i|*|r_{i-1}|)
    #    JV = max(RV - BV, 0) / RV
    # ================================================================
    rv = 0.0
    rv_cnt = 0
    for i in range(n_ret):
        r = rets[i]
        if np.isnan(r):
            continue
        rv += r * r
        rv_cnt += 1

    if rv_cnt > 0:
        if rv == 0.0:
            out[1] = 0.0
        else:
            bv = 0.0
            bv_cnt = 0
            for i in range(1, n_ret):
                r0 = rets[i - 1]
                r1 = rets[i]
                if np.isnan(r0) or np.isnan(r1):
                    continue
                bv += abs(r0) * abs(r1)
                bv_cnt += 1
            bv *= np.pi / 2.0
            jv = rv - bv
            if jv < 0.0:
                jv = 0.0
            out[1] = jv / rv

    # ================================================================
    # 2: corwin_schultz_spread_0930_1030
    #    For each adjacent bar pair, compute spread estimate
    # ================================================================
    sqrt2 = np.sqrt(2.0)
    denom_cs = 3.0 - 2.0 * sqrt2  # ~0.1716
    spread_sum = 0.0
    spread_cnt = 0
    for i in range(n - 1):
        h1 = high[i]
        l1 = low[i]
        h2 = high[i + 1]
        l2 = low[i + 1]
        if np.isnan(h1) or np.isnan(l1) or np.isnan(h2) or np.isnan(l2):
            continue
        if l1 <= 0.0 or l2 <= 0.0 or h1 <= 0.0 or h2 <= 0.0:
            continue

        beta = np.log(h1 / l1) ** 2 + np.log(h2 / l2) ** 2
        h_max = h1 if h1 > h2 else h2
        l_min = l1 if l1 < l2 else l2
        if l_min <= 0.0:
            continue
        gamma = np.log(h_max / l_min) ** 2

        alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / denom_cs - np.sqrt(gamma / denom_cs)
        if alpha < 0.0:
            spread_pair = 0.0
        else:
            ea = np.exp(alpha)
            spread_pair = 2.0 * (ea - 1.0) / (1.0 + ea)
        spread_sum += spread_pair
        spread_cnt += 1

    if spread_cnt > 0:
        out[2] = spread_sum / spread_cnt

    # ================================================================
    # 3: high_volume_ratio_0930_1030
    #    count(volume > 2 * mean(volume)) / n
    # ================================================================
    vol_sum = 0.0
    vol_cnt = 0
    for i in range(n):
        v = volume[i]
        if np.isnan(v):
            continue
        vol_sum += v
        vol_cnt += 1
    if vol_cnt > 0:
        vol_mean = vol_sum / vol_cnt
        threshold_vol = 2.0 * vol_mean
        high_cnt = 0
        for i in range(n):
            v = volume[i]
            if np.isnan(v):
                continue
            if v > threshold_vol:
                high_cnt += 1
        out[3] = float(high_cnt) / float(vol_cnt)

    # ================================================================
    # 4: bvc_order_imbalance_0930_1030
    #    tau = (close - open) / (high - low), if high==low then 0.5
    #    buy_vol = sum(tau * volume), sell_vol = sum((1-tau) * volume)
    #    OIB = (buy - sell) / (buy + sell)
    # ================================================================
    buy_vol = 0.0
    sell_vol = 0.0
    oib_valid = False
    for i in range(n):
        o = open_[i]
        h = high[i]
        l = low[i]
        c = close[i]
        v = volume[i]
        if np.isnan(o) or np.isnan(h) or np.isnan(l) or np.isnan(c) or np.isnan(v):
            continue
        if v <= 0.0:
            continue
        hl_range = h - l
        if hl_range == 0.0:
            tau = 0.5
        else:
            tau = (c - o) / hl_range
        # Clamp tau to [0, 1] for safety
        if tau < 0.0:
            tau = 0.0
        elif tau > 1.0:
            tau = 1.0
        buy_vol += tau * v
        sell_vol += (1.0 - tau) * v
        oib_valid = True
    if oib_valid and (buy_vol + sell_vol) > 0.0:
        out[4] = (buy_vol - sell_vol) / (buy_vol + sell_vol)

    # ================================================================
    # 5: roll_spread_0930_1030
    #    dp_i = close_i - close_{i-1}
    #    cov = autocovariance(dp, lag=1)
    #    roll_spread = 2*sqrt(-cov) if cov < 0, else 0
    # ================================================================
    # Compute dp
    dp = np.empty(n_ret, dtype=np.float64)
    dp_valid = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1):
            dp[i] = np.nan
        else:
            dp[i] = c1 - c0
            dp_valid += 1

    if dp_valid >= 3:
        # mean of dp
        dp_sum = 0.0
        dp_cnt = 0
        for i in range(n_ret):
            if not np.isnan(dp[i]):
                dp_sum += dp[i]
                dp_cnt += 1
        dp_mean = dp_sum / dp_cnt

        # autocovariance lag-1: mean(dp_i * dp_{i+1}) - mean(dp_i)*mean(dp_{i+1})
        # Since both come from same series, mean is dp_mean for both
        prod_sum = 0.0
        prod_cnt = 0
        for i in range(n_ret - 1):
            d0 = dp[i]
            d1 = dp[i + 1]
            if np.isnan(d0) or np.isnan(d1):
                continue
            prod_sum += d0 * d1
            prod_cnt += 1
        if prod_cnt > 0:
            cov = prod_sum / prod_cnt - dp_mean * dp_mean
            if cov < 0.0:
                out[5] = 2.0 * np.sqrt(-cov)
            else:
                out[5] = 0.0

    # ================================================================
    # 6: price_center_of_gravity_0930_1030
    #    cog = sum(close_i * i) / (sum(close_i) * (n-1))
    #    i from 0 to n-1, normalized to [0,1]
    # ================================================================
    cog_num = 0.0
    cog_den = 0.0
    cog_valid = 0
    for i in range(n):
        c = close[i]
        if np.isnan(c):
            continue
        cog_num += c * float(i)
        cog_den += c
        cog_valid += 1
    if cog_valid >= 2 and cog_den != 0.0 and (n - 1) > 0:
        out[6] = cog_num / (cog_den * float(n - 1))

    # ================================================================
    # 7: range_concentration_0930_1030
    #    max(|r_i|) / sum(|r_i|)
    # ================================================================
    abs_ret_sum = 0.0
    abs_ret_max = 0.0
    abs_ret_cnt = 0
    for i in range(n_ret):
        r = rets[i]
        if np.isnan(r):
            continue
        ar = abs(r)
        abs_ret_sum += ar
        if ar > abs_ret_max:
            abs_ret_max = ar
        abs_ret_cnt += 1
    if abs_ret_cnt > 0 and abs_ret_sum > 0.0:
        out[7] = abs_ret_max / abs_ret_sum

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["open", "high", "low", "close", "volume", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "10:30")]),
        slot=RawDataSlot.MIDDAY,
        data_available_at=1031,
        execution_start_at=930,
        execution_end_at=1030,
        expected_bars=40,
        description=(
            "Batch 2A microstructure bundle for the 09:30-10:30 window. "
            "Emits 8 variables: smart money flow, jump variation, "
            "Corwin-Schultz spread, high volume ratio, BVC order imbalance, "
            "Roll spread, price center of gravity, and range concentration."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the batch2a 09:30-10:30 bundle"
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
