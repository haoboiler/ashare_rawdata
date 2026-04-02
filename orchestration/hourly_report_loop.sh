#!/bin/bash
#
# 常驻整点播报循环。
# 立即发送一次状态，然后在每个整点再次执行 hourly_report.sh。
#

set -euo pipefail

PROJECT_DIR="/home/gkh/claude_tasks/ashare_rawdata"
REPORT_SCRIPT="${PROJECT_DIR}/orchestration/hourly_report.sh"

cd "$PROJECT_DIR"

if [ ! -x "$REPORT_SCRIPT" ]; then
    echo "hourly report script not found or not executable: $REPORT_SCRIPT" >&2
    exit 1
fi

echo "[$(date)] hourly_report_loop started"
bash "$REPORT_SCRIPT"

while true; do
    now_epoch=$(date +%s)
    next_hour_epoch=$(( ((now_epoch / 3600) + 1) * 3600 ))
    sleep_seconds=$((next_hour_epoch - now_epoch))
    if [ "$sleep_seconds" -lt 1 ]; then
        sleep_seconds=1
    fi
    echo "[$(date)] next hourly report in ${sleep_seconds}s"
    sleep "$sleep_seconds"
    bash "$REPORT_SCRIPT"
done
