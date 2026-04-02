---
agent_id: "ashare_rawdata_a"
experiment_id: "#035"
direction: "D-026 (robust_liquidity_estimators)"
feature_name: "log_impact_amihud_full"
net_sharpe: 2.11
mono_score: 0.86
status: screening_passed
submitted_at: "2026-03-26T14:30:00"
---

# D-026 Robust Liquidity Estimators — 全天窗口初筛报告

## 方向假设

所有现有 Amihud 变体（45 个 pending）均使用**算术均值** mean(|r_i|/amount_i) 作为聚合函数。算术均值对极端价格冲击 bar 敏感。不同聚合函数（平方根、对数、调和均值、中位数、截尾均值）对分布尾部有不同敏感度，可能产生不同截面排序。

## 测试特征

| # | Feature | 聚合函数 | 物理含义 |
|---|---------|---------|---------|
| 1 | sqrt_impact_amihud_full | mean(|r|^0.5 / amount^0.5) | Kyle 平方根冲击模型 |
| 2 | log_impact_amihud_full | mean(log(1 + K×|r|/amount)) | 对数压缩冲击 |
| 3 | harmonic_amihud_full | n / Σ(amount_i/|r_i|) | 调和均值，由最流动时刻主导 |
| 4 | median_amihud_full | median(|r_i|/amount_i) | 中位数，排除全部异常值 |
| 5 | trimmed_amihud_full | trimmed_mean_10%(|r_i|/amount_i) | 截尾均值，折中方案 |

## 快筛结果（evolve, 全市场 5013 symbols, 2020-2023）

| Feature | |LS Sharpe| | LE Sharpe | IR(LS) | 通过? |
|---------|-----------|-----------|--------|-------|
| sqrt_impact | 1.90 | 1.57 | 0.33 | ✅ |
| **log_impact** | **2.11** | **1.67** | 0.34 | ✅ |
| **harmonic** | 1.85 | 1.61 | **0.39** | ✅ |
| median | 1.06 | 1.61 | -0.01 | ❌ IR≈0 |
| trimmed | 1.91 | 1.47 | 0.34 | ✅ |

**median_amihud 异常**：LE=1.61 但 IR(LS)≈0。中位数 Amihud 只在多头端有效（IC_LO=0.038），空头端无信号。中位数排除了极端冲击 bar，而这些 bar 恰恰是短边 alpha 的来源。

## 正式评估（全市场, 2020-2023, 含 Mono）

| Feature | Variant | |LS| | LE | IR | Mono | 通过 |
|---------|---------|------|------|------|------|------|
| sqrt_impact | raw | 1.90 | 1.57 | 0.33 | **1.00** | ✅ |
| sqrt_impact | neutral | 1.60 | 1.36 | 0.43 | 0.71 | ✅ |
| **log_impact** | raw | **2.11** | **1.67** | 0.34 | 0.86 | ✅ |
| **log_impact** | neutral | **1.83** | **1.38** | **0.44** | 0.86 | ✅ |
| **harmonic** | raw | 1.85 | 1.61 | 0.39 | **1.00** | ✅ |
| **harmonic** | neutral | 1.59 | **1.52** | **0.44** | 0.86 | ✅ |
| trimmed | raw | 1.91 | 1.47 | 0.34 | 0.86 | ✅ |
| trimmed | neutral | 1.73 | 1.44 | 0.43 | 0.86 | ✅ |

4/5 通过全部阈值。median 因 IR≈0 失败。

## 截面相关性分析

### 互相关（rank correlation, 采样日均值）

| | sqrt | log | harmonic | trimmed |
|--|------|-----|----------|---------|
| sqrt | 1.00 | **0.995** | 0.918 | **0.994** |
| log | 0.995 | 1.00 | 0.930 | **0.997** |
| harmonic | 0.918 | 0.930 | 1.00 | 0.934 |
| trimmed | 0.994 | 0.997 | 0.934 | 1.00 |

sqrt/log/trimmed 彼此 0.99+，本质是同一信号。harmonic 最独立（0.92-0.93）。

### 与标准 Amihud (amihud_illiq_full) 的相关性

| Feature | vs 标准 Amihud |
|---------|---------------|
| log_impact | **0.974** |
| harmonic | **0.945** |

标准 Amihud 指标更优（LS=2.37, LE=1.79 > log 2.11/1.67 > harmonic 1.85/1.61）。

## 关键结论

**算术均值 Amihud 是最优聚合函数**。稳健/非线性估计器（sqrt/log/harmonic/trimmed/median）均不如标准算术均值。

原因分析：
1. **极端冲击 bar 携带最多信息**：标准均值对极端 bar 的敏感性是**特征而非缺陷**——大价格冲击 bar 最能区分流动性好/差的股票
2. **压缩极端值 = 丢失信号**：log/sqrt 压缩了最有区分力的极端事件；median 完全忽略它们
3. **调和均值捕捉不同维度**：harmonic 由最小 Amihud bar 主导（最流动时刻），与标准 Amihud 相关性最低（0.945），提供 ~11% 独立信息

## Pending 决策

| Feature | 决策 | 理由 |
|---------|------|------|
| **log_impact_amihud_full** | ✅ Pending | 最佳指标，不同函数形式 |
| **harmonic_amihud_full** | ✅ Pending | 最独立（corr 0.945），raw Mono=1.00，独特物理含义 |
| sqrt_impact_amihud_full | ❌ 冗余 | 与 log 相关 0.995 |
| trimmed_amihud_full | ❌ 冗余 | 与 log 相关 0.997 |
| median_amihud_full | ❌ IR 失败 | IR(LS)≈0，LS 无截面预测力 |

## 文件产出

- Formula: `research/basic_rawdata/robust_liquidity_estimators/register_robust_liquidity_full.py`
- PKL: `.claude-output/analysis/robust_liquidity_estimators/{feature_name}.pkl`
- 评估: `.claude-output/evaluations/robust_liquidity_estimators/{feature_name}/`
- Pending: `research/pending-rawdata/{log_impact_amihud_full,harmonic_amihud_full}/`
