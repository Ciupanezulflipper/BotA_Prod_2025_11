#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

TOOLS="$HOME/BotA/tools"
RUN_ONCE="$TOOLS/run_signal_once.sh"
FORMATTER="$TOOLS/format_card.py"
SENDTG="$TOOLS/send-tg.sh"

: "${SEND_WAIT:=0}"   # 0 = suppress WAIT, 1 = send anyway

# Run once and capture raw output
RAW="$("$RUN_ONCE")"
# Echo to stderr for visibility when running manually
printf "%s\n" "$RAW" >&2

# Extract decision (BUY/SELL/WAIT)
DECISION="$(printf "%s\n" "$RAW" | awk '/^\[run\] .* decision=/{for(i=1;i<=NF;i++){if($i ~ /^decision=/){split($i,a,"="); print toupper(a[2]); exit}}}')"
DECISION="${DECISION:-UNKNOWN}"

if [ "$DECISION" = "WAIT" ] && [ "${SEND_WAIT}" -eq 0 ]; then
  echo "[send_card] Skipped WAIT (set SEND_WAIT=1 to send)" >&2
  exit 0
fi

# Format card and send
CARD="$(printf "%s\n" "$RAW" | "$FORMATTER")"
printf "%s\n" "$CARD" | "$SENDTG"
