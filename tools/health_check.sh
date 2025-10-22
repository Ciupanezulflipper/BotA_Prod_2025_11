#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
echo "== PROCESSES =="
ps -ef | grep -E "runner_confluence.py|status_cmd.py|guarded_runner.py" | grep -v grep || true
LOCK=$(ls -t /data/data/com.termux/files/usr/tmp/*runner.lock 2>/dev/null | head -n1)
if [ -n "${LOCK:-}" ]; then
  echo "== RUNNER LOCK =="
  ls -l "$LOCK"; echo "Age(s): $(( $(date +%s) - $(stat -c %Y "$LOCK") ))"
else
  echo "No runner.lock found"
fi
echo "== LAST LOGS =="
tail -n 50 ~/bot-a/logs/runner_confluence.log 2>/dev/null || true
tail -n 50 ~/bot-a/logs/statusd.log 2>/dev/null || true
echo "== ENV =="
python3 - << 'PY'
import os; print("TOKEN:",bool(os.environ.get("TELEGRAM_BOT_TOKEN")),"CHAT:",bool(os.environ.get("TELEGRAM_CHAT_ID")))
PY
