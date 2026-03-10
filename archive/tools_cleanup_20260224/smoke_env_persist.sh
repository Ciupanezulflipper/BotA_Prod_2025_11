#!/usr/bin/env bash
set -euo pipefail

ROOT="/data/data/com.termux/files/home/BotA"
cd "$ROOT"

ENV_FILE="${1:-$ROOT/.env.botA}"

echo "=== 1) BotA root ==="
pwd

echo
echo "=== 2) Load env safely (no secrets printed) ==="
if [ ! -f "$ENV_FILE" ]; then
  echo "FAIL: env file not found: $ENV_FILE"
  exit 2
fi

# shellcheck disable=SC1090
source "$ROOT/tools/env_safe_source.sh" "$ENV_FILE"

echo
echo "=== 3) Verify Telegram vars (no token printed) ==="
python - <<'PY'
import os
for k in ("TELEGRAM_BOT_TOKEN","TELEGRAM_CHAT_ID"):
    v=os.getenv(k)
    print(k, "SET" if v else "MISSING", (f"len={len(v)}" if v else ""))
PY

echo
echo "=== 4) Compile checks ==="
python -m py_compile tools/tg_send.py && echo "py_compile=tg_send=OK"
python -m py_compile tools/offline_queue_system.py && echo "py_compile=offline_queue_system=OK"
python -m py_compile tools/early_watch.py && echo "py_compile=early_watch=OK"

echo
echo "=== 5) tg_send smoke (PASS: prints SUCCESS) ==="
python tools/tg_send.py "smoke: env persisted + tg_send OK" || true

echo
echo "=== 6) offline queue send (PASS: no crash; sends/archives or says no queued) ==="
python tools/offline_queue_system.py send || true

echo
echo "=== 7) early_watch runtime smoke (PASS: prints lines; no crash) ==="
python -m tools.early_watch --ignore-session 2>&1 | head -n 80 || true

echo
echo "=== DONE ==="
