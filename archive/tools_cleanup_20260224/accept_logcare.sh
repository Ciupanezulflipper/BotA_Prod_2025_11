#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"

echo "== 1) Dry-run quota Telegram message =="
bash "$BASE/tools/tg_quota_status.sh" --dry-run || exit 1

echo "== 2) Real quota Telegram send =="
bash "$BASE/tools/tg_quota_status.sh" || exit 1

echo "== 3) Logrotate dry-run =="
bash "$BASE/tools/logrotate_simple.sh" --dry-run || exit 1

echo "== 4) Cron preview (no changes) =="
bash "$BASE/tools/install_logcare.sh" --preview || exit 1

echo "[ACCEPT] logcare tools OK"
