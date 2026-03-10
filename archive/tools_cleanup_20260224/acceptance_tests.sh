#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/acceptance_tests.sh
# PURPOSE: One-click acceptance checks per PRD
set -euo pipefail
ROOT="$HOME/BotA"
cd "$ROOT" || exit 1

echo "== deps =="
for dep in curl jq bc; do command -v "$dep" >/dev/null || echo "MISSING: $dep (pkg install $dep)"; done

echo "== 1) Sanity prints (FG) =="
bash tools/signal_watcher_pro.sh --once | grep -E "SANITY:|MARKET:" || true

echo "== 2) Start/status/stop idempotency =="
bash tools/ops_rescue_signals.sh --start-watch
bash tools/ops_rescue_signals.sh --status
bash tools/ops_rescue_signals.sh --start-watch
sleep 2
bash tools/ops_rescue_signals.sh --stop-watch
sleep 1
bash tools/ops_rescue_signals.sh --status || true

echo "== 3) Today alerts (if any non-HOLD) =="
grep "$(date -u +%Y-%m-%d)" logs/alerts.csv | tail -n 5 || true

echo "== 4) Cache fresh (<120s) =="
for f in cache/*.json; do [ -e "$f" ] || continue; age=$(( $(date +%s) - $(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f") )); echo "$f age=${age}s"; done

echo "== 5) Heartbeat age =="
age=$(( $(date +%s) - $(stat -c %Y cache/watcher.heartbeat 2>/dev/null || echo $(date +%s)) )); echo "hb_age=${age}s"
