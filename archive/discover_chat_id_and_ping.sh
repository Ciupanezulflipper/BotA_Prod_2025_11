#!/data/data/com.termux/files/usr/bin/bash
# File: $HOME/BotA/tools/discover_chat_id_and_ping.sh
# Purpose: Discover your real chat_id via getUpdates, persist to .env, then send a PING via send-tg.sh.
# Usage: Make sure you already sent /start to your bot in Telegram.

set -euo pipefail
BOT_DIR="${BOT_DIR:-$HOME/BotA}"
ENV_FILE="$BOT_DIR/.env"
SENDER="$BOT_DIR/tools/send-tg.sh"
LOG_DIR="$BOT_DIR/logs"; mkdir -p "$LOG_DIR"
BOT_API_BASE="${BOT_API_BASE:-https://api.telegram.org}"
CURL_OPTS=(-sS -m 20 --retry 2 --retry-delay 2 --retry-connrefused -4)

# Resolve token (no echo)
if [[ -n "${TELEGRAM_TOKEN:-}" ]]; then
  TOKEN="$TELEGRAM_TOKEN"
elif [[ -f "$ENV_FILE" ]]; then
  TOKEN="$(grep -E '^TELEGRAM_TOKEN=' "$ENV_FILE" | head -n1 | cut -d= -f2- || true)"
else
  TOKEN=""
fi
[[ -n "$TOKEN" ]] || { echo "[FAIL] Missing TELEGRAM_TOKEN (env or $ENV_FILE)"; exit 1; }

API_BASE="${BOT_API_BASE%/}/bot${TOKEN}"

# Ask updates
RESP="$(curl "${CURL_OPTS[@]}" "$API_BASE/getUpdates?timeout=5" || true)"

CHAT_ID="$(python3 - <<'PY' 2>/dev/null
import sys, json
try:
    d=json.loads(sys.stdin.read() or "{}")
    best=None; best_date=-1
    for upd in d.get("result",[]):
        msg = upd.get("message") or upd.get("edited_message") or upd.get("channel_post") or {}
        chat = msg.get("chat",{})
        if chat.get("type")=="private" and "id" in chat:
            dt = msg.get("date",0)
            if dt>=best_date:
                best, best_date = chat["id"], dt
    if best: print(best)
except: pass
PY
<<<"$RESP")"

if [[ -z "$CHAT_ID" ]]; then
  echo "[FAIL] No private chat_id found in updates. Open Telegram and send /start to your bot, then rerun."
  exit 2
fi

# Persist to .env
if [[ -f "$ENV_FILE" ]]; then
  if grep -q '^TELEGRAM_CHAT_ID=' "$ENV_FILE"; then
    sed -i "s/^TELEGRAM_CHAT_ID=.*/TELEGRAM_CHAT_ID=${CHAT_ID}/" "$ENV_FILE"
  else
    printf "\nTELEGRAM_CHAT_ID=%s\n" "$CHAT_ID" >> "$ENV_FILE"
  fi
else
  mkdir -p "$BOT_DIR"
  printf "TELEGRAM_CHAT_ID=%s\n" "$CHAT_ID" > "$ENV_FILE"
fi

# Send a ping via sender
read -r -d '' PAYLOAD <<'TXT' || true
<b>BotA PING</b>
• Source: discover_chat_id_and_ping.sh
• Expect: PASS
TXT

"$SENDER" <<< "$PAYLOAD"
echo "[OK] chat_id persisted (${CHAT_ID}) and PING sent."
