#!/usr/bin/env bash
# tools/error_monitor.sh
# Watch ~/.bot-a/logs/*.log for new errors and alert via Telegram.
# - Single-instance guard (PID file)
# - Uses tail -Fn0 so it alerts only on NEW lines
# - Throttles alerts (1 ping / 5 minutes) and summarizes burst count
# - No cron needed; run with:  nohup ~/bot-a/tools/error_monitor.sh >/dev/null 2>&1 &

set -euo pipefail

PY_HOME="${HOME}/bot-a"
LOG_DIR="${HOME}/.bot-a/logs"
RUN_DIR="${HOME}/.bot-a/run"
PIDFILE="${RUN_DIR}/error_monitor.pid"

# Throttle window (seconds) for Telegram alerts
RATE_SEC="${BOT_A_ERROR_RATE_SEC:-300}"  # 5 minutes
mkdir -p "${LOG_DIR}" "${RUN_DIR}"

# Optional wakelock (Termux)
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock || true
fi

# Single instance guard
if [[ -f "${PIDFILE}" ]] && kill -0 "$(cat "${PIDFILE}")" 2>/dev/null; then
  echo "[error_monitor] already running with PID $(cat "${PIDFILE}")"
  exit 0
fi
echo $$ > "${PIDFILE}"

cleanup() {
  rm -f "${PIDFILE}"
  if command -v termux-wake-unlock >/dev/null 2>&1; then
    termux-wake-unlock || true
  fi
}
trap cleanup EXIT INT TERM

# Helper: send Telegram (falls back to print)
send_telegram() {
  local msg="$1"
  EMSG="$msg" PYTHONPATH="$PY_HOME" python - <<'PY' || true
import os, sys
try:
    from tools.telegramalert import send_text
    msg = os.environ.get("EMSG","")
    ok = send_text(msg)
    if not ok:
        print(msg)
except Exception as e:
    # fallback print
    print("[error_monitor] telegram send failed:", e)
    print(os.environ.get("EMSG",""))
PY
}

# Compose alert text
compose_alert() {
  local count="$1"
  local sample="$2"
  local ts
  ts="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  cat <<TXT
🚨 *Bot-A error alert* — ${ts}
• New error lines: *${count}*
• Sample:
\`\`\`
${sample}
\`\`\`
_See ~/.bot-a/logs for full details._
TXT
}

# Prepare file list for tail; if none exists, create a placeholder to avoid tail error
shopt -s nullglob
files=( "${LOG_DIR}"/*.log )
if [[ ${#files[@]} -eq 0 ]]; then
  touch "${LOG_DIR}/_placeholder.log"
  files=( "${LOG_DIR}/_placeholder.log" )
fi

echo "[error_monitor] watching ${#files[@]} file(s) in ${LOG_DIR}"

last_send=0
burst_count=0
sample_line=""

# Patterns that count as "error"
# - Traceback
# - CRITICAL / ERROR
# - our runner/exec failures
# - telegram failures
regex='(Traceback|CRITICAL|ERROR|exec_failed|picker failure|telegram send failed)'

# Tail only NEW lines (-n0) and follow file growth (-F)
tail -Fn0 "${files[@]}" | while read -r line; do
  # Skip empty
  [[ -z "${line// }" ]] && continue

  if echo "$line" | grep -Eiq "$regex"; then
    ((burst_count++))
    # keep first matching line as sample
    if [[ -z "$sample_line" ]]; then
      sample_line="$line"
    fi
    now=$(date -u +%s)
    delta=$(( now - last_send ))
    if [[ $delta -ge $RATE_SEC ]]; then
      # send summary of burst
      alert="$(compose_alert "$burst_count" "$sample_line")"
      send_telegram "$alert"
      last_send=$now
      burst_count=0
      sample_line=""
    fi
  fi
done
