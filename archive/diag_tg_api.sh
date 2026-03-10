#!/data/data/com.termux/files/usr/bin/bash
# File: $HOME/BotA/tools/diag_tg_api.sh
# Purpose: Deep diagnostics for Telegram delivery (IPv4, HTTP status, body preview, CA probe).
# Never prints the token. Uses Bot API base override if provided.

set -euo pipefail
BOT_DIR="${BOT_DIR:-$HOME/BotA}"
ENV_FILE="$BOT_DIR/.env"
SENDER="$BOT_DIR/tools/send-tg.sh"
LOG_DIR="$BOT_DIR/logs"; mkdir -p "$LOG_DIR"
BOT_API_BASE="${BOT_API_BASE:-https://api.telegram.org}"
TMP_BODY="$LOG_DIR/diag_body.tmp"

ts(){ date +"%Y-%m-%d %H:%M:%S%z"; }

# Token resolution (no echo)
if [[ -n "${TELEGRAM_TOKEN:-}" ]]; then
  TOKEN_VALUE="$TELEGRAM_TOKEN"
elif [[ -f "$ENV_FILE" ]]; then
  TOKEN_VALUE="$(grep -E '^TELEGRAM_TOKEN=' "$ENV_FILE" | head -n1 | cut -d= -f2- || true)"
else
  TOKEN_VALUE=""
fi
[[ -n "$TOKEN_VALUE" ]] || { echo "[FAIL] $(ts) | TELEGRAM_TOKEN missing"; exit 1; }

API_BASE="${BOT_API_BASE%/}/bot${TOKEN_VALUE}"

echo "[INFO] $(ts) | curl version: $(curl --version | head -n1)"
echo "[INFO] $(ts) | IPv4 connectivity test to base…"
curl -4 -sS -m 10 -o /dev/null -w "[INFO] $(ts) | base HEAD http=%{http_code} type=%{content_type}\n" "${BOT_API_BASE%/}"

echo "[INFO] $(ts) | getMe (IPv4)…"
HTTP=$(curl -4 -sS -m 20 -w "%{http_code}" -o "$TMP_BODY" "$API_BASE/getMe" || true)
CT=$(file -b --mime-type "$TMP_BODY" 2>/dev/null || echo "unknown")
echo "[INFO] $(ts) | getMe http=${HTTP} mime=${CT}"

if [[ "$HTTP" != "200" ]]; then
  # Show short body preview (redacted)
  PREV="$(head -c 200 "$TMP_BODY" | tr '\n' ' ' | sed 's/[[:cntrl:]]/ /g')"
  echo "[WARN] $(ts) | Non-200 body preview: ${PREV}"
  echo "[INFO] $(ts) | CA probe (insecure, for diagnosis ONLY)…"
  HTTPK=$(curl -4 -k -sS -m 20 -w "%{http_code}" -o /dev/null "$API_BASE/getMe" || true)
  echo "[INFO] $(ts) | insecure getMe http=${HTTPK}"
  if [[ "$HTTPK" == "200" && "$HTTP" != "200" ]]; then
    echo "[FAIL] $(ts) | Likely CA/cert validation issue on device. Install/refresh ca-certificates."
    exit 2
  fi
  echo "[FAIL] $(ts) | Network/API reachability problem (HTTP=$HTTP). Check firewall/DNS/IPv6."
  exit 2
fi

# Parse JSON ok
OK="$(python3 - <<'PY' "$TMP_BODY"
import sys,json; d=json.loads(open(sys.argv[1],'rb').read() or b'{}'); print("true" if d.get("ok") else "false")
PY
)"
if [[ "$OK" != "true" ]]; then
  DESC="$(python3 - <<'PY' "$TMP_BODY"
import sys,json; 
try: print(json.loads(open(sys.argv[1],'rb').read() or b'{}').get("description",""))
except: print("")
PY
)"
  echo "[FAIL] $(ts) | getMe JSON not ok | desc=${DESC}"
  exit 2
fi

# Try a PING via sender (uses IPv4 and overrides)
read -r -d '' PAYLOAD <<'TXT' || true
<b>BotA PING</b>
• Source: diag_tg_api.sh
• Expect: PASS
TXT

if "$SENDER" <<< "$PAYLOAD"; then
  echo "[PASS] $(ts) | Sender delivered PING"
  exit 0
else
  echo "[FAIL] $(ts) | Sender failed despite API OK. Inspect logs/send-tg.log"
  exit 3
fi
