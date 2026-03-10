#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="/data/data/com.termux/files/home/BotA"
LOG="${ROOT}/logs/proof_step5_telegram_path.log"

cd "$ROOT"

safe_source_env() {
  local env_file="$1"
  if [ ! -f "$env_file" ]; then
    echo "[STEP5] safe_source_env: missing $env_file"
    return 0
  fi
  eval "$(
python3 - <<'PY' "$env_file"
import re, sys, shlex
path = sys.argv[1]
out = []
for raw in open(path, "r", encoding="utf-8", errors="ignore"):
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    if line.lower().startswith("export "):
        line = line[7:].strip()
    if "=" not in line:
        continue
    k, v = line.split("=", 1)
    k = k.strip()
    v = v.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k or ""):
        continue
    if (len(v) >= 2) and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        v = v[1:-1]
    out.append(f"export {k}={shlex.quote(v)}")
print("\n".join(out))
PY
)"
}

echo "=== PROOF STEP 5: Telegram path (NO SEND) ==="
echo "DATE: $(date)"
echo "PWD: $(pwd)"
echo

echo "=== LOAD .env (safe) ==="
safe_source_env "${ROOT}/.env" >/dev/null 2>&1 || true
echo "loaded_env=yes (if .env existed)"
echo

token="${TELEGRAM_BOT_TOKEN:-${TELEGRAM_TOKEN:-}}"
chat="${TELEGRAM_CHAT_ID:-${TELEGRAM_CHATID:-}}"

token_present="no"
token_len="0"
if [ -n "${token:-}" ]; then
  token_present="yes"
  token_len="${#token}"
fi

chat_present="no"
if [ -n "${chat:-}" ]; then
  chat_present="yes"
fi

curl_present="no"
if command -v curl >/dev/null 2>&1; then
  curl_present="yes"
fi

echo "token_present=${token_present} token_len=${token_len}"
echo "chat_id_present=${chat_present}"
echo "curl_present=${curl_present}"
echo

echo "=== TELEGRAM API: getMe (safe check; no message) ==="
getme_ok="unknown"
bot_user="unknown"
bot_id="unknown"

if [ "${token_present}" = "yes" ] && [ "${curl_present}" = "yes" ]; then
  # Do NOT echo URL (contains token)
  resp="$(curl -sS --max-time 15 "https://api.telegram.org/bot${token}/getMe" || true)"
  python3 - <<'PY' "$resp"
import json, sys
raw = sys.argv[1]
try:
    j = json.loads(raw)
except Exception as e:
    print("getMe_parse_failed:", e)
    print("raw_head:", raw[:240].replace("\n","\\n"))
    sys.exit(0)

ok = j.get("ok", False)
res = j.get("result") or {}
print("getMe_ok=", ok)
print("bot_id=", res.get("id"))
print("bot_username=", res.get("username"))
PY
else
  echo "SKIP getMe: missing token and/or curl"
fi
echo

echo "=== FIND: telegram entrypoints (top 80 hits) ==="
grep -R --line-number -E 'api\.telegram\.org|sendMessage|getMe|TELEGRAM_CHAT_ID|TELEGRAM_BOT_TOKEN|TELEGRAM_TOKEN|telegram_send|bot/send' \
  "$ROOT" 2>/dev/null | head -n 80 || true
echo

echo "=== WATCHER: telegram callsites (signal_watcher_pro.sh) ==="
if [ -f "${ROOT}/tools/signal_watcher_pro.sh" ]; then
  grep -nE 'TELEGRAM|sendMessage|api\.telegram\.org|telegram' "${ROOT}/tools/signal_watcher_pro.sh" | head -n 160 || true
else
  echo "MISSING: tools/signal_watcher_pro.sh"
fi
echo

echo "=== STEP 5 OUTPUT: 4 LINES TO PASTE BACK ==="
echo "1) token_present=${token_present} token_len=${token_len}"
echo "2) chat_id_present=${chat_present}"
echo "3) curl_present=${curl_present}"
echo "4) getMe_result=SEE_ABOVE (getMe_ok/bot_id/bot_username)"
echo
echo "=== PROOF STEP 5 END ==="
