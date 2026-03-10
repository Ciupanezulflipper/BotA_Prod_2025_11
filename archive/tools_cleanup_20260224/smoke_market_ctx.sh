#!/usr/bin/env bash
set -euo pipefail

TOOLS="$HOME/bot-a/tools"
PY=python3
RED=$'\e[31m'; GRN=$'\e[32m'; YLW=$'\e[33m'; CLR=$'\e[0m'

say() { printf "%s\n" "$*"; }
ok()  { printf "${GRN}✔ %s${CLR}\n" "$*"; }
warn(){ printf "${YLW}⚠ %s${CLR}\n" "$*"; }
fail(){ printf "${RED}✖ %s${CLR}\n" "$*"; exit 1; }

cd "$TOOLS"

say "Smoke: Market Context — $(date -Is)"
say "Using: $(command -v $PY)"

# 1) Basic file sanity
[[ -s "$TOOLS/status_market_block.py" ]] || fail "status_market_block.py missing/empty"
[[ -s "$TOOLS/market_block_v2.py"     ]] || fail "market_block_v2.py missing/empty"
ok "Files present"

# 2) Preview via import (what the card will use)
BLOCK_SHIM="$($PY - <<'PY'
import status_market_block, inspect
print("PATH:", inspect.getfile(status_market_block))
print("---BLOCK---")
print(status_market_block.render_market_block())
PY
)"
IMP_PATH="$(printf "%s\n" "$BLOCK_SHIM" | sed -n 's/^PATH: //p')"
[[ -n "$IMP_PATH" ]] || fail "Could not resolve import path for status_market_block"
ok "Card imports: $IMP_PATH"

CARD_SHIM="$(printf "%s\n" "$BLOCK_SHIM" | sed -n '/^---BLOCK---$/,$p' | sed '1d')"
[[ -n "$CARD_SHIM" ]] || fail "No block text returned by shim"

# 3) Preview direct v2
CARD_V2="$($PY "$TOOLS/market_block_v2.py")"
[[ -n "$CARD_V2" ]] || fail "No block text returned by v2"

# 4) Structural validation (4 venues present)
need_venues=(Sydney Tokyo London NewYork)
for v in "${need_venues[@]}"; do
  echo "$CARD_V2"   | grep -q "^$v"      || fail "v2 missing venue line: $v"
  echo "$CARD_SHIM" | grep -q "^$v"      || fail "shim missing venue line: $v"
done
ok "All venues present"

# 5) Compare shim vs v2 (exact text)
if diff -u <(printf "%s\n" "$CARD_V2") <(printf "%s\n" "$CARD_SHIM") >/dev/null; then
  ok "Shim output matches v2 (no stale import/cache)"
else
  warn "Shim differs from v2. Diff:"
  diff -u <(printf "%s\n" "$CARD_V2") <(printf "%s\n" "$CARD_SHIM") || true
  fail "Mismatch between v2 and shim"
fi

# 6) Optional runner.lock freshness (non-blocking)
LOCK="/data/data/com.termux/files/home/BotA/cache/runner.lock"
if [[ -e "$LOCK" ]]; then
  age=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || stat -f %m "$LOCK") ))
  if (( age <= 3600 )); then ok "runner.lock fresh (${age}s)"; else warn "runner.lock stale (${age}s)"; fi
else
  warn "runner.lock not found (skip freshness check)"
fi

# 7) Send a live card to Telegram
say "Sending status card…"
$PY "$TOOLS/status_card.py" --send || fail "status_card.py --send failed"
ok "Card sent. Compare Telegram text with preview above."

say "Preview (single source of truth):"
printf "%s\n" "$CARD_SHIM"

ok "SMOKE PASS"
