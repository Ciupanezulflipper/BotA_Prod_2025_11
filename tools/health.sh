#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
HOME=/data/data/com.termux/files/home
echo -n "HB age(s): "; echo $(( $(date -u +%s) - $(cat "$HOME/BotA/heartbeat.txt" 2>/dev/null || echo 0) ))
echo "Cron:"
crontab -l
echo "Crond processes:"
pgrep -fa crond || true
echo "Last 6 decisions:"
grep -nE '^(Signal:|Reason:|Telegram sent\.)' "$HOME/BotA/run.log" | tail -18
