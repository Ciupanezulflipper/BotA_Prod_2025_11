#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$HOME/BotA"
cd "$ROOT"
echo "[PROD] Applying production crontab…"
mkdir -p "$ROOT/cron" "$ROOT/logs" "$ROOT/cache"
crontab "$ROOT/cron/prod.crontab"
echo "[PROD] CRON APPLIED"; echo "[PROD] Preview:"; crontab -l | sed -n '1,6p'
echo "[PROD] Stopping any old watcher…"; bash "$ROOT/tools/ops_rescue_signals.sh" --stop-watch || true
sleep 2
echo "[PROD] Starting watcher…"; bash "$ROOT/tools/ops_rescue_signals.sh" --start-watch || true
sleep 4
echo "[PROD] Watcher status:"; bash "$ROOT/tools/ops_rescue_signals.sh" --status || true
echo "[PROD] Quick acceptance:"; echo " 1) Syntax"
bash -n "$ROOT/tools/signal_watcher_pro.sh"; bash -n "$ROOT/tools/data_fetch_candles.sh"; bash -n "$ROOT/tools/scoring_engine.sh"; echo " ✓ Syntax OK"
echo " 2) Heartbeat (<=120s preferred)"; HB="$ROOT/cache/watcher.heartbeat"; [[ -f "$HB" ]] && echo " hb_age=$(( $(date +%s) - $(cat "$HB") ))s" || echo " NO_HEARTBEAT_YET"
echo " 3) Recent alerts (tail 3)"; tail -n 3 "$ROOT/logs/alerts.csv" 2>/dev/null || echo "(no alerts yet)"
echo "[PROD] Done. Monitor: tail -f $ROOT/logs/watcher_nohup.log"
