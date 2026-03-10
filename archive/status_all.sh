#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/status_all.sh
# DESC: Show controller/watch PIDs, heartbeat ages, and recent 409s
set -euo pipefail

age_file() {
  local f="$1"
  if [[ ! -f "$f" ]]; then
    echo "n/a"
    return 0
  fi
  python3 - "$f" <<'PY'
import os, sys, time
p = sys.argv[1]
try:
    val = int(open(p).read().strip() or "0")
    print(int(time.time() - val))
except Exception:
    print("n/a")
PY
}

echo "=== PIDs: telecontroller / tele_control / tg_* / telegram_menu ==="
pgrep -af -f 'tools/(telecontroller\.py|tele_control\.py|tg_control\.py|tg_menu\.py|telegram_menu\.py)' || echo "✅ none"

echo
echo "=== PIDs: watchers ==="
pgrep -af -f 'watch_wrap_market\.sh|wrap_watch_market\.sh|signal_watcher.*\.sh' || echo "✅ none"

echo
echo "=== Heartbeats (age in seconds) ==="
printf "watcher: "; age_file cache/watcher.heartbeat

echo
echo "=== telecontroller.log (tail 20) ==="
tail -n 20 logs/telecontroller.log 2>/dev/null || echo "(no log yet)"

echo
echo "=== recent 409 lines (tail 5) ==="
grep -n "409" logs/telecontroller.log 2>/dev/null | tail -n 5 || echo "None"

echo
echo "=== network check to api.telegram.org ==="
python3 - <<'PY'
import urllib.request
try:
    with urllib.request.urlopen("https://api.telegram.org", timeout=5) as r:
        print(f"OK {r.status}")
except Exception as e:
    print(f"ERROR {e}")
PY
