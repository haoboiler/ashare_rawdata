---
agent_id: "ashare_rawdata_a"
experiment_id: "#021"
direction: "D-010 (hurst_exponent)"
feature_name: "vol_accel_full"
net_sharpe: 1.79
mono_score: 0.86
status: screening_failed
submitted_at: "2026-03-26T08:30:00"
---

# D-010 Hurst Exponent — 扩展粗糙度特征（最终轮）

## 实验目标

在 D-010 方向（hurst_exponent）内探索 vol_roughness_full 的变体，验证是否存在独立增量信号。上轮（Exp#020）已确认 R/S Hurst 退化为波动率代理，仅 vol_roughness_full 通过。本轮是 D-010 的最终确认轮。

## 测试特征

| 特征 | 公式 | 物理假设 |
|------|------|---------|
| `vol_accel_full` | mean(\|Δ²vol\|)/mean(vol) | 二阶加速度 = 量变的变化，捕捉流动性供给的"jerkiness" |
| `log_vol_roughness_full` | mean(\|Δlog(vol+1)\|) | 对数变换压缩极值，可能更稳健的粗糙度估计 |
| `vol_change_asym_full` | count(Δvol>0)/count(Δvol≠0) | 量变方向不对称性 = 机构增仓 vs 活动衰退 |

## 评估结果（2020-2023 全市场快筛 + 完整分组评估）

### Quick-eval 快筛

| 特征 | \|LS Sharpe\| | LE Sharpe | IR(LS) | 快筛结果 |
|------|-------------|-----------|--------|---------|
| `vol_accel_full` | 1.79 | +1.25 | 0.56 | ✅ 通过 |
| `log_vol_roughness_full` | 1.29 | +0.86 | 0.50 | ✅ 通过 |
| `vol_change_asym_full` | 8.46 (负) | -0.80 | 0.12 | ❌ 反向+IR |

### 完整分组评估（通过快筛的特征）

**vol_accel_full**:

| 评估 | LS Sharpe | LE Sharpe | IR(LS) | Mono | 判断 |
|------|-----------|-----------|--------|------|------|
| Raw | 1.79 | 1.25 | 0.56 | **0.86** | ✅ 全部达标 |
| Neutral | 1.40 | 0.98 | 0.56 | **0.71** | ✅ 全部达标 |

年度分解(raw): 2020=-0.27 / 2021=1.91 / 2022=3.34 / 2023=3.59

**log_vol_roughness_full**:

| 评估 | LS Sharpe | LE Sharpe | IR(LS) | Mono | 判断 |
|------|-----------|-----------|--------|------|------|
| Raw | 1.29 | 0.86 | 0.50 | **0.43** | ❌ Mono 失败 |
| Neutral | 0.42 | 0.48 | 0.52 | 0.57 | ❌ LS+LE+Mono |

### 相关性检测

| 特征对 | 截面相关性 | 判断 |
|--------|-----------|------|
| vol_accel_full vs vol_roughness_full | **0.9948** | ❌ 几乎完全相同 |

## 最终判断：全部失败

尽管 vol_accel_full 通过了所有指标阈值，但与已提交的 vol_roughness_full（上轮 Exp#020 pending）的截面相关性高达 0.9948，不提供任何独立增量信号。数学上，对于噪声时序 Δ²x ≈ Δx_t - Δx_{t-1}，连续差分近似独立时 mean|Δ²x| ≈ √2·mean|Δx|，两者排序近乎一致。

## 失败诊断

### vol_accel_full
- **特征**: mean(|vol[t]-2·vol[t-1]+vol[t-2]|)/mean(vol)
- **假设**: 二阶加速度捕捉流动性供给的不稳定性
- **实际**: 通过所有阈值，但与一阶 vol_roughness 相关性 0.9948
- **诊断**: 二阶差分本质是一阶差分的线性组合，在噪声序列上退化为一阶差分的缩放版本
- **结论**: 无独立增量价值

### log_vol_roughness_full
- **特征**: mean(|Δlog(vol+1)|)
- **假设**: Log 变换压缩极值，提供更稳健的粗糙度估计
- **实际**: Raw Mono=0.43（分组1 excess 仅 0.018），neutral LS Sharpe=0.42
- **诊断**: Log 变换压缩了 vol_roughness 信号中的关键极端值差异。粗糙度信号恰恰依赖极端量变来区分高/低流动性不确定性的股票，压缩后截面区分度丧失
- **结论**: 方向性错误——vol_roughness 的有效信号在极值端，不应压缩

### vol_change_asym_full
- **特征**: count(Δvol>0)/total_changes
- **假设**: 量变方向不对称性反映机构行为
- **实际**: sharpe_abs_net=-8.46（强烈反向），IR=0.12，day_tvr=2.74
- **诊断**: 比率指标极高换手（每天 2.74 次双边），信号噪声大。反向可能因为大市值股更接近 0.5（对称），小市值股偏离 0.5（不对称），形成市值代理
- **结论**: 非流动性因子，不适合此方向

## D-010 方向总结

经两轮实验（Exp#020 + Exp#021），共测试 9 个特征：

| 特征类别 | 数量 | 通过 | 独立通过 |
|---------|------|------|---------|
| R/S Hurst 系列 | 4 | 0 | 0 |
| 方差比 | 1 | 0 | 0 |
| 路径粗糙度（一阶） | 1 | 1 | **1** (vol_roughness_full) |
| 路径粗糙度（变体） | 3 | 0 | 0 |

**方向结论**: D-010 已 exhausted。唯一有效特征 vol_roughness_full 已在 Exp#020 提交 pending。所有 Hurst exponent 方法在 237 bars 短序列上退化为波动率代理，粗糙度变体则与一阶 vol_roughness 高度共线。建议标记方向为 exhausted 并切换至新方向。
