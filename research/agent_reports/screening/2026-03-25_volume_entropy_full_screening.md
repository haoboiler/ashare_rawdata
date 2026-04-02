---
agent_id: "ashare_rawdata_b"
experiment_id: "#006"
direction: "D-005 (volume_entropy)"
feature_name: "vol_regime_transitions_full"
net_sharpe: 2.48
mono_score: 0.86
status: screening_passed
submitted_at: "2026-03-25T22:57:00"
---

# D-005 Volume Entropy 方向筛选报告

## 研究概要

**Agent**: ashare_rawdata_b | **实验**: #006 | **日期**: 2026-03-25
**方向**: D-005 volume_entropy — 成交量分布的信息熵，衡量交易活跃度的均匀性
**假设**: 成交量regime切换频率高的股票具有更好的微观结构质量和流动性，获得流动性溢价

## 测试特征汇总

共测试 10 个特征（2 个 bundle × 5 fields），1 个通过自动筛选。

### Bundle 1: volume_microstructure_full（纯成交量分布，5 fields）

| 特征 | |LS Sharpe| | LE Sharpe | |IR(LS)| | 状态 |
|------|-----------|-----------|---------|------|
| `volume_entropy_full` | 2.41 | -0.75 | 0.12 | ❌ IR<0.2, LE<0.7 |
| `volume_gini_full` | 2.45 | -1.67 | 0.17 | ❌ IR<0.2, LE<0.7 |
| `high_vol_bar_ratio_full` | 1.46 | -0.24 | 0.27 | ❌ LS<0.9, LE<0.7 |
| `volume_autocorr1_full` | **6.12** | **-2.81** | **0.74** | ❌ LE 深度失败 |
| `volume_dispersion_ratio_full` | 2.49 | -1.57 | 0.31 | ❌ LE 失败 |

**诊断**: 全部 LE 为负，alpha 集中在空头端。纯成交量分布指标（熵/Gini/离散度）识别的是"坏股票"（成交量不均匀 = 流动性差），而非"好股票"。volume_autocorr1 信号极强（|IR|=0.74）但完全是空头端驱动。

### Bundle 2: volume_informed_trading_full（量价交互，5 fields）

| 特征 | |LS Sharpe| | LE Sharpe | |IR(LS)| | w1 Mono | 状态 |
|------|-----------|-----------|---------|---------|------|
| `informed_trade_ratio_full` | 6.22 | -2.03 | 0.51 | - | ❌ LE 深度失败 |
| `vol_return_sync_full` | 8.15 | -4.85 | 0.36 | - | ❌ LE 深度失败 |
| `vol_weighted_return_std_full` | 7.09 | -5.41 | 0.52 | - | ❌ LE 深度失败 |
| `vol_price_joint_entropy_full` | 0.27 | **+1.10** | 0.24 | - | ❌ LS Sharpe<0.9 |
| **`vol_regime_transitions_full`** | **2.48** | **+1.46** | **0.75** | **0.86** | **✅ PASSED** |

## 通过特征详细评估: vol_regime_transitions_full

### 物理含义

成交量在中位数上下的切换频率（全天 ~237 bars）。高频切换 = 无成交量聚集 = 更好的流动性质量。这是 `reversal_ratio_full`（价格方向反转频率）的成交量版本类比。

### 全量评估结果（w1, 2022-01-01 ~ 2024-12-31）

| 指标 | Raw | Neutral | 阈值 | 判定 |
|------|-----|---------|------|------|
| Coverage | 95.2% | 95.2% | > 30% | ✅ |
| |LS Sharpe| (`sharpe_abs_net`) | 2.48 | 1.95 | > 0.9 | ✅ |
| |IR(LS)| | 0.75 | 0.72 | > 0.2 | ✅ |
| LE Sharpe (`sharpe_long_excess_net`) | 1.46 | 1.28 | > 0.7 | ✅ |
| Mono (8 groups) | 0.86 | 0.71 | > 0.7 | ✅ |

### 年度分解

| 年份 | Raw Sharpe | Raw Return | Neutral Sharpe | Neutral Return |
|------|-----------|------------|----------------|----------------|
| 2022 | 3.59 | +26.5% | 2.97 | +21.7% |
| 2023 | 3.85 | +27.8% | 2.94 | +21.2% |
| 2024 | 1.14 | +13.8% | 0.92 | +11.4% |

### 关键指标

- **IC(LS)**: Raw 0.069, Neutral 0.067（中性化后基本不变，信号独立于市值/行业）
- **Win Rate**: Raw 59.6%, Neutral 58.1%
- **Max Drawdown**: Raw -12.2% (abs), Neutral -15.5% (abs)
- **Segment Stability**: Raw 3/3 positive (1.00), Neutral 2/3 positive (0.67)

### 2024 年信号减弱分析

Raw Sharpe 从 2022-2023 的 3.5-3.9 下降到 2024 的 1.14。Neutral 下降到 0.92。与 reversal_ratio_full 的 2024 衰减模式一致，可能原因：
1. 2024 年量化交易占比提高，流动性因子 alpha 被部分套利
2. 2024 年 A 股市场结构变化（政策市、大小盘分化加剧）

## 关键发现

1. **成交量 regime 切换频率是有效的流动性质量因子** — 与价格反转频率（reversal_ratio）共同验证了"流动性质量"假设方向
2. **纯成交量分布指标系统性失败在 LE** — 熵/Gini/离散度/自相关全部空头端驱动（与价格微观结构因子失败模式一致）
3. **离散化的 regime 切换 >> 连续分布统计** — vol_regime_transitions（离散化计数）远优于 volume_entropy（连续分布统计），与 reversal_ratio >> Roll spread 的结论一致
4. **中性化后信号轻度衰减但保持显著** — LS Sharpe 2.48→1.95，说明部分信号来自市值/行业暴露，但独立 alpha 仍然显著

## 文件路径

- **因子 pkl**: `.claude-output/analysis/volume_entropy/vol_regime_transitions_full.pkl`
- **评估 (raw)**: `.claude-output/evaluations/volume_entropy/vol_regime_transitions_full/file-vol_regime_transitions_full-raw/`
- **评估 (neutral)**: `.claude-output/evaluations/volume_entropy/vol_regime_transitions_full/file-vol_regime_transitions_full-neutral-industry-size/`
- **Pending 包**: `research/pending-rawdata/vol_regime_transitions_full/`
