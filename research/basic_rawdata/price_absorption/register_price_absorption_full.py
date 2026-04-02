#!/usr/bin/env python3
"""Price Absorption & Depth — full-day window (09:30-11:30 + 13:00-14:57).

D-019: 日内价格吸收与深度因子
核心假设：高交易量但低价格冲击的事件（"吸收事件"）频率反映订单簿深度。
与 Amihud（衡量价格冲击）互补：Amihud 看"移动了价格的交易"，absorption 看"未移动价格的交易"。

Features:
  absorption_freq_full      — 高量低冲击 bar 占比（离散计数）
  zero_return_freq_full     — 零收益 bar 占比（价格不动 = 深度支撑）
  depth_volume_ratio_full   — 低冲击 bar 成交量占总量比例
  absorption_amihud_full    — 吸收事件 bar 的条件 Amihud
  impact_efficiency_full    — 每单位成交额的平均价格冲击（全天）
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

NAME = "price_absorption_full"

OUTPUT_NAMES = [
    "absorption_freq_full",
    "zero_return_freq_full",
    "depth_volume_ratio_full",
    "absorption_amihud_full",
    "impact_efficiency_full",
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]
    amount = inputs[2]

    n = close.size
    n_out = 5

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 10:
        return out

    # ---- pre-compute log returns ----
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

    # ---- compute medians for thresholds ----
    # median of |return| (for low-impact threshold)
    valid_abs_rets = np.empty(valid_ret_count, dtype=np.float64)
    idx = 0
    for i in range(n_ret):
        if not np.isnan(abs_rets[i]):
            valid_abs_rets[idx] = abs_rets[i]
            idx += 1
    valid_abs_rets_sorted = np.sort(valid_abs_rets[:idx])
    median_abs_ret = valid_abs_rets_sorted[idx // 2]

    # median of volume (for high-volume threshold)
    valid_vols = np.empty(n_ret, dtype=np.float64)
    vol_idx = 0
    for i in range(n_ret):
        v = volume[i + 1]
        if not np.isnan(v) and v > 0.0:
            valid_vols[vol_idx] = v
            vol_idx += 1

    if vol_idx < 10:
        return out

    valid_vols_sorted = np.sort(valid_vols[:vol_idx])
    median_vol = valid_vols_sorted[vol_idx // 2]

    # ---- Feature 0: absorption_freq_full ----
    # Count bars where volume > median AND |return| < median
    # These are "absorption events" - high trading activity without proportional price movement
    absorption_count = 0
    total_valid = 0
    for i in range(n_ret):
        ar = abs_rets[i]
        v = volume[i + 1]
        if np.isnan(ar) or np.isnan(v):
            continue
        total_valid += 1
        if v > median_vol and ar < median_abs_ret:
            absorption_count += 1

    if total_valid > 0:
        out[0] = absorption_count / total_valid

    # ---- Feature 1: zero_return_freq_full ----
    # Count bars where |return| is essentially zero (< 1e-8)
    # Zero return = price unchanged despite trading = deep order book at current level
    zero_count = 0
    for i in range(n_ret):
        ar = abs_rets[i]
        if np.isnan(ar):
            continue
        if ar < 1e-8:
            zero_count += 1

    if valid_ret_count > 0:
        out[1] = zero_count / valid_ret_count

    # ---- Feature 2: depth_volume_ratio_full ----
    # Fraction of total volume traded during low-impact bars (|ret| < median)
    # High ratio = most volume absorbed without moving price = deep liquidity
    low_impact_volume = 0.0
    total_volume = 0.0
    for i in range(n_ret):
        ar = abs_rets[i]
        v = volume[i + 1]
        if np.isnan(ar) or np.isnan(v):
            continue
        total_volume += v
        if ar < median_abs_ret:
            low_impact_volume += v

    if total_volume > 0.0:
        out[2] = low_impact_volume / total_volume

    # ---- Feature 3: absorption_amihud_full ----
    # Amihud only for absorption event bars (high volume + low impact)
    # Conditional Amihud measuring price impact DURING depth events
    absorption_amihud_sum = 0.0
    absorption_amihud_cnt = 0
    for i in range(n_ret):
        ar = abs_rets[i]
        v = volume[i + 1]
        a = amount[i + 1]
        if np.isnan(ar) or np.isnan(v) or np.isnan(a) or a <= 0.0:
            continue
        if v > median_vol and ar < median_abs_ret:
            absorption_amihud_sum += ar / a
            absorption_amihud_cnt += 1

    if absorption_amihud_cnt > 5:
        out[3] = absorption_amihud_sum / absorption_amihud_cnt

    # ---- Feature 4: impact_efficiency_full ----
    # mean(|return|) / mean(amount) — overall price impact per unit of trading
    # This is essentially the standard Amihud but with mean(amount) instead of per-bar
    # Lower = more efficient = better liquidity
    total_abs_ret = 0.0
    total_amount = 0.0
    impact_cnt = 0
    for i in range(n_ret):
        ar = abs_rets[i]
        a = amount[i + 1]
        if np.isnan(ar) or np.isnan(a) or a <= 0.0:
            continue
        total_abs_ret += ar
        total_amount += a
        impact_cnt += 1

    if impact_cnt > 0 and total_amount > 0.0:
        out[4] = (total_abs_ret / impact_cnt) / (total_amount / impact_cnt)

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
            input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")],
        ),
        slot=RawDataSlot.EVENING,
        data_available_at=1530,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Price absorption & depth bundle for full-day window. "
            "5 features measuring order book depth via absorption events "
            "(high volume + low price impact), zero returns, and depth ratios. "
            "Complements Amihud (impact) with absorption (stability) perspective."
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
