#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd /data/data/com.termux/files/home/BotA || exit 1

ROOT="/data/data/com.termux/files/home/BotA"
PIDFILE="${ROOT}/logs/state/prod_runner.pid"
OUTLOG="${ROOT}/logs/prod_watcher.out"

WATCHER_ABS="${ROOT}/tools/signal_watcher_pro.sh"
WATCHER_REL="tools/signal_watcher_pro.sh"
WATCHER_NAME="signal_watcher_pro.sh"

ENV_RUNTIME="${ROOT}/.env.runtime"

cmd="${1:-status}"

is_pid_alive() {
  local pid="${1:-}"
  [[ -n "${pid}" ]] || return 1
  kill -0 "${pid}" >/dev/null 2>&1
}

read_pidfile() {
  [[ -f "${PIDFILE}" ]] || return 1
  cat "${PIDFILE}" 2>/dev/null | tr -cd '0-9' || true
}

find_watcher_pids() {
  # Return watcher PIDs that match absolute path OR relative path OR basename.
  # This avoids "ps grep miss" when watcher started as: bash tools/signal_watcher_pro.sh
  ps -A -o pid=,args= 2>/dev/null | awk -v a="${WATCHER_ABS}" -v r="${WATCHER_REL}" -v n="${WATCHER_NAME}" '
    $0 ~ a || $0 ~ r || $0 ~ n {print $1}
  ' | tr '\n' ' '
}

first_watcher_pid() {
  local pids=""
  pids="$(find_watcher_pids || true)"
  for p in ${pids}; do
    if is_pid_alive "${p}"; then
      echo "${p}"
      return 0
    fi
  done
  return 1
}

# Safe KEY=VALUE loader (non-eval) for .env.runtime.
# Allow-list prevents surprise exports; values are not executed.
safe_load_env_runtime() {
  [[ -f "${ENV_RUNTIME}" ]] || return 0

  local line key val
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line%$'\r'}"

    # trim
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"

    [[ -z "${line}" ]] && continue
    [[ "${line}" == \#* ]] && continue

    if [[ "${line}" == export\ * ]]; then
      line="${line#export }"
      line="${line#"${line%%[![:space:]]*}"}"
    fi

    if [[ "${line}" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      val="${BASH_REMATCH[2]}"

      case "${key}" in
        BOT_TOKEN|TELEGRAM_BOT_TOKEN|TELEGRAM_TOKEN|CHAT_ID|TELEGRAM_CHAT_ID|TELEGRAM_ENABLED|DRY_RUN_MODE|PAIRS|TIMEFRAMES| \
        FILTER_SCORE_MIN|FILTER_SCORE_MIN_ALL|TELEGRAM_MIN_SCORE|TELEGRAM_TIER_GREEN_MIN|TELEGRAM_TIER_YELLOW_MIN|TELEGRAM_COOLDOWN_SECONDS| \
        INDICATOR_MAX_AGE_SECS|NETWORK_FAIL_MAX)
          ;;
        *)
          continue
          ;;
      esac

      # Strip surrounding quotes if present
      if [[ "${val}" =~ ^\"(.*)\"$ ]]; then
        val="${BASH_REMATCH[1]}"
      elif [[ "${val}" =~ ^\'(.*)\'$ ]]; then
        val="${BASH_REMATCH[1]}"
      fi

      export "${key}=${val}"
    fi
  done < "${ENV_RUNTIME}"
}

normalize_telegram_env() {
  # Force-set Telegram runtime env from .env.runtime, overriding any poisoned interactive env.
  safe_load_env_runtime

  if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
    TELEGRAM_BOT_TOKEN="${TELEGRAM_TOKEN:-${BOT_TOKEN:-}}"
  fi
  if [[ -z "${TELEGRAM_CHAT_ID:-}" ]]; then
    TELEGRAM_CHAT_ID="${CHAT_ID:-}"
  fi

  # Unify names used across scripts
  if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
    TELEGRAM_TOKEN="${TELEGRAM_BOT_TOKEN}"
    BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
  fi
  if [[ -n "${TELEGRAM_CHAT_ID:-}" ]]; then
    CHAT_ID="${TELEGRAM_CHAT_ID}"
  fi

  export TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID TELEGRAM_TOKEN BOT_TOKEN CHAT_ID
  export BOTA_ROOT="${ROOT}"

  # Non-secret diagnostics (no token value printed)
  local tok_ok="no"
  if printf '%s' "${TELEGRAM_BOT_TOKEN:-}" | grep -Eq '^[0-9]{7,12}:[A-Za-z0-9_-]{30,}$' 2>/dev/null; then
    tok_ok="yes"
  fi
  local cid_ok="no"
  [[ -n "${TELEGRAM_CHAT_ID:-}" ]] && cid_ok="yes"

  echo "note=env_runtime_loaded file=.env.runtime telegram_token_regex_ok=${tok_ok} chat_id_present=${cid_ok}"
}

start_runner() {
  mkdir -p "${ROOT}/logs/state" >/dev/null 2>&1 || true
  touch "${OUTLOG}" >/dev/null 2>&1 || true

  # Ensure runtime env is present before any watcher start
  normalize_telegram_env >> "${OUTLOG}" 2>&1 || true

  # 1) pidfile alive -> already running
  local pid=""
  pid="$(read_pidfile || true)"
  if is_pid_alive "${pid}"; then
    echo "status=ALREADY_RUNNING pid=${pid}"
    echo "outlog=${OUTLOG}"
    exit 0
  fi

  # 2) watcher alive but pidfile stale/missing -> adopt (user can run restart to re-seed env)
  local live=""
  live="$(first_watcher_pid || true)"
  if [[ -n "${live}" ]]; then
    echo "${live}" > "${PIDFILE}"
    echo "status=ALREADY_RUNNING adopted_pid=${live} (pidfile was stale/missing)"
    echo "outlog=${OUTLOG}"
    echo "note=if_this_watcher_was_started_before_S22_run_restart_to_apply_env_runtime"
    exit 0
  fi

  # 3) start new watcher (inherits env seeded above)
  nohup bash "${ROOT}/tools/signal_watcher_pro.sh" >> "${OUTLOG}" 2>&1 </dev/null &
  pid="$!"
  echo "${pid}" > "${PIDFILE}"

  # 4) prove it stayed alive
  sleep 1 || true
  if is_pid_alive "${pid}"; then
    echo "status=STARTED pid=${pid} outlog=${OUTLOG}"
    exit 0
  fi

  rm -f "${PIDFILE}" >/dev/null 2>&1 || true
  echo "status=FAIL start_did_not_stick (watcher exited immediately)"
  echo "outlog=${OUTLOG}"
  echo "tail=60 ${OUTLOG}"
  tail -n 60 "${OUTLOG}" 2>/dev/null || true
  exit 1
}

stop_runner() {
  local pid=""
  pid="$(read_pidfile || true)"

  # Stop pidfile PID if alive
  if is_pid_alive "${pid}"; then
    kill "${pid}" >/dev/null 2>&1 || true
    for _ in 1 2 3 4 5; do
      sleep 1 || true
      is_pid_alive "${pid}" || break
    done
    is_pid_alive "${pid}" && kill -9 "${pid}" >/dev/null 2>&1 || true
    rm -f "${PIDFILE}" >/dev/null 2>&1 || true
    echo "status=STOPPED pid=${pid}"
  else
    [[ -f "${PIDFILE}" ]] && rm -f "${PIDFILE}" >/dev/null 2>&1 || true
    echo "status=NOT_RUNNING (stale pidfile cleared pid=${pid:-NA})"
  fi

  # Also stop any stray watcher processes (BotA watcher only)
  local pids=""
  pids="$(find_watcher_pids || true)"
  if [[ -n "${pids// /}" ]]; then
    for p in ${pids}; do
      is_pid_alive "${p}" && kill "${p}" >/dev/null 2>&1 || true
    done
    sleep 1 || true
    for p in ${pids}; do
      is_pid_alive "${p}" && kill -9 "${p}" >/dev/null 2>&1 || true
    done
    echo "note=stray_watchers_killed pids=${pids}"
  fi
}

status_runner() {
  local pid=""
  pid="$(read_pidfile || true)"
  if is_pid_alive "${pid}"; then
    echo "status=RUNNING pid=${pid}"
    echo "outlog=${OUTLOG}"
    exit 0
  fi

  # pidfile stale but watcher actually running -> adopt
  local live=""
  live="$(first_watcher_pid || true)"
  if [[ -n "${live}" ]]; then
    echo "${live}" > "${PIDFILE}"
    echo "status=RUNNING adopted_pid=${live}"
    echo "outlog=${OUTLOG}"
    exit 0
  fi

  echo "status=NOT_RUNNING"
  if [[ -f "${PIDFILE}" ]]; then
    echo "note=pidfile_present_but_not_alive pid=${pid:-NA}"
  fi
  echo "outlog=${OUTLOG}"
}

logs_runner() {
  touch "${OUTLOG}" >/dev/null 2>&1 || true
  echo "tail=120 ${OUTLOG}"
  tail -n 120 "${OUTLOG}" 2>/dev/null || true
}

case "${cmd}" in
  start) start_runner ;;
  stop) stop_runner ;;
  restart) stop_runner; start_runner ;;
  status) status_runner ;;
  logs) logs_runner ;;
  *)
    echo "Usage: bash tools/prod_runnerctl.sh {start|stop|restart|status|logs}"
    exit 2
    ;;
esac
