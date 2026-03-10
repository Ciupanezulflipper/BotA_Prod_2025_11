#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
BASE="$HOME/BotA"
chmod +x "$BASE/tools/quota_guard.sh" \
         "$BASE/tools/td_probe.sh" \
         "$BASE/tools/status_quota.sh"

# Smoke test (consumes ~1 TwelveData credit):
set -a; . "$BASE/.env"; set +a
echo "[install] TD key prefix: ${TWELVEDATA_API_KEY:0:6}…"
bash "$BASE/tools/td_probe.sh" EURUSD || true
bash "$BASE/tools/status_quota.sh"
echo "[install] Done."
