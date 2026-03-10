#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$BASE/logs"
STATE_DIR="$BASE/state"
mkdir -p "$LOG_DIR" "$STATE_DIR"

# Load .env if present (brings TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, defaults, etc.)
if [[ -f "$BASE/.env" ]]; then
  set -a
  . "$BASE/.env"
  set +a || true
fi

# Defaults if not provided by environment
export DRY_RUN_MODE="${DRY_RUN_MODE:-false}"
export PROVIDER_ORDER="${PROVIDER_ORDER:-twelve_data}"
export PAIRS="${PAIRS:-EURUSD,GBPUSD}"
export TF15_SLEEP_PAD="${TF15_SLEEP_PAD:-120}"

echo "[hard_start] Starting BotA with:"
echo "  DRY_RUN_MODE=$DRY_RUN_MODE"
echo "  PROVIDER_ORDER=$PROVIDER_ORDER"
echo "  PAIRS=$PAIRS"
echo "  TF15_SLEEP_PAD=$TF15_SLEEP_PAD"

# Kill any old schedulers/guards first
pgrep -f 'BotA/tools/run_loop\.sh'   | xargs -r kill -TERM || true
pgrep -f 'BotA/tools/loop_guard\.sh' | xargs -r kill -TERM || true
sleep 1
pgrep -f 'BotA/tools/run_loop\.sh'   | xargs -r kill -9 || true
pgrep -f 'BotA/tools/loop_guard\.sh' | xargs -r kill -9 || true

# Clear state locks
rm -f "$STATE_DIR/loop.pid" "$STATE_DIR/loop.lock"

# Start scheduler via daemonctl
if [[ -x "$BASE/tools/daemonctl.sh" ]]; then
  bash "$BASE/tools/daemonctl.sh" start
else
  echo "[hard_start] ERROR: daemonctl.sh missing" >&2
  exit 1
fi

# Wait up to ~5s for run_loop to appear
pid=""
for _ in 1 2 3 4 5; do
  sleep 1
  pid="$(pgrep -f 'BotA/tools/run_loop\.sh' || true)"
  [[ -n "$pid" ]] && break
done

if [[ -z "$pid" ]]; then
  echo "[hard_start] FAIL — run_loop not observed." >&2
  exit 2
fi

pgrep -af 'BotA/tools/run_loop\.sh' || true

# Always put bot_state into LIVE mode so cycles are not [PAUSED]/[skip]
if [[ -x "$BASE/tools/bot_state.sh" ]]; then
  bash "$BASE/tools/bot_state.sh" resume >/dev/null 2>&1 || true
fi

# Telegram notification (if configured)
if [[ -n "${TELEGRAM_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
  curl -s "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    -d chat_id="$TELEGRAM_CHAT_ID" \
    -d text="▶️ BotA HARD-START — running with ${PAIRS} (pad=${TF15_SLEEP_PAD}s, provider=${PROVIDER_ORDER})" \
    >/dev/null 2>&1 || true
fi

echo "[hard_start] Done."
