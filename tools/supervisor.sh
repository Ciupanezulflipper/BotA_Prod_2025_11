#!/usr/bin/env bash
# tools/supervisor.sh
# Keep Bot-A core services running (no heartbeat):
#   - runloop.sh
#   - digest_loop.sh
#   - error_monitor.sh

set -euo pipefail

APP="${HOME}/bot-a"
RUN_DIR="${HOME}/.bot-a/run"
LOG_DIR="${HOME}/.bot-a/logs"
STATE_DIR="${HOME}/.bot-a/state"
mkdir -p "${RUN_DIR}" "${LOG_DIR}" "${STATE_DIR}"

CHECK_SEC="${BOT_A_SUP_CHECK_SEC:-60}"
MAX_RESTARTS="${BOT_A_SUP_MAX_RESTARTS:-3}"
SVC_LIST=("runloop" "digest_loop" "error_monitor")

start_cmd() {
  case "$1" in
    runloop)       echo "nohup ${APP}/tools/runloop.sh       >/dev/null 2>&1 &" ;;
    digest_loop)   echo "nohup ${APP}/tools/digest_loop.sh   >/dev/null 2>&1 &" ;;
    error_monitor) echo "nohup ${APP}/tools/error_monitor.sh >/dev/null 2>&1 &" ;;
    *)             echo "echo unknown service $1" ;;
  esac
}

pidfile_for() {
  case "$1" in
    runloop)       echo "${RUN_DIR}/signal_runner.pid" ;;
    digest_loop)   echo "${RUN_DIR}/digest_loop.pid" ;;
    error_monitor) echo "${RUN_DIR}/error_monitor.pid" ;;
    *)             echo "${RUN_DIR}/unknown.pid" ;;
  esac
}

send_tg() {
  local msg="$1"
  MSG="$msg" PYTHONPATH="${APP}" python - <<'PY' || true
import os
try:
    from tools.telegramalert import send_text
    m=os.environ.get("MSG","")
    ok=send_text(m)
    if not ok: print(m)
except Exception as e:
    print("[supervisor] telegram send failed:", e)
    print(os.environ.get("MSG",""))
PY
}

rate_key() { echo "${STATE_DIR}/$1-restarts.txt"; }

can_restart() {
  local svc="$1" f; f="$(rate_key "$svc")"
  local now=$(date -u +%s) hour_ago=$((now-3600))
  [[ -f "$f" ]] || : > "$f"
  awk -v c="$hour_ago" '{if($1>=c)print $1}' "$f" > "${f}.new" 2>/dev/null || true
  mv -f "${f}.new" "$f"
  local cnt; cnt=$(wc -l < "$f" | awk '{print $1}')
  if (( cnt < MAX_RESTARTS )); then
    echo "$now" >> "$f"; return 0
  else
    return 1
  fi
}

ensure_running() {
  local svc="$1" pf; pf="$(pidfile_for "$svc")"
  if [[ -f "$pf" ]]; then
    local pid; pid=$(cat "$pf" 2>/dev/null || true)
    if kill -0 "$pid" 2>/dev/null; then return 0; fi
    rm -f "$pf"
  fi
  if can_restart "$svc"; then
    eval "$(start_cmd "$svc")"
    send_tg "🔁 *Supervisor*: restarted *${svc}* at $(date -u '+%Y-%m-%d %H:%M:%S UTC')."
  else
    send_tg "⚠️ *Supervisor*: *${svc}* hit restart limit (${MAX_RESTARTS}/h)."
  fi
}

command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock || true

while true; do
  for s in "${SVC_LIST[@]}"; do ensure_running "$s"; done
  sleep "${CHECK_SEC}"
done
