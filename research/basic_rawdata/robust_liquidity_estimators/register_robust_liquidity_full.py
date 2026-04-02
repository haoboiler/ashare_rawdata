#!/usr/bin/env python3
"""Robust Liquidity Estimators — full-day window (09:30-11:30 + 13:00-14:57).

D-026: Amihud 函数变体
核心假设：
  所有现有 Amihud 变体（45 个 pending）均使用算术均值 mean(|r_i|/amount_i) 作为
  聚合函数。算术均值对极端价格冲击 bar 敏感——一个异常大单就能拉高整日 Amihud。

  不同的聚合函数对分布尾部有不同敏感度，可能产生不同的截面排序：
  - sqrt: Kyle (1985) 价格冲击 ∝ sqrt(order_flow)，凹函数压缩极端冲击
  - log: 对数压缩，有界，对极端值最不敏感
  - harmonic: 由最小值主导（最流动时刻），衡量"最优执行潜力"
  - median: 排除全部异常值，只看分布中心
  - trimmed mean: 排除两端各 10%，折中方案

  如果标准 Amihud（算术均值）的截面排序被少数极端 bar 扭曲，
  稳健估计器可能提供更干净的流动性溢价信号。

Features:
  sqrt_impact_amihud_full   — mean(|r_i|^0.5 / amount_i^0.5)
  log_impact_amihud_full    — mean(log(1 + |r_i| * 1e8 / amount_i))
  harmonic_amihud_full      — n / sum(amount_i / |r_i|)  [skip r_i=0 bars]
  median_amihud_full        — median(|r_i| / amount_i)   [skip r_i=0 bars]
  trimmed_amihud_full       — trimmed_mean_10(|r_i| / amount_i)
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

NAME = "robust_liquidity_full"

OUTPUT_NAMES = [
    "sqrt_impact_amihud_full",
    "log_impact_amihud_full",
    "harmonic_amihud_full",
    "median_amihud_full",
    "trimmed_amihud_full",
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
    if n < 30:
        return out

    # ---- Pre-compute per-bar |return| and amount ----
    # Use close-to-close returns for bars 1..n-1
    n_ret = n - 1
    abs_ret = np.empty(n_ret, dtype=np.float64)
    bar_amt = np.empty(n_ret, dtype=np.float64)

    valid_cnt = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        a1 = amount[i + 1]
        if np.isnan(c0) or np.isnan(c1) or np.isnan(a1):
            abs_ret[i] = np.nan
            bar_amt[i] = np.nan
            continue
        if c0 <= 0.0 or a1 <= 0.0:
            abs_ret[i] = np.nan
            bar_amt[i] = np.nan
            continue
        abs_ret[i] = abs(c1 / c0 - 1.0)
        bar_amt[i] = a1
        valid_cnt += 1

    if valid_cnt < 30:
        return out

    # ---- Compute per-bar Amihud for quantile-based features ----
    # Also collect sqrt/log/harmonic accumulators in one pass
    amihud_buf = np.empty(valid_cnt, dtype=np.float64)
    sqrt_sum = 0.0
    log_sum = 0.0
    harmonic_sum = 0.0   # sum(amount_i / |r_i|) for harmonic mean
    harmonic_cnt = 0
    buf_idx = 0

    SCALE_LOG = 1e8  # scale factor to make log argument meaningful

    for i in range(n_ret):
        ar = abs_ret[i]
        am = bar_amt[i]
        if np.isnan(ar) or np.isnan(am):
            continue

        # Per-bar Amihud
        amihud_i = ar / am
        amihud_buf[buf_idx] = amihud_i
        buf_idx += 1

        # Feature 0: sqrt impact — |r|^0.5 / amount^0.5
        sqrt_sum += np.sqrt(ar) / np.sqrt(am)

        # Feature 1: log impact — log(1 + K * |r| / amount)
        log_sum += np.log(1.0 + SCALE_LOG * amihud_i)

        # Feature 2: harmonic mean — need |r| > 0 to avoid division
        if ar > 1e-12:
            harmonic_sum += am / ar
            harmonic_cnt += 1

    if buf_idx < 30:
        return out

    # ==== Feature 0: sqrt_impact_amihud_full ====
    # mean(|r_i|^0.5 / amount_i^0.5)
    # Kyle (1985) square-root price impact model: dampens extreme impacts
    out[0] = sqrt_sum / buf_idx

    # ==== Feature 1: log_impact_amihud_full ====
    # mean(log(1 + K * |r_i| / amount_i))
    # Log compression: bounded, extreme-insensitive
    out[1] = log_sum / buf_idx

    # ==== Feature 2: harmonic_amihud_full ====
    # harmonic mean = n / sum(amount_i / |r_i|) for |r_i| > 0
    # Dominated by smallest values (most liquid moments)
    if harmonic_cnt > 20 and harmonic_sum > 0.0:
        out[2] = harmonic_cnt / harmonic_sum

    # ==== Feature 3: median_amihud_full ====
    # Median of per-bar |r_i| / amount_i
    # Robust central tendency, ignores all outliers
    sorted_amihud = np.sort(amihud_buf[:buf_idx])
    mid = buf_idx // 2
    if buf_idx % 2 == 0:
        out[3] = (sorted_amihud[mid - 1] + sorted_amihud[mid]) / 2.0
    else:
        out[3] = sorted_amihud[mid]

    # ==== Feature 4: trimmed_amihud_full ====
    # Trimmed mean: exclude bottom 10% and top 10% of per-bar Amihud
    # Compromise between mean (sensitive) and median (ignores shape)
    trim_n = int(buf_idx * 0.1)
    if trim_n < 1:
        trim_n = 1
    trim_start = trim_n
    trim_end = buf_idx - trim_n
    if trim_end > trim_start:
        trim_sum = 0.0
        for j in range(trim_start, trim_end):
            trim_sum += sorted_amihud[j]
        out[4] = trim_sum / (trim_end - trim_start)

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
            "Robust liquidity estimators for full-day window. "
            "5 features testing different aggregation functions for Amihud price impact: "
            "sqrt (Kyle square-root impact, dampens extremes), "
            "log (log-compressed impact, bounded), "
            "harmonic mean (dominated by most liquid moments), "
            "median (robust central tendency), "
            "trimmed mean (excludes top/bottom 10%). "
            "Hypothesis: arithmetic mean Amihud is dominated by extreme-impact bars; "
            "robust/nonlinear estimators may produce different cross-sectional rankings."
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Robust liquidity estimators")
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()

    defn = build_definition()
    if args.register:
        from ashare_hf_variable.registry import upsert_definition
        upsert_definition(defn)
        print(f"Registered {NAME}")
    else:
        print(json.dumps(defn.to_dict(), indent=2, ensure_ascii=False))
