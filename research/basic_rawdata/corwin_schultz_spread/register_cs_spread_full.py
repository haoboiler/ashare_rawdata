#!/usr/bin/env python3
"""Register the Corwin-Schultz spread bundle for the full-day window.

Bundle: cs_spread_0930_1130_1300_1457
- Input: high, low, close (from 1m bars)
- Output: 5 variables capturing bid-ask spread and related liquidity measures.

Full-day version of cs_spread_0930_1030.py. Uses 237 bars vs 60 bars
for more stable spread estimates. Excludes closing auction (14:57-15:00).

Physical hypothesis: Corwin-Schultz (2012, JF) decomposition of high-low range
into a bid-ask spread component and a volatility component. Stocks with lower
effective spreads (higher liquidity) tend to have better future returns due to
the liquidity premium.
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

NAME = "cs_spread_0930_1130_1300_1457"

OUTPUT_NAMES = [
    # --- Core CS decomposition (2) ---
    "cs_spread_full",              # Corwin-Schultz bid-ask spread estimate
    "cs_sigma_full",               # CS volatility component (sqrt of sigma^2)
    # --- Relative measures (2) ---
    "cs_relative_spread_full",     # spread / mean(close) — size-normalized
    "cs_spread_to_vol_full",       # spread / sigma — spread importance vs vol
    # --- Distribution (1) ---
    "cs_spread_trend_full",        # corr(bar_index, pair_spread) — spread trend
]

FORMULA = """@njit
def apply_func(inputs):
    high = inputs[0]
    low = inputs[1]
    close = inputs[2]

    n = high.size
    n_out = 5

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 4:
        return out

    # --- Compute bar-pair beta and gamma values ---
    n_pairs = n - 1
    pair_betas = np.empty(n_pairs, dtype=np.float64)
    pair_gammas = np.empty(n_pairs, dtype=np.float64)
    pair_spreads = np.empty(n_pairs, dtype=np.float64)
    valid_pairs = 0

    for j in range(n_pairs):
        h0 = high[j]
        l0 = low[j]
        h1 = high[j + 1]
        l1 = low[j + 1]

        if (np.isnan(h0) or np.isnan(l0) or np.isnan(h1) or np.isnan(l1)
                or l0 <= 0.0 or l1 <= 0.0 or h0 <= 0.0 or h1 <= 0.0):
            pair_betas[j] = np.nan
            pair_gammas[j] = np.nan
            pair_spreads[j] = np.nan
            continue

        lr0 = np.log(h0 / l0)
        lr1 = np.log(h1 / l1)
        beta_j = lr0 * lr0 + lr1 * lr1

        h2 = h0 if h0 > h1 else h1
        l2 = l0 if l0 < l1 else l1
        lr2 = np.log(h2 / l2)
        gamma_j = lr2 * lr2

        pair_betas[j] = beta_j
        pair_gammas[j] = gamma_j

        denom = 3.0 - 2.0 * 1.4142135623730951
        sqrt_2b = np.sqrt(2.0 * beta_j)
        sqrt_b = np.sqrt(beta_j)
        alpha_j = (sqrt_2b - sqrt_b) / denom - np.sqrt(gamma_j / denom) if gamma_j / denom >= 0.0 else np.nan
        pair_spreads[j] = alpha_j
        valid_pairs += 1

    if valid_pairs < 5:
        return out

    # --- Average beta and gamma ---
    beta_sum = 0.0
    gamma_sum = 0.0
    cnt = 0
    for j in range(n_pairs):
        if not np.isnan(pair_betas[j]):
            beta_sum += pair_betas[j]
            gamma_sum += pair_gammas[j]
            cnt += 1
    if cnt == 0:
        return out

    beta_bar = beta_sum / cnt
    gamma_bar = gamma_sum / cnt

    # --- CS decomposition ---
    denom = 3.0 - 2.0 * 1.4142135623730951
    sqrt_2beta = np.sqrt(2.0 * beta_bar)
    sqrt_beta = np.sqrt(beta_bar)

    sigma_sq = (sqrt_2beta - sqrt_beta) / denom
    if sigma_sq < 0.0:
        sigma_sq = 0.0

    gamma_term = gamma_bar / denom
    if gamma_term < 0.0:
        gamma_term = 0.0
    alpha = sigma_sq - np.sqrt(gamma_term)

    # 0: cs_spread
    if alpha >= 0.0:
        ea = np.exp(alpha)
        out[0] = 2.0 * (ea - 1.0) / (1.0 + ea)
    else:
        out[0] = 0.0

    # 1: cs_sigma
    out[1] = np.sqrt(sigma_sq)

    # 2: cs_relative_spread = spread / mean(close)
    close_sum = 0.0
    close_cnt = 0
    for i in range(n):
        c = close[i]
        if not np.isnan(c) and c > 0.0:
            close_sum += c
            close_cnt += 1
    if close_cnt > 0 and close_sum > 0.0:
        mean_close = close_sum / close_cnt
        out[2] = out[0] / mean_close

    # 3: cs_spread_to_vol = spread / sigma
    if out[1] > 1e-12:
        out[3] = out[0] / out[1]

    # 4: cs_spread_trend = corr(pair_index, pair_alpha)
    sx = 0.0
    sy = 0.0
    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    trend_cnt = 0
    for j in range(n_pairs):
        y = pair_spreads[j]
        if np.isnan(y):
            continue
        x = float(j)
        sx += x
        sy += y
        sxx += x * x
        syy += y * y
        sxy += x * y
        trend_cnt += 1
    if trend_cnt >= 5:
        d = (trend_cnt * sxx - sx * sx) * (trend_cnt * syy - sy * sy)
        if d > 0.0:
            out[4] = (trend_cnt * sxy - sx * sy) / np.sqrt(d)

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["high", "low", "close"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]),
        slot=RawDataSlot.EVENING,
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Corwin-Schultz spread decomposition for full trading day "
            "(09:30-11:30 + 13:00-14:57, excluding closing auction). "
            "Emits 5 variables: CS spread, volatility, relative spread, "
            "spread-to-vol ratio, and spread trend. "
            "237 bars for more stable estimates vs 60 in the 0930-1030 version."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the Corwin-Schultz spread full-day bundle"
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
