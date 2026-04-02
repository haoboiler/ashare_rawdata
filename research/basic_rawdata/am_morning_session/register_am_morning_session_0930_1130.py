#!/usr/bin/env python3
"""Register the merged morning-session bundle for the 09:30-11:30 window.

Bundle: am_morning_session_0930_1130
- Input: open, high, low, close, volume, amount (from 1m bars, 09:30-11:30)
- Output: 19 daily fields covering basics, opening impulse, liquidity,
  extremum timing, order toxicity, jump risk, and VWAP path.

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

NAME = "am_morning_session_0930_1130"

OUTPUT_NAMES = [
    # --- basics (5) ---
    "am_close_0930_1130",           # 0
    "am_high_0930_1130",            # 1
    "am_low_0930_1130",             # 2
    "am_volume_sum_0930_1130",      # 3
    "am_amount_sum_0930_1130",      # 4
    # --- opening impulse (3) ---
    "am_open_return_0930_1000",     # 5
    "am_open_volume_share_0930_1000",  # 6
    "am_open_followthrough_1000_1130", # 7
    # --- time-weighted liquidity (2) ---
    "am_tiam_0930_1130",            # 8
    "am_liquidity_decay_slope_0930_1130",  # 9
    # --- extremum timing (4) ---
    "am_high_time_idx_0930_1130",   # 10
    "am_low_time_idx_0930_1130",    # 11
    "am_near_high_minutes_0930_1130",  # 12
    "am_near_low_minutes_0930_1130",   # 13
    # --- order toxicity proxy (2) ---
    "am_toxicity_trend_0930_1130",  # 14
    "am_unfinished_one_sided_flow_0930_1130",  # 15
    # --- jump risk (2) ---
    "am_jump_count_proxy_0930_1130",  # 16
    "am_jump_direction_imbalance_0930_1130",  # 17
    # --- vwap path (1) ---
    "am_vwap_cross_count_0930_1130",  # 18
]

FORMULA = """@njit
def apply_func(inputs):
    open_ = inputs[0]
    high  = inputs[1]
    low   = inputs[2]
    close = inputs[3]
    volume = inputs[4]
    amount = inputs[5]

    n = close.size
    N_OUT = 19
    out = np.full(N_OUT, np.nan, dtype=np.float64)
    if n < 4:
        return out

    # ========== sub-window boundaries (proportional to 120-min AM session) ==========
    q1 = n // 4          # end of 09:30-10:00
    q2 = n // 2          # end of 10:00-10:30
    q3 = 3 * n // 4      # end of 10:30-11:00
    # [q3, n) = 11:00-11:30

    # ========== SHARED: per-bar log-return, sign, impact ==========
    # r[i] = log(close[i] / close[i-1]) for i >= 1, else NaN
    # We also accumulate sigma_r for jump detection
    n_valid_ret = 0
    sum_r = 0.0
    sum_r2 = 0.0
    for i in range(1, n):
        c_prev = close[i - 1]
        c_cur = close[i]
        if np.isnan(c_prev) or np.isnan(c_cur) or c_prev <= 0.0 or c_cur <= 0.0:
            continue
        r = np.log(c_cur / c_prev)
        sum_r += r
        sum_r2 += r * r
        n_valid_ret += 1

    # ================================================================
    # GROUP 1: BASICS (out[0..4])
    # ================================================================

    # 0: am_close — last valid close
    for i in range(n - 1, -1, -1):
        c = close[i]
        if not np.isnan(c):
            out[0] = c
            break
    last_close_full = out[0]

    # 1: am_high — max(high)
    max_high = -np.inf
    for i in range(n):
        h = high[i]
        if not np.isnan(h) and h > max_high:
            max_high = h
    if max_high > -np.inf:
        out[1] = max_high

    # 2: am_low — min(low)
    min_low = np.inf
    for i in range(n):
        l = low[i]
        if not np.isnan(l) and l < min_low:
            min_low = l
    if min_low < np.inf:
        out[2] = min_low

    # 3: am_volume_sum
    vol_full = 0.0
    vol_full_cnt = 0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v):
            vol_full += v
            vol_full_cnt += 1
    if vol_full_cnt > 0:
        out[3] = vol_full

    # 4: am_amount_sum
    amt_full = 0.0
    amt_full_cnt = 0
    for i in range(n):
        a = amount[i]
        if not np.isnan(a):
            amt_full += a
            amt_full_cnt += 1
    if amt_full_cnt > 0:
        out[4] = amt_full

    # ================================================================
    # GROUP 2: OPENING IMPULSE (out[5..7])
    # ================================================================

    # first open in [0, q1)
    first_open = np.nan
    for i in range(q1):
        o = open_[i]
        if not np.isnan(o) and o > 0.0:
            first_open = o
            break

    # last close in [0, q1)
    last_close_q1 = np.nan
    for i in range(q1 - 1, -1, -1):
        c = close[i]
        if not np.isnan(c):
            last_close_q1 = c
            break

    # 5: am_open_return_0930_1000
    if not np.isnan(first_open) and not np.isnan(last_close_q1) and first_open > 0.0:
        out[5] = last_close_q1 / first_open - 1.0

    # 6: am_open_volume_share_0930_1000
    vol_q1 = 0.0
    for i in range(q1):
        v = volume[i]
        if not np.isnan(v):
            vol_q1 += v
    if vol_full > 0.0:
        out[6] = vol_q1 / vol_full

    # 7: am_open_followthrough_1000_1130
    if not np.isnan(last_close_q1) and not np.isnan(last_close_full) and last_close_q1 > 0.0:
        out[7] = last_close_full / last_close_q1 - 1.0

    # ================================================================
    # GROUP 3: TIME-WEIGHTED LIQUIDITY (out[8..9])
    # ================================================================

    # Compute per-bar impact_t = abs(r_t) / amount_t, with TIAM and OLS
    tiam_sum_w = 0.0
    tiam_sum_wi = 0.0
    ols_sum_x = 0.0
    ols_sum_y = 0.0
    ols_sum_xx = 0.0
    ols_sum_xy = 0.0
    n_impact = 0

    for i in range(1, n):
        c_prev = close[i - 1]
        c_cur = close[i]
        a = amount[i]
        if np.isnan(c_prev) or np.isnan(c_cur) or c_prev <= 0.0 or c_cur <= 0.0:
            continue
        if np.isnan(a) or a <= 0.0:
            continue
        r = np.log(c_cur / c_prev)
        impact = abs(r) / a

        w = float(n_impact + 1)
        tiam_sum_w += w
        tiam_sum_wi += w * impact

        n_impact += 1

    # 8: am_tiam
    if tiam_sum_w > 0.0 and n_impact >= 2:
        out[8] = tiam_sum_wi / tiam_sum_w

    # 9: am_liquidity_decay_slope (recompute with normalised x)
    if n_impact >= 3:
        sx = 0.0
        sy = 0.0
        sxx = 0.0
        sxy = 0.0
        idx = 0
        denom_x = float(n_impact - 1)
        for i in range(1, n):
            c_prev = close[i - 1]
            c_cur = close[i]
            a = amount[i]
            if np.isnan(c_prev) or np.isnan(c_cur) or c_prev <= 0.0 or c_cur <= 0.0:
                continue
            if np.isnan(a) or a <= 0.0:
                continue
            r = np.log(c_cur / c_prev)
            impact = abs(r) / a
            x = float(idx) / denom_x
            sx += x
            sy += impact
            sxx += x * x
            sxy += x * impact
            idx += 1
        nf = float(n_impact)
        d = nf * sxx - sx * sx
        if abs(d) > 1e-15:
            out[9] = (nf * sxy - sx * sy) / d

    # ================================================================
    # GROUP 4: EXTREMUM TIMING (out[10..13])
    # ================================================================

    # 10: am_high_time_idx — first occurrence of max_high, normalised
    if max_high > -np.inf:
        n_valid_h = 0
        first_high_valid_idx = -1
        for i in range(n):
            h = high[i]
            if np.isnan(h):
                continue
            if h == max_high and first_high_valid_idx < 0:
                first_high_valid_idx = n_valid_h
            n_valid_h += 1
        if first_high_valid_idx >= 0 and n_valid_h > 1:
            out[10] = float(first_high_valid_idx) / float(n_valid_h - 1)

    # 11: am_low_time_idx — first occurrence of min_low, normalised
    if min_low < np.inf:
        n_valid_l = 0
        first_low_valid_idx = -1
        for i in range(n):
            l = low[i]
            if np.isnan(l):
                continue
            if l == min_low and first_low_valid_idx < 0:
                first_low_valid_idx = n_valid_l
            n_valid_l += 1
        if first_low_valid_idx >= 0 and n_valid_l > 1:
            out[11] = float(first_low_valid_idx) / float(n_valid_l - 1)

    # 12 & 13: near_high / near_low minutes fraction
    range_hl = max_high - min_low
    if max_high > -np.inf and min_low < np.inf and range_hl > 0.0:
        band = 0.2 * range_hl
        high_thr = max_high - band
        low_thr = min_low + band
        n_vc = 0
        n_near_h = 0
        n_near_l = 0
        for i in range(n):
            c = close[i]
            if np.isnan(c):
                continue
            n_vc += 1
            if c >= high_thr:
                n_near_h += 1
            if c <= low_thr:
                n_near_l += 1
        if n_vc > 0:
            out[12] = float(n_near_h) / float(n_vc)
            out[13] = float(n_near_l) / float(n_vc)

    # ================================================================
    # GROUP 5: ORDER TOXICITY PROXY (out[14..15])
    # ================================================================
    # Uses 4 half-hour buckets; need signed_vol per bar

    bucket_starts = np.empty(4, dtype=np.int64)
    bucket_ends = np.empty(4, dtype=np.int64)
    bucket_starts[0] = 0;   bucket_ends[0] = q1
    bucket_starts[1] = q1;  bucket_ends[1] = q2
    bucket_starts[2] = q2;  bucket_ends[2] = q3
    bucket_starts[3] = q3;  bucket_ends[3] = n

    bucket_imb = np.full(4, np.nan, dtype=np.float64)
    full_signed_vol_sum = 0.0

    for b in range(4):
        s = bucket_starts[b]
        e = bucket_ends[b]
        sv_sum = 0.0
        v_sum = 0.0
        for i in range(max(s, 1), e):
            c_prev = close[i - 1]
            c_cur = close[i]
            v = volume[i]
            if np.isnan(c_prev) or np.isnan(c_cur) or c_prev <= 0.0 or c_cur <= 0.0:
                continue
            if np.isnan(v):
                continue
            r = np.log(c_cur / c_prev)
            if r > 0.0:
                sign_r = 1.0
            elif r < 0.0:
                sign_r = -1.0
            else:
                sign_r = 0.0
            sv_sum += sign_r * v
            v_sum += v
        if v_sum > 0.0:
            bucket_imb[b] = abs(sv_sum) / v_sum
        full_signed_vol_sum += sv_sum

    # 14: am_toxicity_trend — OLS slope of bucket_imb vs bucket index
    n_vb = 0
    tx_sx = 0.0
    tx_sy = 0.0
    tx_sxx = 0.0
    tx_sxy = 0.0
    for b in range(4):
        if np.isnan(bucket_imb[b]):
            continue
        x = float(b)
        y = bucket_imb[b]
        tx_sx += x
        tx_sy += y
        tx_sxx += x * x
        tx_sxy += x * y
        n_vb += 1
    if n_vb >= 2:
        nf = float(n_vb)
        d = nf * tx_sxx - tx_sx * tx_sx
        if abs(d) > 1e-15:
            out[14] = (nf * tx_sxy - tx_sx * tx_sy) / d

    # 15: am_unfinished_one_sided_flow
    if full_signed_vol_sum > 0.0:
        dom = 1.0
    elif full_signed_vol_sum < 0.0:
        dom = -1.0
    else:
        dom = 0.0

    if dom != 0.0:
        aligned_full = 0.0
        aligned_last = 0.0
        for i in range(1, n):
            c_prev = close[i - 1]
            c_cur = close[i]
            v = volume[i]
            if np.isnan(c_prev) or np.isnan(c_cur) or c_prev <= 0.0 or c_cur <= 0.0:
                continue
            if np.isnan(v):
                continue
            r = np.log(c_cur / c_prev)
            if r > 0.0:
                sign_r = 1.0
            elif r < 0.0:
                sign_r = -1.0
            else:
                sign_r = 0.0
            if sign_r == dom:
                aligned_full += v
                if i >= q3:
                    aligned_last += v
        if aligned_full > 0.0:
            out[15] = aligned_last / aligned_full

    # ================================================================
    # GROUP 6: JUMP RISK (out[16..17])
    # ================================================================

    if n_valid_ret >= 10:
        mean_r = sum_r / float(n_valid_ret)
        var_r = sum_r2 / float(n_valid_ret) - mean_r * mean_r
        if var_r < 0.0:
            var_r = 0.0
        sigma_r = var_r ** 0.5
        threshold = 2.5 * sigma_r
        if threshold < 0.002:
            threshold = 0.002

        n_jump = 0
        n_up = 0
        n_dn = 0
        for i in range(1, n):
            c_prev = close[i - 1]
            c_cur = close[i]
            if np.isnan(c_prev) or np.isnan(c_cur) or c_prev <= 0.0 or c_cur <= 0.0:
                continue
            r = np.log(c_cur / c_prev)
            if abs(r) > threshold:
                n_jump += 1
                if r > 0.0:
                    n_up += 1
                elif r < 0.0:
                    n_dn += 1

        # 16: am_jump_count_proxy
        out[16] = float(n_jump)

        # 17: am_jump_direction_imbalance
        if n_jump > 0:
            out[17] = float(n_up - n_dn) / float(n_jump)

    # ================================================================
    # GROUP 7: VWAP PATH (out[18])
    # ================================================================

    cum_pv = 0.0
    cum_vol = 0.0
    prev_sign = 0
    cross_count = 0
    n_vwap_valid = 0

    for i in range(n):
        c = close[i]
        v = volume[i]
        if np.isnan(c) or np.isnan(v):
            continue
        cum_pv += c * v
        cum_vol += v
        if cum_vol <= 0.0:
            continue
        cum_vwap = cum_pv / cum_vol
        diff = c - cum_vwap
        n_vwap_valid += 1

        if diff > 0.0:
            cur_sign = 1
        elif diff < 0.0:
            cur_sign = -1
        else:
            cur_sign = prev_sign

        if prev_sign != 0 and cur_sign != 0 and cur_sign != prev_sign:
            cross_count += 1
        if cur_sign != 0:
            prev_sign = cur_sign

    # 18: am_vwap_cross_count
    if n_vwap_valid >= 3:
        out[18] = float(cross_count)

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["open", "high", "low", "close", "volume", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30")]),
        slot=RawDataSlot.MIDDAY,
        data_available_at=1131,
        execution_start_at=930,
        execution_end_at=1130,
        expected_bars=80,
        description=(
            "Merged morning-session bundle for 09:30-11:30. Emits 19 fields "
            "covering basics (close/high/low/volume/amount), opening impulse "
            "(return, volume share, follow-through), time-weighted liquidity "
            "(TIAM, decay slope), extremum timing (high/low timing and "
            "duration), order toxicity (trend, unfinished flow), jump risk "
            "(count, direction imbalance), and VWAP path (cross count)."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the merged morning-session 09:30-11:30 bundle"
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
