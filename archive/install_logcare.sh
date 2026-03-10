#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
QUOTA_LINE='5 * * * * bash "$HOME/BotA/tools/tg_quota_status.sh" >>"$HOME/BotA/logs/quota_tg.log" 2>&1   # BotA logcare'
ROTATE_LINE='0 3 * * * bash "$HOME/BotA/tools/logrotate_simple.sh" --apply >>"$HOME/BotA/logs/logrotate.log" 2>&1   # BotA logcare'

existing="$(crontab -l 2>/dev/null || true)"
preview="$(printf "%s\n%s\n%s\n" "$existing" "$QUOTA_LINE" "$ROTATE_LINE" | awk '!seen[$0]++')"

if [[ "$APPLY" -eq 1 ]]; then
  tmp="$(mktemp)"
  printf "%s\n" "$preview" > "$tmp"
  crontab "$tmp"
  rm -f "$tmp"
  echo "[logcare] crontab updated."
else
  echo "[logcare] preview only (no changes). Use --apply to write."
  echo "----- CRONTAB PREVIEW -----"
  printf "%s\n" "$preview"
  echo "---------------------------"
fi
