#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# --- Load env (silent if missing) ---
ENV_FILE="$HOME/BotA/.env"
if [ -f "$ENV_FILE" ]; then
  set -a; . "$ENV_FILE"; set +a
fi

# --- Defaults / paths ---
BASE_DIR="${BASE_DIR:-$HOME/BotA}"
LOG_DIR="${LOG_DIR:-$BASE_DIR/logs}"
STATE_DIR="${STATE_DIR:-$BASE_DIR/state}"
PAIRS_CSV="${PAIRS:-EURUSD,GBPUSD}"

TELEGRAM_TOKEN="${TELEGRAM_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"
DRY_RUN="${DRY_RUN:-0}"

mkdir -p "$STATE_DIR"

# --- Preconditions ---
LOOP_LOG="$LOG_DIR/loop.log"
if [ ! -s "$LOOP_LOG" ]; then
  echo "[notify] loop.log missing or empty: $LOOP_LOG"
  exit 0
fi

if [ -z "$TELEGRAM_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
  echo "[notify] TELEGRAM env not set; skipping send."
  DRY_RUN=1
fi

# --- Pull latest [run] line per requested pair ---
# Expected line format example:
# [run] EURUSD TF15 decision=WAIT score=0 weak=false provider=twelve_data age=0.0 price=1.15725
LATEST="$(awk -v pairs="$PAIRS_CSV" '
  BEGIN {
    n=split(pairs, want, ",");
    for(i=1;i<=n;i++){ trim=want[i]; gsub(/^ +| +$/,"",trim); W[trim]=1 }
  }
  /\[run\]/ {
    pair=$2;
    if(pair in W) last[pair]=$0
  }
  END {
    for(p in W) if(p in last) printf("%s\n", last[p]);
  }
' "$LOOP_LOG")"

if [ -z "$LATEST" ]; then
  echo "[notify] No matching [run] lines yet for pairs: $PAIRS_CSV"
  exit 0
fi

send_msg() {
  local text="$1"
  if [ "$DRY_RUN" = "1" ]; then
    echo "[notify:DRY] $text"
    return 0
  fi
  curl -s "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    -d chat_id="$TELEGRAM_CHAT_ID" \
    --data-urlencode text="$text" >/dev/null 2>&1 || true
}

# --- Process each latest line and notify on state change ---
changed_any=0
while IFS= read -r line; do
  [ -z "$line" ] && continue
  pair="$(echo "$line" | awk '{print $2}')"
  decision="$(printf "%s\n" "$line" | sed -E 's/.*decision=([A-Z]+).*/\1/')"
  price="$(printf "%s\n" "$line" | sed -E 's/.*price=([0-9]+\.[0-9]+).*/\1/')"
  provider="$(printf "%s\n" "$line" | sed -E 's/.*provider=([a-z_]+).*/\1/')"
  tf="$(printf "%s\n" "$line" | awk '{print $3}')"

  [ -z "$pair" ] && continue
  [ -z "$decision" ] && decision="NA"
  [ -z "$price" ] && price="NA"
  [ -z "$provider" ] && provider="unknown"
  [ -z "$tf" ] && tf="TF?"

  state_file="$STATE_DIR/last_decision_${pair}.txt"
  prev="(none)"
  if [ -f "$state_file" ]; then
    prev="$(cat "$state_file" 2>/dev/null || echo "(none)")"
  fi

  curr="${pair}:${decision}"
  if [ "$curr" != "$prev" ]; then
    printf "%s\n" "$curr" > "$state_file"
    changed_any=1
    # Build compact human message
    msg="🔔 BotA state change\n• ${pair} ${tf}\n• decision: ${prev#*:} → ${decision}\n• price: ${price}\n• provider: ${provider}"
    send_msg "$msg"
    echo "[notify] change: $prev -> $curr"
  else
    echo "[notify] no change for $pair (still ${decision})"
  fi
done <<EOF
$LATEST
EOF

# Optional aggregate ping if multiple changed
if [ "$changed_any" = "1" ]; then
  echo "[notify] done (changes sent)."
else
  echo "[notify] done (no changes)."
fi
