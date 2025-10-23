#!/data/data/com.termux/files/usr/bin/bash
# --------------------------------------------------------
#  Bot A : run_pair.sh  (Safe Execution + Auto Guard)
# --------------------------------------------------------
#  Usage: run_pair.sh PAIR
# --------------------------------------------------------

set -euo pipefail
PAIR="${1:-}"

if [ -z "$PAIR" ]; then
  echo "[ERROR] Usage: run_pair.sh PAIR"
  exit 1
fi

echo "[RUN $(date -u +'%Y-%m-%d %H:%M:%S UTC')] $PAIR starting"

# 1️⃣ Run core analysis and capture outputs
python3 "$HOME/BotA/core/analyze_pair.py" "$PAIR" >"$HOME/BotA/tmp_${PAIR}.out" 2>&1 || true

# 2️⃣ Extract key values
ENTRY=$(grep -m1 '^Entry:' "$HOME/BotA/tmp_${PAIR}.out" | awk '{print $2}')
TP=$(grep -m1 '^TP:' "$HOME/BotA/tmp_${PAIR}.out" | awk '{print $2}')
SL=$(grep -m1 '^SL:' "$HOME/BotA/tmp_${PAIR}.out" | awk '{print $2}')
ATR=$(grep -m1 '^ATR:' "$HOME/BotA/tmp_${PAIR}.out" | awk '{print $2}')
SIDE=$(grep -m1 '^Signal:' "$HOME/BotA/tmp_${PAIR}.out" | awk '{print $2}')
WEIGHTED=$(grep -m1 '^Weighted:' "$HOME/BotA/tmp_${PAIR}.out" | awk '{print $2}')

# 3️⃣ Validation helpers
is_num() { awk "BEGIN{exit ($1+0==$1)?0:1}" 2>/dev/null || return 1; }

# 4️⃣ Conditional logging
if [ -n "${SIDE:-}" ] && [ "$SIDE" != "No" ] && \
   [ -n "${ENTRY:-}" ] && [ -n "${TP:-}" ] && [ -n "${SL:-}" ] && [ -n "${ATR:-}" ] && \
   is_num "$ENTRY" && is_num "$TP" && is_num "$SL" && is_num "$ATR"; then
    echo "[SITE] Valid signal detected ($PAIR $SIDE)"
    python3 "$HOME/BotA/tools/sep_sidewrite.py" "$PAIR" "$SIDE" "$ENTRY" "$TP" "$SL" "$ATR" "${WEIGHTED:-0}"
else
    echo "[SITE] No valid signal ($PAIR)"
fi

# 5️⃣ Optional Telegram echo (already inside analysis)
grep -q "Telegram sent" "$HOME/BotA/tmp_${PAIR}.out" && echo "[SITE] Telegram confirmation seen"

# 6️⃣ Cleanup
rm -f "$HOME/BotA/tmp_${PAIR}.out"
