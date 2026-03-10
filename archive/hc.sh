#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

HOME_DIR="$HOME/bot-a"
TOOLS="$HOME_DIR/tools"
LOGD="$HOME_DIR/logs"
LOG="$LOGD/auto_conf.log"
PIDF="$LOGD/auto_conf.pid"

[ -f "$HOME_DIR/config/tele.env" ] && . "$HOME_DIR/config/tele.env" || true

send_tg () {
  local msg="$1"
  if [ -n "${TG_BOT_TOKEN:-}" ] && [ -n "${TG_CHAT_ID:-}" ]; then
    curl -s -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
      -d chat_id="$TG_CHAT_ID" -d parse_mode=Markdown -d text="$msg" >/dev/null || true
  fi
}

# Run forever
while :; do
  # 1) Process alive?
  if [ ! -f "$PIDF" ] || ! ps -p "$(cat "$PIDF" 2>/dev/null)" >/dev/null 2>&1; then
    send_tg "⚠️ Bot-A: auto_conf not running — attempting restart."
    nohup "$TOOLS/auto_conf.sh" >/dev/null 2>&1 &
    sleep 8
  fi

  # 2) Log freshness?
  if [ -f "$LOG" ]; then
    now=$(date +%s)
    mts=$(date -r "$LOG" +%s 2>/dev/null || stat -c %Y "$LOG" 2>/dev/null || echo "$now")
    age=$((now - mts))
    # If no log update in 10 minutes, restart loop
    if [ "$age" -gt 600 ]; then
      send_tg "⚠️ Bot-A: no log activity for $age s — restarting loop."
      pkill -f auto_conf.sh || true
      nohup "$TOOLS/auto_conf.sh" >/dev/null 2>&1 &
    fi
  fi

  sleep 120
done
