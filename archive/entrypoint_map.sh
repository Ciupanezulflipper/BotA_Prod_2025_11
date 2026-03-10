#!/usr/bin/env bash
set -euo pipefail

# tools/entrypoint_map.sh
# SAFE: does NOT source any .env files; prints NO secrets.
# Purpose:
#   1) Tell you what is ACTUALLY running BotA right now (active crontab = real automation entrypoint)
#   2) Show all scripts that still do: source/. .env or .env.botA (the cause of your '(' crash)
#   3) Point to the exact offender file(s) to replace next (no guessing)

ROOT="/data/data/com.termux/files/home/BotA"
cd "$ROOT"

echo "=== BotA ENTRYPOINT MAP (safe) ==="
echo "PWD: $(pwd)"
echo "DATE_UTC: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo

echo "=== 1) ACTIVE CRON (crontab -l) => REAL daily entrypoint(s) ==="
crontab -l 2>/dev/null | sed -n '1,260p' || echo "(no active crontab installed into cronie)"
echo

echo "=== 2) REPO .crontab (file in repo) => NOT active unless you installed it ==="
if [ -f .crontab ]; then
  nl -ba .crontab | sed -n '1,260p'
else
  echo "(no .crontab file)"
fi
echo

PRIMARY="UNKNOWN"
if crontab -l 2>/dev/null | grep -qE 'signal_watcher_pro\.sh'; then
  PRIMARY="tools/signal_watcher_pro.sh --once (via crontab -l)"
elif crontab -l 2>/dev/null | grep -qE 'run_signal\.sh'; then
  PRIMARY="./run_signal.sh (via crontab -l)"
elif crontab -l 2>/dev/null | grep -qE 'runner_full\.py|runner_confluence\.py|final_runner\.py|autorun\.py'; then
  PRIMARY="python runner (see cron lines above)"
elif [ -f run_signal.sh ]; then
  PRIMARY="./run_signal.sh exists (but NOT scheduled in your active crontab)"
fi

echo "=== 3) PRIMARY_ENTRYPOINT (best inference from active cron) ==="
echo "PRIMARY_ENTRYPOINT=${PRIMARY}"
echo

echo "=== 4) run_signal.sh (exists?) ==="
ls -la run_signal.sh 2>/dev/null || echo "MISSING: run_signal.sh"
echo

echo "=== 5) run_signal.sh (quick scan: what it calls; does it source env?) ==="
if [ -f run_signal.sh ]; then
  echo "--- run_signal.sh: env sourcing patterns ---"
  grep -nE '(^|[[:space:]])(source|\.)([[:space:]]+)+/?\.env(\.botA)?\b' run_signal.sh \
    || echo "(no direct source/. of .env/.env.botA found in run_signal.sh)"
  echo
  echo "--- run_signal.sh: main calls ---"
  grep -nE 'python|python3|python -m|tools/|alert_loop|autorun|runner|final_runner|runner_confluence|status_cmd|tg_send|run_mux_once' run_signal.sh || true
fi
echo

echo "=== 6) OFFENDER SEARCH: any script sourcing .env.botA directly? (THIS triggers your '(' crash) ==="
grep -RIn --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=logs \
  -E '(^|[[:space:]])(source|\.)([[:space:]]+)+.*\.env\.botA\b' \
  . 2>/dev/null || echo "(none found)"
echo

echo "=== 7) BROAD SEARCH: scripts sourcing .env / .env.runtime / config env files ==="
grep -RIn --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=logs \
  -E '(^|[[:space:]])(source|\.)([[:space:]]+)+.*\.env(\.runtime)?\b' \
  tools run_signal.sh *.sh 2>/dev/null || true
echo

echo "=== 8) SHELL STARTUP CHECK: is your terminal auto-sourcing .env.botA? ==="
# Termux bash startup files commonly used:
FILES=(
  "$HOME/.bashrc"
  "$HOME/.profile"
  "$HOME/.bash_profile"
  "$PREFIX/etc/bash.bashrc"
  "$PREFIX/etc/profile"
)
for f in "${FILES[@]}"; do
  if [ -f "$f" ]; then
    if grep -nH -E '\.env\.botA|source .*\.env\.botA|\. .*\.env\.botA' "$f" 2>/dev/null; then
      :
    fi
  fi
done || true
echo "(If nothing printed above, your shell startup files are NOT sourcing .env.botA.)"
echo

echo "=== 9) CONCLUSION (plain) ==="
echo "1) Your REAL daily entrypoint is whatever appears in 'crontab -l'."
echo "2) Your '(' crash happens ONLY when something does: source/. .env.botA (bad)."
echo "3) Next fix step: replace the offender file(s) to use tools/env_safe_source.sh instead of source/."
echo
echo "=== DONE ==="
