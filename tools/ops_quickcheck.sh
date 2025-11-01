# File: $HOME/BotA/tools/ops_quickcheck.sh
#!/bin/bash
set -euo pipefail

ROOT="${HOME}/BotA"
LOGDIR="${ROOT}/logs"
CFGD="${ROOT}/config"
NOW_EPOCH=$(date -u +%s)

ts(){ date -u '+%Y-%m-%d %H:%M:%S UTC'; }
hdr(){ echo -e "\n===== $1 @ $(ts) ====="; }

safe_tail(){ local f="$1" n="${2:-40}"; [[ -f "$f" ]] && { echo "--- $f (last $n) ---"; tail -n "$n" "$f"; } || echo "--- $f (missing) ---"; }

age_sec(){
  # print age in seconds of file mtime; 999999 if missing
  local f="$1"
  if [[ -f "$f" ]]; then
    local mt
    if stat --version >/dev/null 2>&1; then
      mt=$(stat -c %Y "$f")
    else
      mt=$(stat -f %m "$f")
    fi
    echo $(( NOW_EPOCH - mt ))
  else
    echo 999999
  fi
}

freshness_report(){
  local label="$1" f1="$2"
  local age=$(age_sec "$f1")
  local status="STALE"
  [[ "$age" -le 600 ]] && status="FRESH"
  printf "%-18s %-6s age=%6s sec  file=%s\n" "$label" "$status" "$age" "$f1"
}

echo "===== BotA QuickCheck @ $(ts) ====="

# 1) Processes
hdr "Processes"
ps -ef | grep -E 'cloudbot\.py|main\.py|telegram|polling|BotRunner' | grep -v grep || echo "No running bot processes detected."

# 2) Cron
hdr "Cron entries"
crontab -l 2>/dev/null | sed 's/^/CRON: /' || echo "No crontab."

# 3) Config snapshot (non-sensitive)
hdr "Config snapshot (signal/strategy env if present)"
for f in "$CFGD/signal.env" "$CFGD/strategy.env"; do
  if [[ -f "$f" ]]; then
    echo "--- $f ---"
    # hide obvious secrets
    sed -E 's/(TOKEN|KEY|SECRET)=.*/\1=****/g' "$f" | grep -E 'EVAL_WINDOWS|TP_PIPS|SL_PIPS|CONF|RSI|SLOPE|SPREAD|ATR|NEWS|PAIR|ENABLE|WINDOWS' || true
  else
    echo "--- $f (missing) ---"
  fi
done

# 4) Pair list if exists
hdr "Pairs / symbols (if configured)"
for f in "$CFGD/pairs.txt" "$CFGD/symbols.txt"; do
  [[ -f "$f" ]] && { echo "--- $f ---"; cat "$f"; }
done

# 5) Data freshness probes (EURUSD typical paths)
hdr "Data freshness"
freshness_report "cache/EURUSD.txt" "$ROOT/cache/EURUSD.txt"
freshness_report "data/EURUSD.csv"  "$ROOT/data/EURUSD.csv"
freshness_report "alerts.csv"       "$LOGDIR/alerts.csv"
freshness_report "accuracy.csv"     "$LOGDIR/accuracy.csv"
freshness_report "run.log"          "$ROOT/run.log"
freshness_report "cron.accuracy.log" "$LOGDIR/cron.accuracy.log"

# 6) Recent logs
hdr "Recent logs (tail)"
safe_tail "$ROOT/run.log" 50
safe_tail "$ROOT/error.log" 60
safe_tail "$LOGDIR/cron.accuracy.log" 60
safe_tail "$LOGDIR/alerts.csv" 40
safe_tail "$LOGDIR/accuracy.csv" 40

# 7) Quick gates sanity (derived from envs)
hdr "Gate sanity (derived)"
CONF=$( (grep -E 'CONF(IDENCE)?(_THRESHOLD)?=' "$CFGD"/signal.env "$CFGD"/strategy.env 2>/dev/null || true) | tail -n1 | awk -F= '{print $2}')
RSI_SLOPE=$( (grep -E 'RSI(_SLOPE)?_THRESHOLD=' "$CFGD"/signal.env "$CFGD"/strategy.env 2>/dev/null || true) | tail -n1 | awk -F= '{print $2}')
SPREAD_MAX=$( (grep -E 'SPREAD_MAX(_PIPS)?=' "$CFGD"/signal.env "$CFGD"/strategy.env 2>/dev/null || true) | tail -n1 | awk -F= '{print $2}')
ATR_NORM=$( (grep -E 'ATR_H4_MAX_PCT=' "$CFGD"/signal.env "$CFGD"/strategy.env 2>/dev/null || true) | tail -n1 | awk -F= '{print $2}')
printf "confidence>= %s | rsi_slope>= %s | spread<= %s pips | atr_h4<= %s%% (if set)\n" "${CONF:-NA}" "${RSI_SLOPE:-NA}" "${SPREAD_MAX:-NA}" "${ATR_NORM:-NA}"

# 8) Simple conclusions
hdr "Conclusions"
issues=0
if ! ps -ef | grep -E 'cloudbot\.py|main\.py' | grep -v grep >/dev/null; then
  echo "[FAIL] No running bot process."
  ((issues++))
else
  echo "[PASS] Bot process detected."
fi

if ! crontab -l 2>/dev/null | grep -E 'signal_accuracy\.py' >/dev/null; then
  echo "[WARN] accuracy cron entry not found."
else
  echo "[PASS] accuracy cron entry present."
fi

# Alerts present recently?
if [[ -f "$LOGDIR/alerts.csv" ]]; then
  last_alert_epoch=$(awk -F, 'END{print $1}' "$LOGDIR/alerts.csv" 2>/dev/null | xargs -I{} date -u -d "{}" +%s 2>/dev/null || echo 0)
  if [[ "$last_alert_epoch" -gt 0 ]]; then
    delta=$(( NOW_EPOCH - last_alert_epoch ))
    if [[ "$delta" -gt 7200 ]]; then
      echo "[WARN] No new alerts in the last $((delta/60)) minutes (gates too strict or data stale?)."
    else
      echo "[PASS] Alerts seen within the last $((delta/60)) minutes."
    fi
  else
    echo "[WARN] alerts.csv exists but timestamp parse failed."
  fi
else
  echo "[WARN] alerts.csv missing."
fi

echo "Exit with $issues issue(s)."
exit 0
