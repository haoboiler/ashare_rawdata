#!/usr/bin/env python3
"""D-014 Intraday Momentum — amount-normalized path features (full day).

Round 2: Test whether amount normalization (Amihud framework) can rescue
failed path topology features.

Known pattern from prior experiments:
- |return| alone = volatility proxy (fails LE)
- |return|/amount = Amihud (succeeds)
- |acceleration| alone = volatility proxy (fails LE)
- |acceleration|/amount = accel_illiq (succeeds)

So try:
- cumret_area/amount → may rescue cumret_area_norm (which failed at LE=-5.33)
- sum(|ret|)/sum(amount) → batch Amihud (volume-weighted vs equal-weighted)
- max_excursion/amount → may rescue max_excursion_ratio

Also: bar-level path curvature per amount (second-order Amihud of the
cumulative path).

Inputs: close, volume, amount
Window: full day (09:30-11:30, 13:00-14:57)
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

NAME = "intraday_momentum_amihud_full"

OUTPUT_NAMES = [
    # --- Amount-normalized path topology (3) ---
    "cumret_area_amihud_full",       # mean(|cumret_i|) / mean(amount)
    "batch_amihud_full",             # sum(|ret_i|) / sum(amount_i) — volume-weighted Amihud
    "max_excursion_amihud_full",     # max(|cumret_i|) / sum(amount_i)
    # --- Cumulative path Amihud (2) ---
    "cumret_path_roughness_full",    # mean(|Δcumret_i|) / mean(|cumret_i|+eps)
    "vw_amihud_full",                # sum(|ret_i| * vol_i / amount_i) / sum(vol_i) — explicit vol-weighted
    # --- Time-of-day Amihud split (3) ---
    "am_amihud_full",                # Amihud for morning session
    "pm_amihud_full",                # Amihud for afternoon session
    "session_amihud_ratio_full",     # am_amihud / pm_amihud
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]
    amount = inputs[2]

    n = close.size
    n_out = 8

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 10:
        return out

    # ---- bar returns ----
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

    # ---- cumulative returns ----
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

    # ==== 0: cumret_area_amihud_full ====
    # mean(|cumret_i|) / mean(amount_per_bar)
    area_sum = 0.0
    for i in range(n_ret):
        area_sum += abs(cumret[i])
    mean_area = area_sum / n_ret
    out[0] = mean_area / mean_amount

    # ==== 1: batch_amihud_full ====
    # sum(|ret_i|) / sum(amount_i) — volume-weighted price impact
    sum_abs_ret = 0.0
    for i in range(n_ret):
        r = rets[i]
        if not np.isnan(r):
            sum_abs_ret += abs(r)
    out[1] = sum_abs_ret / total_amount

    # ==== 2: max_excursion_amihud_full ====
    # max(|cumret_i|) / sum(amount_i)
    max_abs_cumret = 0.0
    for i in range(n_ret):
        ac = abs(cumret[i])
        if ac > max_abs_cumret:
            max_abs_cumret = ac
    out[2] = max_abs_cumret / total_amount

    # ==== 3: cumret_path_roughness_full ====
    # mean(|cumret[i] - cumret[i-1]|) / mean(|cumret_i|+eps)
    # = mean(|ret_i|) / mean(|cumret_i|+eps)
    # This measures how jagged the cumulative return curve is relative to excursion
    eps = 1e-10
    mean_abs_cumret = area_sum / n_ret + eps
    mean_abs_ret = sum_abs_ret / valid_count if valid_count > 0 else 0.0
    if mean_abs_cumret > eps:
        out[3] = mean_abs_ret / mean_abs_cumret

    # ==== 4: vw_amihud_full ====
    # sum(|ret_i| * vol_i / amount_i) / sum(vol_i)
    # = volume-weighted per-bar Amihud
    vw_num = 0.0
    vw_denom = 0.0
    for i in range(n_ret):
        r = rets[i]
        v = volume[i + 1]
        a = amount[i + 1]
        if np.isnan(r) or np.isnan(v) or np.isnan(a) or v <= 0.0 or a <= 0.0:
            continue
        vw_num += abs(r) / a * v
        vw_denom += v
    if vw_denom > 0.0:
        out[4] = vw_num / vw_denom

    # ==== 5,6,7: Session Amihud split ====
    # Split bars into AM (first ~120 bars) and PM (remaining)
    # In full-day window with 237 bars, AM=120 PM=117
    am_boundary = n // 2  # approx midpoint

    am_sum = 0.0
    am_cnt = 0
    pm_sum = 0.0
    pm_cnt = 0
    for i in range(n_ret):
        r = rets[i]
        a = amount[i + 1]
        if np.isnan(r) or np.isnan(a) or a <= 0.0:
            continue
        impact = abs(r) / a
        if i < am_boundary:
            am_sum += impact
            am_cnt += 1
        else:
            pm_sum += impact
            pm_cnt += 1

    # 5: am_amihud_full
    if am_cnt > 0:
        out[5] = am_sum / am_cnt

    # 6: pm_amihud_full
    if pm_cnt > 0:
        out[6] = pm_sum / pm_cnt

    # 7: session_amihud_ratio_full
    if am_cnt > 0 and pm_cnt > 0:
        am_val = am_sum / am_cnt
        pm_val = pm_sum / pm_cnt
        if pm_val > 1e-20:
            out[7] = am_val / pm_val

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
        data_available_at=1500,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Intraday momentum amount-normalized path features for full day. "
            "8 features: amount-normalized path topology (cumret_area/amount, "
            "batch_amihud, max_excursion/amount), cumulative path roughness, "
            "volume-weighted Amihud, session Amihud split (AM/PM/ratio). "
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
