#!/data/data/com.termux/files/usr/bin/bash
# Bot A — Auto-start bundler (alerts + Telegram controller)
# Safe to run multiple times; idempotent and non-invasive.

set -euo pipefail
ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"
LOG="$ROOT/boot.log"
mkdir -p "$ROOT" "$ROOT/state"

log(){ echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] $*" | tee -a "$LOG"; }

# 0) Optional: load Telegram token/chat id if present
if [ -f "$TOOLS/tele_env.sh" ]; then
  # shellcheck disable=SC1090
  source "$TOOLS/tele_env.sh" >/dev/null 2>&1 || true
fi

# 1) Start alert loop if not running
if pgrep -f "tools/alert_loop.sh" >/dev/null 2>&1; then
  log "alerts: already running"
else
  log "alerts: starting…"
  nohup "$TOOLS/alert_loop.sh" >> "$ROOT/alert.log" 2>&1 & disown
  log "alerts: started"
fi

# 2) Start Telegram controller if not running
if pgrep -f "python3 .*tele_control.py" >/dev/null 2>&1; then
  log "tele_control: already running"
else
  if [ -x "$TOOLS/tele_control.sh" ]; then
    log "tele_control: starting…"
    nohup "$TOOLS/tele_control.sh" >> "$ROOT/control.log" 2>&1 & disown
    log "tele_control: started"
  else
    log "tele_control: missing tele_control.sh — skip"
  fi
fi

# 3) Lightweight health ping to Telegram (optional; only if token/chat id exported)
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
  TEXT="🟢 BotA booted @ $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
       -d "chat_id=${TELEGRAM_CHAT_ID}" -d "text=${TEXT}" -d "parse_mode=HTML" >/dev/null 2>&1 || true
fi

log "boot: done"
