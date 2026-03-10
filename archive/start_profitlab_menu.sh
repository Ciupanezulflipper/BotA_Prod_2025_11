#!/usr/bin/env bash
set -euo pipefail
set -a; . "$HOME/bot-a/.env.profitlab"; set +a
tmux kill-session -t profitlab_menu 2>/dev/null || true
tmux new-session -ds profitlab_menu 'PYTHONPATH="$HOME/bot-a" python3 -u $HOME/bot-a/tools/tg_menu.py >> $HOME/bot-a/logs/tg_menu.log 2>&1'
echo "Profit Lab menu started."
