#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$HOME/bot-a/tools"
python3 status_cmd.py --heartbeat || true
