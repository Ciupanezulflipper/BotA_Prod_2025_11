#!/data/data/com.termux/files/usr/bin/bash
# Lightweight smoke test for multiple pairs/TFs with a Telegram summary

set -euo pipefail

BOT="$HOME/bot-a"
TOOLS="$BOT/tools"
LOGDIR="$BOT/logs"
mkdir -p "$LOGDIR"

# ——— Settings you can tweak ———
PAIRS=(EURUSD XAUUSD)         # Add/remove pairs if you like
TFS=(M15 H1 H4 D1)            # Timeframes to probe
DRY_RUN=false                 # Use false to exercise the full code path
# ————————————————

STAMP="$(date -Is)"
RUNLOG="$LOGDIR/smoke_$(date +%Y%m%d-%H%M%S).log"

echo "=== SMOKE START $STAMP ===" | tee -a "$RUNLOG"
printf "Pairs: %s | TFs: %s | dry_run=%s\n" "${PAIRS[*]}" "${TFS[*]}" "$DRY_RUN" | tee -a "$RUNLOG"

summary_lines=()
had_error=0
had_signal=0

run_one () {
  local pair="$1" tf="$2"
  # Capture single-line result from runner_confluence (already formatted)
  if out="$(python3 "$TOOLS/runner_confluence.py" --pair "$pair" --tf "$tf" --force --dry-run="$DRY_RUN" 2>&1)"; then
    # Keep a clean one-liner for the summary and the full log for diagnostics
    local line="$(echo "$out" | tail -n 1)"
    echo "$out" >> "$RUNLOG"
    summary_lines+=("• ${line}")
    # Detect non-zero BUY/SELL sums in the line (very lightweight parse)
    if echo "$line" | awk '/BUY/ && /SELL/ { if ($0 ~ /BUY [^0-9]*([0-9]+\.[0-9]+|[1-9][0-9]*\.*[0-9]*)/ || $0 ~ /SELL [^0-9]*([0-9]+\.[0-9]+|[1-9][0-9]*\.*[0-9]*)/) print "hit" }' | grep -q hit; then
      had_signal=1
    fi
  else
    had_error=1
    echo "[ERROR] $pair $tf" | tee -a "$RUNLOG"
    echo "$out" >> "$RUNLOG"
    summary_lines+=("• ${pair} ${tf} – ERROR (see log)")
  fi
}

for p in "${PAIRS[@]}"; do
  for tf in "${TFS[@]}"; do
    run_one "$p" "$tf"
  done
done

echo "=== SMOKE END $(date -Is) ===" | tee -a "$RUNLOG"

# Build Telegram message (short + readable)
title="🧪 Smoke: $(date -u +%Y-%m-%dT%H:%MZ) • Pairs ${#PAIRS[@]} × TFs ${#TFS[@]}"
status="OK"
[[ $had_error -eq 1 ]] && status="Issues"
[[ $had_signal -eq 1 ]] && status="$status • Signals"

msg="$title
Status: $status

$(printf "%s\n" "${summary_lines[@]}")"

# Send to Telegram using your existing notifier
python3 "$TOOLS/status_cmd.py" --alert "$msg" >/dev/null 2>&1 || true

# Also print to terminal
printf "\n%s\n" "$msg"

# Exit non-zero if any runner errored (useful for future CI/cron checks)
exit $had_error
