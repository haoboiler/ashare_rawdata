#!/usr/bin/env bash
set -euo pipefail
umask 0002

ROOT="/home/gkh/claude_tasks/ashare_rawdata"
cd "$ROOT"

eval "$(python3 - <<'PY'
from scripts.utils.preload_ray import (
    PRELOAD_RAY_ADDRESS,
    PRELOAD_RAY_AUTOSCALER_METRIC_PORT,
    PRELOAD_RAY_BASE_DIR,
    PRELOAD_RAY_DASHBOARD_AGENT_GRPC_PORT,
    PRELOAD_RAY_DASHBOARD_AGENT_LISTEN_PORT,
    PRELOAD_RAY_DASHBOARD_GRPC_PORT,
    PRELOAD_RAY_DASHBOARD_METRIC_PORT,
    PRELOAD_RAY_DASHBOARD_PORT,
    PRELOAD_RAY_HOST,
    PRELOAD_RAY_LOG_PATH,
    PRELOAD_RAY_MAX_WORKER_PORT,
    PRELOAD_RAY_METRICS_EXPORT_PORT,
    PRELOAD_RAY_MIN_WORKER_PORT,
    PRELOAD_RAY_OBJECT_STORE_BYTES,
    PRELOAD_RAY_PORT,
    PRELOAD_RAY_RUNTIME_DIR,
    PRELOAD_RAY_RUNTIME_ENV_AGENT_PORT,
    PRELOAD_RAY_SESSION_NAME,
)

for key, value in {
    "ADDRESS": PRELOAD_RAY_ADDRESS,
    "HOST": PRELOAD_RAY_HOST,
    "PORT": PRELOAD_RAY_PORT,
    "OBJECT_STORE": PRELOAD_RAY_OBJECT_STORE_BYTES,
    "RUNTIME_DIR": str(PRELOAD_RAY_RUNTIME_DIR),
    "LOG_PATH": str(PRELOAD_RAY_LOG_PATH),
    "SESSION_NAME": PRELOAD_RAY_SESSION_NAME,
    "MIN_WORKER_PORT": PRELOAD_RAY_MIN_WORKER_PORT,
    "MAX_WORKER_PORT": PRELOAD_RAY_MAX_WORKER_PORT,
    "DASHBOARD_AGENT_LISTEN_PORT": PRELOAD_RAY_DASHBOARD_AGENT_LISTEN_PORT,
    "DASHBOARD_AGENT_GRPC_PORT": PRELOAD_RAY_DASHBOARD_AGENT_GRPC_PORT,
    "RUNTIME_ENV_AGENT_PORT": PRELOAD_RAY_RUNTIME_ENV_AGENT_PORT,
    "METRICS_EXPORT_PORT": PRELOAD_RAY_METRICS_EXPORT_PORT,
    "DASHBOARD_PORT": PRELOAD_RAY_DASHBOARD_PORT,
    "DASHBOARD_GRPC_PORT": PRELOAD_RAY_DASHBOARD_GRPC_PORT,
    "AUTOSCALER_METRIC_PORT": PRELOAD_RAY_AUTOSCALER_METRIC_PORT,
    "DASHBOARD_METRIC_PORT": PRELOAD_RAY_DASHBOARD_METRIC_PORT,
    "BASE_DIR": str(PRELOAD_RAY_BASE_DIR),
}.items():
    print(f"{key}={value!r}")
PY
)"

mkdir -p "$(dirname "$LOG_PATH")"
mkdir -p "$BASE_DIR" "$RUNTIME_DIR"
SHARED_GROUP="${ASHARE_RAWDATA_PRELOAD_SHARED_GROUP:-anaconda_group}"
SHARED_USER="${ASHARE_RAWDATA_PRELOAD_SHARED_USER:-gkh}"
chgrp "$SHARED_GROUP" "$BASE_DIR" "$RUNTIME_DIR" 2>/dev/null || true
chmod 2770 "$BASE_DIR" "$RUNTIME_DIR" || true
if command -v setfacl >/dev/null 2>&1; then
  setfacl -m "u:${SHARED_USER}:rwx,g:${SHARED_GROUP}:rwx,m:rwx" "$BASE_DIR" "$RUNTIME_DIR" 2>/dev/null || true
  setfacl -d -m "u:${SHARED_USER}:rwx,g:${SHARED_GROUP}:rwx,m:rwx" "$BASE_DIR" "$RUNTIME_DIR" 2>/dev/null || true
fi

repair_runtime_locks() {
  local runtime_dir=$1
  local shared_group=$2
  local shared_user=$3
  local session_dir

  session_dir=$(find "$runtime_dir" -maxdepth 1 -type d -name 'session_*' | sort | tail -n 1)
  [ -n "$session_dir" ] || return 0

  find "$session_dir" -type d | while read -r path; do
    chgrp "$shared_group" "$path" 2>/dev/null || true
    chmod 2775 "$path" 2>/dev/null || true
    if command -v setfacl >/dev/null 2>&1; then
      setfacl -m "u:${shared_user}:rwx,g:${shared_group}:rwx,m:rwx" "$path" 2>/dev/null || true
      setfacl -d -m "u:${shared_user}:rwx,g:${shared_group}:rwx,m:rwx" "$path" 2>/dev/null || true
    fi
  done

  find "$session_dir" -type f | while read -r path; do
    chgrp "$shared_group" "$path" 2>/dev/null || true
    case "$path" in
      *.lock) chmod 666 "$path" 2>/dev/null || true ;;
      *) chmod 664 "$path" 2>/dev/null || true ;;
    esac
    if command -v setfacl >/dev/null 2>&1; then
      setfacl -m "u:${shared_user}:rw,g:${shared_group}:rw,m:rw" "$path" 2>/dev/null || true
    fi
  done
}

if ray status --address "$ADDRESS" >/dev/null 2>&1; then
  python3 - <<'PY'
from scripts.utils.preload_ray import write_preload_ray_record
write_preload_ray_record()
PY
  echo "Managed preload Ray already running at $ADDRESS"
  exit 0
fi

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  tmux kill-session -t "$SESSION_NAME"
  sleep 2
fi

cmd=$(
  cat <<EOF
cd $ROOT && \
mkdir -p "$BASE_DIR" "$RUNTIME_DIR" "$(dirname "$LOG_PATH")" && \
umask 0002 && \
SHARED_GROUP="${SHARED_GROUP}" && \
SHARED_USER="${SHARED_USER}" && \
chgrp "\$SHARED_GROUP" "$BASE_DIR" "$RUNTIME_DIR" 2>/dev/null || true && \
chmod 2770 "$BASE_DIR" "$RUNTIME_DIR" || true && \
if command -v setfacl >/dev/null 2>&1; then \
  setfacl -m "u:\$SHARED_USER:rwx,g:\$SHARED_GROUP:rwx,m:rwx" "$BASE_DIR" "$RUNTIME_DIR" 2>/dev/null || true; \
  setfacl -d -m "u:\$SHARED_USER:rwx,g:\$SHARED_GROUP:rwx,m:rwx" "$BASE_DIR" "$RUNTIME_DIR" 2>/dev/null || true; \
fi && \
ulimit -n \${ASHARE_RAWDATA_PRELOAD_RAY_NOFILE_LIMIT:-65535} || true && \
AUTOSCALER_METRIC_PORT=$AUTOSCALER_METRIC_PORT \
DASHBOARD_METRIC_PORT=$DASHBOARD_METRIC_PORT \
ray start --disable-usage-stats --head --block \
  --node-ip-address $HOST \
  --port $PORT \
  --include-dashboard false \
  --object-store-memory $OBJECT_STORE \
  --temp-dir $RUNTIME_DIR \
  --min-worker-port $MIN_WORKER_PORT \
  --max-worker-port $MAX_WORKER_PORT \
  --dashboard-agent-listen-port $DASHBOARD_AGENT_LISTEN_PORT \
  --dashboard-agent-grpc-port $DASHBOARD_AGENT_GRPC_PORT \
  --runtime-env-agent-port $RUNTIME_ENV_AGENT_PORT \
  --metrics-export-port $METRICS_EXPORT_PORT \
  --dashboard-port $DASHBOARD_PORT \
  --dashboard-grpc-port $DASHBOARD_GRPC_PORT \
  2>&1 | tee $LOG_PATH
EOF
)

tmux new-session -d -s "$SESSION_NAME" "$cmd"

for _ in $(seq 1 20); do
  if ray status --address "$ADDRESS" >/dev/null 2>&1; then
    repair_runtime_locks "$RUNTIME_DIR" "$SHARED_GROUP" "$SHARED_USER"
    python3 - <<'PY'
from scripts.utils.preload_ray import write_preload_ray_record
write_preload_ray_record()
PY
    echo "Managed preload Ray started at $ADDRESS"
    echo "tmux session: $SESSION_NAME"
    echo "log: $LOG_PATH"
    exit 0
  fi
  sleep 1
done

echo "Failed to start managed preload Ray at $ADDRESS" >&2
echo "Check log: $LOG_PATH" >&2
exit 1
