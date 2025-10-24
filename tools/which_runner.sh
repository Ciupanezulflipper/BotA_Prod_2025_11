#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

PAIR="${1:-EURUSD}"
TMP="$(mktemp)"
CANDIDATES=(
  "$HOME/BotA/runner_confluence.py"
  "$HOME/BotA/runner_confluence_v1_backup.py"
  "$HOME/BotA/runner_v2_bollinger.py"
  "$HOME/BotA/run_signal.sh"
)

echo "[detect] probing runners for $PAIR ..." >&2
FOUND=""

for C in "${CANDIDATES[@]}"; do
  if [ -x "$C" ] || [ -f "$C" ]; then
    # Try python for .py, bash for .sh
    if [[ "$C" == *.py ]]; then
      (python3 "$C" "$PAIR" || true) | tee "$TMP" >/dev/null
    else
      ("$C" "$PAIR" || true) | tee "$TMP" >/dev/null
    fi

    if grep -Eq '^===\s*[A-Z/]{6,7}\s+snapshot\s+===$' "$TMP" && grep -Eq '^(H1|H4|D1): ' "$TMP"; then
      FOUND="$C"
      break
    fi

    # Some runners print everything to stderr; try capturing with bash -c
    if [[ -z "$FOUND" ]]; then
      if [[ "$C" == *.py ]]; then
        (python3 "$C" "$PAIR" 2>&1 || true) | tee "$TMP" >/dev/null
      else
        ("$C" "$PAIR" 2>&1 || true) | tee "$TMP" >/dev/null
      fi
      if grep -Eq '^===\s*[A-Z/]{6,7}\s+snapshot\s+===$' "$TMP" && grep -Eq '^(H1|H4|D1): ' "$TMP"; then
        FOUND="$C"
        break
      fi
    fi
  fi
done

rm -f "$TMP"

if [ -z "$FOUND" ]; then
  echo "[detect] ❌ No runner produced a snapshot block for $PAIR." >&2
  exit 2
fi

# Remember the found runner
mkdir -p "$HOME/BotA/state"
echo "$FOUND" > "$HOME/BotA/state/snapshot_runner.path"
echo "$FOUND"
