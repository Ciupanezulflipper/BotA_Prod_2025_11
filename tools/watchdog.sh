#!/data/data/com.termux/files/usr/bin/bash
# tools/watchdog.sh — keep autorun up, respect hours, avoid API waste (full file)

set -euo pipefail

ROOT="$HOME/bot-a"
ENVF="$HOME/.env"
SESSION="botAuto"
PY="$ROOT/tools/autorun.py"

# load env (tolerant)
if [ -f "$ENVF" ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' "$ENVF" | xargs) || true
fi

ACTIVE_HOURS="${ACTIVE_HOURS:-07:00-23:00}"
WIFI_REQUIRED="${WIFI_REQUIRED:-1}"
CRON_STEP_MIN="${CRON_STEP_MIN:-5}"

log() { printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" ; }

in_window() {
  # ACTIVE_HOURS format: HH:MM-HH:MM (local time)
  now_hm=$(date +%H%M)
  IFS='-' read -r H1 H2 <<<"$ACTIVE_HOURS"
  H1=${H1/:/}; H2=${H2/:/}
  # handle wrap past midnight (e.g., 22:00-06:00)
  if [ "$H1" -le "$H2" ]; then
    [ "$now_hm" -ge "$H1" ] && [ "$now_hm" -le "$H2" ]
  else
    [ "$now_hm" -ge "$H1" ] || [ "$now_hm" -le "$H2" ]
  fi
}

online() {
  # cheap & fast check; no DNS needed
  ping -c1 -W1 1.1.1.1 >/dev/null 2>&1
}

tmux_running() {
  tmux has-session -t "$SESSION" 2>/dev/null
}

start_loop() {
  mkdir -p "$ROOT/state"
  if tmux_running; then
    log "[watchdog] loop already running"
    return
  fi
  log "[watchdog] starting loop..."
  tmux new-session -d -s "$SESSION" "$PY"
}

stop_loop() {
  if tmux_running; then
    log "[watchdog] stopping loop (saving API)..."
    tmux kill-session -t "$SESSION" 2>/dev/null || true
  else
    log "[watchdog] loop not running (ok)"
  fi
}

main() {
  # 1) hours guard
  if ! in_window; then
    stop_loop
    exit 0
  fi

  # 2) online guard
  if [ "$WIFI_REQUIRED" = "1" ] && ! online; then
    log "[watchdog] offline, will not start loop (saving API)"
    stop_loop
    exit 0
  fi

  # 3) ensure running
  start_loop
}

main "$@"
