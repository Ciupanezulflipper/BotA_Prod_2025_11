#!/data/data/com.termux/files/usr/bin/bash
# File: $HOME/BotA/tools/fix_token_chat_env.sh
# Purpose: Ensure $HOME/BotA/.env has both TELEGRAM_TOKEN and TELEGRAM_CHAT_ID set correctly.
# - If chat_id is missing but discoverable via getUpdates, it will persist it.
# - Safe: never prints token, only confirms presence.

set -euo pipefail
BOT_DIR="${BOT_DIR:-$HOME/BotA}"
ENV_FILE="$BOT_DIR/.env"
BOT_API_BASE="${BOT_API_BASE:-https://api.telegram.org}"
CURL=(-4 -sS -m 20 --retry 1)

# Resolve token (no echo)
if [[ -n "${TELEGRAM_TOKEN:-}" ]]; then
  TOKEN="$TELEGRAM_TOKEN"
elif [[ -f "$ENV_FILE" ]]; then
  TOKEN="$(grep -E '^TELEGRAM_TOKEN=' "$ENV_FILE" | head -n1 | cut -d= -f2- || true)"
else
  TOKEN=""
fi
[[ -n "$TOKEN" ]] || { echo "[FAIL] TELEGRAM_TOKEN missing (env or $ENV_FILE)"; exit 1; }

# Ensure .env exists
mkdir -p "$BOT_DIR"
touch "$ENV_FILE"

# If chat id present, done
if grep -q '^TELEGRAM_CHAT_ID=' "$ENV_FILE"; then
  echo "[OK] TELEGRAM_CHAT_ID present in $ENV_FILE"
  exit 0
fi

# Try to discover
RESP="$(curl "${CURL[@]}" "${BOT_API_BASE%/}/bot${TOKEN}/getUpdates?timeout=5" || true)"
CID="$(python3 - <<'PY'
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

if [[ -n "$CID" ]]; then
  printf "\nTELEGRAM_CHAT_ID=%s\n" "$CID" >> "$ENV_FILE"
  echo "[OK] TELEGRAM_CHAT_ID discovered and added to $ENV_FILE"
else
  echo "[FAIL] No private chat found. Open Telegram → Start the bot → send 'hi' → rerun."
  exit 2
fi
