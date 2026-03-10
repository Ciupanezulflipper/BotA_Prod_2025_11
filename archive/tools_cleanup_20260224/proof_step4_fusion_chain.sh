#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="/data/data/com.termux/files/home/BotA"
LOG_ERROR="${ROOT}/logs/error.log"

cd "$ROOT"

safe_source_env() {
  local env_file="$1"
  if [ ! -f "$env_file" ]; then
    echo "[STEP4] safe_source_env: missing $env_file"
    return 0
  fi
  # Parse KEY=VALUE lines safely; supports quotes; ignores comments/blanks.
  # Exports variables without executing arbitrary shell.
  eval "$(
python3 - <<'PY' "$env_file"
import re, sys, shlex
path = sys.argv[1]
out = []
for raw in open(path, "r", encoding="utf-8", errors="ignore"):
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    if line.lower().startswith("export "):
        line = line[7:].strip()
    if "=" not in line:
        continue
    k, v = line.split("=", 1)
    k = k.strip()
    v = v.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k or ""):
        continue
    # Remove surrounding quotes if present
    if (len(v) >= 2) and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        v = v[1:-1]
    out.append(f"export {k}={shlex.quote(v)}")
print("\n".join(out))
PY
)"
}

echo "=== PROOF STEP 4: Fusion chain + market gate + sample payload ==="
echo "DATE: $(date)"
echo "PWD: $(pwd)"
echo

echo "=== QUICK error.log tail (last 25) ==="
if [ -f "$LOG_ERROR" ]; then
  tail -n 25 "$LOG_ERROR" || true
else
  echo "MISSING: $LOG_ERROR"
fi
echo

echo "=== SCHEDULER PROOF: cron watcher line + crond process ==="
crontab -l 2>/dev/null | grep -nE 'signal_watcher_pro\.sh|market_open\.sh|PAIRS=|TIMEFRAMES=' || true
(ps -ef 2>/dev/null || ps -A -o pid,ppid,cmd 2>/dev/null || true) | grep -E 'crond|runsv .*crond' | grep -v grep || true
echo

echo "=== MARKET GATE: market_open.sh exit_code (0=open, nonzero=closed) ==="
set +e
bash "$ROOT/tools/market_open.sh" >/dev/null 2>&1
ec=$?
set -e
echo "market_open.sh exit_code=${ec}"
echo

echo "=== WATCHER CHAIN: show run_fusion() definition (signal_watcher_pro.sh) ==="
if [ -f "$ROOT/tools/signal_watcher_pro.sh" ]; then
  ln=$(grep -n -m 1 -E '^[[:space:]]*run_fusion\(\)' "$ROOT/tools/signal_watcher_pro.sh" | cut -d: -f1)
  if [ -n "${ln:-}" ]; then
    echo "signal_watcher_pro.sh run_fusion() starts_at_line=${ln}"
    nl -ba "$ROOT/tools/signal_watcher_pro.sh" | sed -n "$((ln)), $((ln+80))p" || true
  else
    echo "NOT FOUND: run_fusion() in tools/signal_watcher_pro.sh"
  fi
else
  echo "MISSING: tools/signal_watcher_pro.sh"
fi
echo

echo "=== FUSION SCRIPT: tools/m15_h1_fusion.sh (exists + grep invokers) ==="
if [ -f "$ROOT/tools/m15_h1_fusion.sh" ]; then
  ls -la "$ROOT/tools/m15_h1_fusion.sh" || true
  echo "--- TOP 120 lines ---"
  nl -ba "$ROOT/tools/m15_h1_fusion.sh" | sed -n '1,120p' || true
  echo "--- GREP invokers ---"
  grep -nE 'scoring_engine\.sh|quality_filter\.py|macro6|H1|run_fusion|signal_watcher_pro' "$ROOT/tools/m15_h1_fusion.sh" || true
else
  echo "MISSING: tools/m15_h1_fusion.sh"
fi
echo

echo "=== SCORING SCRIPT: tools/scoring_engine.sh (grep scoring/conf/provider) ==="
if [ -f "$ROOT/tools/scoring_engine.sh" ]; then
  ls -la "$ROOT/tools/scoring_engine.sh" || true
  grep -nE 'score|confidence|provider|engine_A2|60(\.0)?' "$ROOT/tools/scoring_engine.sh" | head -n 120 || true
else
  echo "MISSING: tools/scoring_engine.sh"
fi
echo

echo "=== SAMPLE: run fusion once for EURUSD (no Telegram) ==="
if [ -f "$ROOT/tools/m15_h1_fusion.sh" ]; then
  set +e
  raw="$(bash "$ROOT/tools/m15_h1_fusion.sh" "EURUSD" 2>/dev/null)"
  rc=$?
  set -e
  echo "m15_h1_fusion.sh EURUSD exit_code=${rc}"
  echo "$raw" | head -n 3 || true
  echo
  echo "--- PARSE JSON (score/conf/provider/direction/tf) ---"
  python3 - <<'PY' "$raw"
import json, sys
raw = sys.argv[1]
try:
    data = json.loads(raw)
except Exception as e:
    print("parse_failed:", e)
    print("raw_head:", raw[:240].replace("\n","\\n"))
    sys.exit(0)

def pick(d, keys):
    for k in keys:
        if isinstance(d, dict) and k in d:
            return d.get(k)
    return None

score = pick(data, ["score","total_score"])
conf  = pick(data, ["confidence","conf"])
prov  = pick(data, ["provider"])
direc = pick(data, ["direction","signal","side"])
tf    = pick(data, ["tf","timeframe"])
pair  = pick(data, ["pair","symbol"])

print(f"pair={pair} tf={tf} direction={direc} score={score} conf={conf} provider={prov}")
print("keys=", sorted(list(data.keys()))[:30])
PY
else
  echo "SKIP: missing tools/m15_h1_fusion.sh"
fi
echo

echo "=== WATCHER ONCE (forced TELEGRAM_DISABLED, low thresholds) ==="
if [ -f "$ROOT/tools/signal_watcher_pro.sh" ]; then
  safe_source_env "$ROOT/.env" >/dev/null 2>&1 || true
  export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-${TELEGRAM_TOKEN:-}}"
  DRY_RUN_MODE=1 TELEGRAM_ENABLED=0 TELEGRAM_MIN_SCORE=0 FILTER_SCORE_MIN=0 FILTER_SCORE_MIN_ALL=0 \
  TELEGRAM_TIER_YELLOW_MIN=0 TELEGRAM_TIER_GREEN_MIN=0 \
  PAIRS="EURUSD" TIMEFRAMES="M15" \
  bash "$ROOT/tools/signal_watcher_pro.sh" --once 2>&1 | tail -n 120 || true
else
  echo "SKIP: missing tools/signal_watcher_pro.sh"
fi
echo

echo "=== STEP 4 OUTPUT: 5 LINES TO PASTE BACK ==="
echo "1) market_open_exit_code=${ec}"
echo "2) cron_invoker_present=$(crontab -l 2>/dev/null | grep -c 'signal_watcher_pro.sh' || echo 0)"
echo "3) crond_running=$(( (ps -ef 2>/dev/null || true) | grep -E 'crond .* -n -s' | grep -v grep >/dev/null 2>&1 ) && echo yes || echo no )"
echo "4) fusion_script_exists=$([ -f "$ROOT/tools/m15_h1_fusion.sh" ] && echo yes || echo no)"
echo "5) watcher_run_fusion_line=$(
  if [ -f "$ROOT/tools/signal_watcher_pro.sh" ]; then
    grep -n -m 1 -E 'm15_h1_fusion\.sh|run_fusion' "$ROOT/tools/signal_watcher_pro.sh" | tr '\n' ' ' || true
  fi
)"
echo
echo "=== PROOF STEP 4 END ==="
