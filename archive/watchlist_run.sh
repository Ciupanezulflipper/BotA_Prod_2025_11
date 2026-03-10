#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

TOOLS="$HOME/BotA/tools"
EW="$TOOLS/early_watch.py"

if [ ! -f "$EW" ]; then
  echo "[FAIL] missing $EW" >&2
  exit 2
fi

# Run watcher (ignoring session gates)
out="$(python3 "$EW" --ignore-session 2>/dev/null || true)"
printf "%s\n" "$out"

# Summarize potential WATCH triggers if present
# Heuristic: lines containing 'WATCH' without 'too weak' are considered actionable
echo "---- WATCH SUMMARY ----"
echo "$out" | grep -E "WATCH" | grep -Ev "too weak|outside session" || echo "(no active WATCH signals)"
