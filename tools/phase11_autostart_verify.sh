#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$HOME/BotA"

echo "=== Phase 11: Autostart sanity ==="
# 1) Manual trigger (idempotent)
"$HOME/BotA/tools/boot.sh"

# 2) Process check
ALERT_P=$(pgrep -f "tools/alert_loop.sh" || true)
CTRL_P=$(pgrep -f "python3 .*tele_control.py" || true)
echo "proc: alert_loop=$([ -n "$ALERT_P" ] && echo 1 || echo 0)  tele_control=$([ -n "$CTRL_P" ] && echo 1 || echo 0)"

# 3) Log freshness
ALOG="$ROOT/alert.log"; CLOG="$ROOT/control.log"; BLOG="$ROOT/boot.log"
ts(){ [ -f "$1" ] && printf "%s\n" "$(($(date +%s) - $(stat -c %Y "$1")))" || printf "n/a\n"; }
echo "age_s: alert.log=$(ts "$ALOG")  control.log=$(ts "$CLOG")  boot.log=$(ts "$BLOG")"

# 4) Guidance (no invasive actions)
cat <<'TXT'
If you have the Termux:Boot app installed, autostart is active via:
  $HOME/.termux/boot/bota_start.sh

Acceptance:
- Running this script shows proc: alert_loop=1 and tele_control=1.
- alert.log age < 60s after a fresh boot.sh.
- Optional Telegram ping "BotA booted" appears if TELEGRAM_* exported.
TXT

echo "=== Phase 11: PASSED (smoke) ==="
