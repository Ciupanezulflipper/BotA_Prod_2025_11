#!/data/data/com.termux/files/usr/bin/bash
# File: $HOME/BotA/tools/audit_tg_delivery.sh
# Purpose: Deep, deterministic audit of Telegram delivery failures with explicit root-cause classification.
# What it does (no secrets printed):
#   1) Reads TELEGRAM_TOKEN and TELEGRAM_CHAT_ID from env / $HOME/BotA/.env
#   2) Confirms token via getMe (HTTP+JSON) over IPv4
#   3) Fetches getUpdates to discover your latest private chat_id (if you DM’d /start to this bot)
#   4) Compares configured chat_id vs discovered chat_id
#   5) Performs a direct sendMessage POST (bypassing send-tg.sh) and prints Telegram's "description"
#   6) Classifies the failure (blocked, not-started, wrong chat, group-only, firewall), and prints the FIX

set -euo pipefail

BOT_DIR="${BOT_DIR:-$HOME/BotA}"
ENV_FILE="$BOT_DIR/.env"
LOG_DIR="$BOT_DIR/logs"; mkdir -p "$LOG_DIR"
TMP_DIR="$LOG_DIR/audit-$$"; mkdir -p "$TMP_DIR"

BOT_API_BASE="${BOT_API_BASE:-https://api.telegram.org}"
CURL=(-4 -sS -m 25 --retry 1)

ts(){ date +"%Y-%m-%d %H:%M:%S%z"; }

# ---------- Load token & chat id (no echo of token) ----------
if [[ -n "${TELEGRAM_TOKEN:-}" ]]; then
  TOKEN="$TELEGRAM_TOKEN"
elif [[ -f "$ENV_FILE" ]]; then
  TOKEN="$(grep -E '^TELEGRAM_TOKEN=' "$ENV_FILE" | head -n1 | cut -d= -f2- || true)"
else
  TOKEN=""
fi
[[ -n "$TOKEN" ]] || { echo "[FAIL] $(ts) | TELEGRAM_TOKEN missing (env or $ENV_FILE)"; exit 1; }

CONF_CHAT_ID="${TELEGRAM_CHAT_ID:-}"
if [[ -z "$CONF_CHAT_ID" && -f "$ENV_FILE" ]]; then
  CONF_CHAT_ID="$(grep -E '^TELEGRAM_CHAT_ID=' "$ENV_FILE" | head -n1 | cut -d= -f2- || true)"
fi

API_BASE="${BOT_API_BASE%/}/bot${TOKEN}"

# ---------- 1) getMe ----------
ME_JSON="$TMP_DIR/getMe.json"
HTTP_ME="$(curl "${CURL[@]}" -w "%{http_code}" -o "$ME_JSON" "$API_BASE/getMe" || true)"
OK_ME="$(python3 - <<'PY' "$ME_JSON"
import sys, json
try: print("true" if json.load(open(sys.argv[1],'rb')).get("ok") else "false")
except: print("false")
PY
)"
echo "[INFO] $(ts) | getMe: http=$HTTP_ME ok=$OK_ME"

if [[ "$HTTP_ME" != "200" || "$OK_ME" != "true" ]]; then
  DESC="$(python3 - <<'PY' "$ME_JSON"
import sys, json
try: print(json.load(open(sys.argv[1],'rb')).get("description",""))
except: print("")
PY
)"
  echo "[FAIL] $(ts) | Token invalid or network blocked. desc=${DESC}"
  echo "FIX: verify token in $ENV_FILE, ensure ship/Wi-Fi allows api.telegram.org, try mobile hotspot."
  exit 2
fi

# ---------- 2) getUpdates (for latest private chat id) ----------
UPD_JSON="$TMP_DIR/updates.json"
HTTP_UPD="$(curl "${CURL[@]}" -w "%{http_code}" -o "$UPD_JSON" "$API_BASE/getUpdates?timeout=5" || true)"
DISCOVERED_CHAT_ID="$(python3 - <<'PY' "$UPD_JSON"
import sys, json
try:
    d=json.load(open(sys.argv[1],'rb'))
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
)"
echo "[INFO] $(ts) | getUpdates: http=$HTTP_UPD discovered_private_chat_id=${DISCOVERED_CHAT_ID:-<none>}"

# ---------- 3) Prepare send target ----------
TARGET_CHAT_ID="$CONF_CHAT_ID"
[[ -z "$TARGET_CHAT_ID" && -n "$DISCOVERED_CHAT_ID" ]] && TARGET_CHAT_ID="$DISCOVERED_CHAT_ID"

if [[ -z "$TARGET_CHAT_ID" ]]; then
  echo "[FAIL] $(ts) | No chat_id configured or discovered."
  echo "CAUSE: You haven't DM’d this bot yet (Telegram requires user to /start the bot first)."
  echo "FIX: Open Telegram → search your bot → tap Start → send 'hi' → re-run this audit."
  exit 3
fi

[[ "$TARGET_CHAT_ID" =~ ^-?[0-9]+$ ]] || { echo "[FAIL] $(ts) | chat_id not numeric: $TARGET_CHAT_ID"; exit 3; }

# ---------- 4) Direct sendMessage (bypass shell wrappers) ----------
SEND_JSON="$TMP_DIR/send.json"
HTTP_SEND="$(curl "${CURL[@]}" \
  --data-urlencode "chat_id=$TARGET_CHAT_ID" \
  --data-urlencode "text=BotA AUDIT PING — $(date +%H:%M:%S)" \
  --data-urlencode "parse_mode=HTML" \
  --data-urlencode "disable_web_page_preview=true" \
  -w "%{http_code}" -o "$SEND_JSON" \
  "$API_BASE/sendMessage" || true)"

OK_SEND="$(python3 - <<'PY' "$SEND_JSON"
import sys, json
try: print("true" if json.load(open(sys.argv[1],'rb')).get("ok") else "false")
except: print("false")
PY
)"
DESC_SEND="$(python3 - <<'PY' "$SEND_JSON"
import sys, json
try: print(json.load(open(sys.argv[1],'rb')).get("description",""))
except: print("")
PY
)"
echo "[INFO] $(ts) | sendMessage: http=$HTTP_SEND ok=$OK_SEND desc=${DESC_SEND:-<none>}"

# ---------- 5) Classify & FIX ----------
if [[ "$OK_SEND" == "true" && "$HTTP_SEND" == "200" ]]; then
  echo "[PASS] $(ts) | Delivery works. You should receive 'BotA AUDIT PING' now."
  # Persist discovered chat id if different and .env exists
  if [[ -n "$DISCOVERED_CHAT_ID" && "$DISCOVERED_CHAT_ID" != "$CONF_CHAT_ID" ]]; then
    if [[ -f "$ENV_FILE" ]]; then
      if grep -q '^TELEGRAM_CHAT_ID=' "$ENV_FILE"; then
        sed -i "s/^TELEGRAM_CHAT_ID=.*/TELEGRAM_CHAT_ID=${DISCOVERED_CHAT_ID}/" "$ENV_FILE"
      else
        printf "\nTELEGRAM_CHAT_ID=%s\n" "$DISCOVERED_CHAT_ID" >> "$ENV_FILE"
      fi
      echo "[INFO] $(ts) | Updated $ENV_FILE with TELEGRAM_CHAT_ID=${DISCOVERED_CHAT_ID}"
    fi
  fi
  exit 0
fi

# Normalize desc for matching
low_desc="$(printf "%s" "$DESC_SEND" | tr '[:upper:]' '[:lower:]')"

if printf "%s" "$low_desc" | grep -q "bot was blocked by the user"; then
  echo "[FAIL] $(ts) | CAUSE: Bot is BLOCKED by this user/chat."
  echo "FIX: In Telegram → open chat with the bot → Unblock."
  exit 4
elif printf "%s" "$low_desc" | grep -q "can't initiate conversation with a user"; then
  echo "[FAIL] $(ts) | CAUSE: User has NOT STARTED the chat with this bot."
  echo "FIX: In Telegram → open the bot → tap Start → send any message → rerun audit."
  exit 4
elif printf "%s" "$low_desc" | grep -q "chat not found"; then
  echo "[FAIL] $(ts) | CAUSE: Wrong chat_id for this bot context (e.g., different bot token or old id)."
  echo "FIX: DM this exact bot, then rerun to auto-discover the correct private chat_id."
  exit 4
elif [[ "$HTTP_SEND" == "429" ]] || printf "%s" "$low_desc" | grep -q "too many requests"; then
  echo "[FAIL] $(ts) | CAUSE: Telegram rate limit."
  echo "FIX: Wait a minute and rerun. Consider fewer retries."
  exit 4
elif [[ "$HTTP_SEND" == "403" ]]; then
  echo "[FAIL] $(ts) | CAUSE: Forbidden (blocked/not started/private restriction)."
  echo "FIX: Ensure you started the bot and did not block it."
  exit 4
elif [[ "$HTTP_SEND" == "400" ]]; then
  echo "[FAIL] $(ts) | CAUSE: Bad Request (often bad chat_id)."
  echo "FIX: Use discovered private chat_id from getUpdates. If empty, DM the bot first."
  exit 4
else
  echo "[FAIL] $(ts) | CAUSE: Unknown/Network. Try alternative network or set BOT_API_BASE to your proxy."
  echo "TIP: If on ship Wi-Fi, try mobile data/hotspot; some firewalls block Telegram posts but allow getMe."
  exit 4
fi
