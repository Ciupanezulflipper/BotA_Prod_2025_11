#!/usr/bin/env bash
set -euo pipefail

# BotA entrypoint audit (SAFE):
# - does NOT source .env.botA (so parentheses like MT5_PASSWORD=abc(at) won't break)
# - prints NO secrets
# Goal: find the exact script that is still doing: source .env.botA  (the real offender)

ROOT="/data/data/com.termux/files/home/BotA"
cd "$ROOT"

echo "=== BotA entrypoint audit (no env sourcing; no secrets) ==="
echo "PWD: $(pwd)"
echo "DATE_UTC: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

echo
echo "=== 0) error.log tail (last 80) ==="
mkdir -p logs
tail -n 80 logs/error.log 2>/dev/null || echo "(no logs/error.log yet)"

echo
echo "=== 1) .crontab (repo file) ==="
if [ -f .crontab ]; then
  nl -ba .crontab | sed -n '1,220p'
else
  echo "(no .crontab file)"
fi

echo
echo "=== 2) crontab -l (active cronie config) ==="
crontab -l 2>/dev/null | sed -n '1,220p' || echo "(no active crontab installed into cronie)"

echo
echo "=== 3) run_signal.sh exists? ==="
ls -la run_signal.sh 2>/dev/null || echo "MISSING: run_signal.sh"

echo
echo "=== 4) run_signal.sh content (FULL, numbered) ==="
if [ -f run_signal.sh ]; then
  echo "LINES: $(wc -l < run_signal.sh | tr -d ' ')"
  nl -ba run_signal.sh
else
  echo "SKIP: run_signal.sh not found"
fi

echo
echo "=== 5) does run_signal.sh SOURCE .env.botA / .env ? ==="
if [ -f run_signal.sh ]; then
  grep -nE '(^|[[:space:]])(source|\.)([[:space:]]+)+/?\.env(\.botA)?\b' run_signal.sh \
    || echo "(no direct source/. of .env/.env.botA found in run_signal.sh)"
fi

echo
echo "=== 6) global offenders: any script sourcing .env.botA directly? ==="
grep -RIn --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=logs \
  -E '(^|[[:space:]])(source|\.)([[:space:]]+)+.*\.env\.botA\b' \
  . 2>/dev/null || echo "(none found)"

echo
echo "=== 7) global offenders: any script sourcing .env directly? (FYI) ==="
grep -RIn --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=logs \
  -E '(^|[[:space:]])(source|\.)([[:space:]]+)+.*\.env\b' \
  tools run_signal.sh *.sh 2>/dev/null || true

echo
echo "=== 8) what run_signal.sh actually calls (quick scan) ==="
if [ -f run_signal.sh ]; then
  grep -nE 'python|python3|python -m|tools/|alert_loop|autorun|runner|final_runner|runner_confluence|status_cmd|tg_send' run_signal.sh || true
fi

echo
echo "=== DONE ==="
echo "Paste the FULL output back here. Next step: I will replace the offender script with a safe env loader (env_safe_source), no guessing."
