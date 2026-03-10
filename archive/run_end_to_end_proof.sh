#!/data/data/com.termux/files/usr/bin/bash
# File: $HOME/BotA/tools/run_end_to_end_proof.sh
# Purpose: One-click, end-to-end proof that Bot A can deliver Telegram cards.
# Sequence:
#   1) Ensure TELEGRAM_TOKEN + TELEGRAM_CHAT_ID (.env) via fix_token_chat_env.sh
#   2) Verify Telegram delivery path (direct, smoke, diagnostics)
#   3) Prove formatter → sender by sending a sample BUY card
# Output: Clear PASS/FAIL summary + relevant log tails.
# Exit codes:
#   0 = ALL PASS
#   2 = Telegram delivery path failed
#   3 = Formatter→Sender failed
#   4 = Setup error (missing scripts, token)

set -euo pipefail

BOT_DIR="${BOT_DIR:-$HOME/BotA}"
LOG_DIR="$BOT_DIR/logs"
mkdir -p "$LOG_DIR"

FIX="$BOT_DIR/tools/fix_token_chat_env.sh"
VERIFY="$BOT_DIR/tools/verify_telegram_delivery.sh"
PROVE="$BOT_DIR/tools/prove_card_delivery.sh"
SENDER_LOG="$LOG_DIR/send-tg.log"

# ------- Guards -------
for f in "$FIX" "$VERIFY" "$PROVE"; do
  [[ -x "$f" ]] || { echo "[SETUP FAIL] Missing or non-executable: $f"; exit 4; }
done

# ------- Step 1: Ensure token/chat -------
echo "[STEP 1] Ensuring TELEGRAM_TOKEN + TELEGRAM_CHAT_ID in .env…"
"$FIX" || true

# ------- Step 2: Verify Telegram delivery path -------
echo "[STEP 2] Verifying Telegram delivery path (direct + smoke + diag)…"
set +e
"$VERIFY"
RC_VERIFY=$?
set -e
if [[ $RC_VERIFY -ne 0 ]]; then
  echo
  echo "================= send-tg.log (last 60) ================="
  tail -n 60 "$SENDER_LOG" 2>/dev/null || echo "(no sender log yet)"
  echo "========================================================="
  echo "[FAIL] Telegram delivery verification failed (rc=$RC_VERIFY)"
  exit 2
fi

# ------- Step 3: Prove formatter → sender -------
echo "[STEP 3] Proving formatter → sender (sample BUY card)…"
set +e
"$PROVE"
RC_PROVE=$?
set -e
if [[ $RC_PROVE -ne 0 ]]; then
  echo
  echo "================= send-tg.log (last 60) ================="
  tail -n 60 "$SENDER_LOG" 2>/dev/null || echo "(no sender log yet)"
  echo "========================================================="
  echo "[FAIL] Formatter→Sender proof failed (rc=$RC_PROVE)"
  exit 3
fi

# ------- Summary -------
echo
echo "======================== SUMMARY ========================"
echo "✅ Step 1: Token/Chat ensured"
echo "✅ Step 2: Telegram delivery path (direct, smoke, diag) PASSED"
echo "✅ Step 3: Formatter → Sender BUY card delivered"
echo "========================================================="
exit 0
