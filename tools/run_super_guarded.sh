#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$HOME/bot-a/tools"

# Respect your weekend/holiday guard if present
if python3 weekend_guard.py --closed-now >/dev/null 2>&1; then
  exit 0
fi

# Prevent overlap
LOCK=/data/data/com.termux/files/usr/tmp/runner.lock
if [[ -f "$LOCK" ]] && find "$LOCK" -mmin -1 >/dev/null 2>&1; then
  exit 0
fi

# Run the super-guarded pipeline
python3 "$HOME/bot-a/tools/super_guarded_launcher.py" --pair EURUSD --tf M15 || true

# Touch freshness
date +%s > "$LOCK"
