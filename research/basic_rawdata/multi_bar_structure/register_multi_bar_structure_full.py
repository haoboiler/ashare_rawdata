#!/usr/bin/env python3
"""Multi-Bar Price Structure — full-day window (09:30-11:30 + 13:00-14:57).

D-023: 多Bar价格结构
核心假设：
  - 相邻 bar 的价格范围包含关系（inside bar = 盘整压缩, engulfing = 范围扩张）
    是离散化的微结构事件。离散计数范式已被验证有效（reversal_ratio, vol_regime_transitions）。
  - inside_bar_freq 衡量"价格约束强度"：高频 inside bar = 订单簿有效约束
    价格波动，流动性质量好。这不是简单的波动率代理——它测量 bar 间的
    RELATIVE range 包含关系，而非绝对 range 大小。
  - inside bar 作为 Amihud 事件选择器：盘整期的价格冲击成本（inside_bar_amihud）
    衡量"安静市场条件下的流动性质量"。
  - engulfing bar（范围扩张事件）作为互补视角：衡量价格发现活跃期的频率和成本。

与已有因子关系：
  - reversal_ratio (D-009): 收益方向切换频率 → 本方向看 range 包含/突破
  - vol_regime_transitions (D-005): 成交量 regime 切换 → 本方向看价格结构 regime
  - doji_amihud (D-019): 影线>实体条件 → 本方向用 range 包含条件
  - bar_efficiency (D-019): |C-O|/(H-L) 是波动率代理 → 本方向用离散事件计数而非连续比率

Features:
  inside_bar_freq_full                 — 全天 inside bar 占比（离散计数）
  engulfing_freq_full                  — 全天 engulfing bar 占比（离散计数）
  inside_bar_amihud_full               — inside bar 上的 mean(|ret|/amount)
  high_vol_inside_amihud_full          — 高量 + inside bar 双条件 Amihud
  engulfing_amihud_full                — engulfing bar 上的 mean(|ret|/amount)
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

NAME = "multi_bar_structure_full"

OUTPUT_NAMES = [
    "inside_bar_freq_full",
    "engulfing_freq_full",
    "inside_bar_amihud_full",
    "high_vol_inside_amihud_full",
    "engulfing_amihud_full",
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

    # ---- median volume for high-vol filtering ----
    valid_vols = np.empty(n, dtype=np.float64)
    vol_idx = 0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v) and v > 0.0:
            valid_vols[vol_idx] = v
            vol_idx += 1
    if vol_idx < 20:
        return out
    valid_vols_sorted = np.sort(valid_vols[:vol_idx])
    median_vol = valid_vols_sorted[vol_idx // 2]

    # ---- Classify each bar pair (t-1, t) as inside / engulfing / neither ----
    # Inside bar: high[t] <= high[t-1] AND low[t] >= low[t-1]
    #   = bar t's range fits entirely within bar t-1's range
    # Engulfing bar: high[t] >= high[t-1] AND low[t] <= low[t-1]
    #   = bar t's range completely contains bar t-1's range

    inside_count = 0
    engulfing_count = 0
    pair_count = 0

    # Amihud accumulators
    inside_amihud_sum = 0.0
    inside_amihud_cnt = 0
    hv_inside_amihud_sum = 0.0
    hv_inside_amihud_cnt = 0
    engulfing_amihud_sum = 0.0
    engulfing_amihud_cnt = 0

    for t in range(1, n):
        h_prev = high[t - 1]
        l_prev = low[t - 1]
        h_curr = high[t]
        l_curr = low[t]

        # Skip if any OHLC is NaN
        if np.isnan(h_prev) or np.isnan(l_prev) or np.isnan(h_curr) or np.isnan(l_curr):
            continue

        # Skip flat bars (no range)
        if h_prev <= l_prev or h_curr <= l_curr:
            continue

        pair_count += 1

        # Compute return for Amihud
        c_prev = close[t - 1]
        c_curr = close[t]
        a_curr = amount[t]
        v_curr = volume[t]
        has_amihud = (
            not np.isnan(c_prev) and not np.isnan(c_curr)
            and not np.isnan(a_curr) and a_curr > 0.0
            and c_prev > 0.0
        )
        if has_amihud:
            ret_abs = abs(c_curr - c_prev) / c_prev
            amihud_val = ret_abs / a_curr
        else:
            amihud_val = np.nan

        is_inside = h_curr <= h_prev and l_curr >= l_prev
        is_engulfing = h_curr >= h_prev and l_curr <= l_prev

        if is_inside:
            inside_count += 1
            if not np.isnan(amihud_val):
                inside_amihud_sum += amihud_val
                inside_amihud_cnt += 1
                # High-vol condition
                if not np.isnan(v_curr) and v_curr > median_vol:
                    hv_inside_amihud_sum += amihud_val
                    hv_inside_amihud_cnt += 1

        if is_engulfing:
            engulfing_count += 1
            if not np.isnan(amihud_val):
                engulfing_amihud_sum += amihud_val
                engulfing_amihud_cnt += 1

    # ---- Feature 0: inside_bar_freq_full ----
    # Fraction of bar pairs where current bar is inside previous bar
    # High value = price range consistently contained = strong order book control
    # This is a discrete counting metric (like reversal_ratio, vol_regime_transitions)
    if pair_count > 20:
        out[0] = inside_count / pair_count

    # ---- Feature 1: engulfing_freq_full ----
    # Fraction of bar pairs where current bar engulfs previous bar
    # High value = frequent range expansion = active price discovery
    # Complementary to inside_bar_freq (compression vs expansion)
    if pair_count > 20:
        out[1] = engulfing_count / pair_count

    # ---- Feature 2: inside_bar_amihud_full ----
    # mean(|ret|/amount) on inside bars only
    # Price impact during consolidation (contained range) periods
    # Economic meaning: liquidity cost when market is in compression mode
    if inside_amihud_cnt > 5:
        out[2] = inside_amihud_sum / inside_amihud_cnt

    # ---- Feature 3: high_vol_inside_amihud_full ----
    # mean(|ret|/amount) on inside bars with above-median volume
    # High volume + inside bar = significant trading during price compression
    # This selects for "absorbed volume" events: lots of trading but contained range
    if hv_inside_amihud_cnt > 5:
        out[3] = hv_inside_amihud_sum / hv_inside_amihud_cnt

    # ---- Feature 4: engulfing_amihud_full ----
    # mean(|ret|/amount) on engulfing bars
    # Price impact during expansion (range breakout) events
    # Complementary to inside_bar_amihud: breakout cost vs containment cost
    if engulfing_amihud_cnt > 5:
        out[4] = engulfing_amihud_sum / engulfing_amihud_cnt

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
            "Multi-bar price structure for full-day window. "
            "5 features: inside bar frequency (discrete count of range "
            "containment events), engulfing frequency (range expansion events), "
            "inside bar Amihud (price impact during consolidation), "
            "high-volume inside Amihud (absorbed volume events), "
            "engulfing Amihud (breakout cost). "
            "Based on proven discrete counting + Amihud frameworks."
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()

    defn = build_definition()
    print(json.dumps(defn.model_dump(), indent=2, default=str))

    if args.register:
        from ashare_hf_variable.registry import upsert_definition
        upsert_definition(defn)
        print(f"\n✅ Registered {NAME}")


if __name__ == "__main__":
    main()
