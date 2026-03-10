#!/data/data/com.termux/files/usr/bin/bash
# BotA Live Audit Dashboard
# Shows current health of data providers, scalper snapshot, signals, and alerts.

set -euo pipefail

REPO="${HOME}/BotA"
cd "$REPO" || {
  echo "[FATAL] Cannot cd to $REPO"
  exit 1
}

divider() {
  printf '\n============================================================\n'
}

subheader() {
  printf '\n---- %s ----\n' "$1"
}

divider
echo "[BotA Live Audit] $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
divider

# 1) ENV / PROVIDER KEYS
subheader "ENVIRONMENT / PROVIDER KEYS (visible in this process)"
python3 - <<'PY'
import os
for k in ("TWELVE_DATA_API_KEY", "ALPHA_VANTAGE_API_KEY"):
    v = os.getenv(k)
    print(f"{k} =", ("<SET, length %d>" % len(v)) if v else "<NOT SET>")
PY

# 2) LAST EURUSD / GBPUSD SIGNALS FROM HISTORY
subheader "LAST 10 SIGNALS FROM HISTORY (EURUSD / GBPUSD)"
if [ -f logs/signal_history.csv ]; then
  echo "[EURUSD]"
  grep 'EURUSD' logs/signal_history.csv | tail -n 10 || echo "  (no EURUSD rows)"
  echo
  echo "[GBPUSD]"
  grep 'GBPUSD' logs/signal_history.csv | tail -n 10 || echo "  (no GBPUSD rows)"
else
  echo "logs/signal_history.csv missing"
fi

# 3) PROVIDER HEALTH (cron.signals.log)
subheader "PROVIDER HEALTH (cron.signals.log)"
if [ -f logs/cron.signals.log ]; then
  echo "[Last 15 lines]"
  tail -n 15 logs/cron.signals.log
  echo
  echo "[Last 5 ERROR lines]"
  grep -i 'ERROR' logs/cron.signals.log | tail -n 5 || echo "  (no ERROR lignes in cron.signals.log)"
else
  echo "logs/cron.signals.log missing"
fi

# 4) CURRENT EURUSD M15 SNAPSHOT (signal_EURUSD_15.json)
subheader "CURRENT EURUSD M15 SNAPSHOT (signal_EURUSD_15.json)"
if [ -f logs/signal_EURUSD_15.json ]; then
  python3 - <<'PY'
import json, pathlib, pprint
p = pathlib.Path("logs/signal_EURUSD_15.json")
try:
    data = json.loads(p.read_text())
except Exception as e:
    print("[ERROR] Failed to parse signal_EURUSD_15.json:", e)
else:
    # Show critical fields if present
    ok = data.get("ok")
    err = data.get("error")
    decision = data.get("decision") or data.get("signal") or data.get("indicators", {}).get("decision")
    score = data.get("score") or data.get("indicators", {}).get("score")
    price = data.get("price") or data.get("indicators", {}).get("price")

    print("ok        :", ok)
    if err:
        print("error     :", err)
    print("decision  :", decision)
    print("score     :", score)
    print("price     :", price)
    print("\n[RAW SNAPSHOT]")
    pprint.pp(data)
PY
else
  echo "logs/signal_EURUSD_15.json missing"
fi

# 5) ALERT PIPELINE STATUS (alert.log)
subheader "ALERT PIPELINE STATUS (alert.log)"
if [ -f logs/alert.log ]; then
  echo "[Last 20 lines of alert.log]"
  tail -n 20 logs/alert.log
else
  echo "logs/alert.log missing (no alerts written yet)"
fi

# 6) SIGNAL ENGINE RUNTIME (signal_run.log)
subheader "SIGNAL ENGINE RUNTIME (signal_run.log - last 20 runs)"
if [ -f logs/signal_run.log ]; then
  tail -n 20 logs/signal_run.log
else
  echo "logs/signal_run.log missing"
fi

# 7) SIGNAL WATCHER STATUS (signal_watcher_pro.log / signal_watcher.log)"
subheader "SIGNAL WATCHER STATUS (signal_watcher_pro.log / signal_watcher.log)"
if [ -f logs/signal_watcher_pro.log ]; then
  echo "[signal_watcher_pro.log - last 20 lines]"
  tail -n 20 logs/signal_watcher_pro.log
elif [ -f logs/signal_watcher.log ]; then
  echo "[signal_watcher.log - last 20 lines]"
  tail -n 20 logs/signal_watcher.log
else
  echo "no signal_watcher*.log present"
fi

divider
echo "[BotA Live Audit] End of report."
divider
