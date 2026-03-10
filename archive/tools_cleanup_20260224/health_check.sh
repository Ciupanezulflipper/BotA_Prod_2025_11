#!/data/data/com.termux/files/usr/bin/bash
# BotA Health Check — structural integrity checker
# Purpose: Ensure BotA is ready BEFORE markets open.

set -euo pipefail

ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"
LOGS="$ROOT/logs"
CACHE="$ROOT/cache"

echo "------------------------------------------------------------"
echo "[HEALTH] BotA structural health check"
echo "Root: $ROOT"
echo "------------------------------------------------------------"

PASS=true

check_file() {
    local f="$1"
    if [ -f "$f" ]; then
        echo "[OK] exists: $f"
    else
        echo "[FAIL] missing file: $f"
        PASS=false
    fi
}

check_exec() {
    local f="$1"
    if [ -x "$f" ]; then
        echo "[OK] exec: $f"
    else
        echo "[FAIL] not executable: $f"
        PASS=false
    fi
}

check_dir() {
    local d="$1"
    if [ -d "$d" ]; then
        echo "[OK] dir: $d"
    else
        echo "[FAIL] missing dir: $d"
        PASS=false
    fi
}

echo "Checking directories..."
check_dir "$TOOLS"
check_dir "$LOGS"
check_dir "$CACHE"

echo
echo "Checking core tool files..."
check_file "$TOOLS/data_fetch_candles.sh"
check_file "$TOOLS/build_indicators.py"
check_file "$TOOLS/indicators_updater.sh"
check_file "$TOOLS/scoring_engine.sh"
check_file "$TOOLS/quality_filter.py"
check_file "$TOOLS/signal_watcher_pro.sh"

echo
echo "Checking executables..."
check_exec "$TOOLS/data_fetch_candles.sh"
check_exec "$TOOLS/build_indicators.py"
check_exec "$TOOLS/indicators_updater.sh"
check_exec "$TOOLS/scoring_engine.sh"
check_exec "$TOOLS/quality_filter.py"
check_exec "$TOOLS/signal_watcher_pro.sh"

echo
echo "Checking for known broken path patterns..."
if grep -R "tools}" "$ROOT" 2>/dev/null | grep -q "tools}"; then
    echo "[FAIL] Found malformed path 'tools}' in codebase."
    PASS=false
else
    echo "[OK] No malformed 'tools}' paths found."
fi

echo
echo "Checking error.log for critical errors..."
if tail -n 20 "$LOGS/error.log" 2>/dev/null | grep -qi "No such file\|tools}"; then
    echo "[WARN] Recent critical errors detected (path / missing files)."
else
    echo "[OK] No critical errors in last 20 lines of error.log."
fi

echo
echo "==================== RESULT ===================="
if [ "$PASS" = true ]; then
    echo "✅ HEALTH STATUS: PASS — BotA structure looks correct."
else
    echo "❌ HEALTH STATUS: FAIL — Fix issues before trusting signals."
fi
echo "================================================"
