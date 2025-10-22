#!/usr/bin/env bash
# Run Bot-A signals for all symbols (send to Telegram if env is set)

set -euo pipefail
export PYTHONPATH="$HOME/bot-a"

python "$HOME/bot-a/tools/signal_runner.py" --send
