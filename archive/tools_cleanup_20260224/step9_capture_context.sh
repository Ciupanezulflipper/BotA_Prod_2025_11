#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p logs

TS="$(date +%Y%m%d_%H%M%S)"
OUT="logs/step9_context_${TS}.txt"

have() { command -v "$1" >/dev/null 2>&1; }

sanitize_env_lines() {
  sed -E \
    -e 's/(TOKEN|SECRET|KEY|PASS|PASSWORD|API_KEY|BOT_TOKEN|PRIVATE|CHAT_ID|WEBHOOK)[^=]*=.*/\1=[REDACTED]/Ig' \
    -e 's/=.*/=[VALUE]/'
}

print_file_block() {
  local f="$1"
  echo ""
  echo "===== FILE: $f ====="
  if [[ -f "$f" ]]; then
    if have sha256sum; then
      sha256sum "$f" | awk '{print "sha256: "$1}'
    elif have shasum; then
      shasum -a 256 "$f" | awk '{print "sha256: "$1}'
    else
      echo "sha256: (no sha tool found)"
    fi
    echo "--- BEGIN CONTENT ($f) ---"
    cat "$f"
    echo "--- END CONTENT ($f) ---"
  else
    echo "(missing)"
  fi
}

{
  echo "BotA Step 9 Context Capture (Option B prerequisite)"
  echo "timestamp: $TS"
  echo "pwd: $(pwd)"
  echo "uname: $(uname -a 2>/dev/null || true)"
  echo "python: $(python3 -V 2>&1 || true)"
  echo ""

  echo "=== SANITIZED ENV (selected keys only) ==="
  env | grep -E '^(TELEGRAM_|BOTA_|BOT_|MIN_SCORE|SCORE_|CONFIDENCE|PAIRS|PAIR|TIMEFRAMES|TF|DRY_RUN|ENV_|PROVIDER|CACHE_|DATA_)=' \
    | sanitize_env_lines \
    | sort || true

  echo ""
  echo "=== DIRECTORY SNAPSHOT ==="
  ls -la
  echo ""
  echo "=== tools/ LISTING ==="
  ls -la tools || true
  echo ""
  echo "=== logs/ LISTING ==="
  ls -la logs || true

  echo ""
  echo "=== CRON SNAPSHOT ==="
  (crontab -l 2>/dev/null || echo "(no crontab)") \
    | sed -E 's/(TOKEN|KEY|SECRET|PASS|PASSWORD|API_KEY|BOT_TOKEN).*/\1=[REDACTED]/Ig'

  echo ""
  echo "=== RECENT LOG TAILS ==="
  echo "--- logs/error.log (tail 200) ---"
  tail -n 200 logs/error.log 2>/dev/null || echo "(no logs/error.log)"
  echo ""
  echo "--- logs/cron*.log (tail 140 each) ---"
  for lf in logs/cron*.log logs/*send*.log logs/*signals*.log; do
    [[ -f "$lf" ]] || continue
    echo ""
    echo "### $lf"
    tail -n 140 "$lf" || true
  done

  echo ""
  echo "=== GREP: WHERE IS TELEGRAM_MIN_SCORE ENFORCED? (first 300 hits) ==="
  grep -RIn --exclude-dir=.git --exclude='*.pyc' --exclude='*.pyo' \
    -E 'TELEGRAM_MIN_SCORE|MIN_SCORE|score_threshold|min_score' . 2>/dev/null | head -n 300 || true

  echo ""
  echo "=== GREP: SCORE PINNING / CONSTANTS (first 300 hits) ==="
  grep -RIn --exclude-dir=.git --exclude='*.pyc' --exclude='*.pyo' \
    -E 'score[[:space:]]*=[[:space:]]*[0-9]+|return[[:space:]]+[0-9]+|confidence[[:space:]]*=' . 2>/dev/null | head -n 300 || true

  echo ""
  echo "=== GREP: run_fusion / fusion scripts (first 200 hits) ==="
  grep -RIn --exclude-dir=.git \
    -E 'run_fusion|m15_h1_fusion|fusion\.sh|scoring_engine\.sh|quality_filter\.py' . 2>/dev/null | head -n 200 || true

  echo ""
  echo "=== TARGET FILES (FULL CONTENT) ==="
  print_file_block "tools/signal_watcher_pro.sh"
  print_file_block "tools/m15_h1_fusion.sh"
  print_file_block "tools/scoring_engine.sh"
  print_file_block "tools/quality_filter.py"
  print_file_block "tools/data_fetch_candles.sh"

  echo ""
  echo "=== FIND: send_candidates* (maxdepth 6) ==="
  find . -maxdepth 6 -type f -iname '*send_candidates*' -print 2>/dev/null || true
  for sf in $(find . -maxdepth 6 -type f -iname '*send_candidates*' -print 2>/dev/null); do
    print_file_block "$sf"
  done

  echo ""
  echo "=== STATIC SYNTAX CHECKS ==="
  bash -n tools/step9_capture_context.sh && echo "bash -n tools/step9_capture_context.sh: OK" || echo "bash -n tools/step9_capture_context.sh: FAIL"
  [[ -f tools/signal_watcher_pro.sh ]] && (bash -n tools/signal_watcher_pro.sh && echo "bash -n tools/signal_watcher_pro.sh: OK" || echo "bash -n tools/signal_watcher_pro.sh: FAIL") || true
  [[ -f tools/m15_h1_fusion.sh ]] && (bash -n tools/m15_h1_fusion.sh && echo "bash -n tools/m15_h1_fusion.sh: OK" || echo "bash -n tools/m15_h1_fusion.sh: FAIL") || true
  [[ -f tools/scoring_engine.sh ]] && (bash -n tools/scoring_engine.sh && echo "bash -n tools/scoring_engine.sh: OK" || echo "bash -n tools/scoring_engine.sh: FAIL") || true
  [[ -f tools/quality_filter.py ]] && (python3 -m py_compile tools/quality_filter.py && echo "py_compile tools/quality_filter.py: OK" || echo "py_compile tools/quality_filter.py: FAIL") || true

  echo ""
  echo "=== OUTPUT FILE ==="
  echo "$OUT"
} | tee "$OUT"
