#!/usr/bin/env python3
"""Cross-Bar Stability Patterns — full-day window (09:30-11:30 + 13:00-14:57).

D-024: 跨Bar稳定性模式
核心假设：
  路径粗糙度（mean|ΔX|/mean(X)）已在两个维度验证有效：
  - vol_roughness (volume): LS=1.42, LE=0.85, IR=0.53, Mono=0.71
  - amihud_diff_mean (Amihud): LS=1.24, LE=1.21, Mono=0.71

  本方向测试粗糙度范式在新维度上的泛化性：
  1. Amount roughness — 成交额稳定性。amount=price×volume，捕捉价格和交易量
     的联合不稳定性。结论#20指出amount不适合做transition(离散)，
     但roughness是连续水平量。
  2. Range roughness — bar range(H-L)的稳定性。衡量"波动率的波动率"。
     风险：可能退化为波动率代理。
  3. Body roughness — bar body(|C-O|)的稳定性。衡量方向性承诺强度的稳定性。

  额外测试：
  4. Joint reversal+vol regime change — 复合离散事件频率。
     reversal_ratio和vol_regime_transitions各自有效，测试它们的交集事件。
  5. Rogers-Satchell Amihud — 使用OHLC全信息的高效波动率估计量 / mean(amount)。
     与标准Amihud（|ret|/amount）不同：RS衡量bar内方差，ret衡量bar间变化。

Features:
  amount_roughness_full     — mean(|Δamount|) / mean(amount)
  range_roughness_full      — mean(|Δ(H-L)|) / mean(H-L)
  body_roughness_full       — mean(|Δ|C-O||) / mean(|C-O|)
  joint_reversal_vol_full   — 价格反转且成交量regime变化的bar占比
  rs_amihud_full            — mean(Rogers-Satchell bar vol) / mean(amount)
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

NAME = "cross_bar_stability_full"

OUTPUT_NAMES = [
    "amount_roughness_full",
    "range_roughness_full",
    "body_roughness_full",
    "joint_reversal_vol_full",
    "rs_amihud_full",
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

    # ---- Pre-compute returns for reversal detection ----
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    valid_ret = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = c1 / c0 - 1.0
            valid_ret += 1

    # ---- Compute volume median for regime detection ----
    vol_buf = np.empty(n, dtype=np.float64)
    vol_cnt = 0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v) and v > 0.0:
            vol_buf[vol_cnt] = v
            vol_cnt += 1
    if vol_cnt < 20:
        return out
    vol_sorted = np.sort(vol_buf[:vol_cnt])
    vol_median = vol_sorted[vol_cnt // 2]

    # ==== Feature 0: amount_roughness_full ====
    # mean(|amount[i] - amount[i-1]|) / mean(amount)
    # Economic meaning: unstable trading amount → unpredictable execution cost → premium
    amt_diff_sum = 0.0
    amt_diff_cnt = 0
    amt_sum = 0.0
    amt_cnt = 0
    for i in range(n):
        a = amount[i]
        if np.isnan(a) or a <= 0.0:
            continue
        amt_sum += a
        amt_cnt += 1
        if i > 0:
            a_prev = amount[i - 1]
            if not np.isnan(a_prev) and a_prev > 0.0:
                amt_diff_sum += abs(a - a_prev)
                amt_diff_cnt += 1
    if amt_cnt > 20 and amt_diff_cnt > 20 and amt_sum > 0.0:
        out[0] = (amt_diff_sum / amt_diff_cnt) / (amt_sum / amt_cnt)

    # ==== Feature 1: range_roughness_full ====
    # mean(|range[i] - range[i-1]|) / mean(range) where range = high - low
    # Measures "vol-of-vol" at 1min scale: how erratic is bar-level volatility
    rng_diff_sum = 0.0
    rng_diff_cnt = 0
    rng_sum = 0.0
    rng_cnt = 0
    for i in range(n):
        h = high[i]
        l = low[i]
        if np.isnan(h) or np.isnan(l):
            continue
        rng_i = h - l
        if rng_i < 0.0:
            continue
        rng_sum += rng_i
        rng_cnt += 1
        if i > 0:
            h_prev = high[i - 1]
            l_prev = low[i - 1]
            if not np.isnan(h_prev) and not np.isnan(l_prev):
                rng_prev = h_prev - l_prev
                if rng_prev >= 0.0:
                    rng_diff_sum += abs(rng_i - rng_prev)
                    rng_diff_cnt += 1
    if rng_cnt > 20 and rng_diff_cnt > 20 and rng_sum > 0.0:
        out[1] = (rng_diff_sum / rng_diff_cnt) / (rng_sum / rng_cnt)

    # ==== Feature 2: body_roughness_full ====
    # mean(||C-O|[i] - |C-O|[i-1]|) / mean(|C-O|)
    # Bar body = directional commitment. Roughness = how erratic this commitment is.
    body_diff_sum = 0.0
    body_diff_cnt = 0
    body_sum = 0.0
    body_cnt = 0
    for i in range(n):
        c = close[i]
        o = opn[i]
        if np.isnan(c) or np.isnan(o):
            continue
        body_i = abs(c - o)
        body_sum += body_i
        body_cnt += 1
        if i > 0:
            c_prev = close[i - 1]
            o_prev = opn[i - 1]
            if not np.isnan(c_prev) and not np.isnan(o_prev):
                body_prev = abs(c_prev - o_prev)
                body_diff_sum += abs(body_i - body_prev)
                body_diff_cnt += 1
    if body_cnt > 20 and body_diff_cnt > 20 and body_sum > 0.0:
        out[2] = (body_diff_sum / body_diff_cnt) / (body_sum / body_cnt)

    # ==== Feature 3: joint_reversal_vol_full ====
    # Fraction of bar transitions where BOTH:
    #   (a) return sign changes (price reversal)
    #   (b) volume crosses median (volume regime change)
    # Tests if compound discrete events add signal beyond individual frequencies
    joint_count = 0
    total_pairs = 0
    for i in range(1, n_ret):
        r_curr = rets[i]
        r_prev = rets[i - 1]
        v_curr = volume[i + 1]
        v_prev = volume[i]
        if np.isnan(r_curr) or np.isnan(r_prev):
            continue
        if np.isnan(v_curr) or np.isnan(v_prev):
            continue
        if v_curr <= 0.0 or v_prev <= 0.0:
            continue
        total_pairs += 1
        sign_change = (r_curr > 0.0 and r_prev < 0.0) or (r_curr < 0.0 and r_prev > 0.0)
        vol_regime_change = (
            (v_curr > vol_median and v_prev <= vol_median)
            or (v_curr <= vol_median and v_prev > vol_median)
        )
        if sign_change and vol_regime_change:
            joint_count += 1
    if total_pairs > 20:
        out[3] = joint_count / total_pairs

    # ==== Feature 4: rs_amihud_full ====
    # Rogers-Satchell volatility per bar: h*(h-c) + l*(l-c)
    #   where h=ln(H/O), l=ln(L/O), c=ln(C/O)
    # Then RS_amihud = mean(RS_bar) / mean(amount)
    # Unlike standard Amihud (inter-bar |ret|/amount), this uses INTRA-bar OHLC
    # to measure variance per unit of trading - a more efficient estimator.
    rs_sum = 0.0
    rs_cnt = 0
    for i in range(n):
        h = high[i]
        l = low[i]
        c = close[i]
        o = opn[i]
        if np.isnan(h) or np.isnan(l) or np.isnan(c) or np.isnan(o):
            continue
        if o <= 0.0 or h <= 0.0 or l <= 0.0 or c <= 0.0:
            continue
        if h < l:
            continue
        h_log = np.log(h / o)
        l_log = np.log(l / o)
        c_log = np.log(c / o)
        rs_bar = h_log * (h_log - c_log) + l_log * (l_log - c_log)
        if not np.isnan(rs_bar) and rs_bar >= 0.0:
            rs_sum += rs_bar
            rs_cnt += 1
    if rs_cnt > 20 and amt_cnt > 0 and amt_sum > 0.0:
        out[4] = (rs_sum / rs_cnt) / (amt_sum / amt_cnt)

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
            "Cross-bar stability patterns for full-day window. "
            "5 features testing roughness/stability patterns on new dimensions: "
            "amount roughness (trading cost instability), "
            "range roughness (bar-level vol-of-vol), "
            "body roughness (directional commitment instability), "
            "joint reversal+volume regime compound event frequency, "
            "Rogers-Satchell Amihud (OHLC-efficient intra-bar variance per unit amount). "
            "Hypothesis: roughness pattern generalizes beyond volume and Amihud dimensions."
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cross-bar stability patterns")
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()

    defn = build_definition()
    if args.register:
        from ashare_hf_variable.registry import upsert_definition
        upsert_definition(defn)
        print(f"Registered {NAME}")
    else:
        print(json.dumps(defn.to_dict(), indent=2, ensure_ascii=False))
