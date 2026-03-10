#!/bin/bash
# ops_smoke.sh — BotA quick health check for Termux
set -euo pipefail
ROOT="$HOME/BotA"
LOGDIR="$ROOT/logs"
CFG="$ROOT/config/signal.env"
TELE="$ROOT/config/tele.env"

ts() { date -u +"%Y-%m-%d %H:%M:%S UTC"; }

echo "==== BotA Ops Smoke — $(ts) ===="

# 1) Files & dirs
if [ -d "$ROOT" ]; then
  echo "✅ Bot root found: $ROOT"
else
  echo "❌ Missing $ROOT"
  exit 1
fi
mkdir -p "$LOGDIR"
echo "✅ Logs dir: $LOGDIR"

# 2) Config presence
if [ -f "$CFG" ]; then
  echo "✅ Found $CFG"
  grep -E '^(PAIRS|RSI_MIN|ALERTS_CSV)=' "$CFG" || echo "⚠️  Some keys missing in signal.env"
else
  echo "❌ Missing $CFG"
  exit 1
fi

# 3) Telegram creds
if [ -f "$TELE" ]; then
  echo "✅ Found $TELE"
  . "$TELE"
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    echo "✅ Telegram creds loaded (masked)"
  else
    echo "⚠️  Missing Telegram vars in tele.env"
  fi
else
  echo "⚠️  No tele.env file found"
fi

# 4) Cron entries
if crontab -l >/dev/null 2>&1; then
  echo "---- crontab -l ----"
  crontab -l
  echo "--------------------"
else
  echo "⚠️  No crontab installed for this user"
fi

# 5) Key log tails
for f in "$LOGDIR/signal_watcher_pro.log" "$LOGDIR/cron.signals.log" "$LOGDIR/cron.autostatus.log" "$LOGDIR/cron.heartbeat.log"; do
  if [ -f "$f" ]; then
    echo "---- tail -n 20 $f ----"
    tail -n 20 "$f" || true
  else
    echo "⚠️  Missing log: $f"
  fi
done

# 6) Alerts CSV
ALERTS_CSV="$(grep '^ALERTS_CSV=' "$CFG" | cut -d= -f2- | sed "s~\$HOME~$HOME~")"
if [ -n "$ALERTS_CSV" ] && [ -f "$ALERTS_CSV" ]; then
  echo "✅ Alerts CSV found: $ALERTS_CSV"
  echo "---- tail -n 10 $ALERTS_CSV ----"
  tail -n 10 "$ALERTS_CSV" || true
else
  echo "⚠️  No alerts CSV found yet ($ALERTS_CSV)"
fi

# 7) Optional smoke tick
if [ -x "$ROOT/tools/signal_watcher_pro.sh" ]; then
  echo "---- smoke: signal_watcher_pro.sh ----"
  bash "$ROOT/tools/signal_watcher_pro.sh" || true
  echo "✅ Smoke tick executed"
else
  echo "⚠️  Missing or non-executable: $ROOT/tools/signal_watcher_pro.sh"
fi

echo "✅ Ops smoke completed at $(ts)"
