#!/data/data/com.termux/files/usr/bin/bash
# BotA — Phase 12: render/cache audit
set -euo pipefail
TOOLS="$HOME/BotA/tools"
CACHE="$HOME/BotA/cache"
ok(){ printf "[OK] %s\n" "$*"; }
warn(){ printf "[WARN] %s\n" "$*" >&2; }
fail=0

now=$(date -u +%s)
for p in EURUSD GBPUSD; do
  f="$CACHE/$p.txt"
  if [[ ! -s "$f" ]]; then warn "$p: cache missing"; fail=$((fail+1)); continue; fi
  age=$(( now - $(stat -c %Y "$f") ))
  if (( age > 1800 )); then warn "$p: cache stale (${age}s)"; fail=$((fail+1)); else ok "$p: cache fresh (${age}s)"; fi
  for tf in H1 H4 D1; do
    grep -q "^$tf:" "$f" || { warn "$p: $tf line missing"; fail=$((fail+1)); }
  done
done

OUT="$("$TOOLS/analyze_now.py" EURUSD GBPUSD)"
echo "$OUT" | sed -n '1,10p'
if echo "$OUT" | grep -q 'cache missing\|cache incomplete'; then
  warn "analyze shows gaps — investigate providers/session"
  fail=$((fail+1))
else
  ok "analyze_now pretty output OK"
fi

if (( fail==0 )); then
  echo "=== PHASE 12: PASSED ==="
else
  echo "=== PHASE 12: ATTENTION ($fail issue(s)) ==="
fi
