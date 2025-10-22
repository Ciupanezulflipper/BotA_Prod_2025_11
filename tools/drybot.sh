#!/usr/bin/env bash
# Dry run (no Telegram send). Useful for quick checks.

set -euo pipefail
export PYTHONPATH="$HOME/bot-a"

python "$HOME/bot-a/tools/signal_runner.py" --dry
