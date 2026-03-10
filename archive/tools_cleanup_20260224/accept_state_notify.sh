#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

echo "== DRY RUN =="
DRY_RUN=1 bash "$HOME/BotA/tools/notify_on_change.sh" || true

echo "== FORCE one tick per pair (consumes credits) =="
set -a; . "$HOME/BotA/.env"; set +a
pairs="${PAIRS:-EURUSD,GBPUSD}"
IFS=',' read -r -a A <<< "$pairs"
for p in "${A[@]}"; do
  p_trim="$(echo "$p" | sed 's/^[[:space:]]\+//; s/[[:space:]]\+$//')"
  [ -z "$p_trim" ] && continue
  DRY_RUN_MODE=false PROVIDER_ORDER="twelve_data" "$HOME/BotA/tools/run_signal_once.py" "$p_trim" | tee -a "$HOME/BotA/logs/loop.log" || true
done

echo "== REAL send only if state changed =="
bash "$HOME/BotA/tools/notify_on_change.sh" || true

echo "[accept] notify-on-change OK"
