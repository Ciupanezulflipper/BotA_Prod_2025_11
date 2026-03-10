#!/usr/bin/env bash
set -euo pipefail
termux-wake-lock >/dev/null 2>&1 || true
nohup "$HOME/bot-a/tools/auto_eurusd.sh" >/dev/null 2>&1 &
echo "Started auto EURUSD (pid $!). Tail logs with: tail -f $HOME/bot-a/logs/auto_eurusd.log"
