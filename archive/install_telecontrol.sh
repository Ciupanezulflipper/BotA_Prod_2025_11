#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Preserve existing crontab, then add @reboot line if missing
tmp="$(mktemp)"
crontab -l 2>/dev/null > "$tmp" || true

BOOT_LINE='@reboot bash "/data/data/com.termux/files/home/BotA/tools/telecontrol.sh" start >>"/data/data/com.termux/files/home/BotA/logs/cron.boot.log" 2>&1   # BotA telecontrol'

grep -F "$BOOT_LINE" "$tmp" >/dev/null 2>&1 || echo "$BOOT_LINE" >> "$tmp"

crontab "$tmp"
rm -f "$tmp"
echo "[install] telecontrol @reboot installed."
