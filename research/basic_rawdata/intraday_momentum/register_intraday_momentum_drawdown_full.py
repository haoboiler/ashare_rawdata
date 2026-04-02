#!/usr/bin/env python3
"""D-014 Intraday Momentum — drawdown path + wick decomposition (full day).

Final round for D-014. Three genuinely novel angles:

1. DRAWDOWN PATH AMIHUD: max_drawdown (peak-to-trough) differs from
   max_excursion (start-to-peak). Drawdown measures "fragility of gains"
   while excursion measures "displacement from origin". For up-trending
   stocks they diverge significantly.

2. UPPER/LOWER WICK SPLIT AMIHUD: wick_amihud_full (total wick/amount)
   passed at LS=2.36. Decomposing into upper (rejected upward exploration)
   vs lower (rejected downward exploration) per amount may separate
   different market microstructure mechanisms.

3. CUMRET ZERO-CROSSING FREQUENCY: counts how often the cumulative return
   crosses zero (returns to opening price). Different from reversal_ratio
   (bar-level sign changes): reversal_ratio = bid-ask bounce frequency,
   zero_crossing = path-level mean reversion frequency.

Inputs: close, open, high, low, volume, amount (basic6)
Window: full day (09:30-11:30, 13:00-14:57), ~237 bars
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

NAME = "intraday_momentum_drawdown_full"

OUTPUT_NAMES = [
    # --- Drawdown path Amihud (3) ---
    "max_drawdown_amihud_full",      # max(cummax(cumret) - cumret) / total_amount
    "drawdown_area_amihud_full",     # mean(cummax(cumret) - cumret) / mean(amount)
    "max_drawup_amihud_full",        # max(cumret - cummin(cumret)) / total_amount
    # --- Upper/Lower wick Amihud split (2) ---
    "upper_wick_amihud_full",        # mean((H - max(O,C)) / amount) per bar
    "lower_wick_amihud_full",        # mean((min(O,C) - L) / amount) per bar
    # --- Cumret zero-crossing frequency (1) ---
    "cumret_zero_cross_freq_full",   # count(cumret crosses zero) / n_bars
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
    n_out = 6

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 10:
        return out

    # ---- bar returns (close-to-close) ----
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    valid_count = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = (c1 - c0) / c0
            valid_count += 1

    if valid_count < 10:
        return out

    # ---- cumulative returns from bar 0 ----
    cumret = np.empty(n_ret, dtype=np.float64)
    running = 0.0
    for i in range(n_ret):
        r = rets[i]
        if np.isnan(r):
            cumret[i] = running
        else:
            running += r
            cumret[i] = running

    # ---- total amount ----
    total_amount = 0.0
    amount_cnt = 0
    for i in range(n):
        a = amount[i]
        if not np.isnan(a) and a > 0.0:
            total_amount += a
            amount_cnt += 1

    if total_amount <= 0.0 or amount_cnt == 0:
        return out

    mean_amount = total_amount / amount_cnt

    # ==== 0: max_drawdown_amihud_full ====
    # max(cummax(cumret) - cumret) / total_amount
    # Drawdown = peak-to-current distance; max_drawdown = worst pullback from running high
    cum_max = cumret[0]
    max_dd = 0.0
    for i in range(n_ret):
        cr = cumret[i]
        if cr > cum_max:
            cum_max = cr
        dd = cum_max - cr
        if dd > max_dd:
            max_dd = dd
    out[0] = max_dd / total_amount

    # ==== 1: drawdown_area_amihud_full ====
    # mean(cummax(cumret) - cumret) / mean(amount)
    # Average distance from running high, normalized by avg trading volume
    cum_max2 = cumret[0]
    dd_area_sum = 0.0
    for i in range(n_ret):
        cr = cumret[i]
        if cr > cum_max2:
            cum_max2 = cr
        dd_area_sum += (cum_max2 - cr)
    mean_dd = dd_area_sum / n_ret
    out[1] = mean_dd / mean_amount

    # ==== 2: max_drawup_amihud_full ====
    # max(cumret - cummin(cumret)) / total_amount
    # Symmetric to drawdown: worst trough-to-peak rise
    cum_min = cumret[0]
    max_du = 0.0
    for i in range(n_ret):
        cr = cumret[i]
        if cr < cum_min:
            cum_min = cr
        du = cr - cum_min
        if du > max_du:
            max_du = du
    out[2] = max_du / total_amount

    # ==== 3: upper_wick_amihud_full ====
    # mean((H - max(O,C)) / amount) — rejected upward price exploration per amount
    uw_sum = 0.0
    uw_cnt = 0
    for i in range(n):
        h = high[i]
        o = open_[i]
        c = close[i]
        a = amount[i]
        if np.isnan(h) or np.isnan(o) or np.isnan(c) or np.isnan(a) or a <= 0.0:
            continue
        max_oc = o if o > c else c
        upper_wick = h - max_oc
        if upper_wick < 0.0:
            upper_wick = 0.0
        uw_sum += upper_wick / a
        uw_cnt += 1
    if uw_cnt > 0:
        out[3] = uw_sum / uw_cnt

    # ==== 4: lower_wick_amihud_full ====
    # mean((min(O,C) - L) / amount) — rejected downward exploration per amount
    lw_sum = 0.0
    lw_cnt = 0
    for i in range(n):
        l = low[i]
        o = open_[i]
        c = close[i]
        a = amount[i]
        if np.isnan(l) or np.isnan(o) or np.isnan(c) or np.isnan(a) or a <= 0.0:
            continue
        min_oc = o if o < c else c
        lower_wick = min_oc - l
        if lower_wick < 0.0:
            lower_wick = 0.0
        lw_sum += lower_wick / a
        lw_cnt += 1
    if lw_cnt > 0:
        out[4] = lw_sum / lw_cnt

    # ==== 5: cumret_zero_cross_freq_full ====
    # Fraction of bars where cumulative return crosses zero
    # Different from reversal_ratio (bar-level sign changes):
    # this captures path-level mean reversion to opening price
    cross_count = 0
    for i in range(1, n_ret):
        prev_cr = cumret[i - 1]
        curr_cr = cumret[i]
        # A crossing occurs when sign changes (or touches zero from nonzero)
        if prev_cr * curr_cr < 0.0:
            cross_count += 1
    if n_ret > 1:
        out[5] = cross_count / (n_ret - 1.0)

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
            "Intraday momentum drawdown path + wick decomposition features. "
            "6 features: drawdown-based Amihud (max_drawdown/total_amount, "
            "drawdown_area/mean_amount, max_drawup/total_amount), "
            "upper/lower wick Amihud split, cumret zero-crossing frequency. "
            "Window: 09:30-14:57."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
