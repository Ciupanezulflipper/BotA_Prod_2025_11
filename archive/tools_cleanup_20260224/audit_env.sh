#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"
LOG="$ROOT/run.log"

echo "=== AUDIT: Bot A Environment ==="
echo "UTC: $(date -u '+%Y-%m-%d %H:%M:%S')"
echo "Device: $(uname -a)"
echo

# ---------- Python ----------
echo "[PYTHON]"
if command -v python3 >/dev/null 2>&1; then
  python3 --version
  which python3
else
  echo "python3 not found" && exit 2
fi
echo

# ---------- Paths / Tools ----------
echo "[TOOLS]"
ls -ld "$TOOLS" || { echo "Missing tools dir: $TOOLS"; exit 2; }
for f in emit_snapshot.py data_fetch.py early_watch.py cache_dump.py run_pair.sh; do
  p="$TOOLS/$f"
  printf "%-24s: " "$f"
  if [ -f "$p" ]; then
    perms="$(ls -l "$p" | awk '{print $1}')"
    echo "OK ($perms)"
  else
    echo "MISSING"
  fi
done
echo

# ---------- API Key ----------
echo "[API KEY]"
if [ -n "${TWELVEDATA_API_KEY:-}" ]; then
  echo "TWELVEDATA_API_KEY set: YES (hidden)"
else
  echo "TWELVEDATA_API_KEY set: NO"
fi
echo

# ---------- Network sanity ----------
echo "[NETWORK]"
# DNS/HTTP quick checks (no data download)
if command -v curl >/dev/null 2>&1; then
  curl -sS --max-time 5 -I https://api.twelvedata.com | head -n 1 || true
  curl -sS --max-time 5 -I https://query1.finance.yahoo.com | head -n 1 || true
else
  echo "curl not found; skipping HTTP HEAD checks"
fi
echo

# ---------- Provider ping (safe) ----------
echo "[PROVIDER PING]"
python3 - <<'PY' || true
import json, sys, os
# Try Yahoo small ping (no key required)
from urllib.request import urlopen
from urllib.parse import urlencode
def ping_yahoo(sym):
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
    q={"range":"5d","interval":"60m"}
    try:
        with urlopen(url+"?"+urlencode(q), timeout=8) as resp:
            print("Yahoo HTTP:", getattr(resp, "status", 200))
    except Exception as e:
        print("Yahoo ping error:", e)
# Try TwelveData ping (if key set)
def ping_td(key):
    from urllib.request import urlopen
    from urllib.parse import urlencode
    url="https://api.twelvedata.com/time_series"
    q={"symbol":"EUR/USD","interval":"1h","outputsize":"2","apikey":key}
    try:
        with urlopen(url+"?"+urlencode(q), timeout=8) as resp:
            print("TwelveData HTTP:", getattr(resp, "status", 200))
    except Exception as e:
        print("TwelveData ping error:", e)
print("Ping: Yahoo EURUSD=X")
ping_yahoo("EURUSD=X")
key=os.getenv("TWELVEDATA_API_KEY","")
if key:
    print("Ping: TwelveData EUR/USD")
    ping_td(key)
else:
    print("Ping: TwelveData skipped (no key)")
PY
echo

# ---------- Log markers ----------
echo "[RUN.LOG MARKERS]"
if [ -f "$LOG" ]; then
  grep -nE '^=== .* snapshot ===$|^(H1|H4|D1): ' "$LOG" | tail -n 12 || true
else
  echo "No run.log yet at $LOG"
fi
echo

# ---------- Summary ----------
echo "=== AUDIT SUMMARY ==="
missing=0
for f in emit_snapshot.py run_pair.sh; do
  [ -f "$TOOLS/$f" ] || { echo "MISSING: $f"; missing=1; }
done
if [ "$missing" -ne 0 ]; then
  echo "status: FAIL (missing required files)"; exit 1
fi
echo "status: OK"
exit 0
