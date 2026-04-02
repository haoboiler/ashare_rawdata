---
agent_id: "ashare_rawdata_a"
experiment_id: "#030"
direction: "D-021 (range_discovery_dynamics)"
feature_name: "body_amihud_full"
net_sharpe: 1.34
mono_score: 0.86
status: screening_passed
submitted_at: "2026-03-26T12:40:00"
---

# D-021 Range Discovery Dynamics — 初筛报告

## 方向概述

**D-021: 日内价格区间发现动态**

探索 bar 内 OHLC body（|C-O|）和 open displacement（|O-midpoint|）作为 Amihud 框架的新 numerator，以及日内价格区间扩展频率（discrete count）作为价格发现的度量。

### 物理假设

1. **Body Amihud (|C-O|/amount)**: bar 内定向价格承诺成本。|C-O| 衡量 bar 内收盘相对开盘的偏移（bar 内变化），不同于标准 Amihud 的 |ret|（bar 间变化）。
2. **Open Displacement Amihud (|O-(H+L)/2|/amount)**: 开盘偏离 bar range 中点的程度。互补于 close_disp_amihud（D-020）。
3. **Range Discovery Frequency**: 日内后半段设新 high/low 的 bar 占比，衡量价格发现持续性。

## 快筛结果（全市场 2020-2023, basic6）

| 特征 | |LS Sharpe| | LE | |IR(LS)| | Coverage | 状态 |
|------|-----------|------|---------|----------|--------|
| body_amihud_full | 0.98 | +0.59 | 0.43 | 86.7% | ⚠️ LS 边缘 |
| open_disp_amihud_full | 0.97 | +0.62 | 0.48 | 86.5% | ⚠️ LS 边缘 |
| range_discovery_freq_full | 2.91(neg) | -1.28 | 0.11 | 86.7% | ❌ 反向+IR 低 |
| range_discovery_amihud_full | 0.84 | +0.19 | 0.33 | 64.1% | ❌ LS+LE+覆盖 |
| high_vol_body_amihud_full | 0.80 | +0.66 | 0.34 | 86.7% | ❌ LS<0.9 |

## 正式评估结果（2020-2023, 含 neutralize + Mono）

### body_amihud_full ✅

| 指标 | Raw | Neutral |
|------|-----|---------|
| LS Sharpe (abs_net) | 0.98 | **1.34** |
| Long Excess (net) | 0.59 | **1.24** |
| IR(LS) | 0.43 | **0.45** |
| Mono (8 groups) | 0.71 | **0.86** |
| Coverage | 86.7% | 86.7% |
| TVR | 0.82 | 0.87 |

**分组表现 (neutral):**
| G1 | G2 | G3 | G4 | G5 | G6 | G7 | G8 |
|----|----|----|----|----|----|----|----|
| +13.6% | +11.3% | +7.9% | +6.8% | +4.8% | -16.6% | -23.0% | -23.8% |

中性化后信号大幅增强（LS +37%, LE +110%, Mono +21%），说明信号独立于市值/行业暴露。G6-G8 excess 大幅转负，空头端贡献显著。

### open_disp_amihud_full ✅

| 指标 | Raw | Neutral |
|------|-----|---------|
| LS Sharpe (abs_net) | 0.97 | **1.38** |
| Long Excess (net) | 0.62 | **1.27** |
| IR(LS) | 0.48 | **0.47** |
| Mono (8 groups) | 0.86 | **0.86** |
| Coverage | 86.5% | 86.5% |

**分组表现 (neutral):**
| G1 | G2 | G3 | G4 | G5 | G6 | G7 | G8 |
|----|----|----|----|----|----|----|----|
| +13.9% | +14.5% | +9.1% | +7.0% | +7.4% | -14.2% | -25.1% | -24.0% |

Open displacement 比 close displacement 在 raw 表现更好（IR 0.48 vs 0.43），中性化后两者接近。

## 失败特征诊断

### range_discovery_freq_full ❌
- **假设**: 日内后半段设新 high/low 频率衡量价格发现持续性
- **实际**: |LS|=2.91 但强烈反向（负值），IR=0.11 极低
- **诊断**: 区间扩展频率本质是**波动率代理**——高波动股票自然更频繁突破已有 range。与结论#22（直接 HL range 是波动率代理）一致。离散计数范式（结论#16）不能救波动率本质的度量
- **结论**: 区间扩展频率不是独立的价格发现维度

### range_discovery_amihud_full ❌
- **假设**: 设新 high/low 的 bar 上的 Amihud 衡量价格发现成本
- **实际**: |LS|=0.84，LE=+0.19，覆盖率仅 64%
- **诊断**: 选择"发现 bar"后样本量骤降（只有 ~36% 的 bar 是发现事件），且这些 bar 本身就是高波动 bar，信号与标准 Amihud 高度重叠但统计量更不稳定

### high_vol_body_amihud_full ❌
- **假设**: 高量 bar 的 body Amihud 更纯净
- **实际**: |LS|=0.80（低于 0.9 阈值）
- **诊断**: 高量过滤后 |C-O| 的截面差异减小（高量 bar 本身体较大），反而削弱信号

## 关键发现

1. **|C-O|/amount 是 Amihud 框架的有效新 numerator** — body_amihud neutral LS=1.34, Mono=0.86。与标准 Amihud（|ret|/amount）不同：|C-O| 衡量 bar 内价格承诺，|ret| 衡量 bar 间价格变化。
2. **|O-midpoint|/amount 互补于 |C-midpoint|/amount** — open_disp_amihud neutral LS=1.38, 与 close_disp_amihud (LS=1.55) 一起构成 bar 内 OHLC 位置的完整 Amihud 度量。
3. **区间发现频率是波动率代理** — range_discovery_freq 的离散计数形式无法救波动率本质（与结论#22 一致）。
4. **中性化一致增强 OHLC Amihud 变体** — body_amihud（+37%）和 open_disp_amihud（+42%）中性化后均大幅增强，与 close_disp（+48%）、wick（+82%）趋势一致。
5. **PKL 覆盖 2020-2023**（preload 限制），2024 数据覆盖待确认。

## 与已有因子的潜在相关性

body_amihud (|C-O|/amount) 和 close_disp_amihud (|C-midpoint|/amount) 在数学上相关：当 O≈midpoint 时，|C-O|≈|C-midpoint|。预计截面相关性较高，最终入库时需通过相关性检测决定是否保留。

## Pending 特征

1. `body_amihud_full` → `research/pending-rawdata/body_amihud_full/`
2. `open_disp_amihud_full` → `research/pending-rawdata/open_disp_amihud_full/`
