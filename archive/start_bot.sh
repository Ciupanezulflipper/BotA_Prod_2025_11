#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# ---------- Paths ----------
HOME_DIR="$HOME/bot-a"
TOOLS="$HOME_DIR/tools"
LOGD="$HOME_DIR/logs"
PIDF="$LOGD/auto_conf.pid"
LOG="$LOGD/auto_conf.log"
CONF_ENV="$HOME_DIR/config/tele.env"

mkdir -p "$LOGD"

# ---------- Load credentials (Telegram) ----------
if [[ -f "$CONF_ENV" ]]; then
  # shellcheck source=/dev/null
  source "$CONF_ENV"
fi

: "${TG_BOT_TOKEN:=}"
: "${TG_CHAT_ID:=}"

if [[ -z "${TG_BOT_TOKEN}" || -z "${TG_CHAT_ID}" ]]; then
  echo "WARN: TG_BOT_TOKEN or TG_CHAT_ID is empty (tele.env). Telegram sends will fail."
fi

# ---------- Tunables (env overrides allowed) ----------
export LOOP_SEC="${LOOP_SEC:-60}"           # check cadence (s)
export DIGEST_MIN="${DIGEST_MIN:-30}"       # quiet digest cadence (min)
export STRONG_CONF="${STRONG_CONF:-6.0}"    # immediate send threshold
export HEARTBEAT_HOURS="${HEARTBEAT_HOURS:-6}"
export DIGEST_HOURS="${DIGEST_HOURS:-24}"
export TG_RETRIES="${TG_RETRIES:-3}"
export LOG_ROTATE_KB="${LOG_ROTATE_KB:-500}"

# ---------- Clean any old loop ----------
if [[ -f "$PIDF" ]]; then
  oldpid="$(cat "$PIDF" || true)"
  if [[ -n "${oldpid:-}" ]] && ps -p "$oldpid" >/dev/null 2>&1; then
    echo "Stopping previous auto_conf loop (pid $oldpid)…"
    kill "$oldpid" 2>/dev/null || true
    sleep 1
    kill -9 "$oldpid" 2>/dev/null || true
  fi
  rm -f "$PIDF"
fi
# double-safety: kill by name, ignore errors
pkill -f "$TOOLS/auto_conf.sh" 2>/dev/null || true

# ---------- Start fresh loop ----------
echo "Starting auto_conf loop…"
nohup "$TOOLS/auto_conf.sh" >/dev/null 2>&1 &
newpid=$!
echo "$newpid" > "$PIDF"
echo "auto_conf: started pid $newpid"

# ---------- Quick self-test ----------
sleep 2
echo "---- last 25 log lines ----"
if [[ -s "$LOG" ]]; then
  tail -n 25 "$LOG" || true
else
  echo "(no log yet)"
fi

# Helpful hints
echo "Tip:"
echo "  • To watch logs: tail -n 60 -f $LOG"
echo "  • To stop loop : kill \$(cat $PIDF) && rm -f $PIDF"
