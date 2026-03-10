#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SCRIPT='$HOME/BotA/tools/notify_on_change.sh'
LINE='*/5 * * * * DRY_RUN=0 bash "$HOME/BotA/tools/notify_on_change.sh" >>"$HOME/BotA/logs/notify_change.log" 2>&1   # BotA notify-on-change'

tmp="$(mktemp)"
crontab -l 2>/dev/null >"$tmp" || true
grep -Fq 'notify-on-change' "$tmp" || echo "$LINE" >>"$tmp"
crontab "$tmp"
rm -f "$tmp"
echo "[install] cron installed for notify-on-change (*/5)."
