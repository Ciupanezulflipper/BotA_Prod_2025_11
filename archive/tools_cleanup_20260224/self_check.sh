#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
echo "=== BOT-A SELF CHECK ($(date -u +'%a %b %d %T UTC %Y')) ==="

req=(
  "$HOME/bot-a/tools/runner_confluence.py"
  "$HOME/bot-a/tools/digest_v2.py"
  "$HOME/bot-a/tools/retry_outbox.py"
  "$HOME/bot-a/tools/csv_writer.py"
  "$HOME/bot-a/tools/lib_utils.py"
  "$HOME/bot-a/config/policy.json"
  "$HOME/bot-a/config/tele.env"
  "$HOME/bot-a/logs"
  "$HOME/bot-a/data"
)
for p in "${req[@]}"; do
  if [[ -e "$p" ]]; then echo "[OK] $p exists"; else echo "[MISS] $p missing"; fi
done

echo "--- Permissions ---"
ls -l "$HOME/bot-a/config/"* || true

echo "--- Runner dry-run ---"
python3 "$HOME/bot-a/tools/runner_confluence.py" --dry-run || echo "[WARN] runner dry-run failed"

echo "--- Digest closed-window check ---"
python3 "$HOME/bot-a/tools/digest_v2.py" || echo "[WARN] digest run failed"

echo "--- Outbox retry ---"
python3 "$HOME/bot-a/tools/retry_outbox.py" || echo "[WARN] retry failed"

echo "=== SELF CHECK COMPLETE ==="
