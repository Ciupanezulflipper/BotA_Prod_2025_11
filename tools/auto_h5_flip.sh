#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

LOG="$HOME/bot-a/logs/auto_h5.log"
PID="$HOME/bot-a/logs/auto_h5.pid"
STATE="$HOME/bot-a/logs/auto_h5.state"
GATE=13    # 80% of 16

mkdir -p "$HOME/bot-a/logs"
echo $$ > "$PID"

last_dec="$(cat "$STATE" 2>/dev/null || echo "")"

while true; do
  out="$(PYTHONPATH="$HOME/bot-a" python3 "$HOME/bot-a/tools/signal_h5_sent.py" --no-send || true)"

  # Parse Decision and Tech from the card
  dec="$(printf "%s\n" "$out" | awk -F'[*]' '/^Decision:/ {print $2}')"
  tech="$(printf "%s\n" "$out" | sed -n 's/^Tech: *\([0-9]\+\)\/16.*/\1/p')"

  send=0
  if [[ "$dec" != "$last_dec" && "$dec" != "HOLD" ]]; then
    send=1
  elif [[ "${tech:-0}" -ge $GATE ]]; then
    send=1
  fi

  if [[ $send -eq 1 ]]; then
    printf "%s\n" "$out" >>"$LOG"
    printf "%s\n" "$out" | "$HOME/bot-a/tools/send_tg.sh"
    echo "$dec" >"$STATE"
    last_dec="$dec"
  fi

  sleep 60
done >>"$LOG" 2>&1
