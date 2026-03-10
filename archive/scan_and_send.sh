# ~/bot-a/tools/scan_and_send.sh
#!/data/data/com.termux/files/usr/bin/bash
set -e

PAIR="${1:-EURUSD}"
TF="${2:-M15}"

# Load env from BotA if present
if [ -f "$HOME/BotA/.env" ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' "$HOME/BotA/.env" | xargs)
fi

# Default confidence threshold if not in env
: "${CONF_MIN:=0.8}"

# Run the confluence runner as a module from inside the BotA package
cd "$HOME/BotA"
LINE=$(python -m tools.runner_confluence --pair "$PAIR" --tf "$TF" --force --dry-run=false)
echo "$LINE"

# Parse "Score X.YZ" from the line
score=$(echo "$LINE" | awk -F'Score ' '{print $2}' | awk '{print $1}')
min="$CONF_MIN"

# send only if |score| >= min
awk -v s="$score" -v m="$min" 'BEGIN{ exit !( (s >= m) || (s <= -m) ) }' || exit 0

# Use existing alert sender
python3 "$HOME/bot-a/tools/status_cmd.py" --alert "$LINE" >/dev/null 2>&1 || true
