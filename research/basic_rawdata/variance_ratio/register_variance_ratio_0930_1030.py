#!/usr/bin/env python3
"""Register the variance-ratio bundle for the 09:30-10:30 window.

Bundle: variance_ratio_0930_1030
- Input: close (from 1m bars)
- Output: 5 variables capturing return autocorrelation structure
  (variance ratios, AR(1), absolute-return AR(1))

Physical rationale:
  VR(q) = Var(q-bar return) / (q * Var(1-bar return))
  VR=1 → random walk; VR<1 → mean reversion; VR>1 → momentum/persistence
  In A-share market, low VR stocks exhibit retail-driven overreaction,
  high VR stocks exhibit informed order flow persistence.
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

NAME = "variance_ratio_0930_1030"

OUTPUT_NAMES = [
    "vr_2_0930_1030",               # Variance Ratio at q=2
    "vr_5_0930_1030",               # Variance Ratio at q=5
    "ar1_0930_1030",                # First-order return autocorrelation
    "abs_ar1_0930_1030",            # First-order |return| autocorrelation (vol clustering)
    "vr_ratio_5_2_0930_1030",       # VR(5)/VR(2), cross-scale autocorrelation change
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]

    n = close.size
    n_out = 5
    out = np.full(n_out, np.nan, dtype=np.float64)

    if n < 15:
        return out

    # ---- compute log returns ----
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    valid_count = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = np.log(c1 / c0)
            valid_count += 1

    if valid_count < 10:
        return out

    # ---- 1-bar variance ----
    ret_sum = 0.0
    ret_cnt = 0
    for i in range(n_ret):
        if not np.isnan(rets[i]):
            ret_sum += rets[i]
            ret_cnt += 1

    if ret_cnt < 5:
        return out

    ret_mean = ret_sum / ret_cnt
    var1 = 0.0
    for i in range(n_ret):
        if not np.isnan(rets[i]):
            var1 += (rets[i] - ret_mean) ** 2
    var1 /= (ret_cnt - 1)

    if var1 <= 1e-20:
        return out

    # ---- VR(q) using overlapping returns ----
    # VR(q) = Var(q-bar overlapping return) / (q * Var(1-bar return))
    # With bias correction for overlapping returns (Lo-MacKinlay 1988)
    vr_vals = np.full(2, np.nan, dtype=np.float64)  # for q=2, q=5

    for q_idx in range(2):
        q = 2 if q_idx == 0 else 5
        if n_ret < q + 1:
            continue

        # Compute overlapping q-bar returns
        q_sum = 0.0
        q_cnt = 0
        for i in range(n_ret - q + 1):
            total = 0.0
            valid = True
            for j in range(q):
                if np.isnan(rets[i + j]):
                    valid = False
                    break
                total += rets[i + j]
            if valid:
                q_sum += total
                q_cnt += 1

        if q_cnt < 3:
            continue

        q_mean = q_sum / q_cnt
        var_q = 0.0
        for i in range(n_ret - q + 1):
            total = 0.0
            valid = True
            for j in range(q):
                if np.isnan(rets[i + j]):
                    valid = False
                    break
                total += rets[i + j]
            if valid:
                var_q += (total - q_mean) ** 2
        var_q /= (q_cnt - 1)

        vr = var_q / (q * var1)
        vr_vals[q_idx] = vr

    # out[0] = VR(2)
    out[0] = vr_vals[0]
    # out[1] = VR(5)
    out[1] = vr_vals[1]

    # ---- 2: AR(1) coefficient ----
    # AR(1) = Cov(r_t, r_{t-1}) / Var(r_{t-1})
    # Using demeaned returns for proper estimation
    ar_num = 0.0
    ar_den = 0.0
    ar_cnt = 0
    for i in range(1, n_ret):
        if not np.isnan(rets[i]) and not np.isnan(rets[i - 1]):
            r_curr = rets[i] - ret_mean
            r_prev = rets[i - 1] - ret_mean
            ar_num += r_curr * r_prev
            ar_den += r_prev * r_prev
            ar_cnt += 1
    if ar_cnt >= 5 and ar_den > 1e-20:
        out[2] = ar_num / ar_den

    # ---- 3: abs_AR(1) = autocorrelation of |returns| ----
    # Captures volatility clustering
    abs_sum = 0.0
    abs_cnt = 0
    for i in range(n_ret):
        if not np.isnan(rets[i]):
            abs_sum += abs(rets[i])
            abs_cnt += 1
    if abs_cnt < 5:
        return out
    abs_mean = abs_sum / abs_cnt

    abs_ar_num = 0.0
    abs_ar_den = 0.0
    abs_ar_cnt = 0
    for i in range(1, n_ret):
        if not np.isnan(rets[i]) and not np.isnan(rets[i - 1]):
            a_curr = abs(rets[i]) - abs_mean
            a_prev = abs(rets[i - 1]) - abs_mean
            abs_ar_num += a_curr * a_prev
            abs_ar_den += a_prev * a_prev
            abs_ar_cnt += 1
    if abs_ar_cnt >= 5 and abs_ar_den > 1e-20:
        out[3] = abs_ar_num / abs_ar_den

    # ---- 4: VR(5)/VR(2) - cross-scale autocorrelation ratio ----
    if not np.isnan(out[0]) and not np.isnan(out[1]) and out[0] > 1e-10:
        out[4] = out[1] / out[0]

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "10:30")]),
        slot=RawDataSlot.MIDDAY,
        data_available_at=1031,
        execution_start_at=930,
        execution_end_at=1030,
        expected_bars=40,
        description=(
            "Variance ratio bundle for 09:30-10:30 window. "
            "Emits 5 variables: VR(2), VR(5), AR(1), absolute-return AR(1), "
            "and VR(5)/VR(2) cross-scale ratio. Measures return predictability "
            "and autocorrelation structure at different time scales."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the variance-ratio 09:30-10:30 bundle"
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
