---
agent_id: "ashare_rawdata_b"
experiment_id: "#038"
direction: "D-025 (temporal_microstructure)"
feature_name: "none"
net_sharpe: 0
mono_score: 0
status: screening_failed
submitted_at: "2026-03-26T15:00:00"
---

# Cycle #14 死锁报告 — ashare_rawdata_b

## 状态

**持续死锁（第 2 轮）**。D-025 `temporal_microstructure` 已在 Exp#035+#036 中排除（10 个排除方向之一），但 `current_direction` 仍锁定在 D-025，方向锁规则禁止自行修改。

## 死锁原因

1. `current_direction: temporal_microstructure` / `current_direction_id: D-025` 未被 leader 重置为 null
2. D-025 在 KNOWLEDGE-BASE §三 已排除（两轮 14 特征仅 1 个 Amihud 变体通过 `open_gap_amihud`）
3. 方向池中无可用未认领方向（全部 exhausted 或已被 ashare_rawdata_a 认领）
4. 方向锁规则禁止 researcher 自行修改 `current_direction`

## 已有产出（D-022 微观结构噪声，上一有效 cycle）

D-022 microstructure_noise 已完成研究，两个特征通过筛选并 pending：
- `excess_bounce_amihud_full`: neutral LS=1.29, LE=1.43, IR=0.44, Mono=0.86 ✅
- `bar_pair_noise_amihud_full`: neutral LS=0.91, LE=1.07, IR=0.23, Mono=0.86 ✅（边缘）

## 需要 Leader 操作（优先级排序）

1. **重置方向** → 将 `current_direction` / `current_direction_id` 设为 null，让 researcher 可认领新方向
2. **新增方向到方向池** → 当前方向池已 exhausted/claimed，需要补充新方向
3. **或分配特定任务** → 如 D-022 补充正式评估、或对已有 pending 特征做相关性分析

## 系统状态

- Preload bridge: ✅ ready（5013/5191 symbols, basic6 fields）
- 连续失败: 2（死锁导致，非研究质量问题）
- 上轮有效产出: Exp#033（D-022），2 个特征 pending
