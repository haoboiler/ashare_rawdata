#!/usr/bin/env python3
"""Register the noise-liquidity interaction bundle for the full-day window.

Bundle: noise_interaction_0930_1130_1300_1457
- Input: close, open, high, low, volume, amount (from 1m bars)
- Output: 6 variables capturing interactions between microstructure noise
  and liquidity metrics.

Physical hypothesis:
1. noise_amihud_product: noise_ratio × amihud_illiq — captures the
   "noise cost component" of Amihud. High noise ratio + high Amihud =
   worst case (noisy AND illiquid). This interaction might have
   stronger LS Sharpe than noise_amihud alone.
2. bar_pair_noise_amihud: mean(|r_i * r_{i+1}| / avg_amount_{i,i+1})
   — per-pair normalized noise, analogous to how standard Amihud
   normalizes per bar rather than in aggregate.
3. neg_autocov_amihud: -sum(r_i*r_{i+1}) / mean(amount) — SIGNED
   autocovariance (positive = more bounce = less liquid). Without
   absolute value, preserves the mean-reversion signal.
4. noise_depth: noise variance / mean(amount)^2 — noise per unit of
   trading depth squared, different scaling from noise_amihud.
5. excess_bounce_amihud: mean(|r_i|*(r_i*r_{i+1}<0)) / mean(amount) —
   Amihud computed only on bounce bars (where next bar reverses).
   This is reversal_amihud from the NOISE perspective.
6. high_vol_autocov_amihud: bar-pair autocovariance/amount on high-volume pairs.
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

NAME = "noise_interaction_0930_1130_1300_1457"

OUTPUT_NAMES = [
    "noise_amihud_product_full",       # noise_ratio_5 * amihud_illiq (interaction)
    "bar_pair_noise_amihud_full",      # mean(|r_i*r_{i+1}| / avg_amount) * 1e18
    "neg_autocov_amihud_full",         # -sum(r_i*r_{i+1}) / mean(amount) * 1e9 (signed)
    "noise_depth_full",                # (RV_1min - RV_5min) / mean(amount)^2 * 1e18
    "excess_bounce_amihud_full",       # mean(|r_i| on bounce bars) / mean(amount) * 1e9
    "high_vol_autocov_amihud_full",    # autocov/amount on high-vol pairs
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    open_ = inputs[1]
    high = inputs[2]
    low = inputs[3]
    volume = inputs[4]
    amount = inputs[5]

    n = close.size
    n_out = 6

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 20:
        return out

    # --- Pre-compute returns ---
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    valid_ret_count = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0 or c1 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = c1 / c0 - 1.0
            valid_ret_count += 1

    if valid_ret_count < 20:
        return out

    # --- Compute mean(amount) ---
    amt_sum = 0.0
    amt_cnt = 0
    for i in range(n):
        if not np.isnan(amount[i]) and amount[i] > 0.0:
            amt_sum += amount[i]
            amt_cnt += 1
    if amt_cnt == 0:
        return out
    mean_amt = amt_sum / amt_cnt

    # --- Compute volume median ---
    valid_vols = np.empty(n, dtype=np.float64)
    vol_cnt = 0
    for i in range(n):
        if not np.isnan(volume[i]) and volume[i] > 0.0:
            valid_vols[vol_cnt] = volume[i]
            vol_cnt += 1
    vol_median = 0.0
    if vol_cnt > 0:
        sorted_vols = valid_vols[:vol_cnt].copy()
        sorted_vols.sort()
        if vol_cnt % 2 == 0:
            vol_median = (sorted_vols[vol_cnt // 2 - 1] + sorted_vols[vol_cnt // 2]) / 2.0
        else:
            vol_median = sorted_vols[vol_cnt // 2]

    # --- Compute RV_1min ---
    rv_1min = 0.0
    for i in range(n_ret):
        if not np.isnan(rets[i]):
            rv_1min += rets[i] * rets[i]

    # --- Compute standard Amihud for interaction ---
    amihud_sum = 0.0
    amihud_cnt = 0
    for i in range(n_ret):
        if not np.isnan(rets[i]) and not np.isnan(amount[i + 1]) and amount[i + 1] > 0.0:
            amihud_sum += abs(rets[i]) / amount[i + 1]
            amihud_cnt += 1
    amihud_val = 0.0
    if amihud_cnt > 0:
        amihud_val = amihud_sum / amihud_cnt * 1e9

    # --- Compute RV_5min for noise_ratio ---
    block_size = 5
    n_blocks = n_ret // block_size
    rv_5min = 0.0
    rv_5min_cnt = 0
    for b in range(n_blocks):
        start = b * block_size
        block_ret = 0.0
        block_valid = True
        for j in range(start, start + block_size):
            if j >= n_ret or np.isnan(rets[j]):
                block_valid = False
                break
            block_ret += rets[j]
        if block_valid:
            rv_5min += block_ret * block_ret
            rv_5min_cnt += 1

    noise_ratio_5 = np.nan
    if rv_1min > 0.0 and rv_5min_cnt > 4:
        noise_ratio_5 = 1.0 - rv_5min / rv_1min

    # === Feature 0: noise_amihud_product_full ===
    # noise_ratio_5 * amihud_illiq — interaction term
    if not np.isnan(noise_ratio_5) and amihud_val > 0.0:
        out[0] = noise_ratio_5 * amihud_val

    # === Feature 1: bar_pair_noise_amihud_full ===
    # Per-pair: |r_i * r_{i+1}| / avg(amount_i, amount_{i+1})
    pair_sum = 0.0
    pair_cnt = 0
    for i in range(n_ret - 1):
        if (not np.isnan(rets[i]) and not np.isnan(rets[i + 1]) and
                not np.isnan(amount[i + 1]) and not np.isnan(amount[i + 2]) and
                amount[i + 1] > 0.0 and amount[i + 2] > 0.0):
            avg_amt = (amount[i + 1] + amount[i + 2]) / 2.0
            pair_sum += abs(rets[i] * rets[i + 1]) / avg_amt
            pair_cnt += 1
    if pair_cnt > 10:
        out[1] = pair_sum / pair_cnt * 1e18

    # === Feature 2: neg_autocov_amihud_full ===
    # Signed: -sum(r_i * r_{i+1}) / mean(amount) * 1e9
    # Positive = more bounce = more noise = less liquid
    autocov_sum = 0.0
    autocov_cnt = 0
    for i in range(n_ret - 1):
        if not np.isnan(rets[i]) and not np.isnan(rets[i + 1]):
            autocov_sum += rets[i] * rets[i + 1]
            autocov_cnt += 1
    if autocov_cnt > 5:
        out[2] = -autocov_sum / (autocov_cnt * mean_amt) * 1e9

    # === Feature 3: noise_depth_full ===
    # (RV_1min - RV_5min) / mean(amount)^2 * 1e18
    if rv_1min > 0.0 and rv_5min_cnt > 4:
        noise_var = rv_1min - rv_5min
        out[3] = noise_var / (mean_amt * mean_amt) * 1e18

    # === Feature 4: excess_bounce_amihud_full ===
    # Amihud computed only on bars where the NEXT bar reverses direction
    bounce_sum = 0.0
    bounce_cnt = 0
    for i in range(n_ret - 1):
        if (not np.isnan(rets[i]) and not np.isnan(rets[i + 1]) and
                not np.isnan(amount[i + 1]) and amount[i + 1] > 0.0):
            # Check if direction reverses
            if rets[i] * rets[i + 1] < 0.0:
                bounce_sum += abs(rets[i]) / amount[i + 1]
                bounce_cnt += 1
    if bounce_cnt > 10:
        out[4] = bounce_sum / bounce_cnt * 1e9

    # === Feature 5: high_vol_autocov_amihud_full ===
    # autocov/amount on pairs where BOTH bars have volume > median
    if vol_median > 0.0:
        hv_autocov_sum = 0.0
        hv_autocov_cnt = 0
        for i in range(n_ret - 1):
            if (not np.isnan(rets[i]) and not np.isnan(rets[i + 1]) and
                    not np.isnan(volume[i]) and not np.isnan(volume[i + 1]) and
                    volume[i] > vol_median and volume[i + 1] > vol_median):
                hv_autocov_sum += rets[i] * rets[i + 1]
                hv_autocov_cnt += 1
        if hv_autocov_cnt > 5:
            out[5] = abs(hv_autocov_sum) / (hv_autocov_cnt * mean_amt) * 1e9

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "open", "high", "low", "volume", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]),
        slot=RawDataSlot.EVENING,
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Noise-liquidity interaction factors for full trading day. "
            "Combines microstructure noise metrics with Amihud framework "
            "through interaction terms, per-pair normalization, and "
            "conditional computation on bounce/high-volume bars."
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()

    defn = build_definition()
    if args.register:
        from ashare_hf_variable.registry import upsert_definition

        upsert_definition(defn)
        print(f"[OK] Registered {NAME}")
    else:
        print(json.dumps(defn.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
