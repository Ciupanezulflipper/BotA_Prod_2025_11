#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

LOG="$HOME/bot-a/logs/runner_debug.log"
mkdir -p "$HOME/bot-a/logs"
cd "$HOME/bot-a/tools"

echo "==== DEBUG RUNNER START $(date -Is) TZ=${TZ:-unset} ====" | tee -a "$LOG"

# Snapshot of Python/env/import locations
python3 - <<'PY' | tee -a "$LOG"
import sys, os, platform, inspect
print("Python:", sys.executable, platform.python_version())
print("CWD:", os.getcwd())
print("HOME:", os.path.expanduser("~"))
print("TZ env:", os.environ.get("TZ"))
print("PATH:", os.environ.get("PATH"))
print("sys.path:", sys.path)

def where(mod):
    try:
        m = __import__(mod)
        print(f"{mod} ->", inspect.getfile(m))
    except Exception as e:
        print(f"{mod} -> import FAILED: {e}")

for mod in ["status_market_block","market_block_v2","runner_confluence","signal_journal"]:
    where(mod)
PY

# Show any locks
ls -l "$HOME/bot-a/data/"*lock* 2>/dev/null || true

# Run the runner with maximal visibility
export PYTHONFAULTHANDLER=1
export PYTHONUNBUFFERED=1

CMD=(python3 "$HOME/bot-a/tools/runner_confluence.py" --pair EURUSD --tf M15 --force --dry-run)
echo "+ ${CMD[*]}" | tee -a "$LOG"
"${CMD[@]}" 2>&1 | tee -a "$LOG"; RC=${PIPESTATUS[0]}

echo "Runner exit code: $RC" | tee -a "$LOG"
echo "==== DEBUG RUNNER END $(date -Is) ====" | tee -a "$LOG"
exit $RC
