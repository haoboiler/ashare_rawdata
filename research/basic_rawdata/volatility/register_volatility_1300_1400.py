#!/usr/bin/env python3
"""Register the volatility bundle for the 13:00-14:00 window.

Bundle 1: volatility_1300_1400
- Input: open, high, low, close (OHLC from 1m bars)
- Output: 20 variables covering price volatility, return distribution,
  and microstructure metrics.

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

NAME = "volatility_1300_1400"

OUTPUT_NAMES = [
    # --- 价格波动 (10) ---
    "price_std_1300_1400",
    "return_std_1300_1400",
    "realized_vol_1300_1400",
    "upside_vol_1300_1400",
    "downside_vol_1300_1400",
    "vol_asymmetry_1300_1400",
    "parkinson_vol_1300_1400",
    "garman_klass_vol_1300_1400",
    "price_range_1300_1400",
    "bar_avg_range_1300_1400",
    # --- 收益分布 (6) ---
    "window_return_1300_1400",
    "return_skew_1300_1400",
    "return_kurt_1300_1400",
    "max_return_1300_1400",
    "min_return_1300_1400",
    "max_drawdown_1300_1400",
    # --- 微观结构 (4) ---
    "trend_strength_1300_1400",
    "autocorr_1_1300_1400",
    "sign_change_ratio_1300_1400",
    "close_position_1300_1400",
]

FORMULA = """@njit
def apply_func(inputs):
    open_ = inputs[0]
    high = inputs[1]
    low = inputs[2]
    close = inputs[3]

    n = close.size
    n_out = 20

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

    # ---- 0: price_std ----
    out[0] = np.nanstd(close)

    # ---- 1: return_std ----
    if valid_ret_count >= 2:
        mean_r = 0.0
        cnt = 0
        for i in range(n_ret):
            if not np.isnan(rets[i]):
                mean_r += rets[i]
                cnt += 1
        mean_r /= cnt
        ss = 0.0
        for i in range(n_ret):
            if not np.isnan(rets[i]):
                ss += (rets[i] - mean_r) ** 2
        out[1] = np.sqrt(ss / (cnt - 1))

    # ---- 2: realized_vol = sqrt(sum(r^2)) ----
    sum_r2 = 0.0
    for i in range(n_ret):
        if not np.isnan(rets[i]):
            sum_r2 += rets[i] ** 2
    if valid_ret_count > 0:
        out[2] = np.sqrt(sum_r2)

    # ---- 3: upside_vol = sqrt(sum(r^2 where r>0)) ----
    # ---- 4: downside_vol = sqrt(sum(r^2 where r<0)) ----
    up_sum = 0.0
    dn_sum = 0.0
    up_cnt = 0
    dn_cnt = 0
    for i in range(n_ret):
        r = rets[i]
        if np.isnan(r):
            continue
        if r > 0.0:
            up_sum += r * r
            up_cnt += 1
        elif r < 0.0:
            dn_sum += r * r
            dn_cnt += 1
    if up_cnt > 0:
        out[3] = np.sqrt(up_sum)
    if dn_cnt > 0:
        out[4] = np.sqrt(dn_sum)

    # ---- 5: vol_asymmetry = upside_vol - downside_vol ----
    if up_cnt > 0 and dn_cnt > 0:
        out[5] = out[3] - out[4]

    # ---- 6: parkinson_vol = sqrt(sum(ln(H/L)^2) / (4*n*ln2)) ----
    park_sum = 0.0
    park_cnt = 0
    for i in range(n):
        h = high[i]
        l = low[i]
        if np.isnan(h) or np.isnan(l) or l <= 0.0 or h <= 0.0:
            continue
        hl = np.log(h / l)
        park_sum += hl * hl
        park_cnt += 1
    if park_cnt > 0:
        out[6] = np.sqrt(park_sum / (4.0 * park_cnt * np.log(2.0)))

    # ---- 7: garman_klass_vol ----
    # GK = sqrt( (1/n) * sum[ 0.5*ln(H/L)^2 - (2ln2-1)*ln(C/O)^2 ] )
    gk_sum = 0.0
    gk_cnt = 0
    for i in range(n):
        o = open_[i]
        h = high[i]
        l = low[i]
        c = close[i]
        if np.isnan(o) or np.isnan(h) or np.isnan(l) or np.isnan(c):
            continue
        if o <= 0.0 or h <= 0.0 or l <= 0.0 or c <= 0.0:
            continue
        hl = np.log(h / l)
        co = np.log(c / o)
        gk_sum += 0.5 * hl * hl - (2.0 * np.log(2.0) - 1.0) * co * co
        gk_cnt += 1
    if gk_cnt > 0:
        gk_var = gk_sum / gk_cnt
        out[7] = np.sqrt(max(gk_var, 0.0))

    # ---- 8: price_range = (max(high) - min(low)) / mean(close) ----
    max_h = -np.inf
    min_l = np.inf
    mean_c = 0.0
    c_cnt = 0
    for i in range(n):
        if not np.isnan(high[i]) and high[i] > max_h:
            max_h = high[i]
        if not np.isnan(low[i]) and low[i] < min_l:
            min_l = low[i]
        if not np.isnan(close[i]):
            mean_c += close[i]
            c_cnt += 1
    if c_cnt > 0 and max_h > -np.inf and min_l < np.inf:
        mean_c /= c_cnt
        if mean_c > 0.0:
            out[8] = (max_h - min_l) / mean_c

    # ---- 9: bar_avg_range = mean((H-L)/C) ----
    range_sum = 0.0
    range_cnt = 0
    for i in range(n):
        h = high[i]
        l = low[i]
        c = close[i]
        if np.isnan(h) or np.isnan(l) or np.isnan(c) or c <= 0.0:
            continue
        range_sum += (h - l) / c
        range_cnt += 1
    if range_cnt > 0:
        out[9] = range_sum / range_cnt

    # ---- 10: window_return = last_close / first_close - 1 ----
    first_c = np.nan
    last_c = np.nan
    for i in range(n):
        if not np.isnan(close[i]):
            first_c = close[i]
            break
    for i in range(n - 1, -1, -1):
        if not np.isnan(close[i]):
            last_c = close[i]
            break
    if not np.isnan(first_c) and not np.isnan(last_c) and first_c > 0.0:
        out[10] = last_c / first_c - 1.0

    # ---- 11: return_skew ----
    # ---- 12: return_kurt ----
    if valid_ret_count >= 3:
        mean_r = 0.0
        cnt = 0
        for i in range(n_ret):
            if not np.isnan(rets[i]):
                mean_r += rets[i]
                cnt += 1
        mean_r /= cnt
        m2 = 0.0
        m3 = 0.0
        m4 = 0.0
        for i in range(n_ret):
            if not np.isnan(rets[i]):
                d = rets[i] - mean_r
                d2 = d * d
                m2 += d2
                m3 += d2 * d
                m4 += d2 * d2
        m2 /= cnt
        m3 /= cnt
        m4 /= cnt
        if m2 > 0.0:
            sd = np.sqrt(m2)
            out[11] = m3 / (sd * sd * sd)
            out[12] = m4 / (m2 * m2) - 3.0

    # ---- 13: max_return ----
    # ---- 14: min_return ----
    max_r = -np.inf
    min_r = np.inf
    for i in range(n_ret):
        r = rets[i]
        if np.isnan(r):
            continue
        if r > max_r:
            max_r = r
        if r < min_r:
            min_r = r
    if max_r > -np.inf:
        out[13] = max_r
    if min_r < np.inf:
        out[14] = min_r

    # ---- 15: max_drawdown ----
    peak = -np.inf
    max_dd = 0.0
    for i in range(n):
        c = close[i]
        if np.isnan(c):
            continue
        if c > peak:
            peak = c
        dd = (peak - c) / peak
        if dd > max_dd:
            max_dd = dd
    if peak > -np.inf:
        out[15] = max_dd

    # ---- 16: trend_strength = |cum_return| / sum(|bar_return|) ----
    abs_sum = 0.0
    cum_ret = 0.0
    for i in range(n_ret):
        r = rets[i]
        if np.isnan(r):
            continue
        cum_ret += r
        abs_sum += abs(r)
    if abs_sum > 0.0:
        out[16] = abs(cum_ret) / abs_sum

    # ---- 17: autocorr_1 = corr(r[:-1], r[1:]) ----
    if valid_ret_count >= 3:
        # build paired arrays (r_t, r_{t+1}) where both are valid
        sx = 0.0
        sy = 0.0
        sxx = 0.0
        syy = 0.0
        sxy = 0.0
        pair_cnt = 0
        for i in range(n_ret - 1):
            x = rets[i]
            y = rets[i + 1]
            if np.isnan(x) or np.isnan(y):
                continue
            sx += x
            sy += y
            sxx += x * x
            syy += y * y
            sxy += x * y
            pair_cnt += 1
        if pair_cnt >= 2:
            denom = (pair_cnt * sxx - sx * sx) * (pair_cnt * syy - sy * sy)
            if denom > 0.0:
                out[17] = (pair_cnt * sxy - sx * sy) / np.sqrt(denom)

    # ---- 18: sign_change_ratio ----
    sign_changes = 0
    sign_total = 0
    prev_sign = 0  # -1, 0, +1
    for i in range(n_ret):
        r = rets[i]
        if np.isnan(r) or r == 0.0:
            continue
        cur_sign = 1 if r > 0.0 else -1
        if prev_sign != 0:
            sign_total += 1
            if cur_sign != prev_sign:
                sign_changes += 1
        prev_sign = cur_sign
    if sign_total > 0:
        out[18] = sign_changes / sign_total

    # ---- 19: close_position = mean((C-L)/(H-L)) ----
    cp_sum = 0.0
    cp_cnt = 0
    for i in range(n):
        c = close[i]
        h = high[i]
        l = low[i]
        if np.isnan(c) or np.isnan(h) or np.isnan(l):
            continue
        hl = h - l
        if hl > 0.0:
            cp_sum += (c - l) / hl
            cp_cnt += 1
    if cp_cnt > 0:
        out[19] = cp_sum / cp_cnt

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["open", "high", "low", "close"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("13:00", "14:00")]),
        slot=RawDataSlot.EVENING,
        data_available_at=1401,
        execution_start_at=1300,
        execution_end_at=1400,
        expected_bars=40,
        description=(
            "Volatility bundle for the 13:00-14:00 window. "
            "Emits 20 variables: price volatility (std, realized, upside/downside, "
            "Parkinson, Garman-Klass, range), return distribution (skew, kurtosis, "
            "extremes, drawdown), and microstructure (trend strength, autocorr, "
            "sign changes, close position)."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the volatility 13:00-14:00 bundle"
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
