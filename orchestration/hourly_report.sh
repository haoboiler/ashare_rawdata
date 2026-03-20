#!/bin/bash
#
# 每小时 TG 播报：研究员进展 + 本周成本 + 产出统计
#

set -uo pipefail

PROJECT_DIR="/home/gkh/claude_tasks/ashare_rawdata"
STATE_DIR="${PROJECT_DIR}/orchestration/state/agent_states"
COST_TRACKER="${PROJECT_DIR}/orchestration/state/cost_tracker.yaml"
TG_SEND="${PROJECT_DIR}/orchestration/tg_send.py"
REPORT_DIR="${PROJECT_DIR}/.claude-output/reports"
EVAL_DIR="${PROJECT_DIR}/.claude-output/evaluations"
SENT_REPORTS="${PROJECT_DIR}/orchestration/state/.last_sent_reports"
cd "$PROJECT_DIR"

# === 研究员状态 ===
get_agent_status() {
    local agent_id=$1
    local state_file="${STATE_DIR}/${agent_id}.yaml"
    if [ ! -f "$state_file" ]; then
        echo "❓ ${agent_id}: 状态文件不存在"
        return
    fi
    local status=$(grep '^status:' "$state_file" | awk '{print $2}')
    local direction=$(grep '^current_direction:' "$state_file" | sed 's/^current_direction: *//')
    local direction_id=$(grep '^current_direction_id:' "$state_file" | sed 's/^current_direction_id: *//;s/"//g')
    local cycle_count=$(grep '^cycle_count:' "$state_file" | awk '{print $2}')
    local last_cycle=$(grep '^last_cycle_at:' "$state_file" | sed 's/^last_cycle_at: *//;s/"//g;s/^'\''//;s/'\''$//')
    local failures=$(grep '^consecutive_failures:' "$state_file" | awk '{print $2}')

    [ "$status" = "null" ] && status="启动中"
    [ "$direction" = "null" ] && direction="-"
    [ "$direction_id" = "null" ] && direction_id="-"
    [ "$cycle_count" = "null" ] && cycle_count="0"
    [ "$last_cycle" = "null" ] && last_cycle="-"

    local tmux_status="🔴停止"
    if tmux has-session -t "$agent_id" 2>/dev/null; then
        tmux_status="🟢运行中"
    fi

    local fail_flag=""
    if [ "${failures:-0}" -ge 3 ] 2>/dev/null; then
        fail_flag=" ⚠️连续失败${failures}次"
    fi

    local last_short="$last_cycle"
    if [[ "$last_cycle" == *"T"* ]]; then
        last_short=$(echo "$last_cycle" | sed 's/.*T//;s/\..*//')
    fi

    echo "${agent_id} ${tmux_status} | ${status} | cycle#${cycle_count} ${direction_id} ${direction} |${fail_flag} | last:${last_short}"
}

AGENT_STATUSES=""
for state_file in "$STATE_DIR"/*.yaml; do
    [ -f "$state_file" ] || continue
    agent_id=$(basename "$state_file" .yaml)
    [[ "$agent_id" == *"_STOP"* ]] && continue
    status_line=$(get_agent_status "$agent_id")
    if [ -n "$AGENT_STATUSES" ]; then
        AGENT_STATUSES="${AGENT_STATUSES}
  ${status_line}"
    else
        AGENT_STATUSES="  ${status_line}"
    fi
done

if [ -z "$AGENT_STATUSES" ]; then
    AGENT_STATUSES="  (无活跃研究员)"
fi

# === 成本统计 ===
WEEK_TOTAL="0.00"
WEEK_BUDGET="500"
WEEK_START="N/A"
if [ -f "$COST_TRACKER" ]; then
    WEEK_TOTAL=$(grep '^week_total_usd:' "$COST_TRACKER" | awk '{print $2}' || echo "0.00")
    WEEK_BUDGET=$(grep '^weekly_budget_usd:' "$COST_TRACKER" | awk '{print $2}' || echo "500")
    WEEK_START=$(grep '^week_start:' "$COST_TRACKER" | sed 's/^week_start: *//;s/"//g')
fi
REMAINING=$(echo "$WEEK_BUDGET $WEEK_TOTAL" | awk '{printf "%.2f", $1 - $2}')
PCT=$(echo "$WEEK_TOTAL $WEEK_BUDGET" | awk '{if($2>0) printf "%d", $1/$2*100; else print 0}')
PCT=${PCT:-0}

BUDGET_EMOJI="✅"
if (( PCT >= 80 )); then BUDGET_EMOJI="⚠️"; fi
if (( PCT >= 100 )); then BUDGET_EMOJI="🔴"; fi

# === 最近 1h 内新产出统计 ===
NEW_REPORTS=0
NEW_EVALS=0
if [ -d "$REPORT_DIR" ]; then
    NEW_REPORTS=$(find "$REPORT_DIR" -name "*.md" -mmin -60 2>/dev/null | wc -l)
fi
if [ -d "$EVAL_DIR" ]; then
    NEW_EVALS=$(find "$EVAL_DIR" -name "stats.json" -mmin -60 2>/dev/null | wc -l)
fi

# === Pending 统计 ===
PENDING_COUNT=0
if [ -d "${PROJECT_DIR}/research/pending-rawdata" ]; then
    PENDING_COUNT=$(find "${PROJECT_DIR}/research/pending-rawdata" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
fi

# === 组装状态消息 ===
NOW=$(date "+%Y-%m-%d %H:%M")
MSG="⏰ A股RawData整点播报 (${NOW})

📊 研究员状态:
${AGENT_STATUSES}

💰 本周成本 (${WEEK_START}起):
  ${BUDGET_EMOJI} 已用: \$${WEEK_TOTAL} / \$${WEEK_BUDGET} (${PCT}%)
  剩余: \$${REMAINING}"

if [ "$PENDING_COUNT" -gt 0 ] || [ "$NEW_EVALS" -gt 0 ]; then
    MSG="${MSG}

📦 RawData 产出:
  待审核: ${PENDING_COUNT} 个
  近1h评估: ${NEW_EVALS} 个 | 新报告: ${NEW_REPORTS} 个"
fi

# === 发送状态消息 ===
echo "[$(date)] Sending hourly report..."
python "$TG_SEND" --text "$MSG" 2>&1 || echo "[ERROR] TG status send failed"

# === 发送最近 1h 内新产出的报告（去重）===
touch "$SENT_REPORTS"
SCREENING_DIR="${PROJECT_DIR}/research/agent_reports/screening"
if [ -d "$SCREENING_DIR" ]; then
    find "$SCREENING_DIR" -name "*.md" -mmin -60 2>/dev/null | while read -r report; do
        report_basename=$(basename "$report")
        if grep -qF "$report_basename" "$SENT_REPORTS" 2>/dev/null; then
            continue
        fi
        echo "[$(date)] Sending new report: $report_basename"
        python "$TG_SEND" --file "$report" --caption "📄 新初筛报告: ${report_basename}" 2>&1 || true
        echo "$report_basename" >> "$SENT_REPORTS"
    done
fi

echo "[$(date)] Hourly report done."
