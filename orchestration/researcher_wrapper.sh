#!/bin/bash
#
# A股 RawData 研究员 Agent 外部循环脚本
#
# 每次循环启动一个独立的 Claude Code 一次性会话，
# 会话完成后检查产出、追踪成本、冷却后进入下一个循环。
#
# Usage:
#   bash orchestration/researcher_wrapper.sh ashare_rawdata_a
#
# 在 tmux 中启动:
#   tmux new-session -d -s ashare_rawdata_a "bash orchestration/researcher_wrapper.sh ashare_rawdata_a 2>&1 | tee orchestration/logs/ashare_rawdata_a.log"
#
# 停止:
#   touch orchestration/state/agent_states/ashare_rawdata_a_STOP
#

set -euo pipefail

# === 参数检查 ===
AGENT_ID="${1:-}"
if [ -z "$AGENT_ID" ]; then
    echo "Usage: $0 <agent_id>"
    echo "Example: $0 ashare_rawdata_a"
    exit 1
fi

# === 配置 ===
PROJECT_DIR="/home/gkh/claude_tasks/ashare_rawdata"
STATE_DIR="${PROJECT_DIR}/orchestration/state/agent_states"
LOG_DIR="${PROJECT_DIR}/orchestration/logs"
PROMPT_FILE="${PROJECT_DIR}/orchestration/prompts/researcher.md"
TG_SEND="${PROJECT_DIR}/orchestration/tg_send.py"
TG_CONFIG="${PROJECT_DIR}/orchestration/config.yaml"
COST_TRACKER="${PROJECT_DIR}/orchestration/state/cost_tracker.yaml"

# 从 config.yaml 读取配置
CONFIG_FILE="${PROJECT_DIR}/orchestration/config.yaml"
MAX_TURNS=$(grep 'max_turns_per_cycle' "$CONFIG_FILE" | awk '{print $2}' || echo 150)
COOLDOWN=$(grep 'cooldown_seconds' "$CONFIG_FILE" | awk '{print $2}' || echo 120)
PERMISSION_MODE=$(grep 'permission_mode' "$CONFIG_FILE" | awk '{print $2}' || echo "bypassPermissions")
MODEL=$(grep '  model:' "$CONFIG_FILE" | awk '{print $2}' || echo "")
EFFORT=$(grep '  effort:' "$CONFIG_FILE" | awk '{print $2}' || echo "")
RAY_CPU_LIMIT=$(grep 'ray_num_cpus_per_researcher' "$CONFIG_FILE" | awk '{print $2}' || echo 16)
WEEKLY_BUDGET_USD=$(grep 'weekly_limit_usd' "$CONFIG_FILE" | awk '{print $2}' || echo 500)

# CPU 资源隔离
export OMP_NUM_THREADS="$RAY_CPU_LIMIT"
export MKL_NUM_THREADS="$RAY_CPU_LIMIT"
export NUMBA_NUM_THREADS="$RAY_CPU_LIMIT"
export PYTHON_CPU_COUNT="$RAY_CPU_LIMIT"

case "$AGENT_ID" in
    ashare_rawdata_a) CPU_RANGE="0-$((RAY_CPU_LIMIT - 1))" ;;
    ashare_rawdata_b) CPU_RANGE="${RAY_CPU_LIMIT}-$((RAY_CPU_LIMIT * 2 - 1))" ;;
    ashare_rawdata_c) CPU_RANGE="$((RAY_CPU_LIMIT * 2))-$((RAY_CPU_LIMIT * 3 - 1))" ;;
    ashare_rawdata_d) CPU_RANGE="$((RAY_CPU_LIMIT * 3))-$((RAY_CPU_LIMIT * 4 - 1))" ;;
    *) CPU_RANGE="0-$((RAY_CPU_LIMIT - 1))" ;;
esac
TASKSET_PREFIX="taskset -c ${CPU_RANGE}"

# 状态完成后超时时间（秒）
POST_COMPLETE_TIMEOUT=300  # 5 分钟

# === 成本追踪函数 ===

init_cost_tracker() {
    if [ ! -f "$COST_TRACKER" ]; then
        cat > "$COST_TRACKER" <<YAML
# 周预算成本追踪器 — 由 researcher_wrapper.sh 自动维护
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
    local current_week
    current_week=$(get_week_start)
    local tracker_week
    tracker_week=$(grep '^week_start:' "$COST_TRACKER" | awk '{print $2}' | tr -d '"')

    if [ "$tracker_week" != "$current_week" ]; then
        local old_total
        old_total=$(grep '^week_total_usd:' "$COST_TRACKER" | awk '{print $2}')
        cat > "$COST_TRACKER" <<YAML
# 周预算成本追踪器 — 由 researcher_wrapper.sh 自动维护
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
        return 1  # 超预算
    fi
    return 0
}

record_cycle_cost() {
    local cost_usd=$1
    local agent=$2
    local cycle_num=$3
    local timestamp
    timestamp=$(date +%Y-%m-%dT%H:%M:%S)

    init_cost_tracker
    local current_week
    current_week=$(get_week_start)
    local tracker_week
    tracker_week=$(grep '^week_start:' "$COST_TRACKER" | awk '{print $2}' | tr -d '"')

    if [ "$tracker_week" != "$current_week" ]; then
        check_weekly_budget
    fi

    local old_total
    old_total=$(grep '^week_total_usd:' "$COST_TRACKER" | awk '{print $2}')
    local new_total
    new_total=$(echo "$old_total $cost_usd" | awk '{printf "%.4f", $1 + $2}')

    sed -i "s/^week_total_usd: .*/week_total_usd: ${new_total}/" "$COST_TRACKER"
    sed -i "/^records:/a\\  - {agent: \"${agent}\", cycle: ${cycle_num}, cost_usd: ${cost_usd}, total_usd: ${new_total}, at: \"${timestamp}\"}" "$COST_TRACKER"

    # 80% 预警
    local threshold
    threshold=$(echo "$WEEKLY_BUDGET_USD" | awk '{printf "%.2f", $1 * 0.8}')
    if echo "$new_total $threshold $old_total" | awk '{exit !($1 >= $2 && $3 < $2)}'; then
        python "$TG_SEND" --text "⚠️ A股RawData预算预警: 本周累计 \$${new_total} 已达周预算 \$${WEEKLY_BUDGET_USD} 的 80%。" 2>&1 || true
    fi
}

# === 初始化 ===
mkdir -p "$LOG_DIR" "$STATE_DIR"
cd "$PROJECT_DIR"
init_cost_tracker

STOP_FILE="${STATE_DIR}/${AGENT_ID}_STOP"
STATE_FILE="${STATE_DIR}/${AGENT_ID}.yaml"
CYCLE=0

# 如果状态文件不存在，创建初始状态
if [ ! -f "$STATE_FILE" ]; then
    cat > "$STATE_FILE" <<YAML
# A股 RawData 研究员状态文件 — 由 researcher_wrapper.sh 初始化
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
notes: "初始化"
YAML
fi

echo "========================================="
echo "  A股 RawData 研究员 Agent 启动: ${AGENT_ID}"
echo "  项目目录: ${PROJECT_DIR}"
echo "  最大 turns: ${MAX_TURNS}"
echo "  冷却时间: ${COOLDOWN}s"
echo "  完成后超时: ${POST_COMPLETE_TIMEOUT}s"
echo "  模型: ${MODEL:-default}"
echo "  思考深度: ${EFFORT:-default}"
echo "  CPU 限制: ${CPU_RANGE} (${RAY_CPU_LIMIT} cores)"
echo "  周预算: \$${WEEKLY_BUDGET_USD}"
echo "  停止信号: ${STOP_FILE}"
echo "========================================="
echo ""

# === 后台监控函数 ===
monitor_claude_process() {
    local claude_pid=$1
    local log_file=$2
    local state_file_mtime_before=$3

    while kill -0 "$claude_pid" 2>/dev/null; do
        # 检查 STOP 信号
        if [ -f "$STOP_FILE" ]; then
            local current_mtime
            current_mtime=$(stat -c %Y "$STATE_FILE" 2>/dev/null || echo "0")
            if [ "$current_mtime" != "$state_file_mtime_before" ]; then
                echo "[$(date)] Monitor: STOP + state updated. Killing claude (PID=$claude_pid)..." | tee -a "$log_file"
                kill "$claude_pid" 2>/dev/null || true
                sleep 5
                kill -9 "$claude_pid" 2>/dev/null || true
                return 0
            else
                echo "[$(date)] Monitor: STOP detected, research in progress. Waiting..." | tee -a "$log_file"
            fi
        fi

        # 检查状态文件更新（研究完成）
        local current_mtime
        current_mtime=$(stat -c %Y "$STATE_FILE" 2>/dev/null || echo "0")
        if [ "$current_mtime" != "$state_file_mtime_before" ]; then
            echo "[$(date)] Monitor: State file updated. Waiting ${POST_COMPLETE_TIMEOUT}s for exit..." | tee -a "$log_file"
            local waited=0
            while kill -0 "$claude_pid" 2>/dev/null && [ "$waited" -lt "$POST_COMPLETE_TIMEOUT" ]; do
                sleep 10
                waited=$((waited + 10))
            done
            if kill -0 "$claude_pid" 2>/dev/null; then
                echo "[$(date)] Monitor: Force killing after timeout (PID=$claude_pid)..." | tee -a "$log_file"
                kill "$claude_pid" 2>/dev/null || true
                sleep 5
                kill -9 "$claude_pid" 2>/dev/null || true
            fi
            return 0
        fi

        sleep 30
    done
}

# === 主循环 ===
set +e
while true; do
    CYCLE=$((CYCLE + 1))
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    LOG_FILE="${LOG_DIR}/${AGENT_ID}_cycle${CYCLE}_${TIMESTAMP}.log"

    echo "[$(date)] ===== Cycle ${CYCLE} starting =====" | tee -a "$LOG_FILE"

    # --- 检查周预算 ---
    if ! check_weekly_budget; then
        TOTAL=$(grep '^week_total_usd:' "$COST_TRACKER" | awk '{print $2}')
        echo "[$(date)] BUDGET EXCEEDED: \$${TOTAL} >= \$${WEEKLY_BUDGET_USD}. Stopping." | tee -a "$LOG_FILE"
        python "$TG_SEND" --text "⚠️ A股RawData预算熔断: ${AGENT_ID} 已停止。本周累计 \$${TOTAL} 超出 \$${WEEKLY_BUDGET_USD} 上限。" 2>&1 || true
        break
    fi

    # --- 检查停止信号 ---
    if [ -f "$STOP_FILE" ]; then
        echo "[$(date)] STOP signal detected. Exiting gracefully." | tee -a "$LOG_FILE"
        rm -f "$STOP_FILE"
        break
    fi

    # --- 检查研究员状态 ---
    if [ -f "$STATE_FILE" ]; then
        STATUS=$(grep '^status:' "$STATE_FILE" | awk '{print $2}' || echo "unknown")
    else
        STATUS="idle"
    fi

    echo "[$(date)] Agent status: ${STATUS}" | tee -a "$LOG_FILE"

    if [ "$STATUS" = "stopped" ]; then
        echo "[$(date)] Agent status is 'stopped'. Exiting." | tee -a "$LOG_FILE"
        break
    fi

    # --- 提取组长指令（如有）---
    LEADER_INSTRUCTION=""
    if [ -f "$STATE_FILE" ]; then
        LEADER_INSTRUCTION=$(grep '^leader_instruction:' "$STATE_FILE" | sed 's/^leader_instruction: *"//;s/"$//' || true)
    fi

    # --- 构建 prompt ---
    PROMPT="你是 A股 RawData 研究员 ${AGENT_ID}，这是你的第 ${CYCLE} 个研究周期。

首先读取你的状态文件：
cat orchestration/state/agent_states/${AGENT_ID}.yaml

然后严格遵循 orchestration/prompts/researcher.md 中的工作流。

重要提示：
- 会话结束前必须更新你的状态文件。
- 所有命令从项目根目录 /home/gkh/claude_tasks/ashare_rawdata 运行。
- 入库方式：ashare_hf_variable 的 register + updater（详见 docs/ASHARE_ADMISSION.md）。
- A股特性：后复权(hfq)、T+1、涨跌停、停牌。
- 共享评估脚本：/home/gkh/claude_tasks/ashare_alpha/backtest/evaluate.py"

    if [ -n "$LEADER_INSTRUCTION" ]; then
        PROMPT="${PROMPT}

===== 组长特别指令 =====
${LEADER_INSTRUCTION}
========================="
    fi

    # --- 加载系统提示词 ---
    if [ ! -f "$PROMPT_FILE" ]; then
        echo "[$(date)] ERROR: Prompt file not found: $PROMPT_FILE" | tee -a "$LOG_FILE"
        sleep "$COOLDOWN"
        continue
    fi
    SYSTEM_PROMPT=$(cat "$PROMPT_FILE")

    # --- 记录状态文件 mtime ---
    STATE_MTIME_BEFORE=$(stat -c %Y "$STATE_FILE" 2>/dev/null || echo "0")

    # --- 执行 Claude Code 会话 ---
    echo "[$(date)] Starting Claude Code session (max_turns=${MAX_TURNS}, CPU=${CPU_RANGE})..." | tee -a "$LOG_FILE"

    MODEL_FLAG=""
    EFFORT_FLAG=""
    [ -n "$MODEL" ] && MODEL_FLAG="--model $MODEL"
    [ -n "$EFFORT" ] && EFFORT_FLAG="--effort $EFFORT"

    $TASKSET_PREFIX claude --print \
        --output-format stream-json --verbose \
        --permission-mode "$PERMISSION_MODE" \
        --max-turns "$MAX_TURNS" \
        $MODEL_FLAG $EFFORT_FLAG \
        --append-system-prompt "$SYSTEM_PROMPT" \
        -p "$PROMPT" \
        2>&1 | tee -a "$LOG_FILE" &
    CLAUDE_PIPE_PID=$!

    sleep 2
    CLAUDE_PID=$(ps -eo pid,ppid,comm --no-headers | awk -v ppid=$$ '$2 == ppid && $3 == "claude" {print $1}' | head -1)
    if [ -z "$CLAUDE_PID" ]; then
        CLAUDE_PID=$CLAUDE_PIPE_PID
    fi
    echo "[$(date)] Claude PID: ${CLAUDE_PID}, Pipe PID: ${CLAUDE_PIPE_PID}" | tee -a "$LOG_FILE"

    # 启动后台监控
    monitor_claude_process "$CLAUDE_PID" "$LOG_FILE" "$STATE_MTIME_BEFORE" &
    MONITOR_PID=$!
    echo "[$(date)] Monitor PID: ${MONITOR_PID}" | tee -a "$LOG_FILE"

    # 等待完成
    wait $CLAUDE_PIPE_PID 2>/dev/null
    EXIT_CODE=$?

    kill "$MONITOR_PID" 2>/dev/null || true
    wait "$MONITOR_PID" 2>/dev/null || true

    echo "" | tee -a "$LOG_FILE"
    echo "[$(date)] Claude session ended with exit code: ${EXIT_CODE}" | tee -a "$LOG_FILE"

    # --- 提取成本 ---
    CYCLE_COST=$(grep -o '"total_cost_usd":[0-9.]*' "$LOG_FILE" | tail -1 | cut -d: -f2 || true)
    if [ -n "$CYCLE_COST" ] && [ "$CYCLE_COST" != "0" ]; then
        record_cycle_cost "$CYCLE_COST" "$AGENT_ID" "$CYCLE"
        WEEK_TOTAL=$(grep '^week_total_usd:' "$COST_TRACKER" | awk '{print $2}')
        echo "[$(date)] Cycle cost: \$${CYCLE_COST} | Week total: \$${WEEK_TOTAL} / \$${WEEKLY_BUDGET_USD}" | tee -a "$LOG_FILE"
    else
        echo "[$(date)] Could not extract cost from session output" | tee -a "$LOG_FILE"
    fi

    # --- 重新生成知识库 ---
    echo "[$(date)] Regenerating KNOWLEDGE-BASE.md..." | tee -a "$LOG_FILE"
    python scripts/regenerate_kb.py 2>&1 | tee -a "$LOG_FILE" || true

    # --- 再次检查停止信号 ---
    if [ -f "$STOP_FILE" ]; then
        echo "[$(date)] STOP signal detected after cycle. Exiting." | tee -a "$LOG_FILE"
        rm -f "$STOP_FILE"
        break
    fi

    # --- 冷却 ---
    echo "[$(date)] Cycle ${CYCLE} complete. Cooling down ${COOLDOWN}s..." | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    sleep "$COOLDOWN"
done

echo "[$(date)] ===== ${AGENT_ID} wrapper exited after ${CYCLE} cycles =====" | tee -a "$LOG_FILE"
