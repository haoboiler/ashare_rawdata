#!/usr/bin/env python3
"""Wick Extended — full-day window (09:30-11:30 + 13:00-14:57).

D-019 Iteration 3: wick 维度的扩展变体
核心假设：
  - wick = (H-L-|C-O|) 是被订单簿拒绝的价格探索
  - 将成功的 roughness/regime-transition/conditional 范式应用到 wick 维度
  - wick_roughness = bar-to-bar |Δwick| 的路径粗糙度 (parallel to vol_roughness)
  - doji_amihud = 标准 Amihud 但仅在 doji-like bars (wick > body) 上计算

Features:
  wick_roughness_full        — mean|Δwick|/mean(wick), wick 路径粗糙度
  doji_amihud_full           — |ret|/amount for bars where wick > body
  high_vol_doji_amihud_full  — 高量 + doji 双条件 Amihud
  wick_regime_transitions_full — wick 在日内中位数上下的切换频率
  rejection_intensity_full   — mean(wick / close) for bars with |ret| > median_abs_ret
                                高冲击 bar 的价格拒绝强度/close 归一化
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

NAME = "wick_extended_full"

OUTPUT_NAMES = [
    "wick_roughness_full",
    "doji_amihud_full",
    "high_vol_doji_amihud_full",
    "wick_regime_transitions_full",
    "rejection_intensity_full",
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

    # ---- pre-compute per-bar wick sizes ----
    wicks = np.empty(n, dtype=np.float64)
    bodies = np.empty(n, dtype=np.float64)
    valid_bar_count = 0
    for i in range(n):
        h = high[i]
        l = low[i]
        c = close[i]
        o = opn[i]
        if np.isnan(h) or np.isnan(l) or np.isnan(c) or np.isnan(o):
            wicks[i] = np.nan
            bodies[i] = np.nan
        else:
            bar_range = h - l
            body = abs(c - o)
            wicks[i] = bar_range - body
            bodies[i] = body
            valid_bar_count += 1

    if valid_bar_count < 10:
        return out

    # ---- pre-compute abs returns ----
    n_ret = n - 1
    abs_rets = np.empty(n_ret, dtype=np.float64)
    valid_ret_count = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            abs_rets[i] = np.nan
        else:
            abs_rets[i] = abs(np.log(c1 / c0))
            valid_ret_count += 1

    if valid_ret_count < 10:
        return out

    # median |return| for rejection_intensity
    valid_abs_rets = np.empty(valid_ret_count, dtype=np.float64)
    idx = 0
    for i in range(n_ret):
        if not np.isnan(abs_rets[i]):
            valid_abs_rets[idx] = abs_rets[i]
            idx += 1
    valid_abs_rets_sorted = np.sort(valid_abs_rets[:idx])
    median_abs_ret = valid_abs_rets_sorted[idx // 2]

    # median volume for high-vol filtering
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

    # median wick for regime transitions
    valid_wicks = np.empty(valid_bar_count, dtype=np.float64)
    w_idx = 0
    for i in range(n):
        if not np.isnan(wicks[i]):
            valid_wicks[w_idx] = wicks[i]
            w_idx += 1
    valid_wicks_sorted = np.sort(valid_wicks[:w_idx])
    median_wick = valid_wicks_sorted[w_idx // 2]

    # ---- Feature 0: wick_roughness_full ----
    # mean|Δwick| / mean(wick)  — path roughness of wick sizes
    # Parallel to vol_roughness_full which works (LS=1.42, LE=0.85)
    wick_mean_sum = 0.0
    wick_mean_cnt = 0
    delta_wick_sum = 0.0
    delta_wick_cnt = 0
    prev_wick = np.nan
    for i in range(n):
        w = wicks[i]
        if np.isnan(w):
            prev_wick = np.nan
            continue
        wick_mean_sum += w
        wick_mean_cnt += 1
        if not np.isnan(prev_wick):
            delta_wick_sum += abs(w - prev_wick)
            delta_wick_cnt += 1
        prev_wick = w

    if wick_mean_cnt > 0 and delta_wick_cnt > 0:
        mean_wick = wick_mean_sum / wick_mean_cnt
        if mean_wick > 1e-12:
            out[0] = (delta_wick_sum / delta_wick_cnt) / mean_wick

    # ---- Feature 1: doji_amihud_full ----
    # Standard |ret|/amount but only for doji-like bars (wick > body)
    # Doji bars = order book absorbed initial move and pushed price back
    # Their Amihud measures price impact during absorption events
    doji_sum = 0.0
    doji_cnt = 0
    for i in range(n_ret):
        ar = abs_rets[i]
        a = amount[i + 1]
        w = wicks[i + 1]
        b = bodies[i + 1]
        if np.isnan(ar) or np.isnan(a) or a <= 0.0 or np.isnan(w) or np.isnan(b):
            continue
        if w > b:  # doji condition: wick exceeds body
            doji_sum += ar / a
            doji_cnt += 1

    if doji_cnt > 5:
        out[1] = doji_sum / doji_cnt

    # ---- Feature 2: high_vol_doji_amihud_full ----
    # Double condition: high volume AND doji bar
    hvd_sum = 0.0
    hvd_cnt = 0
    for i in range(n_ret):
        ar = abs_rets[i]
        v = volume[i + 1]
        a = amount[i + 1]
        w = wicks[i + 1]
        b = bodies[i + 1]
        if np.isnan(ar) or np.isnan(v) or np.isnan(a) or a <= 0.0 or np.isnan(w) or np.isnan(b):
            continue
        if v > median_vol and w > b:
            hvd_sum += ar / a
            hvd_cnt += 1

    if hvd_cnt > 5:
        out[2] = hvd_sum / hvd_cnt

    # ---- Feature 3: wick_regime_transitions_full ----
    # Count times wick crosses above/below median_wick
    # Parallel to vol_regime_transitions which works (Exp#007)
    transitions = 0
    trans_total = 0
    prev_above = -1  # -1 = unset, 0 = below, 1 = above
    for i in range(n):
        w = wicks[i]
        if np.isnan(w):
            continue
        current_above = 1 if w > median_wick else 0
        if prev_above >= 0:
            trans_total += 1
            if current_above != prev_above:
                transitions += 1
        prev_above = current_above

    if trans_total > 10:
        out[3] = transitions / trans_total

    # ---- Feature 4: rejection_intensity_full ----
    # For high-impact bars (|ret| > median), measure wick/close
    # This captures: during price shocks, how much is rejected by the order book?
    # High rejection_intensity = deep book that pushes back even during shocks
    ri_sum = 0.0
    ri_cnt = 0
    for i in range(n_ret):
        ar = abs_rets[i]
        w = wicks[i + 1]
        c = close[i + 1]
        if np.isnan(ar) or np.isnan(w) or np.isnan(c) or c <= 0.0:
            continue
        if ar > median_abs_ret:
            ri_sum += w / c
            ri_cnt += 1

    if ri_cnt > 5:
        out[4] = ri_sum / ri_cnt

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
            "Extended wick features for full-day window. "
            "5 features applying proven patterns (roughness, regime-transitions, "
            "conditional Amihud) to the wick dimension of 1-min bar OHLC structure."
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
