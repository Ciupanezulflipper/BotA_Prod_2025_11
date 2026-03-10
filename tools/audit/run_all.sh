#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd ~/BotA
[ -f .env ] && export $(grep -v ^# .env | xargs) || true

imports="$(python -c 'import BotA.tools.runner_confluence as r; print("ok")' 2>&1 || true)"
tg_ping="$(python -m BotA.tools.tg_utils --test "BotA audit ping" 2>&1 || true)"
prd_smoke="$(python -m BotA.tools.runner_confluence --pair EURUSD --tf M15 --dry-run=true --force 2>&1 || true)"

jq -n --arg imports "$imports\n" \
      --arg tg_ping "$tg_ping\n" \
      --arg prd_smoke "$prd_smoke\n" \
      '{imports:$imports, tg_ping:$tg_ping, prd_smoke:$prd_smoke}'
