#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
# load env if present
if [ -f "$HOME/.env" ]; then
  export $(grep -v '^#' "$HOME/.env" | xargs)
fi
export PYTHONPATH="$HOME/bot-a"
python "$HOME/bot-a/tools/signal_fusion.py" --since-min 120 --send || true
