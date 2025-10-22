#!/usr/bin/env bash
set -euo pipefail
export HOME="${HOME:-/data/data/com.termux/files/home}"
export PYTHONPATH="$HOME/bot-a/tools:${PYTHONPATH:-}"
cd "$HOME/bot-a/tools"
# weekend/holiday guard likely already blocks when closed; this just runs
exec python3 "$HOME/bot-a/tools/guarded_launcher.py" "$@"
