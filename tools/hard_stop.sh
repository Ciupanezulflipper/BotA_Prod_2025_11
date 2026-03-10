#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$BASE/logs"
STATE_DIR="$BASE/state"
mkdir -p "$LOG_DIR" "$STATE_DIR"
echo "[hard_stop] Stopping BotA scheduler…"
if [[ -x "$BASE/tools/daemonctl.sh" ]]; then
  bash "$BASE/tools/daemonctl.sh" stop || true
fi
pgrep -f 'BotA/tools/run_loop\.sh'     | xargs -r kill -TERM || true
pgrep -f 'BotA/tools/loop_guard\.sh'   | xargs -r kill -TERM || true
pgrep -f 'BotA/tools/watchdog\.sh'     | xargs -r kill -TERM || true
sleep 1
pgrep -f 'BotA/tools/run_loop\.sh'     | xargs -r kill -9    || true
pgrep -f 'BotA/tools/loop_guard\.sh'   | xargs -r kill -9    || true
pgrep -f 'BotA/tools/watchdog\.sh'     | xargs -r kill -9    || true
rm -f "$STATE_DIR/loop.pid" "$STATE_DIR/loop.lock"
pids="$(pgrep -af 'BotA/tools/run_loop\.sh' || true)"
if [[ -z "$pids" ]]; then
  echo "[hard_stop] OK — no run_loop processes."
else
  echo "[hard_stop] WARN — still running:"; echo "$pids"
fi
echo "[hard_stop] State cleared: $(ls -1 "$STATE_DIR" 2>/dev/null | wc -l) files remain."
if [[ -f "$BASE/.env" ]]; then
  set -a; . "$BASE/.env"; set +a || true
  if [[ -n "${TELEGRAM_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
    curl -s "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
      -d chat_id="$TELEGRAM_CHAT_ID" \
      -d text="⏹️ BotA HARD-STOP executed — all schedulers terminated" >/dev/null 2>&1 || true
  fi
fi
echo "[hard_stop] Done."
