#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

PAIR="EURUSD"
DATA_DIR="$HOME/bot-a/data"
mkdir -p "$DATA_DIR"

SCORE_FILE="$DATA_DIR/news_score.txt"
WHY_FILE="$DATA_DIR/news_why.txt"
OUT="$DATA_DIR/news_cache.json"

# Read score (first token), clamp 0..6
SCORE=0
if [[ -f "$SCORE_FILE" ]]; then
  read -r SCORE _ < "$SCORE_FILE" || SCORE=0
fi
case "$SCORE" in ''|*[!0-9]*) SCORE=0;; esac
(( SCORE < 0 )) && SCORE=0
(( SCORE > 6 )) && SCORE=6

# Read why (single line)
WHY="auto"
if [[ -f "$WHY_FILE" ]]; then
  WHY="$(tr -d '\n' < "$WHY_FILE")"
fi

UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cat > "$OUT" <<JSON
{"pair":"$PAIR","updated_utc":"$UTC","score_0_6":$SCORE,"why":"$WHY","sources":["manual","calendar"]}
JSON

echo "News cache updated: $OUT (score=$SCORE, utc=$UTC)"
