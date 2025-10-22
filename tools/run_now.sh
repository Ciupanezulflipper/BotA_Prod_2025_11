#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Ensure env
if [ -f "$HOME/.env" ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' "$HOME/.env" | xargs)
fi
export PYTHONPATH="$HOME/bot-a"

usage() {
  echo "Usage: $0 {summary|news|audit|collect}"
  echo "  summary  -> send the daily Telegram recap now"
  echo "  news     -> run news sentiment fetch & append CSV (no Telegram)"
  echo "  audit    -> run post-trade audit of last 3 signals, 12h lookahead"
  echo "  collect  -> build daily merged & summary CSVs; tries Telegram"
  exit 1
}

cmd="${1:-}"
case "$cmd" in
  summary)
    python "$HOME/bot-a/tools/telegram_summary.py"
    ;;
  news)
    python "$HOME/bot-a/tools/news_sentiment.py" --limit 20
    ;;
  audit)
    python "$HOME/bot-a/tools/audit.py" --n 3 --lookahead 12 --write
    ;;
  collect)
    python "$HOME/bot-a/tools/daily_collect.py" --telegram
    ;;
  *)
    usage
    ;;
esac
