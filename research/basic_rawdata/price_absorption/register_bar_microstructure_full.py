#!/usr/bin/env python3
"""Bar Microstructure — full-day window (09:30-11:30 + 13:00-14:57).

D-019 Iteration 2: 从 bar 级 OHLC 结构探索价格吸收信号
核心假设：
  - bar 内 wick（影线）= 价格被订单簿拒绝的幅度，反映市场深度
  - wick_ratio（影线占比）是无量纲的，避免波动率代理陷阱
  - wick/amount 是 Amihud 框架的扩展：|f(rejected_price)|/amount

Features:
  wick_ratio_full           — mean((H-L-|C-O|)/(H-L+eps))  无量纲影线占比
  wick_amihud_full          — mean((H-L-|C-O|)/amount)      被拒绝价格的 Amihud
  high_vol_wick_amihud_full — 高量 bar 的 wick Amihud
  bar_efficiency_full       — mean(|C-O|/(H-L+eps))         bar 效率（1-wick_ratio）
  low_impact_amihud_full    — |ret| < p25 的 bar 的 Amihud（平静期冲击底线）
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

NAME = "bar_microstructure_full"

OUTPUT_NAMES = [
    "wick_ratio_full",
    "wick_amihud_full",
    "high_vol_wick_amihud_full",
    "bar_efficiency_full",
    "low_impact_amihud_full",
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

    # ---- pre-compute per-bar metrics ----
    n_ret = n - 1

    # abs returns for Amihud
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

    # compute 25th percentile of |return| for low_impact_amihud
    valid_abs_rets = np.empty(valid_ret_count, dtype=np.float64)
    idx = 0
    for i in range(n_ret):
        if not np.isnan(abs_rets[i]):
            valid_abs_rets[idx] = abs_rets[i]
            idx += 1
    valid_abs_rets_sorted = np.sort(valid_abs_rets[:idx])
    p25_idx = idx // 4
    p25_abs_ret = valid_abs_rets_sorted[p25_idx]

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

    # ---- Feature 0: wick_ratio_full ----
    # mean((H - L - |C - O|) / (H - L + eps))
    # Dimensionless: what fraction of each bar's range is "wick" (rejected price exploration)
    # High wick ratio = more price rejection = deeper order book
    eps = 1e-10
    wick_sum = 0.0
    wick_cnt = 0
    for i in range(n):
        h = high[i]
        l = low[i]
        c = close[i]
        o = opn[i]
        if np.isnan(h) or np.isnan(l) or np.isnan(c) or np.isnan(o):
            continue
        bar_range = h - l
        body = abs(c - o)
        wick_frac = (bar_range - body) / (bar_range + eps)
        wick_sum += wick_frac
        wick_cnt += 1

    if wick_cnt > 0:
        out[0] = wick_sum / wick_cnt

    # ---- Feature 1: wick_amihud_full ----
    # mean((H - L - |C - O|) / amount)
    # Amihud variant with wick (rejected price) as numerator
    # Higher = more rejected price exploration per unit of trading = shallower book
    wa_sum = 0.0
    wa_cnt = 0
    for i in range(n):
        h = high[i]
        l = low[i]
        c = close[i]
        o = opn[i]
        a = amount[i]
        if np.isnan(h) or np.isnan(l) or np.isnan(c) or np.isnan(o) or np.isnan(a) or a <= 0.0:
            continue
        bar_range = h - l
        body = abs(c - o)
        wick = bar_range - body
        if wick >= 0.0:
            wa_sum += wick / a
            wa_cnt += 1

    if wa_cnt > 0:
        out[1] = wa_sum / wa_cnt

    # ---- Feature 2: high_vol_wick_amihud_full ----
    # Wick Amihud only for high-volume bars (vol > median)
    # Focuses on active trading periods, filters out noise from quiet bars
    hvwa_sum = 0.0
    hvwa_cnt = 0
    for i in range(n):
        h = high[i]
        l = low[i]
        c = close[i]
        o = opn[i]
        v = volume[i]
        a = amount[i]
        if np.isnan(h) or np.isnan(l) or np.isnan(c) or np.isnan(o) or np.isnan(v) or np.isnan(a) or a <= 0.0:
            continue
        if v <= median_vol:
            continue
        bar_range = h - l
        body = abs(c - o)
        wick = bar_range - body
        if wick >= 0.0:
            hvwa_sum += wick / a
            hvwa_cnt += 1

    if hvwa_cnt > 5:
        out[2] = hvwa_sum / hvwa_cnt

    # ---- Feature 3: bar_efficiency_full ----
    # mean(|C - O| / (H - L + eps))
    # How much of each bar's range is "used" (body vs wick)
    # = 1 - wick_ratio; low efficiency = more rejection = deeper book
    eff_sum = 0.0
    eff_cnt = 0
    for i in range(n):
        h = high[i]
        l = low[i]
        c = close[i]
        o = opn[i]
        if np.isnan(h) or np.isnan(l) or np.isnan(c) or np.isnan(o):
            continue
        bar_range = h - l
        body = abs(c - o)
        eff = body / (bar_range + eps)
        eff_sum += eff
        eff_cnt += 1

    if eff_cnt > 0:
        out[3] = eff_sum / eff_cnt

    # ---- Feature 4: low_impact_amihud_full ----
    # Standard Amihud but only for bars with |ret| in bottom 25%
    # Measures the "floor" of price impact — baseline sensitivity
    li_sum = 0.0
    li_cnt = 0
    for i in range(n_ret):
        ar = abs_rets[i]
        a = amount[i + 1]
        if np.isnan(ar) or np.isnan(a) or a <= 0.0:
            continue
        if ar <= p25_abs_ret:
            li_sum += ar / a
            li_cnt += 1

    if li_cnt > 5:
        out[4] = li_sum / li_cnt

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
            "Bar-level microstructure features for full-day window. "
            "5 features exploring wick/body structure of 1-min bars "
            "and low-impact Amihud. Uses OHLC to measure price rejection "
            "and order book depth signals."
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
