#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="/data/data/com.termux/files/home/BotA"
LOG_SIGNALS="${ROOT}/logs/cron.signals.log"
LOG_ERROR="${ROOT}/logs/error.log"
SPOOL1="/data/data/com.termux/files/usr/var/spool/cron/u0_a24"
SPOOL2="${PREFIX:-/data/data/com.termux/files/usr}/var/spool/cron/u0_a24"

cd "$ROOT"

echo "=== PROOF STEP 3: Ghost invokers (beyond crontab -l) ==="
echo "DATE: $(date)"
echo "WHOAMI: $(whoami 2>/dev/null || true)"
echo "PWD: $(pwd)"
echo

echo "=== QUICK error.log tail (last 30) ==="
if [ -f "$LOG_ERROR" ]; then
  tail -n 30 "$LOG_ERROR" || true
else
  echo "MISSING: $LOG_ERROR"
fi
echo

echo "=== CRONTAB (current) watcher-related lines ==="
crontab -l 2>/dev/null | grep -nE 'signal_watcher_pro|m15_h1_fusion|scoring_engine|quality_filter|send_candidates_now|telegram_send|sendMessage|market_open' || true
echo

echo "=== CRON SPOOL (authoritative storage) ==="
for f in "$SPOOL1" "$SPOOL2"; do
  if [ -f "$f" ]; then
    echo "--- FOUND SPOOL FILE: $f ---"
    ls -la "$f" || true
    echo "--- TOP 80 lines ---"
    nl -ba "$f" | sed -n '1,80p' || true
    echo "--- GREP invokers ---"
    grep -nE 'signal_watcher_pro|m15_h1_fusion|scoring_engine|quality_filter|send_candidates_now|telegram_send|sendMessage|market_open' "$f" || true
    echo
  fi
done

echo "=== PROCESS: cron daemon present? ==="
(ps -ef 2>/dev/null || ps -A -o pid,ppid,cmd 2>/dev/null || true) | grep -E 'crond|cron' | grep -v grep || true
echo

echo "=== PROCESS: any live watcher/fusion/scoring/telegram processes RIGHT NOW ==="
(ps -ef 2>/dev/null || ps -A -o pid,ppid,cmd 2>/dev/null || true) | grep -E 'signal_watcher_pro\.sh|m15_h1_fusion\.sh|scoring_engine\.sh|quality_filter\.py|telegram|sendMessage' | grep -v grep || true
echo

echo "=== TERMUX:BOOT hooks (show + grep) ==="
BOOT_DIR="$HOME/.termux/boot"
TASKER_DIR="$HOME/.termux/tasker"
for d in "$BOOT_DIR" "$TASKER_DIR"; do
  if [ -e "$d" ]; then
    echo "--- FOUND: $d ---"
    ls -la "$d" 2>/dev/null || true
    echo "--- GREP invokers (top 120) ---"
    grep -R --line-number -E 'BotA|signal_watcher_pro\.sh|signal_watcher_guard\.sh|watch_wrap|cron_signals|m15_h1_fusion\.sh|scoring_engine\.sh|quality_filter\.py|send_candidates_now|telegram|crontab|crond|sv |runsv|nohup|&' "$d" 2>/dev/null | head -n 120 || true
    echo
    if [ -f "$d/start_bot.sh" ]; then
      echo "--- SHOW: $d/start_bot.sh ---"
      nl -ba "$d/start_bot.sh" | sed -n '1,200p' || true
      echo
    fi
  fi
done
echo

echo "=== TERMUX-SERVICES (runit): service dirs + broken links ==="
for svcdir in "$PREFIX/var/service" "/data/data/com.termux/files/usr/var/service" "$HOME/.termux/services"; do
  if [ -e "$svcdir" ]; then
    echo "--- DIR: $svcdir ---"
    ls -la "$svcdir" 2>/dev/null || true
    echo "--- GREP invokers inside (top 200) ---"
    grep -R --line-number -E 'BotA|signal_watcher_pro\.sh|m15_h1_fusion\.sh|scoring_engine\.sh|quality_filter\.py|send_candidates_now|telegram|crontab|crond' "$svcdir" 2>/dev/null | head -n 200 || true
    echo
  fi
done
echo

echo "=== sv status (best effort) ==="
if command -v sv >/dev/null 2>&1; then
  for d in "$PREFIX/var/service" "/data/data/com.termux/files/usr/var/service"; do
    if [ -d "$d" ]; then
      echo "--- sv status for $d ---"
      sv status "$d"/* 2>/dev/null || true
      echo
    fi
  done
else
  echo "sv not found (ok)"
fi
echo

echo "=== TMUX: sessions/panes (ghost loops often run in tmux) ==="
if command -v tmux >/dev/null 2>&1; then
  tmux ls 2>/dev/null || echo "(no tmux sessions)"
  echo
  tmux list-panes -a -F '#S:#I.#P | cmd=#{pane_current_command} | start=#{pane_start_command}' 2>/dev/null || true
else
  echo "tmux not found (ok)"
fi
echo

echo "=== LOGS: recent WATCHER/TELEGRAM evidence (tail) ==="
if [ -f "$LOG_SIGNALS" ]; then
  echo "--- last 20 WATCHER SANITY ---"
  grep -nE '^\[WATCHER .*SANITY:' "$LOG_SIGNALS" | tail -n 20 || true
  echo
  echo "--- last 20 TELEGRAM SENT ---"
  grep -nE '^\[TELEGRAM .*SENT:' "$LOG_SIGNALS" | tail -n 20 || true
  echo
  echo "--- last 30 TELEGRAM tier_skip/cooldown ---"
  grep -nE '^\[TELEGRAM .* (tier_skip|cooldown)' "$LOG_SIGNALS" | tail -n 30 || true
else
  echo "MISSING: $LOG_SIGNALS"
fi
echo

echo "=== REPO: search for any invokers of watcher (top 180) ==="
grep -R --line-number -E 'signal_watcher_pro\.sh|signal_watcher_guard\.sh|watch_wrap_market\.sh|cron_signals\.sh|install_signals_cron_gate\.sh|send_candidates_now|telegram_send|sendMessage' "$ROOT" 2>/dev/null | head -n 180 || true
echo

echo "=== PROOF STEP 3 END ==="
