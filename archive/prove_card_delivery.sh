#!/data/data/com.termux/files/usr/bin/bash
# File: $HOME/BotA/tools/prove_card_delivery.sh
# Purpose: Prove end-to-end delivery (formatter → Telegram) and print a clear PASS/FAIL.
# Behavior:
#   - Builds a sample BUY card payload
#   - Pipes through format_card.py → send-tg.sh
#   - Detects success by comparing "OK  | sent" counters in logs/send-tg.log
#   - Tails the last 40 log lines for human review
# Exit codes:
#   0 = PASS (card delivered)
#   2 = FAIL (no new "OK  | sent" after attempt)
#   3 = Setup error (missing files/token)

set -euo pipefail

BOT_DIR="${BOT_DIR:-$HOME/BotA}"
FORMATTER="$BOT_DIR/tools/format_card.py"
SENDER="$BOT_DIR/tools/send-tg.sh"
LOG_DIR="$BOT_DIR/logs"
LOG_FILE="$LOG_DIR/send-tg.log"

# --- Guards ---
[[ -x "$FORMATTER" ]] || { echo "[SETUP FAIL] Missing or non-executable: $FORMATTER"; exit 3; }
[[ -x "$SENDER"    ]] || { echo "[SETUP FAIL] Missing or non-executable: $SENDER"; exit 3; }
mkdir -p "$LOG_DIR"

# Token presence (env or .env resolved by sender, just sanity check here)
if [[ -z "${TELEGRAM_TOKEN:-}" ]]; then
  if [[ -f "$BOT_DIR/.env" ]]; then
    grep -q '^TELEGRAM_TOKEN=' "$BOT_DIR/.env" || { echo "[SETUP FAIL] TELEGRAM_TOKEN not found in $BOT_DIR/.env"; exit 3; }
  else
    echo "[SETUP FAIL] TELEGRAM_TOKEN not set and $BOT_DIR/.env missing"
    exit 3
  fi
fi

# --- Count OK lines before send ---
pre_ok_count="$(grep -c "OK  | sent" "$LOG_FILE" 2>/dev/null || true)"

# --- Sample payload (BUY card) ---
read -r -d '' PAYLOAD <<'TXT' || true
pair=EURUSD
decision=BUY
score=72
weak=false
provider=YF
age=0.2
price=1.1111
TXT

# --- Send pipeline: formatter → sender ---
printf "%s" "$PAYLOAD" | "$FORMATTER" | "$SENDER" || true

# Give the logger a moment
sleep 1.5

# --- Count OK lines after send ---
post_ok_count="$(grep -c "OK  | sent" "$LOG_FILE" 2>/dev/null || true)"

echo
echo "================= send-tg.log (last 40) ================="
tail -n 40 "$LOG_FILE" 2>/dev/null || echo "(no log yet)"
echo "========================================================="
echo

if [[ "$post_ok_count" -gt "$pre_ok_count" ]]; then
  echo "[PASS] Card delivered via formatter → Telegram (OK count ${pre_ok_count} → ${post_ok_count})"
  exit 0
else
  echo "[FAIL] No new successful send detected (OK count stayed at ${pre_ok_count})"
  echo "Hint: If logs show WARN/FAIL, share the last 40 lines above."
  exit 2
fi
