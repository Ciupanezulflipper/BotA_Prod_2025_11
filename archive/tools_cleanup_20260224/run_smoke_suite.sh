#!/data/data/com.termux/files/usr/bin/bash
# File: $HOME/BotA/tools/run_smoke_suite.sh
# Purpose: One-click runner for send-tg.sh post-audit smoke tests.

set -euo pipefail

BOT_DIR="${BOT_DIR:-$HOME/BotA}"
SENDER="$BOT_DIR/tools/send-tg.sh"
SMOKE="$BOT_DIR/tools/smoke_send_tg.sh"
LOG_DIR="$BOT_DIR/logs"
SENDER_LOG="$LOG_DIR/send-tg.log"
mkdir -p "$LOG_DIR"

# Guards
EXPECTED_SHEBANG="/data/data/com.termux/files/usr/bin/bash"
[[ -x "$EXPECTED_SHEBANG" ]] || { echo "[SETUP FAIL] Expected Termux bash not found at $EXPECTED_SHEBANG"; exit 3; }
[[ -x "$SENDER" ]] || { echo "[SETUP FAIL] Missing or non-executable: $SENDER"; exit 3; }
[[ -x "$SMOKE"  ]] || { echo "[SETUP FAIL] Missing or non-executable: $SMOKE"; exit 3; }

# Token: allow env or .env
if [[ -z "${TELEGRAM_TOKEN:-}" ]]; then
  if [[ -f "$BOT_DIR/.env" ]]; then
    export TELEGRAM_TOKEN="$(grep -E '^TELEGRAM_TOKEN=' "$BOT_DIR/.env" | head -n1 | cut -d= -f2- || true)"
  fi
fi
[[ -n "${TELEGRAM_TOKEN:-}" ]] || { echo "[SETUP FAIL] TELEGRAM_TOKEN not set (env or $BOT_DIR/.env required)"; exit 3; }

echo "[RUN] Smoke tests starting..."
set +e
"$SMOKE"
rc=$?
set -e

echo
echo "================= Sender Log (last 50) ================="
if [[ -f "$SENDER_LOG" ]]; then
  tail -n 50 "$SENDER_LOG" || true
else
  echo "(no sender log found at $SENDER_LOG)"
fi
echo "========================================================"
echo

case "$rc" in
  0) echo "[RESULT] ALL TESTS PASSED" ;;
  2) echo "[RESULT] ONE OR MORE TESTS FAILED" ;;
  *) echo "[RESULT] UNKNOWN RETURN CODE: $rc" ;;
esac

exit "$rc"
