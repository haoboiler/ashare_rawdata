#!/usr/bin/env python3
"""Range Discovery Dynamics — full-day window (09:30-11:30 + 13:00-14:57).

D-021: 日内价格区间发现动态
核心假设：
  - |C-O|/amount (body Amihud) 是 Amihud 框架的新 numerator，衡量 bar 内定向价格
    承诺成本（close 相对 open 的偏移 / 交易额）。与 |ret|/amount 不同之处：
    |ret| = bar间变化, |C-O| = bar内变化。
  - |O-(H+L)/2|/amount (open displacement Amihud) 衡量开盘偏离 bar range 中点的程度，
    互补于 close_disp_amihud。
  - range_discovery_freq 计算日内后半段设新 high/low 的 bar 占比（离散计数），
    衡量价格发现的持续性。与 reversal_ratio（方向切换）和 vol_regime_transitions
    （成交量 regime）正交。
  - range_discovery_amihud 在设新 high/low 的 bar 上计算 Amihud，衡量价格发现的成本。

与已有因子关系：
  - close_disp_amihud (D-020): |C-midpoint|/amount → 本方向探索 |C-O|/amount 和 |O-midpoint|/amount
  - reversal_ratio (D-009): 收益方向切换频率 → range_discovery_freq 是范围扩展频率
  - amihud_illiq: |ret|/amount → body_amihud 用 bar内 |C-O| 替代 bar间 |ret|

Features:
  body_amihud_full                   — mean(|C-O| / amount), bar 内定向价格承诺成本
  open_disp_amihud_full              — mean(|O-(H+L)/2| / amount), 开盘偏离成本
  range_discovery_freq_full          — 后半段设新 high/low 的 bar 占比（离散计数）
  range_discovery_amihud_full        — 设新 high/low 的 bar 上的 mean(|ret|/amount)
  high_vol_body_amihud_full          — 高量 bar 的 body Amihud
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

NAME = "range_discovery_full"

OUTPUT_NAMES = [
    "body_amihud_full",
    "open_disp_amihud_full",
    "range_discovery_freq_full",
    "range_discovery_amihud_full",
    "high_vol_body_amihud_full",
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

    # ---- Feature 0: body_amihud_full ----
    # mean(|C - O| / amount) over all bars
    # Economic meaning: directional price commitment per unit of trading
    # |C-O| captures how much the close moves from open WITHIN the bar
    # Different from standard Amihud |ret| which is BETWEEN consecutive bars
    ba_sum = 0.0
    ba_cnt = 0
    for i in range(n):
        c = close[i]
        o = opn[i]
        a = amount[i]
        if np.isnan(c) or np.isnan(o) or np.isnan(a) or a <= 0.0:
            continue
        ba_sum += abs(c - o) / a
        ba_cnt += 1

    if ba_cnt > 0:
        out[0] = ba_sum / ba_cnt

    # ---- Feature 1: open_disp_amihud_full ----
    # mean(|O - (H+L)/2| / amount) over all bars
    # Economic meaning: how far the opening price deviates from the midpoint of the bar
    # Complementary to close_disp_amihud which measures close displacement
    # High value = open consistently displaced from range center = directional opening pressure
    od_sum = 0.0
    od_cnt = 0
    for i in range(n):
        o = opn[i]
        h = high[i]
        l = low[i]
        a = amount[i]
        if np.isnan(o) or np.isnan(h) or np.isnan(l) or np.isnan(a) or a <= 0.0:
            continue
        bar_range = h - l
        if bar_range < 1e-12:
            continue  # flat bar, skip
        midpoint = (h + l) / 2.0
        od_sum += abs(o - midpoint) / a
        od_cnt += 1

    if od_cnt > 0:
        out[1] = od_sum / od_cnt

    # ---- Feature 2: range_discovery_freq_full ----
    # Fraction of bars (after warm-up period) that set a new running daily high or low
    # Discrete count: measures how long price keeps exploring new territory
    # Low freq = range established early, rest is consolidation (efficient price discovery)
    # High freq = range keeps expanding (uncertain price discovery, more exploration needed)
    # Warm-up: skip first 30 bars (first ~30 minutes) where most bars trivially set new extremes
    # This is ORTHOGONAL to reversal_ratio (direction changes) and vol_regime_transitions (volume regimes)
    warmup = 30  # skip first 30 bars
    if n <= warmup + 10:
        return out  # need enough post-warmup bars

    # Compute running high/low up to warmup
    running_high = -1e18
    running_low = 1e18
    for i in range(warmup):
        h = high[i]
        l = low[i]
        if not np.isnan(h) and h > running_high:
            running_high = h
        if not np.isnan(l) and l < running_low:
            running_low = l

    if running_high < -1e17 or running_low > 1e17:
        return out  # no valid data in warmup period

    # Count discovery events after warmup
    discovery_count = 0
    post_warmup_valid = 0
    for i in range(warmup, n):
        h = high[i]
        l = low[i]
        if np.isnan(h) or np.isnan(l):
            continue
        post_warmup_valid += 1
        is_discovery = False
        if h > running_high:
            running_high = h
            is_discovery = True
        if l < running_low:
            running_low = l
            is_discovery = True
        if is_discovery:
            discovery_count += 1

    if post_warmup_valid > 10:
        out[2] = discovery_count / post_warmup_valid

    # ---- Feature 3: range_discovery_amihud_full ----
    # mean(|ret| / amount) only on bars that set a new running daily high or low
    # Economic meaning: price impact cost during price discovery events
    # These are the bars where new information is being incorporated into prices
    # Need to re-scan with running high/low tracking + compute ret
    running_high2 = -1e18
    running_low2 = 1e18
    rd_amihud_sum = 0.0
    rd_amihud_cnt = 0
    prev_close = np.nan
    for i in range(n):
        h = high[i]
        l = low[i]
        c = close[i]
        a = amount[i]

        if np.isnan(h) or np.isnan(l):
            prev_close = c if not np.isnan(c) else prev_close
            continue

        is_discovery = False
        if h > running_high2:
            running_high2 = h
            is_discovery = True
        if l < running_low2:
            running_low2 = l
            is_discovery = True

        if is_discovery and not np.isnan(prev_close) and not np.isnan(c) and not np.isnan(a) and a > 0.0:
            ret_abs = abs(c - prev_close)
            rd_amihud_sum += ret_abs / a
            rd_amihud_cnt += 1

        if not np.isnan(c):
            prev_close = c

    if rd_amihud_cnt > 5:
        out[3] = rd_amihud_sum / rd_amihud_cnt

    # ---- Feature 4: high_vol_body_amihud_full ----
    # mean(|C - O| / amount) on bars with volume > median
    # High-volume bars are active trading events; body Amihud on them
    # captures directional commitment cost during active periods
    hvba_sum = 0.0
    hvba_cnt = 0
    for i in range(n):
        c = close[i]
        o = opn[i]
        v = volume[i]
        a = amount[i]
        if np.isnan(c) or np.isnan(o) or np.isnan(v) or np.isnan(a) or a <= 0.0:
            continue
        if v > median_vol:
            hvba_sum += abs(c - o) / a
            hvba_cnt += 1

    if hvba_cnt > 5:
        out[4] = hvba_sum / hvba_cnt

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
            "Range discovery dynamics for full-day window. "
            "5 features: body Amihud (|C-O|/amount), open displacement Amihud "
            "(|O-midpoint|/amount), range discovery frequency (discrete count of "
            "bars setting new daily highs/lows after warmup), range discovery "
            "Amihud (price impact on discovery bars), high-vol body Amihud. "
            "Orthogonal to reversal_ratio (direction changes) and "
            "vol_regime_transitions (volume regimes)."
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
