#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
# Ensure env is available
if [ -f "$HOME/.env" ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' "$HOME/.env" | xargs)
fi
export PYTHONPATH="$HOME/bot-a"
python3 "$HOME/bot-a/tools/news_sentiment.py" || true
