#!/data/data/com.termux/files/usr/bin/bash
# BotA Status Dashboard (read-only)
set -euo pipefail
ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"

passes=0; fails=0
run_check () {
  local name="$1"; shift
  echo "=== $name ==="
  if "$@"; then echo "[OK] $name"; passes=$((passes+1)); else echo "[FAIL] $name"; fails=$((fails+1)); fi
  echo
}

# Use existing verifiers; safe to call repeatedly
run_check "Phase 3 verify"  "$TOOLS/phase3_verify.sh"
run_check "Phase 6 verify"  "$TOOLS/phase6_verify.sh"
echo "=== Phase 9 smoke (DRY) ==="
DRY=1 MIN_WEIGHT=0 ONCE=1 "$TOOLS/alert_loop.sh" >/dev/null && echo "[OK] Phase 9 smoke" || echo "[WARN] Phase 9 smoke"
echo
echo "=== Phase 10 smoke (DRY) ==="
DRY=1 MAX_KB=1 KEEP=3 "$TOOLS/logrotate.sh" >/dev/null && echo "[OK] logrotate (DRY)" || echo "[WARN] logrotate"
DRY=1 python3 "$TOOLS/health_ping.py" >/dev/null && echo "[OK] health_ping (DRY)" || echo "[WARN] health_ping"
echo

total=$((passes+fails)); [ "$total" -eq 0 ] && total=1
score=$(( 100 * passes / total ))
echo "=== Connectivity & Freshness ==="
python3 - <<'PY'
import os,re,datetime
run=os.path.expanduser('~/BotA/run.log')
header=re.compile(r'^===\s+([A-Z/]+)\s+snapshot\s+===$')
tfre=re.compile(r'^(H1|H4|D1):\s+t=([0-9:-]+\s?[0-9:]*?)Z')
errre=re.compile(r'provider_error=',re.I)
tf_count=0; err_count=0; last=None
try:
  for ln in open(run,encoding='utf-8',errors='replace'):
    if errre.search(ln): err_count+=1
    m=tfre.match(ln.strip())
    if m:
      tf_count+=1
      ts=m.group(2)
      try:
        dt=datetime.datetime.strptime(ts,'%Y-%m-%d %H:%M:%S')
        if (last is None) or (dt>last): last=dt
      except: pass
except FileNotFoundError: pass
age = f"{int((datetime.datetime.utcnow()-last).total_seconds())}s ago" if last else "unknown"
print(f"last snapshot age: {age}")
print(f"TF lines: {tf_count}   provider_error lines: {err_count}")
PY
echo
echo "=== STATUS SUMMARY ==="
echo "passes=$passes fails=$fails  -> completion_score~${score}% (based on available verify scripts)"
exit 0
