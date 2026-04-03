#!/bin/bash
#
# A股 RawData 研究员 Worker Wrapper v2
#
# 基于 agent-orchestration 模式重构：
#   dispatch (0 token) → briefing (Sonnet/Python) → working (Opus) → postprocess (0 token) → cooldown
#
# Usage:
#   bash orchestration/v2/worker_wrapper.sh ashare_rawdata_a
#
# 在 tmux 中启动:
#   tmux new-session -d -s ashare_rawdata_a \
#     "bash orchestration/v2/worker_wrapper.sh ashare_rawdata_a 2>&1 | tee orchestration/logs/ashare_rawdata_a.log"
#
# 停止:
#   touch orchestration/state/agent_states/ashare_rawdata_a_STOP
#

set -euo pipefail

# === 参数检查 ===
AGENT_ID="${1:-}"
if [ -z "$AGENT_ID" ]; then
    echo "Usage: $0 <agent_id>"
    exit 1
fi

# === 配置 ===
PROJECT_DIR="/home/gkh/claude_tasks/ashare_rawdata"
STATE_DIR="${PROJECT_DIR}/orchestration/state/agent_states"
BRIEFING_DIR="${PROJECT_DIR}/orchestration/state/briefings"
LOG_DIR="${PROJECT_DIR}/orchestration/logs"
PROMPT_FILE="${PROJECT_DIR}/orchestration/v2/prompts/researcher_lean.md"
TG_SEND="${PROJECT_DIR}/orchestration/tg_send.py"
COST_TRACKER="${PROJECT_DIR}/orchestration/state/cost_tracker.yaml"
SENT_REPORTS="${PROJECT_DIR}/orchestration/state/.last_sent_reports"
RUNTIME_ENV_FILE="${PROJECT_DIR}/orchestration/researcher_runtime_env.sh"
AUTO_DISPATCH="${PROJECT_DIR}/orchestration/v2/auto_dispatch.py"
BRIEFING_GEN="${PROJECT_DIR}/orchestration/v2/generate_briefing.py"

CONFIG_FILE="${PROJECT_DIR}/orchestration/config.yaml"
MAX_TURNS=$(grep 'max_turns_per_cycle' "$CONFIG_FILE" | awk '{print $2}' || echo 150)
COOLDOWN=$(grep 'cooldown_seconds' "$CONFIG_FILE" | awk '{print $2}' || echo 120)
PERMISSION_MODE=$(grep 'permission_mode' "$CONFIG_FILE" | awk '{print $2}' || echo "bypassPermissions")
MODEL=$(grep '  model:' "$CONFIG_FILE" | awk '{print $2}' || echo "")
EFFORT=$(grep '  effort:' "$CONFIG_FILE" | awk '{print $2}' || echo "")
RAY_CPU_LIMIT=$(grep 'ray_num_cpus_per_researcher' "$CONFIG_FILE" | awk '{print $2}' || echo 16)
WEEKLY_BUDGET_USD=$(grep 'weekly_limit_usd' "$CONFIG_FILE" | awk '{print $2}' || echo 500)

# Wrapup timeout（分钟）— AI 会话最长运行时间
WRAPUP_MINUTES=${WRAPUP_MINUTES:-90}
POST_COMPLETE_TIMEOUT=300

# CPU 资源隔离
export OMP_NUM_THREADS="$RAY_CPU_LIMIT"
export MKL_NUM_THREADS="$RAY_CPU_LIMIT"
export NUMBA_NUM_THREADS="$RAY_CPU_LIMIT"
export PYTHON_CPU_COUNT="$RAY_CPU_LIMIT"

if [ -f "$RUNTIME_ENV_FILE" ]; then
    # shellcheck disable=SC1090
    source "$RUNTIME_ENV_FILE"
fi

case "$AGENT_ID" in
    ashare_rawdata_a) CPU_RANGE="0-$((RAY_CPU_LIMIT - 1))" ;;
    ashare_rawdata_b) CPU_RANGE="${RAY_CPU_LIMIT}-$((RAY_CPU_LIMIT * 2 - 1))" ;;
    ashare_rawdata_c) CPU_RANGE="$((RAY_CPU_LIMIT * 2))-$((RAY_CPU_LIMIT * 3 - 1))" ;;
    ashare_rawdata_d) CPU_RANGE="$((RAY_CPU_LIMIT * 3))-$((RAY_CPU_LIMIT * 4 - 1))" ;;
    *) CPU_RANGE="0-$((RAY_CPU_LIMIT - 1))" ;;
esac
TASKSET_PREFIX="taskset -c ${CPU_RANGE}"

# === 成本追踪（复用 v1 逻辑）===

init_cost_tracker() {
    if [ ! -f "$COST_TRACKER" ]; then
        cat > "$COST_TRACKER" <<YAML
weekly_budget_usd: ${WEEKLY_BUDGET_USD}
week_start: ""
week_total_usd: 0.0
records: []
YAML
    fi
}

get_week_start() {
    date -d "$(date +%Y-%m-%d) - $(( ($(date +%u) - 1) )) days" +%Y-%m-%d
}

check_weekly_budget() {
    init_cost_tracker
    local current_week tracker_week
    current_week=$(get_week_start)
    tracker_week=$(grep '^week_start:' "$COST_TRACKER" | awk '{print $2}' | tr -d '"')

    if [ "$tracker_week" != "$current_week" ]; then
        local old_total
        old_total=$(grep '^week_total_usd:' "$COST_TRACKER" | awk '{print $2}')
        cat > "$COST_TRACKER" <<YAML
weekly_budget_usd: ${WEEKLY_BUDGET_USD}
week_start: "${current_week}"
week_total_usd: 0.0
last_week_total_usd: ${old_total:-0.0}
records: []
YAML
        return 0
    fi

    local total
    total=$(grep '^week_total_usd:' "$COST_TRACKER" | awk '{print $2}')
    if echo "$total $WEEKLY_BUDGET_USD" | awk '{exit !($1 >= $2)}'; then
        return 1
    fi
    return 0
}

record_cycle_cost() {
    local cost_usd=$1 agent=$2 cycle_num=$3
    local timestamp
    timestamp=$(date +%Y-%m-%dT%H:%M:%S)

    init_cost_tracker
    local current_week tracker_week
    current_week=$(get_week_start)
    tracker_week=$(grep '^week_start:' "$COST_TRACKER" | awk '{print $2}' | tr -d '"')
    [ "$tracker_week" != "$current_week" ] && check_weekly_budget

    local old_total new_total
    old_total=$(grep '^week_total_usd:' "$COST_TRACKER" | awk '{print $2}')
    new_total=$(echo "$old_total $cost_usd" | awk '{printf "%.4f", $1 + $2}')

    sed -i "s/^week_total_usd: .*/week_total_usd: ${new_total}/" "$COST_TRACKER"
    sed -i "/^records:/a\\  - {agent: \"${agent}\", cycle: ${cycle_num}, cost_usd: ${cost_usd}, total_usd: ${new_total}, at: \"${timestamp}\"}" "$COST_TRACKER"

    local threshold
    threshold=$(echo "$WEEKLY_BUDGET_USD" | awk '{printf "%.2f", $1 * 0.8}')
    if echo "$new_total $threshold $old_total" | awk '{exit !($1 >= $2 && $3 < $2)}'; then
        python "$TG_SEND" --text "⚠️ A股RawData预算预警: 本周累计 \$${new_total} 已达 80%。" 2>&1 || true
    fi
}

# === Phase 更新 ===
update_phase() {
    local phase=$1
    python3 - "$STATE_DIR/${AGENT_ID}.yaml" "$phase" <<'PY'
import sys
sys.path.insert(0, '.')
from scripts.utils.state_manager import update_state
update_state(sys.argv[1], {'runtime_phase': sys.argv[2]})
PY
    echo "[$(date)] Phase: ${phase}"
}

# === 辅助函数 ===
get_state_field() {
    grep "^${1}:" "$STATE_DIR/${AGENT_ID}.yaml" 2>/dev/null | head -1 | sed "s/^${1}: *//" | tr -d '"' || echo ""
}

get_state_mtime_ns() {
    python3 -c "import os; print(os.stat('$STATE_DIR/${AGENT_ID}.yaml').st_mtime_ns)" 2>/dev/null || echo 0
}

maybe_send_report_fallback() {
    local log_file=$1
    local status report_path report_basename

    status=$(get_state_field "status")
    [ "$status" != "idle" ] && return 0

    # 从 state 的 last_checkpoint.report_path 读
    report_path=$(python3 -c "
import yaml
with open('$STATE_DIR/${AGENT_ID}.yaml') as f:
    s = yaml.safe_load(f) or {}
print((s.get('last_checkpoint') or {}).get('report_path', ''))
" 2>/dev/null || echo "")

    [ -z "$report_path" ] && return 0
    [[ "$report_path" != /* ]] && report_path="${PROJECT_DIR}/${report_path}"
    [ ! -f "$report_path" ] && return 0

    report_basename=$(basename "$report_path")
    touch "$SENT_REPORTS"
    grep -qF "$report_basename" "$SENT_REPORTS" 2>/dev/null && return 0

    echo "[$(date)] Shell fallback: sending unsent report ${report_basename}..." | tee -a "$log_file"
    if python "$TG_SEND" --file "$report_path" 2>&1 | tee -a "$log_file"; then
        echo "$report_basename" >> "$SENT_REPORTS"
    fi
}

monitor_claude_process() {
    local claude_pid=$1 log_file=$2 state_mtime_before=$3
    local saw_non_idle=0

    while kill -0 "$claude_pid" 2>/dev/null; do
        local current_status current_mtime_ns
        current_status=$(get_state_field "status")
        current_mtime_ns=$(get_state_mtime_ns)

        [ "$current_status" != "idle" ] && [ "$current_status" != "unknown" ] && saw_non_idle=1

        # STOP 信号
        if [ -f "$STATE_DIR/${AGENT_ID}_STOP" ]; then
            if [ "$current_status" = "idle" ] && [ "$saw_non_idle" -eq 1 ]; then
                echo "[$(date)] Monitor: STOP + idle. Killing claude..." | tee -a "$log_file"
                kill "$claude_pid" 2>/dev/null || true
                sleep 5
                kill -9 "$claude_pid" 2>/dev/null || true
                return 0
            fi
        fi

        # 研究完成检测
        if [ "$current_status" = "idle" ] && [ "$saw_non_idle" -eq 1 ]; then
            echo "[$(date)] Monitor: research complete (idle). Waiting ${POST_COMPLETE_TIMEOUT}s..." | tee -a "$log_file"
            local waited=0
            while kill -0 "$claude_pid" 2>/dev/null && [ "$waited" -lt "$POST_COMPLETE_TIMEOUT" ]; do
                sleep 10
                waited=$((waited + 10))
            done
            if kill -0 "$claude_pid" 2>/dev/null; then
                echo "[$(date)] Monitor: Force killing after timeout..." | tee -a "$log_file"
                kill "$claude_pid" 2>/dev/null || true
                sleep 5
                kill -9 "$claude_pid" 2>/dev/null || true
            fi
            return 0
        fi

        sleep 30
    done
}

# === 初始化 ===
mkdir -p "$LOG_DIR" "$STATE_DIR" "$BRIEFING_DIR"
cd "$PROJECT_DIR"
init_cost_tracker

STOP_FILE="${STATE_DIR}/${AGENT_ID}_STOP"
STATE_FILE="${STATE_DIR}/${AGENT_ID}.yaml"
CYCLE=0

# 初始化状态文件（如不存在）
if [ ! -f "$STATE_FILE" ]; then
    cat > "$STATE_FILE" <<YAML
agent_id: "${AGENT_ID}"
status: idle
task_type: research
cycle_count: 0
consecutive_failures: 0
current_direction: null
current_direction_id: null
pending_features: []
last_checkpoint: {}
last_cycle_at: null
notes: "v2 初始化"
YAML
fi

echo "========================================="
echo "  Worker v2: ${AGENT_ID}"
echo "  Model: ${MODEL:-default} | Effort: ${EFFORT:-default}"
echo "  CPU: ${CPU_RANGE} (${RAY_CPU_LIMIT} cores)"
echo "  Wrapup: ${WRAPUP_MINUTES}min | Cooldown: ${COOLDOWN}s"
echo "  Budget: \$${WEEKLY_BUDGET_USD}/week"
echo "  Stop: ${STOP_FILE}"
echo "========================================="
echo ""

# === 主循环 ===
set +e
while true; do
    CYCLE=$((CYCLE + 1))
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    LOG_FILE="${LOG_DIR}/${AGENT_ID}_cycle${CYCLE}_${TIMESTAMP}.log"

    echo "[$(date)] ===== Cycle ${CYCLE} starting =====" | tee -a "$LOG_FILE"

    # --- Pre-checks ---
    if [ -f "$STOP_FILE" ]; then
        echo "[$(date)] STOP signal. Exiting." | tee -a "$LOG_FILE"
        rm -f "$STOP_FILE"
        break
    fi

    if ! check_weekly_budget; then
        TOTAL=$(grep '^week_total_usd:' "$COST_TRACKER" | awk '{print $2}')
        echo "[$(date)] BUDGET EXCEEDED: \$${TOTAL}. Stopping." | tee -a "$LOG_FILE"
        python "$TG_SEND" --text "⚠️ 预算熔断: ${AGENT_ID} 停止。\$${TOTAL}/\$${WEEKLY_BUDGET_USD}" 2>&1 || true
        break
    fi

    # === Phase: DISPATCH (0 AI tokens) ===
    update_phase "dispatch"
    echo "[$(date)] Running auto-dispatch..." | tee -a "$LOG_FILE"

    python "$AUTO_DISPATCH" --agent "$AGENT_ID" 2>&1 | tee -a "$LOG_FILE"
    DISPATCH_RC=${PIPESTATUS[0]}

    case $DISPATCH_RC in
        0) echo "[$(date)] Dispatch: task assigned." | tee -a "$LOG_FILE" ;;
        1)
            echo "[$(date)] Dispatch: needs intervention. Pausing." | tee -a "$LOG_FILE"
            update_phase "needs_intervention"
            python "$TG_SEND" --text "⚠️ ${AGENT_ID} 需要人工干预" 2>&1 || true
            break
            ;;
        2)
            echo "[$(date)] Dispatch: pool empty. Pausing." | tee -a "$LOG_FILE"
            update_phase "pool_empty"
            python "$TG_SEND" --text "📭 方向池空，${AGENT_ID} 暂停" 2>&1 || true
            break
            ;;
        *)
            echo "[$(date)] Dispatch: error (rc=$DISPATCH_RC). Retrying after cooldown." | tee -a "$LOG_FILE"
            sleep "$COOLDOWN"
            continue
            ;;
    esac

    # === Phase: BRIEFING (Sonnet/Python, 低成本) ===
    update_phase "briefing"
    TASK_CARD=$(get_state_field "task_card")
    BRIEFING_FILE="${BRIEFING_DIR}/${AGENT_ID}_cycle${CYCLE}.md"

    echo "[$(date)] Generating briefing..." | tee -a "$LOG_FILE"
    python "$BRIEFING_GEN" \
        --agent "$AGENT_ID" \
        --task-card "$TASK_CARD" \
        --output "$BRIEFING_FILE" \
        2>&1 | tee -a "$LOG_FILE"

    if [ ! -f "$BRIEFING_FILE" ]; then
        echo "[$(date)] Briefing generation failed, using fallback." | tee -a "$LOG_FILE"
        # Fallback: 最小化 briefing
        cat > "$BRIEFING_FILE" <<EOF
# Briefing
方向: $(get_state_field "current_direction") ($(get_state_field "current_direction_id"))
请先阅读 research/KNOWLEDGE-BASE.md 和 docs/BACKTEST.md
EOF
    fi

    # === Phase: WORKING (Opus, 主要 token 消耗) ===
    update_phase "working"

    # 转为 in_progress
    python3 - "$STATE_FILE" <<'PY'
import sys
sys.path.insert(0, '.')
from scripts.utils.state_manager import update_state
update_state(sys.argv[1], {'status': 'in_progress'})
PY

    # Wrapup timer
    (sleep $((WRAPUP_MINUTES * 60)); touch "${STATE_DIR}/${AGENT_ID}_WRAPUP") &
    WRAPUP_PID=$!

    # 构建 prompt
    SYSTEM_PROMPT=$(cat "$PROMPT_FILE")
    BRIEFING_CONTENT=$(cat "$BRIEFING_FILE")

    PROMPT="你是 A股 RawData 研究员 ${AGENT_ID}，第 ${CYCLE} 个研究周期。
所有命令从 ${PROJECT_DIR} 运行。

你的状态文件: orchestration/state/agent_states/${AGENT_ID}.yaml
Task card: ${TASK_CARD}

严格遵循 lean prompt 中的工作流。Briefing 如下。"

    MODEL_FLAG=""
    EFFORT_FLAG=""
    [ -n "$MODEL" ] && MODEL_FLAG="--model $MODEL"
    [ -n "$EFFORT" ] && EFFORT_FLAG="--effort $EFFORT"

    STATE_MTIME_BEFORE=$(get_state_mtime_ns)

    echo "[$(date)] Starting Claude session (max_turns=${MAX_TURNS})..." | tee -a "$LOG_FILE"

    $TASKSET_PREFIX claude --print \
        --output-format stream-json --verbose \
        --permission-mode "$PERMISSION_MODE" \
        --max-turns "$MAX_TURNS" \
        $MODEL_FLAG $EFFORT_FLAG \
        --append-system-prompt "${SYSTEM_PROMPT}

---

${BRIEFING_CONTENT}" \
        -p "$PROMPT" \
        2>&1 | tee -a "$LOG_FILE" &
    CLAUDE_PIPE_PID=$!

    sleep 2
    CLAUDE_PID=$(ps -eo pid,ppid,comm --no-headers | awk -v ppid=$$ '$2 == ppid && $3 == "claude" {print $1}' | head -1)
    [ -z "$CLAUDE_PID" ] && CLAUDE_PID=$CLAUDE_PIPE_PID

    # 后台监控
    monitor_claude_process "$CLAUDE_PID" "$LOG_FILE" "$STATE_MTIME_BEFORE" &
    MONITOR_PID=$!

    wait $CLAUDE_PIPE_PID 2>/dev/null
    EXIT_CODE=$?

    kill "$WRAPUP_PID" 2>/dev/null || true
    kill "$MONITOR_PID" 2>/dev/null || true
    wait "$MONITOR_PID" 2>/dev/null || true
    rm -f "${STATE_DIR}/${AGENT_ID}_WRAPUP"

    echo "[$(date)] Claude session ended (rc=${EXIT_CODE})" | tee -a "$LOG_FILE"

    # === Phase: POSTPROCESS (0 AI tokens) ===
    update_phase "postprocess"

    # 报告发送兜底
    maybe_send_report_fallback "$LOG_FILE"

    # 成本提取
    CYCLE_COST=$(grep -o '"total_cost_usd":[0-9.]*' "$LOG_FILE" | tail -1 | cut -d: -f2 || true)
    if [ -n "$CYCLE_COST" ] && [ "$CYCLE_COST" != "0" ]; then
        record_cycle_cost "$CYCLE_COST" "$AGENT_ID" "$CYCLE"
        WEEK_TOTAL=$(grep '^week_total_usd:' "$COST_TRACKER" | awk '{print $2}')
        echo "[$(date)] Cost: \$${CYCLE_COST} | Week: \$${WEEK_TOTAL}/\$${WEEKLY_BUDGET_USD}" | tee -a "$LOG_FILE"
    fi

    # KB 重新生成
    echo "[$(date)] Regenerating KB..." | tee -a "$LOG_FILE"
    python scripts/regenerate_kb.py 2>&1 | tee -a "$LOG_FILE" || true

    # 清理 briefing 文件（保留最近 5 个）
    ls -1t "${BRIEFING_DIR}/${AGENT_ID}"_*.md 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true

    # === 再次检查停止信号 ===
    if [ -f "$STOP_FILE" ]; then
        echo "[$(date)] STOP after cycle. Exiting." | tee -a "$LOG_FILE"
        rm -f "$STOP_FILE"
        break
    fi

    # === Phase: COOLDOWN ===
    update_phase "cooldown"
    echo "[$(date)] Cycle ${CYCLE} done. Cooling down ${COOLDOWN}s..." | tee -a "$LOG_FILE"
    sleep "$COOLDOWN"
done

echo "[$(date)] ===== ${AGENT_ID} v2 wrapper exited after ${CYCLE} cycles =====" | tee -a "$LOG_FILE"
