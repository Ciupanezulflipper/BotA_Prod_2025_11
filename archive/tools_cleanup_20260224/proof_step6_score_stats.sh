#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="/data/data/com.termux/files/home/BotA"
LOG="${ROOT}/logs/cron.signals.log"

cd "$ROOT"

echo "=== PROOF STEP 6: Score distribution vs thresholds (NO CHANGES) ==="
echo "DATE: $(date)"
echo "PWD: $(pwd)"
echo

if [ ! -f "$LOG" ]; then
  echo "MISSING: $LOG"
  echo "TIP: list logs:"
  ls -la logs || true
  exit 0
fi

echo "=== QUICK: last 40 FILTER lines (sanity) ==="
tail -n 4000 "$LOG" 2>/dev/null | grep -E '^\[FILTER ' | tail -n 40 || true
echo

echo "=== QUICK: any Telegram sends in cron log? ==="
grep -E '^\[TELEGRAM .*SENT:|^\[TELEGRAM .*gate:|^\[TELEGRAM .*tier_skip:|^\[TELEGRAM .*cooldown active:' "$LOG" 2>/dev/null | tail -n 40 || true
echo

echo "=== COMPUTE: per pair/tf stats + threshold hit counts ==="
python3 - <<'PY' "$LOG"
import re, sys, statistics
path = sys.argv[1]

# Read tail to keep Termux fast
MAX_LINES = 50000
with open(path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()[-MAX_LINES:]

rx = re.compile(r'^\[FILTER [^\]]+\]\s+([A-Z0-9_]+)\s+([A-Z0-9]+)\s+(accepted|rejected_by_filter)\s+score=([0-9]+\.[0-9]+)\s+conf=([0-9]+\.[0-9]+)\s+filters=(.*)$')

by = {}   # (pair,tf) -> list of scores
top = []  # (score, line)
acc = 0
rej = 0

for line in lines:
    m = rx.match(line.strip())
    if not m:
        continue
    pair, tf, status, score_s, conf_s, filters = m.groups()
    score = float(score_s)
    by.setdefault((pair, tf), []).append(score)
    top.append((score, line.strip()))
    if status == "accepted":
        acc += 1
    else:
        rej += 1

top.sort(key=lambda x: x[0], reverse=True)
def pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    k = int(round((p/100.0) * (len(s)-1)))
    return s[max(0, min(k, len(s)-1))]

print(f"parsed_filter_lines={acc+rej} accepted={acc} rejected={rej} (from last {MAX_LINES} log lines)")
print()

rows = []
for (pair, tf), vals in sorted(by.items()):
    mn = min(vals)
    mx = max(vals)
    avg = statistics.mean(vals)
    p90 = pct(vals, 90)
    p95 = pct(vals, 95)
    ge60 = sum(1 for v in vals if v >= 60)
    ge70 = sum(1 for v in vals if v >= 70)
    ge75 = sum(1 for v in vals if v >= 75)
    rows.append((pair, tf, len(vals), mn, avg, mx, p90, p95, ge60, ge70, ge75))

# Pretty print
print("PAIR  TF   N   MIN   AVG   MAX   P90   P95   >=60 >=70 >=75")
for r in rows:
    pair, tf, n, mn, avg, mx, p90, p95, ge60, ge70, ge75 = r
    print(f"{pair:6} {tf:4} {n:4d} {mn:5.1f} {avg:5.1f} {mx:5.1f} {p90:5.1f} {p95:5.1f} {ge60:4d} {ge70:4d} {ge75:4d}")

print()
print("TOP 12 HIGHEST SCORES (line excerpts):")
for score, line in top[:12]:
    print(f"{score:5.1f}  {line[:220]}")
PY
echo

echo "=== STEP 6 OUTPUT: paste this whole section back ==="
echo "---- STEP6_BEGIN ----"
# Keep it compact for chat paste
tail -n 50000 "$LOG" 2>/dev/null \
  | python3 - <<'PY'
import re, sys, statistics
lines = sys.stdin.read().splitlines()
rx = re.compile(r'^\[FILTER [^\]]+\]\s+([A-Z0-9_]+)\s+([A-Z0-9]+)\s+(accepted|rejected_by_filter)\s+score=([0-9]+\.[0-9]+)')
by={}
scores=[]
for ln in lines:
    m=rx.match(ln)
    if not m: continue
    pair, tf, status, score_s = m.groups()
    sc=float(score_s)
    by.setdefault((pair,tf), []).append(sc)
    scores.append(sc)

def pct(vals,p):
    if not vals: return None
    s=sorted(vals)
    k=int(round((p/100.0)*(len(s)-1)))
    return s[max(0,min(k,len(s)-1))]

if not scores:
    print("NO_FILTER_LINES_FOUND")
    sys.exit(0)

print(f"overall_n={len(scores)} overall_min={min(scores):.1f} overall_avg={statistics.mean(scores):.1f} overall_max={max(scores):.1f} p90={pct(scores,90):.1f} p95={pct(scores,95):.1f}")
print("per_pair_tf_max:")
for (pair,tf), vals in sorted(by.items()):
    print(f"- {pair} {tf}: max={max(vals):.1f} n={len(vals)} >=75={sum(1 for v in vals if v>=75)} >=70={sum(1 for v in vals if v>=70)} >=60={sum(1 for v in vals if v>=60)}")
PY
echo "---- STEP6_END ----"
echo "=== PROOF STEP 6 END ==="
