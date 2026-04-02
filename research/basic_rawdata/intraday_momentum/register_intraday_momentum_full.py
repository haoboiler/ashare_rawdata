#!/usr/bin/env python3
"""D-014 Intraday Momentum — price path topology features (full day).

Based on 21 experiments of prior knowledge:
- Pure directional momentum fails at Long Excess in A-shares (conclusions #6/#9/#24)
- Liquidity level factors succeed (Amihud, CS spread, reversal_ratio)
- |f(price)|/amount template is effective
- Discrete conditioning > continuous distribution stats

Strategy: Reframe "momentum" as price PATH TOPOLOGY — geometric shape
features of the intraday cumulative return curve, combined with
established liquidity frameworks.

Hypotheses:
1. path_efficiency: |total_ret|/sum(|ret_i|) — continuous version of
   (1-reversal_ratio); low efficiency = illiquid
2. up/down Amihud split: directional price impact asymmetry may reveal
   information quality
3. macro_amihud: net displacement/total amount — different from bar-level
4. cumret excursion: intraday path overshoot measures uncertainty

Inputs: close, volume, amount (basic6)
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

NAME = "intraday_momentum_full"

OUTPUT_NAMES = [
    # --- Path topology (3) ---
    "path_efficiency_full",          # |total_ret| / sum(|ret_i|)
    "vw_path_efficiency_full",       # volume-weighted path efficiency
    "max_excursion_ratio_full",      # max(|cumret_i|) / |total_ret|
    # --- Directional Amihud (3) ---
    "up_amihud_full",                # mean(|ret|/amount) for ret > 0 bars
    "down_amihud_full",              # mean(|ret|/amount) for ret < 0 bars
    "amihud_directional_asym_full",  # (up - down) / (up + down)
    # --- Macro liquidity (2) ---
    "macro_amihud_full",             # |close[-1]-close[0]| / sum(amount)
    "cumret_area_norm_full",         # mean(|cumret_i|) — avg abs excursion
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]
    amount = inputs[2]

    n = close.size
    n_out = 8

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 5:
        return out

    # ---- pre-compute bar returns ----
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    valid_ret_count = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = (c1 - c0) / c0
            valid_ret_count += 1

    if valid_ret_count < 5:
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

    total_ret = running  # close[-1]/close[0] - 1 approx

    # ---- sum of absolute returns ----
    sum_abs_ret = 0.0
    for i in range(n_ret):
        r = rets[i]
        if not np.isnan(r):
            sum_abs_ret += abs(r)

    # ==== 0: path_efficiency_full ====
    # |total_ret| / sum(|ret_i|)
    # High = trending/direct path, Low = meandering/reversals
    if sum_abs_ret > 1e-15:
        out[0] = abs(total_ret) / sum_abs_ret

    # ==== 1: vw_path_efficiency_full ====
    # Volume-weighted: |sum(ret_i * vol_i)| / sum(|ret_i| * vol_i)
    vw_signed = 0.0
    vw_unsigned = 0.0
    for i in range(n_ret):
        r = rets[i]
        v = volume[i + 1]
        if np.isnan(r) or np.isnan(v) or v <= 0.0:
            continue
        vw_signed += r * v
        vw_unsigned += abs(r) * v
    if vw_unsigned > 1e-15:
        out[1] = abs(vw_signed) / vw_unsigned

    # ==== 2: max_excursion_ratio_full ====
    # max(|cumret_i|) / |total_ret|  — how much path overshoots destination
    max_abs_cumret = 0.0
    for i in range(n_ret):
        ac = abs(cumret[i])
        if ac > max_abs_cumret:
            max_abs_cumret = ac
    abs_total = abs(total_ret)
    if abs_total > 1e-15:
        out[2] = max_abs_cumret / abs_total

    # ==== 3,4,5: Directional Amihud ====
    up_sum = 0.0
    up_cnt = 0
    down_sum = 0.0
    down_cnt = 0
    for i in range(n_ret):
        r = rets[i]
        a = amount[i + 1]
        if np.isnan(r) or np.isnan(a) or a <= 0.0:
            continue
        impact = abs(r) / a
        if r > 0.0:
            up_sum += impact
            up_cnt += 1
        elif r < 0.0:
            down_sum += impact
            down_cnt += 1

    # 3: up_amihud_full
    if up_cnt > 0:
        out[3] = up_sum / up_cnt

    # 4: down_amihud_full
    if down_cnt > 0:
        out[4] = down_sum / down_cnt

    # 5: amihud_directional_asym_full
    up_val = out[3]
    down_val = out[4]
    if not np.isnan(up_val) and not np.isnan(down_val):
        denom = up_val + down_val
        if denom > 1e-20:
            out[5] = (up_val - down_val) / denom

    # ==== 6: macro_amihud_full ====
    # |net price displacement| / total amount
    total_amount = 0.0
    for i in range(n):
        a = amount[i]
        if not np.isnan(a):
            total_amount += a
    if total_amount > 0.0 and abs_total > 1e-15:
        out[6] = abs_total / total_amount

    # ==== 7: cumret_area_norm_full ====
    # mean(|cumret_i|) — average absolute excursion of intraday path
    area_sum = 0.0
    area_cnt = 0
    for i in range(n_ret):
        area_sum += abs(cumret[i])
        area_cnt += 1
    if area_cnt > 0:
        out[7] = area_sum / area_cnt

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
            "Intraday momentum/path topology features for full day. "
            "8 features: path efficiency (equal/vol-weighted), max excursion ratio, "
            "directional Amihud (up/down/asymmetry), macro Amihud, "
            "and cumulative return area. Window: 09:30-14:57."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register intraday momentum full-day bundle"
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
