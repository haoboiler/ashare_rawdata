---
agent_id: "ashare_rawdata_a"
experiment_id: "#029"
direction: "D-020 (ohlc_microstructure_decomposition)"
feature_name: "upper_wick_amihud_full"
net_sharpe: 2.18
mono_score: 0.86
status: screening_passed
submitted_at: "2026-03-26T12:10:00"
---

# D-020 OHLC 微观结构分解 — 初筛报告

## 方向假设

将 bar 内 OHLC 结构分解为更细的组件（close displacement / upper wick / lower wick），归一化到 amount 后作为 Amihud 框架的新 numerator。

**经济含义**：
- **close_disp_amihud** = |C - (H+L)/2| / amount：实现价差（realized effective spread）代理——close 偏离 bar 中点的程度反映做市均衡的失衡
- **upper_wick_amihud** = (H - max(O,C)) / amount：卖压拒绝成本——价格向上探索后被推回的幅度
- **lower_wick_amihud** = (min(O,C) - L) / amount：买压拒绝成本——价格向下探索后被推回的幅度
- **close_disp_roughness** = mean|Δ(close_disp)| / mean(close_disp)：价差路径粗糙度

与 D-019 的关系：
- wick_amihud (D-019) = (upper_wick + lower_wick) / amount → 本方向将其分解为两个方向性组件
- close displacement 是全新的 Amihud numerator，与 |ret| 和 wick 在数学上不同

## 快筛结果（evolve, 全市场 2020-2023, basic6）

| 特征 | |LS Sharpe| | LE | IR(LS) | TVR |
|------|-----------|------|--------|-----|
| close_disp_amihud_full | 1.054 | 0.606 | 0.442 | 0.749 |
| high_vol_close_disp_amihud_full | 1.009 | 0.670 | 0.418 | 0.582 |
| **upper_wick_amihud_full** | **1.263** | **0.737** | **0.462** | 1.026 |
| lower_wick_amihud_full | 1.101 | 0.600 | 0.476 | 0.993 |
| close_disp_roughness_full | -2.201 | -0.265 | 0.063 | 1.252 |

## 正式评估结果（evaluate_rawdata.py, 2020-2024, w1, 8 groups）

| 特征 | 组 | LS Sharpe | LE | IR(LS) | Mono | TVR | 判定 |
|------|------|----------|------|--------|------|-----|------|
| close_disp_amihud_full | raw | 1.05 | 0.61 | 0.44 | 0.75 | 0.75 | ⚠️ LE |
| | **neutral** | **1.55** | **1.28** | **0.46** | **0.89** | 0.81 | **✅ 全通过** |
| high_vol_close_disp_amihud_full | raw | 1.01 | 0.67 | 0.42 | 0.79 | 0.58 | ⚠️ LE |
| | **neutral** | **1.13** | **1.16** | **0.45** | **0.82** | 0.66 | **✅ 全通过** |
| upper_wick_amihud_full | **raw** | **1.26** | **0.74** | **0.46** | **0.86** | 1.03 | **✅ 全通过** |
| | **neutral** | **2.18** | **1.37** | **0.48** | **0.86** | 1.05 | **✅ 全通过** |
| lower_wick_amihud_full | raw | 1.10 | 0.60 | 0.48 | 0.79 | 0.99 | ⚠️ LE |
| | **neutral** | **2.16** | **1.36** | **0.49** | **0.86** | 1.01 | **✅ 全通过** |
| close_disp_roughness_full | raw | -2.20 | -0.27 | 0.06 | - | 1.25 | ❌ IR 极低 |

## 关键发现

1. **OHLC 分解后的 Amihud 变体全部有效** — 4/5 特征通过自动筛选（close_disp/upper_wick/lower_wick 及其高量变体），证明 bar 内 OHLC 结构包含丰富的流动性信息

2. **中性化后信号大幅增强** — 所有 4 个特征中性化后 LS/LE 均显著提升（LS 提升 12%-72%, LE 提升 73%-127%），说明原始信号中混杂了市值/行业效应，去除后暴露出更纯的流动性 alpha

3. **upper_wick 和 lower_wick 几乎等强** — neutral LS 2.18 vs 2.16, LE 1.37 vs 1.36, 二者高度对称。卖压拒绝成本和买压拒绝成本提供几乎相同的截面信号，说明流动性溢价不依赖于价格探索的方向

4. **close displacement 是有效的新 Amihud numerator** — close_disp_amihud neutral LS=1.55, LE=1.28, Mono=0.89（最高），证明 |C - midpoint| / amount 作为实现价差代理有独立信号

5. **roughness 范式在 close displacement 上失效** — close_disp_roughness IR=0.06（噪声），与 wick_roughness 失败（结论#66）一致：只有 volume 粗糙度含独立于市值的信号，其他维度的粗糙度信号主要来自市值暴露

6. **与 D-019 wick_amihud 预计高度相关** — upper_wick + lower_wick ≈ wick，因此新特征与已 pending 的 wick_amihud_full 可能高度相关。但 close_disp_amihud 使用不同的 numerator（|C-midpoint| vs H-L-|C-O|），可能提供增量信息

## 失败诊断

- **close_disp_roughness_full**: IR=0.063，路径粗糙度范式在 close displacement 维度上无截面区分度。与 wick_roughness（结论#66）失败模式一致——非 volume 维度的粗糙度信号主要反映市值/价格水平差异而非流动性不确定性

## Pending 特征

| 特征 | 最佳组 | LS | LE | IR | Mono |
|------|--------|----|----|----|----|
| close_disp_amihud_full | neutral | 1.55 | 1.28 | 0.46 | 0.89 |
| high_vol_close_disp_amihud_full | neutral | 1.13 | 1.16 | 0.45 | 0.82 |
| upper_wick_amihud_full | neutral | 2.18 | 1.37 | 0.48 | 0.86 |
| lower_wick_amihud_full | neutral | 2.16 | 1.36 | 0.49 | 0.86 |

## 数据覆盖

- pkl 覆盖期: 2020-01-02 ~ 2023-12-31 (970 交易日)
- 覆盖率: 86.7% (非 NaN 占比)
- 注意: pkl 仅覆盖到 2023-12-31（preload 窗口），正式评估时 2024 年数据为 NaN。入库前需要重新计算全量数据
