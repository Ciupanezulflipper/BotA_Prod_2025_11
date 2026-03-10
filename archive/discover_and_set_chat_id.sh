#!/data/data/com.termux/files/usr/bin/bash
# File: $HOME/BotA/tools/discover_and_set_chat_id.sh
# Purpose: Discover your real Telegram chat_id and persist it into $HOME/BotA/.env
# Safety: No token echoing; minimal logs.

set -euo pipefail

BOT_DIR="${BOT_DIR:-$HOME/BotA}"
ENV_FILE="$BOT_DIR/.env"
LOG_DIR="$BOT_DIR/logs"
LOG_FILE="$LOG_DIR/chatid.log"
mkdir -p "$LOG_DIR"

ts() { date +"%Y-%m-%d %H:%M:%S%z"; }

# Resolve TELEGRAM_TOKEN (env > .env)
if [[ -n "${TELEGRAM_TOKEN:-}" ]]; then
  TOKEN="$TELEGRAM_TOKEN"
elif [[ -f "$ENV_FILE" ]]; then
  TOKEN="$(grep -E '^TELEGRAM_TOKEN=' "$ENV_FILE" | head -n1 | cut -d= -f2- || true)"
  TOKEN="${TOKEN:-}"
else
  TOKEN=""
fi

if [[ -z "$TOKEN" ]]; then
  echo "$(ts) | FAIL | Missing TELEGRAM_TOKEN (export it or set in $ENV_FILE)" | tee -a "$LOG_FILE" >/dev/null
  exit 1
fi

API="https://api.telegram.org/bot${TOKEN}"

# Hint the user if needed
echo "$(ts) | INFO | If this finds no messages, open Telegram, DM your bot and send: /start" | tee -a "$LOG_FILE" >/dev/null

# Pull updates (do not print token)
RESP="$(curl -sS -m 20 --retry 2 --retry-delay 2 --retry-connrefused "$API/getUpdates?timeout=5")" || {
  echo "$(ts) | FAIL | getUpdates network error" | tee -a "$LOG_FILE" >/dev/null
  exit 1
}

# Parse the newest private chat_id; fall back to any chat if needed
CHAT_ID="$(
python3 - <<'PY' 2>/dev/null
import sys, json
try:
    d = json.loads(sys.stdin.read() or "{}")
    res = d.get("result", [])
    # Prefer newest, private chats first
    for prefer_private in (True, False):
        best = None
        best_date = -1
        for upd in res:
            msg = upd.get("message") or upd.get("edited_message") or upd.get("channel_post") or {}
            chat = msg.get("chat", {})
            ctype = chat.get("type")
            if prefer_private and ctype != "private":
                continue
            if not prefer_private and ctype is None:
                continue
            date = msg.get("date", 0)
            if date >= best_date and "id" in chat:
                best, best_date = chat["id"], date
        if best is not None:
            print(best)
            raise SystemExit(0)
except Exception:
    pass
PY
<<<"$RESP"
)"

if [[ -z "$CHAT_ID" ]]; then
  echo "$(ts) | FAIL | Could not find any chat_id in updates. Send /start to your bot, then rerun." | tee -a "$LOG_FILE" >/dev/null
  exit 2
fi

# Persist into .env (idempotent replace or append)
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

echo "$(ts) | OK | chat_id discovered and saved | TELEGRAM_CHAT_ID=${CHAT_ID} (hidden from logs elsewhere)" | tee -a "$LOG_FILE" >/dev/null
exit 0
