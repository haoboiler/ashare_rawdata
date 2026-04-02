#!/usr/bin/env python3
"""Price Acceleration bundle for full-day window.

Bundle: price_accel_full
- Input: close, volume, amount (from 1m bars, full day)
- Output: 8 features capturing price path curvature through
  liquidity and structural lenses.

Physical basis:
  acceleration_t = ret_{t+1} - ret_t = log(c_{t+2}/c_{t+1}) - log(c_{t+1}/c_t)
  Measures how quickly the price *direction* is changing — path curvature.

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

NAME = "price_accel_full"

OUTPUT_NAMES = [
    # --- Liquidity-framed (2) ---
    "accel_illiq_full",           # mean(|accel| / avg_amount) — Amihud-like for curvature
    "high_vol_accel_illiq_full",  # same but only top-25% volume bars
    # --- Structural (1) ---
    "accel_regime_trans_full",    # fraction of sign changes in acceleration
    # --- Distributional (5) ---
    "abs_accel_mean_full",        # mean(|accel|) — path roughness
    "accel_std_full",             # std(accel) — curvature volatility
    "accel_vol_corr_full",        # corr(|accel|, volume)
    "accel_skew_full",            # skewness of acceleration
    "accel_kurtosis_full",        # excess kurtosis of acceleration
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

    # ---- compute log returns ----
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0 or c1 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = np.log(c1 / c0)

    # ---- compute acceleration = ret[i+1] - ret[i] ----
    n_acc = n_ret - 1
    accel = np.empty(n_acc, dtype=np.float64)
    valid_acc = 0
    for i in range(n_acc):
        r0 = rets[i]
        r1 = rets[i + 1]
        if np.isnan(r0) or np.isnan(r1):
            accel[i] = np.nan
        else:
            accel[i] = r1 - r0
            valid_acc += 1

    if valid_acc < 5:
        return out

    # ---- Feature 0: accel_illiq_full ----
    # mean(|accel_i| / avg_amount_i) where avg_amount_i = (amount[i+1]+amount[i+2])/2
    # accel[i] uses close[i], close[i+1], close[i+2]
    ai_sum = 0.0
    ai_cnt = 0
    for i in range(n_acc):
        a = accel[i]
        a1 = amount[i + 1]
        a2 = amount[i + 2] if (i + 2) < n else np.nan
        if np.isnan(a) or np.isnan(a1) or np.isnan(a2):
            continue
        avg_amt = (a1 + a2) * 0.5
        if avg_amt > 0.0:
            ai_sum += abs(a) / avg_amt
            ai_cnt += 1
    if ai_cnt > 0:
        out[0] = ai_sum / ai_cnt

    # ---- Feature 1: high_vol_accel_illiq_full ----
    # Same as above but only for bars where volume[i+2] is in top-25%
    # First find volume threshold (75th percentile)
    vol_vals = np.empty(n, dtype=np.float64)
    vol_cnt = 0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v):
            vol_vals[vol_cnt] = v
            vol_cnt += 1
    if vol_cnt >= 4:
        # Sort to find 75th percentile
        for ii in range(vol_cnt):
            for jj in range(ii + 1, vol_cnt):
                if vol_vals[jj] < vol_vals[ii]:
                    tmp = vol_vals[ii]
                    vol_vals[ii] = vol_vals[jj]
                    vol_vals[jj] = tmp
        p75_idx = int(vol_cnt * 0.75)
        if p75_idx >= vol_cnt:
            p75_idx = vol_cnt - 1
        vol_threshold = vol_vals[p75_idx]

        hv_sum = 0.0
        hv_cnt = 0
        for i in range(n_acc):
            a = accel[i]
            idx2 = i + 2
            if idx2 >= n:
                continue
            v2 = volume[idx2]
            a1 = amount[i + 1]
            a2 = amount[idx2]
            if np.isnan(a) or np.isnan(v2) or np.isnan(a1) or np.isnan(a2):
                continue
            if v2 >= vol_threshold:
                avg_amt = (a1 + a2) * 0.5
                if avg_amt > 0.0:
                    hv_sum += abs(a) / avg_amt
                    hv_cnt += 1
        if hv_cnt > 0:
            out[1] = hv_sum / hv_cnt

    # ---- Feature 2: accel_regime_trans_full ----
    # Fraction of sign changes in acceleration sequence
    sign_changes = 0
    sign_pairs = 0
    for i in range(n_acc - 1):
        a0 = accel[i]
        a1 = accel[i + 1]
        if np.isnan(a0) or np.isnan(a1):
            continue
        sign_pairs += 1
        if (a0 > 0.0 and a1 < 0.0) or (a0 < 0.0 and a1 > 0.0):
            sign_changes += 1
    if sign_pairs > 0:
        out[2] = float(sign_changes) / float(sign_pairs)

    # ---- Pre-compute acceleration statistics for features 3-7 ----
    acc_mean = 0.0
    acc_cnt = 0
    abs_sum = 0.0
    for i in range(n_acc):
        a = accel[i]
        if not np.isnan(a):
            acc_mean += a
            abs_sum += abs(a)
            acc_cnt += 1

    if acc_cnt < 3:
        return out

    acc_mean /= acc_cnt

    # ---- Feature 3: abs_accel_mean_full ----
    out[3] = abs_sum / acc_cnt

    # ---- Feature 4: accel_std_full ----
    ss = 0.0
    for i in range(n_acc):
        a = accel[i]
        if not np.isnan(a):
            ss += (a - acc_mean) ** 2
    out[4] = np.sqrt(ss / (acc_cnt - 1))

    # ---- Feature 5: accel_vol_corr_full ----
    # corr(|accel|, volume) — are large accelerations at high-volume bars?
    sx = 0.0
    sy = 0.0
    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    cv_cnt = 0
    for i in range(n_acc):
        a = accel[i]
        idx2 = i + 2
        if idx2 >= n:
            continue
        v = volume[idx2]
        if np.isnan(a) or np.isnan(v):
            continue
        x = abs(a)
        sx += x
        sy += v
        sxx += x * x
        syy += v * v
        sxy += x * v
        cv_cnt += 1
    if cv_cnt >= 2:
        denom = (cv_cnt * sxx - sx * sx) * (cv_cnt * syy - sy * sy)
        if denom > 0.0:
            out[5] = (cv_cnt * sxy - sx * sy) / np.sqrt(denom)

    # ---- Feature 6: accel_skew_full ----
    if acc_cnt >= 3:
        m2 = 0.0
        m3 = 0.0
        for i in range(n_acc):
            a = accel[i]
            if not np.isnan(a):
                d = a - acc_mean
                d2 = d * d
                m2 += d2
                m3 += d2 * d
        m2 /= acc_cnt
        m3 /= acc_cnt
        if m2 > 0.0:
            out[6] = m3 / (m2 * np.sqrt(m2))

    # ---- Feature 7: accel_kurtosis_full ----
    if acc_cnt >= 4:
        m2 = 0.0
        m4 = 0.0
        for i in range(n_acc):
            a = accel[i]
            if not np.isnan(a):
                d = a - acc_mean
                d2 = d * d
                m2 += d2
                m4 += d2 * d2
        m2 /= acc_cnt
        m4 /= acc_cnt
        if m2 > 0.0:
            out[7] = m4 / (m2 * m2) - 3.0

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
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Price acceleration (path curvature) bundle for full-day window. "
            "Emits 8 features: accel Amihud illiquidity (all + high-vol), "
            "acceleration regime transitions, path roughness (abs mean, std), "
            "acceleration-volume correlation, skewness, and excess kurtosis. "
            "Acceleration = ret[t+1] - ret[t], measuring price direction change rate."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the price acceleration full-day bundle"
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
