#!/usr/bin/env python3
"""OHLC Microstructure Decomposition — full-day window (09:30-11:30 + 13:00-14:57).

D-020: Bar 内 OHLC 结构分解
核心假设：
  - close 在 bar range 内的位置（displacement from midpoint）是实现价差（realized spread）的代理
  - wick 可以分解为 upper wick（卖压拒绝）和 lower wick（买压拒绝），各自 /amount 后是独立信号
  - close displacement 的 bar-to-bar 变化（roughness）反映价差不确定性

与已有因子关系：
  - wick_amihud (D-019): 总 wick / amount → 本方向将 wick 分解为 upper/lower
  - amihud_illiq: |ret| / amount → 本方向用 |close-midpoint| / amount 替代 numerator
  - 直接 HL range (结论#22): 波动率代理 → 分解后应能分离流动性成分

Features:
  close_disp_amihud_full        — mean(|C-(H+L)/2| / amount), 实现价差 Amihud
  high_vol_close_disp_amihud_full — 高量 bar 的 close displacement Amihud
  upper_wick_amihud_full        — mean((H-max(O,C)) / amount), 上影线(卖压拒绝) Amihud
  lower_wick_amihud_full        — mean((min(O,C)-L) / amount), 下影线(买压拒绝) Amihud
  close_disp_roughness_full     — mean|Δ(close_disp)| / mean(close_disp), 价差路径粗糙度
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

NAME = "ohlc_decomposition_full"

OUTPUT_NAMES = [
    "close_disp_amihud_full",
    "high_vol_close_disp_amihud_full",
    "upper_wick_amihud_full",
    "lower_wick_amihud_full",
    "close_disp_roughness_full",
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    opn = inputs[1]
    high = inputs[2]
    low = inputs[3]
    volume = inputs[4]
    amount = inputs[5]

    n = close.size
    n_out = 5
    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 10:
        return out

    # ---- pre-compute per-bar close displacement and wick components ----
    close_disps = np.empty(n, dtype=np.float64)
    upper_wicks = np.empty(n, dtype=np.float64)
    lower_wicks = np.empty(n, dtype=np.float64)
    valid_bar_count = 0
    for i in range(n):
        h = high[i]
        l = low[i]
        c = close[i]
        o = opn[i]
        if np.isnan(h) or np.isnan(l) or np.isnan(c) or np.isnan(o):
            close_disps[i] = np.nan
            upper_wicks[i] = np.nan
            lower_wicks[i] = np.nan
        else:
            bar_range = h - l
            if bar_range < 1e-12:
                # flat bar (H=L), all components zero
                close_disps[i] = 0.0
                upper_wicks[i] = 0.0
                lower_wicks[i] = 0.0
            else:
                midpoint = (h + l) / 2.0
                close_disps[i] = abs(c - midpoint)
                max_oc = max(o, c)
                min_oc = min(o, c)
                upper_wicks[i] = h - max_oc
                lower_wicks[i] = min_oc - l
            valid_bar_count += 1

    if valid_bar_count < 10:
        return out

    # ---- median volume for high-vol filtering ----
    valid_vols = np.empty(n, dtype=np.float64)
    vol_idx = 0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v) and v > 0.0:
            valid_vols[vol_idx] = v
            vol_idx += 1
    if vol_idx < 10:
        return out
    valid_vols_sorted = np.sort(valid_vols[:vol_idx])
    median_vol = valid_vols_sorted[vol_idx // 2]

    # ---- Feature 0: close_disp_amihud_full ----
    # mean(|C - midpoint| / amount) over all bars
    # Economic meaning: realized effective spread per unit of trading activity
    # High value = close consistently displaced from midpoint even with given amount
    cd_sum = 0.0
    cd_cnt = 0
    for i in range(n):
        cd = close_disps[i]
        a = amount[i]
        if np.isnan(cd) or np.isnan(a) or a <= 0.0:
            continue
        cd_sum += cd / a
        cd_cnt += 1

    if cd_cnt > 0:
        out[0] = cd_sum / cd_cnt

    # ---- Feature 1: high_vol_close_disp_amihud_full ----
    # Same as above but only for bars with volume > median
    # High-volume bars are active price discovery events
    hvcd_sum = 0.0
    hvcd_cnt = 0
    for i in range(n):
        cd = close_disps[i]
        v = volume[i]
        a = amount[i]
        if np.isnan(cd) or np.isnan(v) or np.isnan(a) or a <= 0.0:
            continue
        if v > median_vol:
            hvcd_sum += cd / a
            hvcd_cnt += 1

    if hvcd_cnt > 5:
        out[1] = hvcd_sum / hvcd_cnt

    # ---- Feature 2: upper_wick_amihud_full ----
    # mean((H - max(O,C)) / amount) — selling pressure rejection cost per unit amount
    # Upper wick = price explored upward but was pushed back by selling pressure
    uw_sum = 0.0
    uw_cnt = 0
    for i in range(n):
        uw = upper_wicks[i]
        a = amount[i]
        if np.isnan(uw) or np.isnan(a) or a <= 0.0:
            continue
        uw_sum += uw / a
        uw_cnt += 1

    if uw_cnt > 0:
        out[2] = uw_sum / uw_cnt

    # ---- Feature 3: lower_wick_amihud_full ----
    # mean((min(O,C) - L) / amount) — buying pressure rejection cost per unit amount
    # Lower wick = price explored downward but was pushed back by buying support
    lw_sum = 0.0
    lw_cnt = 0
    for i in range(n):
        lw = lower_wicks[i]
        a = amount[i]
        if np.isnan(lw) or np.isnan(a) or a <= 0.0:
            continue
        lw_sum += lw / a
        lw_cnt += 1

    if lw_cnt > 0:
        out[3] = lw_sum / lw_cnt

    # ---- Feature 4: close_disp_roughness_full ----
    # mean|Δ(close_disp)| / mean(close_disp) — path roughness of close displacement
    # Parallel to vol_roughness_full (LS=1.42, LE=0.85, conclusion #41)
    # High roughness = effective spread fluctuates erratically = execution cost uncertainty
    cd_mean_sum = 0.0
    cd_mean_cnt = 0
    delta_cd_sum = 0.0
    delta_cd_cnt = 0
    prev_cd = np.nan
    for i in range(n):
        cd = close_disps[i]
        if np.isnan(cd):
            prev_cd = np.nan
            continue
        cd_mean_sum += cd
        cd_mean_cnt += 1
        if not np.isnan(prev_cd):
            delta_cd_sum += abs(cd - prev_cd)
            delta_cd_cnt += 1
        prev_cd = cd

    if cd_mean_cnt > 0 and delta_cd_cnt > 0:
        mean_cd = cd_mean_sum / cd_mean_cnt
        if mean_cd > 1e-12:
            out[4] = (delta_cd_sum / delta_cd_cnt) / mean_cd

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
            input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")],
        ),
        slot=RawDataSlot.EVENING,
        data_available_at=1530,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "OHLC microstructure decomposition for full-day window. "
            "5 features decomposing bar-level OHLC structure: close displacement "
            "(realized spread proxy), upper/lower wick (directional rejection costs), "
            "and displacement roughness. All normalized by amount (Amihud framework). "
            "Extends wick_amihud (D-019) with finer structural decomposition."
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()

    defn = build_definition()
    print(json.dumps(defn.model_dump(), indent=2, default=str))

    if args.register:
        from ashare_hf_variable.registry import upsert_definition
        upsert_definition(defn)
        print(f"\n✅ Registered {NAME}")


if __name__ == "__main__":
    main()
