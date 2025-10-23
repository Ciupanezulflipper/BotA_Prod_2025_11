#!/usr/bin/env bash
set -e
vars=(
  TRADE_UTC_START TRADE_UTC_END NEWS_PAUSE COOLDOWN_MINUTES
  DEDUPE_WINDOW_MIN FRIDAY_UTC_CUTOFF MONDAY_UTC_START
  SEP_CSV_FALLBACK VOTE_BUY_THRESHOLD VOTE_SELL_THRESHOLD
  ENFORCE_WEIGHTED_ONLY RSI_CHOP_GUARD ATR_MULT_SL ATR_MULT_TP
)
for k in "${vars[@]}"; do printf "%-22s= %s\n" "$k" "${!k}"; done
echo; echo "[SITE] tail:"
tail -n 30 "$HOME/BotA/run.log" 2>/dev/null | sed -n '/^\[SITE\]/p' | tail -n 10
