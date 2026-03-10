#!/usr/bin/env bash
set -euo pipefail
set -a; . "$HOME/bot-a/.env.botA"; set +a
tmux kill-session -t botA_h1 2>/dev/null || true
tmux new-session -ds botA_h1 'bash $HOME/bot-a/tools/auto_h1.sh'
echo "Bot A loop started."
