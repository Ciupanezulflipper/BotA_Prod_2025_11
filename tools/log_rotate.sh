#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/log_rotate.sh
# PURPOSE: Truncate watcher log and alerts CSV to sane sizes; purge old logs
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "[ROTATE $(date -Iseconds)] start"
[ -f logs/watcher_nohup.log ] && { tail -10000 logs/watcher_nohup.log > logs/.tmp && mv logs/.tmp logs/watcher_nohup.log; echo "[ROTATE] watcher_nohup.log → 10k lines"; }
if [ -f logs/alerts.csv ]; then
  (head -1 logs/alerts.csv; tail -5000 logs/alerts.csv | grep -v '^timestamp,') > logs/.tmp && mv logs/.tmp logs/alerts.csv
  echo "[ROTATE] alerts.csv → 5k rows"
fi
find logs/ -name "*.log.*" -mtime +7 -delete 2>/dev/null || true
echo "[ROTATE] done"
