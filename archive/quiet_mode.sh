#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/quiet_mode.sh
# PURPOSE: Immediately stop all Bot A message spam by disabling cron entries
#          and killing any stray watcher/accuracy/telegram loops.
# SAFE: Idempotent; can be re-run anytime.

set -euo pipefail
ROOT="$HOME/BotA"
LOGDIR="$ROOT/logs"
CACHEDIR="$ROOT/cache"
mkdir -p "$LOGDIR" "$CACHEDIR"
cd "$ROOT"

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

echo "[QUIET $(ts)] Starting quiet mode…"

# 1) Backup and disable ALL cron entries (prefix with '# DISABLED ')
echo "[QUIET $(ts)] Backing up crontab and disabling entries…"
crontab -l > "$LOGDIR/crontab.backup.$(date -u +%F_%H%M%S).txt" 2>/dev/null || true
crontab -l 2>/dev/null | sed 's/^/# DISABLED /' | crontab - || true

# 2) Kill any running loops that could post to Telegram / spam
echo "[QUIET $(ts)] Killing possible spammers (accuracy/watcher/telegram)…"
pkill -f "signal_accuracy.py" 2>/dev/null || true
pkill -f "signal_watcher_pro.sh" 2>/dev/null || true
pkill -f "ops_rescue_signals.sh" 2>/dev/null || true
pkill -f "TomaiSignalAI" 2>/dev/null || true
pkill -f "telegram" 2>/dev/null || true
pkill -f "accuracy.*FETCH" 2>/dev/null || true

# 3) Clean stale PIDs/heartbeats
rm -f "$CACHEDIR/watcher.pid" "$CACHEDIR/watcher.heartbeat" 2>/dev/null || true

# 4) Show current state for acceptance
echo "[QUIET $(ts)] Current crontab (should be fully commented):"
crontab -l || echo "(no crontab)"

echo "[QUIET $(ts)] Process check (should print '✅ clean' if none):"
ps -Af | grep -E "signal_accuracy|watcher|TomaiSignalAI|telegram|FETCH 30m" | grep -v grep || echo "✅ clean"

# 5) Tail likely cron logs to confirm silence (best-effort)
for f in "$LOGDIR/cron.accuracy.log" "$LOGDIR/cron.signals.log" "$LOGDIR/watcher_nohup.log"; do
  [ -f "$f" ] && { echo "[QUIET $(ts)] Tail: $f"; tail -n 3 "$f" || true; }
done

echo "[QUIET $(ts)] Quiet mode complete."
