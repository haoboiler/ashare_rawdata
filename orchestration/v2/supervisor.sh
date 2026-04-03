#!/bin/bash
#
# Supervisor — 零 AI token 的顶层生命周期管理器
#
# 取代 lead Agent，管理 N 个 worker wrapper。
# 职责：健康检查、预算执行、方向池水位、pending 提醒、整点报告。
#
# Usage:
#   bash orchestration/v2/supervisor.sh [agent_id ...]
#   bash orchestration/v2/supervisor.sh ashare_rawdata_a ashare_rawdata_b
#
# 在 tmux 中启动:
#   tmux new-session -d -s supervisor \
#     "bash orchestration/v2/supervisor.sh ashare_rawdata_a ashare_rawdata_b 2>&1 | tee orchestration/logs/supervisor.log"
#
# 停止:
#   touch orchestration/state/SUPERVISOR_STOP
#

set -euo pipefail

# === 配置 ===
PROJECT_DIR="/home/gkh/claude_tasks/ashare_rawdata"
STATE_DIR="${PROJECT_DIR}/orchestration/state"
AGENT_STATES_DIR="${STATE_DIR}/agent_states"
LOG_DIR="${PROJECT_DIR}/orchestration/logs"
TG_SEND="${PROJECT_DIR}/orchestration/tg_send.py"
CONFIG_FILE="${PROJECT_DIR}/orchestration/config.yaml"
COST_TRACKER="${STATE_DIR}/cost_tracker.yaml"
POOL_PATH="${STATE_DIR}/direction_pool.yaml"
HOURLY_REPORT="${PROJECT_DIR}/orchestration/hourly_report.sh"
AUTO_DISPATCH="${PROJECT_DIR}/orchestration/v2/auto_dispatch.py"
WORKER_WRAPPER="${PROJECT_DIR}/orchestration/v2/worker_wrapper.sh"

WEEKLY_BUDGET_USD=$(grep 'weekly_limit_usd' "$CONFIG_FILE" | awk '{print $2}' || echo 500)

# Supervisor loop 间隔（秒）
LOOP_INTERVAL=180  # 3 分钟

# 方向池低水位阈值
POOL_LOW_WATER=2

# Pending 堆积阈值
PENDING_ALERT_THRESHOLD=5

# 自动重启 idle worker
AUTO_REARM=true

# === 参数 ===
AGENT_LIST=("$@")
if [ ${#AGENT_LIST[@]} -eq 0 ]; then
    echo "Usage: $0 <agent_id> [agent_id ...]"
    echo "Example: $0 ashare_rawdata_a ashare_rawdata_b"
    exit 1
fi

# === 辅助函数 ===

tg_send() {
    python "$TG_SEND" --text "$1" 2>/dev/null || true
}

get_state_field() {
    local agent=$1 field=$2
    grep "^${field}:" "${AGENT_STATES_DIR}/${agent}.yaml" 2>/dev/null \
        | head -1 | sed "s/^${field}: *//" | tr -d '"' || echo ""
}

get_pool_available_count() {
    grep -c "status: available" "$POOL_PATH" 2>/dev/null || echo 0
}

get_pool_claimed_count() {
    grep -c "status: claimed" "$POOL_PATH" 2>/dev/null || echo 0
}

get_pending_count() {
    local count=0
    if [ -d "${PROJECT_DIR}/research/pending-rawdata" ]; then
        count=$(find "${PROJECT_DIR}/research/pending-rawdata" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
    fi
    echo "$count"
}

get_weekly_spend() {
    grep '^week_total_usd:' "$COST_TRACKER" 2>/dev/null | awk '{print $2}' || echo "0"
}

is_over_budget() {
    local spent=$1
    echo "$spent $WEEKLY_BUDGET_USD" | awk '{exit !($1 >= $2)}'
}

restart_worker() {
    local agent=$1
    echo "[$(date)] Restarting worker: ${agent}"

    # 先清理残留的 STOP 信号
    rm -f "${AGENT_STATES_DIR}/${agent}_STOP"

    tmux new-session -d -s "$agent" \
        "bash ${WORKER_WRAPPER} ${agent} 2>&1 | tee ${LOG_DIR}/${agent}.log"

    echo "[$(date)] Worker ${agent} started in tmux session."
}

stop_all_agents() {
    for agent in "${AGENT_LIST[@]}"; do
        touch "${AGENT_STATES_DIR}/${agent}_STOP"
    done
    echo "[$(date)] STOP signals sent to all agents."
}

# === 初始化 ===
cd "$PROJECT_DIR"
mkdir -p "$LOG_DIR" "$AGENT_STATES_DIR"

SUPERVISOR_STOP="${STATE_DIR}/SUPERVISOR_STOP"
rm -f "$SUPERVISOR_STOP"  # 清理残留

LOOP_COUNT=0
LAST_PENDING_ALERT=0
LAST_POOL_ALERT=0

echo "========================================="
echo "  Supervisor v2"
echo "  Agents: ${AGENT_LIST[*]}"
echo "  Loop interval: ${LOOP_INTERVAL}s"
echo "  Budget: \$${WEEKLY_BUDGET_USD}/week"
echo "  Pool low water: ${POOL_LOW_WATER}"
echo "  Auto rearm: ${AUTO_REARM}"
echo "  Stop: ${SUPERVISOR_STOP}"
echo "========================================="
echo ""

# 启动整点报告（如果还没在运行）
if ! tmux has-session -t ashare_rawdata_hourly_report 2>/dev/null; then
    echo "[$(date)] Starting hourly report loop..."
    tmux new-session -d -s ashare_rawdata_hourly_report \
        "cd ${PROJECT_DIR} && bash ${HOURLY_REPORT}" 2>/dev/null || true
fi

# 初始启动所有 worker
for agent in "${AGENT_LIST[@]}"; do
    if ! tmux has-session -t "$agent" 2>/dev/null; then
        # 先做一次 dispatch
        echo "[$(date)] Initial dispatch for ${agent}..."
        python "$AUTO_DISPATCH" --agent "$agent" --allow-stopped 2>&1 || true
        restart_worker "$agent"
    else
        echo "[$(date)] Worker ${agent} already running."
    fi
done

tg_send "🚀 Supervisor v2 启动: ${AGENT_LIST[*]}"

# === 主循环 ===
while true; do
    [ -f "$SUPERVISOR_STOP" ] && {
        echo "[$(date)] SUPERVISOR_STOP detected. Shutting down."
        tg_send "🛑 Supervisor 停止"
        break
    }

    LOOP_COUNT=$((LOOP_COUNT + 1))

    # --- 1. Worker 健康检查 ---
    for agent in "${AGENT_LIST[@]}"; do
        if ! tmux has-session -t "$agent" 2>/dev/null; then
            # Worker 不在了，检查是否该重启
            status=$(get_state_field "$agent" "status")
            phase=$(get_state_field "$agent" "runtime_phase")

            if [ "$phase" = "pool_empty" ]; then
                # 方向池空导致的停止，不重启，等方向池补充
                continue
            fi

            if [ "$phase" = "needs_intervention" ]; then
                # 需要人工干预，不自动重启
                continue
            fi

            echo "[$(date)] Worker ${agent} died (status=${status}, phase=${phase}). Restarting." | tee -a "${LOG_DIR}/supervisor.log"
            tg_send "⚠️ ${agent} 崩溃 (status=${status})，自动重启"

            # 先 dispatch
            python "$AUTO_DISPATCH" --agent "$agent" --allow-stopped 2>&1 || true
            restart_worker "$agent"

        else
            # tmux 在但检查 wrapper 进程是否活着
            if ! pgrep -f "worker_wrapper.*${agent}" >/dev/null 2>&1; then
                # Stale tmux session
                echo "[$(date)] Stale tmux for ${agent}. Cleaning up." | tee -a "${LOG_DIR}/supervisor.log"
                tmux kill-session -t "$agent" 2>/dev/null || true
                python "$AUTO_DISPATCH" --agent "$agent" --allow-stopped 2>&1 || true
                restart_worker "$agent"
            fi
        fi
    done

    # --- 2. 预算检查（每 10 轮 = ~30 分钟）---
    if (( LOOP_COUNT % 10 == 0 )); then
        SPENT=$(get_weekly_spend)
        if is_over_budget "$SPENT"; then
            echo "[$(date)] BUDGET EXCEEDED: \$${SPENT}/\$${WEEKLY_BUDGET_USD}" | tee -a "${LOG_DIR}/supervisor.log"
            tg_send "🔴 预算熔断: \$${SPENT}/\$${WEEKLY_BUDGET_USD}。全部 worker 停止。"
            stop_all_agents
            break
        fi
    fi

    # --- 3. 方向池水位检查 ---
    AVAILABLE=$(get_pool_available_count)
    CLAIMED=$(get_pool_claimed_count)
    NOW_TS=$(date +%s)

    if (( AVAILABLE <= POOL_LOW_WATER )); then
        # 每小时最多提醒一次
        if (( NOW_TS - LAST_POOL_ALERT > 3600 )); then
            echo "[$(date)] Pool low: ${AVAILABLE} available, ${CLAIMED} claimed" | tee -a "${LOG_DIR}/supervisor.log"
            tg_send "📊 方向池水位低: 可用 ${AVAILABLE} | 进行中 ${CLAIMED}。请补充方向或启动 scout。"
            LAST_POOL_ALERT=$NOW_TS
        fi
    fi

    # --- 4. Pending 堆积检查 ---
    PENDING=$(get_pending_count)
    if (( PENDING >= PENDING_ALERT_THRESHOLD )); then
        if (( NOW_TS - LAST_PENDING_ALERT > 3600 )); then
            tg_send "📋 ${PENDING} 个特征待审核，请 review"
            LAST_PENDING_ALERT=$NOW_TS
        fi
    fi

    # --- 5. Auto-rearm idle/stopped workers ---
    if [ "$AUTO_REARM" = "true" ]; then
        for agent in "${AGENT_LIST[@]}"; do
            # 只处理不在 tmux 中的 worker
            if ! tmux has-session -t "$agent" 2>/dev/null; then
                status=$(get_state_field "$agent" "status")
                phase=$(get_state_field "$agent" "runtime_phase")

                # 跳过需要干预或方向池空的
                [ "$phase" = "needs_intervention" ] && continue
                [ "$phase" = "pool_empty" ] && continue

                if [ "$status" = "idle" ] || [ "$status" = "assigned" ]; then
                    echo "[$(date)] Auto-rearming ${agent} (status=${status})" | tee -a "${LOG_DIR}/supervisor.log"
                    python "$AUTO_DISPATCH" --agent "$agent" 2>&1 || true
                    DISPATCH_RC=$?
                    if [ "$DISPATCH_RC" -eq 0 ]; then
                        restart_worker "$agent"
                    fi
                fi
            fi
        done
    fi

    sleep "$LOOP_INTERVAL"
done

echo "[$(date)] ===== Supervisor exited ====="
