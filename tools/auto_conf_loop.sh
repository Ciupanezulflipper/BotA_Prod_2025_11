#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

LOG="$HOME/bot-a/logs/auto_conf.log"
PID="$HOME/bot-a/logs/auto_conf.pid"
STATE="$HOME/bot-a/logs/auto_conf.state"

mkdir -p "$HOME/bot-a/logs"
echo $$ >"$PID"

# how often to check (sec)
INTERVAL=60

# run loop
while true; do
  TS="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"

  # generate the card (no send here)
  OUT="$(PYTHONPATH="$HOME/bot-a" python3 "$HOME/bot-a/tools/runner_confluence.py" 2>&1 || true)"

  # pull the one-line “Adj/Confidence/Final Bias” area to use as a change key
  KEY="$(printf '%s\n' "$OUT" | awk '/^\* Final Bias:/,/^$/' | tr -d '\r')"

  SEND=0
  NOTE=""

  # change-based trigger
  if [[ ! -s "$STATE" ]]; then
    SEND=1
    NOTE="first_run"
  else
    LAST="$(cat "$STATE" || true)"
    if [[ "$KEY" != "$LAST" ]]; then
      SEND=1
      NOTE="flip_or_conf_change"
    fi
  fi

  # save current snapshot
  printf '%s' "$KEY" > "$STATE"

  # log every cycle
  {
    echo "[$TS] ---"
    printf '%s\n' "$OUT" | sed -n '1,20p'
    echo "[gate] reason=$NOTE send=$SEND"
  } >>"$LOG" 2>&1

  # optional send (only if token/env properly set)
  if [[ "${SEND}" -eq 1 && -n "${BOT_TOKEN:-}" && -n "${CHAT_ID:-}" ]]; then
    if [[ -x "$HOME/bot-a/tools/send_tg.sh" ]]; then
      printf '%s\n' "$OUT" | "$HOME/bot-a/tools/send_tg.sh" >>"$LOG" 2>&1 || true
    else
      # fallback: curl raw
      curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d chat_id="${CHAT_ID}" \
        --data-urlencode text@"-" \
        -d parse_mode="Markdown" >>"$LOG" 2>&1 <<<"$OUT" || true
    fi
  fi

  sleep "$INTERVAL"
done
