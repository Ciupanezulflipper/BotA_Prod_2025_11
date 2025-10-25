#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
TOOLS="$HOME/BotA/tools"

echo "---- RAW WATCH OUTPUT ----"
python3 "$TOOLS/early_watch.py" --ignore-session 2>/dev/null || true

echo
echo "---- ACTIONABLE (MIN_WEIGHT=${MIN_WEIGHT:-2}) ----"
python3 - <<'PY'
import os, sys, json, subprocess
mw = os.getenv("MIN_WEIGHT","2")
p = subprocess.run([ "python3", os.path.expanduser("~/BotA/tools/early_watch.py"), "--ignore-session"],
                   stdout=subprocess.PIPE, text=True)
q = subprocess.run([ "python3", os.path.expanduser("~/BotA/tools/alert_rules.py")],
                   input=p.stdout, stdout=subprocess.PIPE, text=True)
print(q.stdout)
PY

echo
echo "---- ENRICHED (analytics) ----"
python3 - <<'PY'
import sys, json, subprocess, os
raw = sys.stdin.read() if not sys.stdin.isatty() else None
if raw is None:
    # recompute from early_watch
    p = subprocess.run([ "python3", os.path.expanduser("~/BotA/tools/early_watch.py"), "--ignore-session"],
                       stdout=subprocess.PIPE, text=True)
    a = subprocess.run([ "python3", os.path.expanduser("~/BotA/tools/alert_rules.py")],
                       input=p.stdout, stdout=subprocess.PIPE, text=True).stdout
else:
    a = raw
b = subprocess.run([ "python3", os.path.expanduser("~/BotA/tools/analytics.py")],
                   input=a, stdout=subprocess.PIPE, text=True).stdout
print(b)
PY

echo
echo "---- PREVIEW MESSAGE ----"
DRY=1 MIN_WEIGHT="${MIN_WEIGHT:-2}" ONCE=1 "$TOOLS/alert_loop.sh" || true
