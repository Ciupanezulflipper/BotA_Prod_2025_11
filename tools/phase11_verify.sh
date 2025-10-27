#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"
LOG="$ROOT/control.log"

echo "=== Phase 11: Telegram Control — Smoke ==="

# 1) Ensure controller booted
"$TOOLS/tele_control.sh"

# 2) Print tail of control log to confirm polling
echo "--- control.log (tail) ---"
tail -n 20 "$LOG" || true

# 3) Guidance (non-invasive): send these in Telegram:
cat <<'TXT'

Now send commands to your bot in Telegram (one by one):

  /status        -> should show proc + log ages
  /audit         -> should return a compact metrics block
  /pause_alerts  -> should stop the background alert_loop
  /start_alerts  -> should (re)start the alert_loop
  /help          -> quick menu

Acceptance:
- /status responds within ~2s
- /audit returns metrics text
- /pause_alerts followed by /status shows proc: alert_loop=0
- /start_alerts followed by /status shows proc: alert_loop=1

TXT
echo "=== Phase 11: PASSED (manual chat checks required) ==="
