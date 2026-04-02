#!/usr/bin/env python3
"""Volume microstructure bundle for the full-day window.

Bundle: volume_microstructure_full
- Input: volume (from 1m bars, 09:30-11:30 + 13:00-14:57)
- Output: 5 variables measuring volume distribution quality as a liquidity proxy.

Hypothesis: Stocks with more concentrated/uneven intraday volume distribution
have worse microstructure quality and require a liquidity premium, leading to
higher expected returns. This is the volume-based complement to reversal_ratio
(price-based bid-ask bounce).

Uses full-day window (~237 bars) for stable estimation per conclusion #11.
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

NAME = "volume_microstructure_full"

OUTPUT_NAMES = [
    "volume_entropy_full",            # Normalized Shannon entropy of volume
    "volume_gini_full",               # Gini coefficient of volume distribution
    "high_vol_bar_ratio_full",        # Fraction of bars with vol > 2x median
    "volume_autocorr1_full",          # Lag-1 autocorrelation of volume
    "volume_dispersion_ratio_full",   # IQR / median (robust dispersion)
]

FORMULA = """@njit
def apply_func(inputs):
    volume = inputs[0]

    n = volume.size
    n_out = 5

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 20:
        return out

    # ---- Collect valid volume values ----
    valid_vols = np.empty(n, dtype=np.float64)
    valid_cnt = 0
    vol_total = 0.0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v) and v > 0.0:
            valid_vols[valid_cnt] = v
            vol_total += v
            valid_cnt += 1

    if valid_cnt < 20 or vol_total <= 0.0:
        return out

    # ---- 0: volume_entropy (normalized Shannon entropy) ----
    # H = -sum(p_i * ln(p_i)) / ln(N), range [0, 1]
    # High entropy = uniform volume = more liquid
    entropy = 0.0
    ln_n = np.log(float(valid_cnt))
    if ln_n > 0.0:
        for i in range(valid_cnt):
            p = valid_vols[i] / vol_total
            if p > 1e-15:
                entropy -= p * np.log(p)
        out[0] = entropy / ln_n

    # ---- Sort valid volumes for Gini, median, IQR ----
    sorted_vols = np.empty(valid_cnt, dtype=np.float64)
    for i in range(valid_cnt):
        sorted_vols[i] = valid_vols[i]
    sorted_vols = np.sort(sorted_vols)

    # ---- 1: volume_gini (Gini coefficient) ----
    # G = (2 * sum(i * x_i)) / (n * sum(x_i)) - (n + 1) / n
    weighted_sum = 0.0
    for i in range(valid_cnt):
        weighted_sum += float(i + 1) * sorted_vols[i]

    total_sum = 0.0
    for i in range(valid_cnt):
        total_sum += sorted_vols[i]

    if total_sum > 0.0 and valid_cnt > 1:
        gini = (2.0 * weighted_sum) / (float(valid_cnt) * total_sum) - (float(valid_cnt) + 1.0) / float(valid_cnt)
        out[1] = gini

    # ---- Compute median ----
    if valid_cnt % 2 == 0:
        median_vol = (sorted_vols[valid_cnt // 2 - 1] + sorted_vols[valid_cnt // 2]) / 2.0
    else:
        median_vol = sorted_vols[valid_cnt // 2]

    # ---- 2: high_vol_bar_ratio (fraction of bars with vol > 2 * median) ----
    threshold = 2.0 * median_vol
    high_cnt = 0
    for i in range(valid_cnt):
        if valid_vols[i] > threshold:
            high_cnt += 1
    out[2] = float(high_cnt) / float(valid_cnt)

    # ---- 3: volume_autocorr1 (lag-1 autocorrelation of volume) ----
    # Use original ordering (not sorted)
    # Pearson corr(vol[:-1], vol[1:])
    sx = 0.0
    sy = 0.0
    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    ac_cnt = 0
    for i in range(n - 1):
        v0 = volume[i]
        v1 = volume[i + 1]
        if np.isnan(v0) or np.isnan(v1) or v0 <= 0.0 or v1 <= 0.0:
            continue
        sx += v0
        sy += v1
        sxx += v0 * v0
        syy += v1 * v1
        sxy += v0 * v1
        ac_cnt += 1

    if ac_cnt >= 10:
        n_f = float(ac_cnt)
        denom = (n_f * sxx - sx * sx) * (n_f * syy - sy * sy)
        if denom > 0.0:
            out[3] = (n_f * sxy - sx * sy) / np.sqrt(denom)

    # ---- 4: volume_dispersion_ratio (IQR / median) ----
    # Q1 = sorted_vols[n/4], Q3 = sorted_vols[3n/4]
    if median_vol > 0.0 and valid_cnt >= 4:
        q1_idx = valid_cnt // 4
        q3_idx = (3 * valid_cnt) // 4
        iqr = sorted_vols[q3_idx] - sorted_vols[q1_idx]
        out[4] = iqr / median_vol

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["volume"],
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
            "Volume microstructure bundle for full-day window "
            "(09:30-11:30 + 13:00-14:57). 5 metrics measuring volume distribution "
            "quality as a liquidity proxy: Shannon entropy, Gini coefficient, "
            "high-volume bar ratio, lag-1 autocorrelation, and IQR/median dispersion. "
            "Hypothesis: illiquidity premium from concentrated/uneven volume distribution."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the volume microstructure full-day bundle"
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
    if args.register:
        from ashare_hf_variable.registry import upsert_definition
        upsert_definition(definition, validate=not args.skip_validate)
        print(f"registered: {definition.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
