#!/data/data/com.termux/files/usr/bin/bash
# File: $HOME/BotA/tools/smoke_send_tg.sh
# Purpose: Post-audit smoke tests for tools/send-tg.sh (no token leakage).
# Fix: Use here-strings (<<<) to feed stdin reliably on Termux (avoids empty BODY).
# Exit: 0 all pass, 2 any fail, 1 setup error.

set -euo pipefail

BOT_DIR="${BOT_DIR:-$HOME/BotA}"
SENDER="$BOT_DIR/tools/send-tg.sh"
LOG_DIR="$BOT_DIR/logs"
mkdir -p "$LOG_DIR"

# --- Guards ---
[[ -x "$SENDER" ]] || { echo "[FAIL] Missing or non-executable: $SENDER"; exit 1; }
if [[ -z "${TELEGRAM_TOKEN:-}" && ! -f "$BOT_DIR/.env" ]]; then
  echo "[FAIL] TELEGRAM_TOKEN not set (env or $BOT_DIR/.env required)"
  exit 1
fi

_passes=0
_fails=0
_ts() { date +"%Y-%m-%d %H:%M:%S%z"; }

_send_case() {
  # $1=name  $2=payload
  local name="$1"
  local payload="$2"
  local len
  len="$(printf "%s" "$payload" | wc -c | tr -d ' ')"

  printf "[INFO] %s | Running: %s | bytes=%s\n" "$(_ts)" "$name" "$len"

  if [[ "$len" -eq 0 ]]; then
    printf "[FAIL] %s | %s | empty payload\n" "$(_ts)" "$name"
    _fails=$((_fails+1))
    return
  fi

  # Primary: here-string into SENDER (reliable stdin on Termux)
  if "$SENDER" <<< "$payload"; then
    printf "[PASS] %s | %s\n" "$(_ts)" "$name"
    _passes=$((_passes+1))
    return
  fi

  # Fallback: classic pipe (printf → SENDER)
  if printf "%s" "$payload" | "$SENDER"; then
    printf "[PASS] %s | %s (fallback pipe)\n" "$(_ts)" "$name"
    _passes=$((_passes+1))
  else
    printf "[FAIL] %s | %s\n" "$(_ts)" "$name"
    _fails=$((_fails+1))
  fi

  sleep 1
}

# --- Case 1: Simple HTML message (should succeed as HTML) ---
case1_payload=$(
  cat <<'MSG'
<b>Bot A Smoke</b>
• Mode: <i>Debug</i>
• Expect: <u>PASS (HTML)</u>
— — — — —
<code>FORMAT_CARD</code> ✓ • Timeout ✓ • Retries ✓ • LengthGuard ✓
MSG
)
_send_case "Case 1: Simple HTML" "$case1_payload"

# --- Case 2: Entities/HTML stress (forces fallback <pre>) ---
case2_payload=$(
  cat <<'MSG'
<b>Entities Stress</b>
Raw angle brackets and ampersands:
  <this_should_be_literal> & this & that
Broken HTML start tag: <b><i>unclosed
JSON-like:
{
  "pair": "EURUSD",
  "signal": "WAIT",
  "score": 26,
  "note": "Expect <pre> fallback if entities break HTML"
}
MSG
)
_send_case "Case 2: Entities Stress → <pre> fallback" "$case2_payload"

# --- Case 3: Oversize 5000 chars (should trim to 4096 safely) ---
case3_payload="$(python3 - <<'PY'
import string
unit = ("[LONG] " + string.ascii_letters + " <> & ")*20
text = "Oversize Test — expect trimmed to 4096 and PASS.\n" + unit*50
print(text)
PY
)"
_send_case "Case 3: Oversize 5k → Trim 4096" "$case3_payload"

echo
printf "==============================================\n"
printf " Smoke Test Summary: PASS=%d  FAIL=%d\n" "$_passes" "$_fails"
printf " Log file (sender): %s/send-tg.log\n" "$LOG_DIR"
printf "==============================================\n"

[[ $_fails -gt 0 ]] && exit 2 || exit 0
