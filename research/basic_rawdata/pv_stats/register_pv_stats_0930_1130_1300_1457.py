#!/usr/bin/env python3
"""Register the price-volume stats bundle for the full-day window (excl. closing auction).

Bundle: pv_stats_0930_1130_1300_1457
- Input: close, volume, amount (from 1m bars)
- Output: 15 variables covering TWAP/VWAP, price-volume relationships,
  and volume/amount statistics.
- Window: 09:30-11:30 + 13:00-14:57 (excludes 14:57-15:00 closing auction)

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

NAME = "pv_stats_0930_1130_1300_1457"

OUTPUT_NAMES = [
    # --- 基础均价 (2) ---
    "twap_0930_1130_1300_1457",
    "vwap_0930_1130_1300_1457",
    # --- 量价关系 (7) ---
    "amihud_0930_1130_1300_1457",
    "price_volume_corr_0930_1130_1300_1457",
    "return_volume_corr_0930_1130_1300_1457",
    "volume_imbalance_0930_1130_1300_1457",
    "amount_imbalance_0930_1130_1300_1457",
    "vwap_deviation_0930_1130_1300_1457",
    "kyle_lambda_0930_1130_1300_1457",
    # --- 成交量统计 (5) ---
    "volume_std_0930_1130_1300_1457",
    "volume_cv_0930_1130_1300_1457",
    "volume_skew_0930_1130_1300_1457",
    "volume_concentration_0930_1130_1300_1457",
    "volume_trend_0930_1130_1300_1457",
    # --- 成交额统计 (1) ---
    "amount_cv_0930_1130_1300_1457",
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]
    amount = inputs[2]

    n = close.size
    n_out = 15

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n == 0:
        return out

    # ---- pre-compute log returns ----
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    valid_ret_count = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = np.log(c1 / c0)
            valid_ret_count += 1

    # ---- 0: twap = mean(close) ----
    out[0] = np.nanmean(close)

    # ---- 1: vwap = sum(close * volume) / sum(volume) ----
    weighted_sum = 0.0
    volume_sum = 0.0
    for i in range(n):
        c = close[i]
        v = volume[i]
        if np.isnan(c) or np.isnan(v):
            continue
        weighted_sum += c * v
        volume_sum += v
    if volume_sum > 0.0:
        out[1] = weighted_sum / volume_sum

    # ---- 2: amihud = mean(|r| / amount) ----
    amihud_sum = 0.0
    amihud_cnt = 0
    for i in range(n_ret):
        r = rets[i]
        a = amount[i + 1]
        if np.isnan(r) or np.isnan(a) or a <= 0.0:
            continue
        amihud_sum += abs(r) / a
        amihud_cnt += 1
    if amihud_cnt > 0:
        out[2] = amihud_sum / amihud_cnt

    # ---- 3: price_volume_corr = corr(close, volume) ----
    sx = 0.0
    sy = 0.0
    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    pv_cnt = 0
    for i in range(n):
        x = close[i]
        y = volume[i]
        if np.isnan(x) or np.isnan(y):
            continue
        sx += x
        sy += y
        sxx += x * x
        syy += y * y
        sxy += x * y
        pv_cnt += 1
    if pv_cnt >= 2:
        denom = (pv_cnt * sxx - sx * sx) * (pv_cnt * syy - sy * sy)
        if denom > 0.0:
            out[3] = (pv_cnt * sxy - sx * sy) / np.sqrt(denom)

    # ---- 4: return_volume_corr = corr(returns, volume[1:]) ----
    sx = 0.0
    sy = 0.0
    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    rv_cnt = 0
    for i in range(n_ret):
        x = rets[i]
        y = volume[i + 1]
        if np.isnan(x) or np.isnan(y):
            continue
        sx += x
        sy += y
        sxx += x * x
        syy += y * y
        sxy += x * y
        rv_cnt += 1
    if rv_cnt >= 2:
        denom = (rv_cnt * sxx - sx * sx) * (rv_cnt * syy - sy * sy)
        if denom > 0.0:
            out[4] = (rv_cnt * sxy - sx * sy) / np.sqrt(denom)

    # ---- 5: volume_imbalance = sum(vol where r>0) / sum(vol) - 0.5 ----
    vol_up = 0.0
    vol_total = 0.0
    for i in range(n_ret):
        r = rets[i]
        v = volume[i + 1]
        if np.isnan(r) or np.isnan(v):
            continue
        vol_total += v
        if r > 0.0:
            vol_up += v
    if vol_total > 0.0:
        out[5] = vol_up / vol_total - 0.5

    # ---- 6: amount_imbalance = sum(amt where r>0) / sum(amt) - 0.5 ----
    amt_up = 0.0
    amt_total = 0.0
    for i in range(n_ret):
        r = rets[i]
        a = amount[i + 1]
        if np.isnan(r) or np.isnan(a):
            continue
        amt_total += a
        if r > 0.0:
            amt_up += a
    if amt_total > 0.0:
        out[6] = amt_up / amt_total - 0.5

    # ---- 7: vwap_deviation = (vwap - twap) / twap ----
    if not np.isnan(out[0]) and not np.isnan(out[1]) and out[0] > 0.0:
        out[7] = (out[1] - out[0]) / out[0]

    # ---- 8: kyle_lambda = regression(|delta_price|, volume) slope ----
    if n_ret > 0:
        sx = 0.0
        sy = 0.0
        sxx = 0.0
        sxy = 0.0
        kl_cnt = 0
        for i in range(n_ret):
            v = volume[i + 1]
            c0 = close[i]
            c1 = close[i + 1]
            if np.isnan(v) or np.isnan(c0) or np.isnan(c1):
                continue
            dp = abs(c1 - c0)
            sx += v
            sy += dp
            sxx += v * v
            sxy += v * dp
            kl_cnt += 1
        if kl_cnt >= 2:
            var_x = kl_cnt * sxx - sx * sx
            if var_x > 0.0:
                out[8] = (kl_cnt * sxy - sx * sy) / var_x

    # ---- volume statistics ----
    vol_mean = 0.0
    vol_cnt = 0
    vol_max = -np.inf
    vol_sum = 0.0
    for i in range(n):
        v = volume[i]
        if np.isnan(v):
            continue
        vol_mean += v
        vol_sum += v
        vol_cnt += 1
        if v > vol_max:
            vol_max = v
    if vol_cnt > 0:
        vol_mean /= vol_cnt

    # ---- 9: volume_std ----
    if vol_cnt >= 2:
        ss = 0.0
        for i in range(n):
            v = volume[i]
            if np.isnan(v):
                continue
            ss += (v - vol_mean) ** 2
        vol_std = np.sqrt(ss / (vol_cnt - 1))
        out[9] = vol_std

        # ---- 10: volume_cv = std / mean ----
        if vol_mean > 0.0:
            out[10] = vol_std / vol_mean

    # ---- 11: volume_skew ----
    if vol_cnt >= 3:
        m2 = 0.0
        m3 = 0.0
        for i in range(n):
            v = volume[i]
            if np.isnan(v):
                continue
            d = v - vol_mean
            d2 = d * d
            m2 += d2
            m3 += d2 * d
        m2 /= vol_cnt
        m3 /= vol_cnt
        if m2 > 0.0:
            out[11] = m3 / (m2 * np.sqrt(m2))

    # ---- 12: volume_concentration = max(volume) / sum(volume) ----
    if vol_sum > 0.0 and vol_max > -np.inf:
        out[12] = vol_max / vol_sum

    # ---- 13: volume_trend = corr(bar_index, volume) ----
    sx = 0.0
    sy = 0.0
    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    vt_cnt = 0
    for i in range(n):
        v = volume[i]
        if np.isnan(v):
            continue
        x = float(i)
        sx += x
        sy += v
        sxx += x * x
        syy += v * v
        sxy += x * v
        vt_cnt += 1
    if vt_cnt >= 2:
        denom = (vt_cnt * sxx - sx * sx) * (vt_cnt * syy - sy * sy)
        if denom > 0.0:
            out[13] = (vt_cnt * sxy - sx * sy) / np.sqrt(denom)

    # ---- 14: amount_cv = std(amount) / mean(amount) ----
    amt_mean = 0.0
    amt_cnt = 0
    for i in range(n):
        a = amount[i]
        if np.isnan(a):
            continue
        amt_mean += a
        amt_cnt += 1
    if amt_cnt >= 2:
        amt_mean /= amt_cnt
        ss = 0.0
        for i in range(n):
            a = amount[i]
            if np.isnan(a):
                continue
            ss += (a - amt_mean) ** 2
        amt_std = np.sqrt(ss / (amt_cnt - 1))
        if amt_mean > 0.0:
            out[14] = amt_std / amt_mean

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "volume", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]),
        slot=RawDataSlot.EVENING,
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Price-volume stats bundle for the full-day window "
            "(09:30-11:30 + 13:00-14:57, excludes closing auction). "
            "Emits 15 variables: TWAP/VWAP, price-volume relationships "
            "(Amihud, correlations, imbalance, Kyle's lambda), "
            "volume statistics (std, CV, skew, concentration, trend), "
            "and amount CV."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the price-volume stats full-day bundle"
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
