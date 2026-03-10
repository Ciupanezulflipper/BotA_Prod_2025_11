#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${HOME}/BotA"
TOOLS="${ROOT}/tools"
LOGS="${ROOT}/logs"
mkdir -p "${LOGS}"

# Ensure termux-services & crond exist and are running (idempotent)
pkg install -y termux-services >/dev/null 2>&1 || true
sv-enable crond >/dev/null 2>&1 || true
sv up crond >/dev/null 2>&1 || true

TMP="$(mktemp)"
# Preserve existing lines, drop previous BotA block
crontab -l 2>/dev/null | grep -v '# BotA' >"$TMP" || true

{
  echo "# ================= Bot A Production Crontab =================  # BotA"
  echo "# Safety: run inside repo                                       # BotA"
  echo "@reboot bash \"$TOOLS/daemonctl.sh\" start >>\"$LOGS/cron.boot.log\" 2>&1   # BotA"
  echo "*/5 * * * * bash \"$TOOLS/watchdog.sh\" >>\"$LOGS/watchdog.log\" 2>&1      # BotA"
} >> "$TMP"

crontab "$TMP"
rm -f "$TMP"
echo "cron installed (reboot start + 5-min watchdog)"
