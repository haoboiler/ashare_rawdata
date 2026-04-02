---
agent_id: "ashare_rawdata_b"
experiment_id: "#022"
direction: "D-014 (intraday_momentum)"
feature_name: "batch_amihud_full"
net_sharpe: 2.12
mono_score: 1.00
status: screening_passed
submitted_at: "2026-03-26T09:00:00"
---

# D-014 Intraday Momentum / Price Path Topology — 全市场筛选报告

## 研究背景

D-014 是方向池中最后一个可用方向。基于 21 轮实验的结论：
- 纯动量/方向性信号在 A 股日内系统性失败于 Long Excess（结论 #6/#9/#24）
- 流动性水平因子（Amihud, CS spread, reversal_ratio）是唯一有效类别（结论 #24）
- |f(price)|/amount 模板具有通用性（结论 #35）

**策略**：将 D-014 重新定义为"价格路径拓扑"——探索全天累积收益曲线的几何形状特征，并结合已建立的流动性框架。

## 核心假设

1. **路径效率**：|total_ret| / sum(|ret_i|) — 价格路径直接性的连续度量，低效率 = 频繁反转 = bid-ask bounce 多 = 差流动性
2. **方向性 Amihud 分裂**：买方/卖方价格冲击的不对称性，可能捕捉信息不对称
3. **Amount 归一化路径拓扑**：将失败的路径特征（cumret_area, max_excursion）除以 amount，应用 Amihud 框架挽救波动率代理

## 快筛结果（全市场 2020-2023，5013 symbols）

### Round 1：路径拓扑 + 方向性 Amihud（8 特征）

| 特征 | |LS Sharpe| | LE Sharpe | |IR| | 状态 |
|------|-----------|-----------|------|------|
| path_efficiency_full | 8.23 | -5.36 | 0.095 | ❌ 波动率代理，LE深负 |
| vw_path_efficiency_full | 6.78 | -2.05 | 0.074 | ❌ 波动率代理 |
| max_excursion_ratio_full | 3.86 | -1.72 | 0.087 | ❌ 波动率代理 |
| **up_amihud_full** | **1.58** | **+1.28** | **0.374** | ✅ 方向性条件 Amihud |
| **down_amihud_full** | **1.47** | **+1.14** | **0.379** | ✅ 方向性条件 Amihud |
| amihud_directional_asym_full | 7.84 | -0.48 | 0.121 | ❌ 方向性信号失败 |
| macro_amihud_full | 0.18 | +0.85 | 0.287 | ❌ |LS|<0.9 |
| cumret_area_norm_full | 5.64 | -5.33 | 0.379 | ❌ 波动率代理 |

### Round 2：Amount 归一化路径特征（8 特征）

| 特征 | |LS Sharpe| | LE Sharpe | |IR| | 状态 |
|------|-----------|-----------|------|------|
| **batch_amihud_full** | **2.12** | **+1.63** | **0.365** | ✅ Volume-weighted Amihud |
| **vw_amihud_full** | **2.09** | **+1.63** | **0.359** | ✅ ≈batch_amihud |
| **cumret_area_amihud_full** | **1.08** | **+1.11** | **0.302** | ✅ 路径积分/amount（新颖） |
| **max_excursion_amihud_full** | **1.53** | **+1.35** | **0.295** | ✅ 最大偏移/amount（新颖） |
| **am_amihud_full** | **1.62** | **+1.19** | **0.354** | ✅ 上午 Amihud |
| **pm_amihud_full** | **1.62** | **+1.22** | **0.343** | ✅ 下午 Amihud |
| cumret_path_roughness_full | 3.73 | -0.77 | 0.099 | ❌ 粗糙度比率无信号 |
| session_amihud_ratio_full | 7.05 | -4.21 | 0.047 | ❌ 比率=方向性信号 |

**累计 2 轮 16 特征，8 通过快筛，8 失败。**

## Shortlist 正式评估（2020-2023，含 Mono）

4 个代表性特征进入正式评估（含分组回测 Mono 评分）：

| 特征 | |LS|(r/n) | LE(r/n) | |IR|(r/n) | Mono(r/n) | 状态 |
|------|---------|---------|---------|-----------|------|
| `batch_amihud_full` | 2.12/1.94 | +1.63/+1.49 | 0.36/0.47 | **1.00/0.86** | ✅ 通过 |
| `up_amihud_full` | 1.58/1.50 | +1.28/+1.45 | 0.37/0.44 | **1.00/0.71** | ✅ 通过 |
| `max_excursion_amihud_full` | 1.53/1.11 | +1.35/+1.18 | 0.29/0.43 | **0.86/0.86** | ✅ 通过 |
| `cumret_area_amihud_full` | 1.08/0.37 | +1.11/+0.92 | 0.30/0.44 | **0.86/0.71** | ✅ 通过(raw) |

**注意**：
- Mono 方向为反向（低因子值 → 高收益），评估框架已自动检测
- cumret_area_amihud_full neutral LS=0.37 低于 0.9，但 raw 组通过所有阈值
- 2024 年数据正在串行计算中，正式覆盖到 2024-12-31 的评估待完成

## 关键发现

### ✅ 新发现

1. **Amount 归一化可以挽救失败的路径拓扑特征**：cumret_area_norm（LE=-5.33）→ cumret_area_amihud（LE=+1.11），max_excursion_ratio（LE=-1.72）→ max_excursion_amihud（LE=+1.35）。这再次验证了 |f(path)|/amount 模板的通用性

2. **Batch Amihud（sum|ret|/sum(amount)）与 bar-level Amihud（mean(|ret|/amount)）表现相近**：batch_amihud LS=2.12 vs amihud_illiq LS=2.37。Volume-weighted 聚合方式几乎不改变信号

3. **方向性 Amihud 分裂产生有效因子但非对称性无效**：up_amihud 和 down_amihud 各自通过，但它们的差值（amihud_directional_asym）|IR|=0.12 接近噪声。说明买卖双方价格冲击的截面排序一致

### ❌ 确认/排除

4. **纯路径拓扑特征全部是波动率/市值代理**：path_efficiency, vw_path_efficiency, max_excursion_ratio, cumret_area_norm 全部 LE 深度负值（-1.72 到 -5.36），与 BPV（结论#5）、HL range（结论#22）、quarticity（结论#28）失败模式完全一致

5. **宏观 Amihud（净收益/总成交额）信号极弱**：|LS|=0.18。net return = |close_end/close_start - 1| 在全天路径中互相抵消（反转的 bar 贡献为零），丢失了 bar 级微观结构信息

6. **D-014 本质上没有产生超越已有 Amihud 框架的因子**：通过的 8 个特征全部是 Amihud 变体（条件化/聚合方式/归一化目标的变化），预计与已有 Amihud 系列高度相关

## 结论

D-014 作为"日内动量"方向已被完全重新定义为"路径拓扑"，测试了 16 个特征。结果进一步强化了结论 #24：A 股有效日内因子的边界仅限于流动性水平量。所有路径拓扑创新（效率、面积、偏移比）都只有在接入 Amihud 归一化框架后才能产生信号。

**建议**：
- 4 个通过特征进入 pending（待 2024 正式确认）
- D-014 标记为 explored（路径拓扑角度已穷尽，Amihud 变体空间进一步饱和）
- 方向池中所有 14 个方向均已 exhausted/explored，建议补充新方向候选

## 评估路径

- **Evolve 产出**: `.claude-output/evolve/20260326-083109/`, `.claude-output/evolve/20260326-083603/`
- **正式评估**: `.claude-output/evaluations/intraday_momentum/`
- **PKL**: `.claude-output/analysis/intraday_momentum/`
