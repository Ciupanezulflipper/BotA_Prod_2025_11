#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BOTA_ROOT="/data/data/com.termux/files/home/BotA"
LOG_SIGNALS="${BOTA_ROOT}/logs/cron.signals.log"
LOG_ERROR="${BOTA_ROOT}/logs/error.log"

cd "$BOTA_ROOT"

echo "=== PROOF START ==="
date
echo

echo "=== CRONTAB: watcher-related lines ==="
crontab -l 2>/dev/null | grep -nE 'signal_watcher_pro|send_candidates_now|telegram_send|sendMessage' || true
echo

echo "=== PROCESS: any live watcher/fusion processes RIGHT NOW ==="
# busybox ps formats differ; try both
(ps -ef 2>/dev/null || ps -A -o pid,ppid,cmd 2>/dev/null || true) | grep -E 'signal_watcher_pro\.sh|m15_h1_fusion\.sh|scoring_engine\.sh|quality_filter\.py|telegram' | grep -v grep || true
echo

echo "=== PROCESS: cron daemon present? ==="
(ps -ef 2>/dev/null || ps -A -o pid,ppid,cmd 2>/dev/null || true) | grep -E 'crond|cron' | grep -v grep || true
echo

echo "=== LOG: last 30 WATCHER SANITY lines (raw) ==="
if [ -f "$LOG_SIGNALS" ]; then
  grep -nE '^\[WATCHER .*SANITY:' "$LOG_SIGNALS" | tail -n 30 || true
else
  echo "MISSING: $LOG_SIGNALS"
fi
echo

echo "=== LOG: cadence analysis (minutes between SANITY timestamps) ==="
python3 - <<'PY'
import re
from datetime import datetime, timezone, timedelta
import sys, os

log = "/data/data/com.termux/files/home/BotA/logs/cron.signals.log"
if not os.path.exists(log):
    print("MISSING:", log)
    raise SystemExit(0)

rx = re.compile(r'^\[WATCHER ([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+[0-9]{4})\] SANITY:')
ts = []
with open(log, "r", errors="replace") as f:
    for line in f:
        m = rx.match(line)
        if m:
            ts.append(m.group(1))

# Use last 25 points
ts = ts[-25:]
def parse(s: str) -> datetime:
    # format like 2026-02-09T01:35:02+0200
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")

if len(ts) < 2:
    print("Not enough SANITY points to compute cadence.")
    raise SystemExit(0)

dts = [parse(x) for x in ts]
gaps = []
for a,b in zip(dts, dts[1:]):
    gaps.append((b-a).total_seconds()/60.0)

print("count=", len(dts))
print("first=", ts[0], "last=", ts[-1])
print("gaps_minutes=", ", ".join(f"{g:.0f}" if abs(g-round(g))<1e-6 else f"{g:.2f}" for g in gaps))
print("min_gap=", min(gaps), "max_gap=", max(gaps))
PY
echo

echo "=== LOG: last 20 TELEGRAM SENT lines ==="
if [ -f "$LOG_SIGNALS" ]; then
  grep -nE '^\[TELEGRAM .*SENT:' "$LOG_SIGNALS" | tail -n 20 || true
fi
echo

echo "=== LOG: last 40 TELEGRAM tier_skip/cooldown lines ==="
if [ -f "$LOG_SIGNALS" ]; then
  grep -nE '^\[TELEGRAM .* (tier_skip|cooldown)' "$LOG_SIGNALS" | tail -n 40 || true
fi
echo

echo "=== LOG: proof check (no SENT after last tier_skip) ==="
python3 - <<'PY'
import re, os

log = "/data/data/com.termux/files/home/BotA/logs/cron.signals.log"
if not os.path.exists(log):
    print("MISSING:", log)
    raise SystemExit(0)

sent_rx = re.compile(r'^\[TELEGRAM .*SENT:')
skip_rx = re.compile(r'^\[TELEGRAM .*tier_skip:')

last_sent = None
last_skip = None

with open(log, "r", errors="replace") as f:
    for i, line in enumerate(f, 1):
        if sent_rx.match(line):
            last_sent = (i, line.strip())
        if skip_rx.match(line):
            last_skip = (i, line.strip())

print("last_sent_line=", last_sent[0] if last_sent else None)
print("last_skip_line=", last_skip[0] if last_skip else None)

if last_skip and last_sent:
    if last_sent[0] > last_skip[0]:
        print("FAIL: Found SENT after last tier_skip (spam risk).")
        print(" last_sent:", last_sent[1])
        print(" last_skip:", last_skip[1])
    else:
        print("PASS: No SENT after last tier_skip (gating working).")
        print(" last_sent:", last_sent[1])
        print(" last_skip:", last_skip[1])
elif last_skip and not last_sent:
    print("PASS: tier_skip exists and no SENT exists in log.")
elif last_sent and not last_skip:
    print("WARN: SENT exists but no tier_skip found (gating may not be active).")
else:
    print("WARN: Neither SENT nor tier_skip found (insufficient evidence).")
PY
echo

echo "=== REPO: find other invokers of signal_watcher_pro.sh ==="
# If anything else runs it (loops, services, other scripts), it will show here.
grep -R --line-number -E 'signal_watcher_pro\.sh' "$BOTA_ROOT" 2>/dev/null | head -n 120 || true
echo

echo "=== error.log: last 60 lines (sanity) ==="
if [ -f "$LOG_ERROR" ]; then
  tail -n 60 "$LOG_ERROR" || true
else
  echo "MISSING: $LOG_ERROR"
fi
echo

echo "=== PROOF END ==="
