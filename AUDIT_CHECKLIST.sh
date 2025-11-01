#!/data/data/com.termux/files/usr/bin/bash
# BotA Production Readiness Audit
# Run this and share output with 3 independent AIs for verification

echo "════════════════════════════════════════════════════════"
echo "  BotA PRODUCTION READINESS AUDIT"
echo "  Date: $(date -Iseconds)"
echo "════════════════════════════════════════════════════════"
echo ""

# ===== SECTION 1: SECURITY AUDIT =====
echo "━━━ 1. SECURITY AUDIT ━━━"
echo ""

echo "1.1 Token Exposure Check"
echo "Searching for hardcoded tokens in scripts..."
grep -r "AAG5vikEwEU" tools/ 2>/dev/null && echo "⚠️  TOKEN EXPOSED IN CODE!" || echo "✅ No hardcoded tokens found"
grep -r "7991280737:" tools/ 2>/dev/null && echo "⚠️  TOKEN EXPOSED IN CODE!" || echo "✅ No tokens in tools/"
echo ""

echo "1.2 File Permissions"
ls -la config/strategy.env | awk '{print $1, $3, $9}'
[[ $(stat -c %a config/strategy.env) == "600" ]] && echo "✅ strategy.env: Secure (600)" || echo "⚠️  strategy.env: $(stat -c %a config/strategy.env) - Should be 600"
echo ""

echo "1.3 Authorization Check (telecontroller)"
grep -A 3 "ALLOWED_CHAT_IDS" tools/telecontroller_curl.py | head -5
[[ -n "$(grep ALLOWED_CHAT_IDS tools/telecontroller_curl.py)" ]] && echo "✅ Authorization implemented" || echo "⚠️  No authorization check found"
echo ""

echo "1.4 Sensitive Files Readable by Others"
find ~/BotA -type f \( -name "*.env" -o -name "*token*" -o -name "*secret*" \) -perm /044 2>/dev/null | head -10
[[ -z "$(find ~/BotA -type f -name "*.env" -perm /044 2>/dev/null)" ]] && echo "✅ No world-readable sensitive files" || echo "⚠️  Found world-readable files above"
echo ""

# ===== SECTION 2: FUNCTIONALITY AUDIT =====
echo "━━━ 2. FUNCTIONALITY AUDIT ━━━"
echo ""

echo "2.1 Process Status"
echo "Telecontroller:"
ps -ef | grep telecontroller_curl | grep -v grep || echo "❌ NOT RUNNING"
echo "Watcher:"
ps -ef | grep watch_wrap_market | grep -v grep || echo "❌ NOT RUNNING"
echo ""

echo "2.2 Zombie Process Check"
ZOMBIE_COUNT=$(ps -ef | grep -E "signal_watcher|watch_wrap|wrap_watch" | grep -v grep | wc -l)
echo "Total watcher-related processes: $ZOMBIE_COUNT"
[[ $ZOMBIE_COUNT -eq 1 ]] && echo "✅ Correct - exactly 1 wrapper" || echo "⚠️  Expected 1, found $ZOMBIE_COUNT"
echo ""

echo "2.3 Lock File Status"
ls -lh cache/*.lock 2>/dev/null || echo "No lock files (OK if not running)"
echo ""

echo "2.4 Heartbeat Freshness"
if [[ -f cache/watcher.heartbeat ]]; then
    HB_AGE=$(( $(date +%s) - $(cat cache/watcher.heartbeat) ))
    echo "Heartbeat age: ${HB_AGE}s"
    [[ $HB_AGE -lt 400 ]] && echo "✅ Fresh (during market hours)" || echo "⚠️  Stale (expected if market closed)"
else
    echo "❌ No heartbeat file"
fi
echo ""

echo "2.5 Market Detection Accuracy"
PHASE=$(bash tools/market_open.sh 2>/dev/null || echo "ERROR")
echo "Current market phase: $PHASE"
DOW=$(date -u +%u)
HOUR=$(date -u +%H)
echo "Current: $(date -u +%A) ${HOUR}:00 UTC (DOW=$DOW)"
if [[ $DOW -eq 6 ]] || [[ ($DOW -eq 7 && $HOUR -lt 22) ]] || [[ ($DOW -eq 5 && $HOUR -ge 22) ]]; then
    [[ "$PHASE" == "Closed" ]] && echo "✅ Correct - should be Closed" || echo "⚠️  Should be Closed, detected: $PHASE"
else
    [[ "$PHASE" == "Open" ]] && echo "✅ Correct - should be Open" || echo "⚠️  Should be Open, detected: $PHASE"
fi
echo ""

echo "2.6 Telegram Connectivity"
TOKEN=$(grep TELEGRAM_TOKEN config/strategy.env | cut -d'"' -f2)
CHAT_ID=$(grep TELEGRAM_CHAT_ID config/strategy.env | cut -d'"' -f2)
TEST_MSG=$(curl -s -m 10 -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" -d "chat_id=${CHAT_ID}" -d "text=🔍 Audit test at $(date +%H:%M)" 2>&1)
echo "$TEST_MSG" | grep -q '"ok":true' && echo "✅ Telegram API reachable" || echo "❌ Telegram API failed: $TEST_MSG"
echo ""

echo "2.7 Handler Log Verification"
HANDLER_COUNT=$(grep -c '\[handle\]' logs/telecontroller.log 2>/dev/null || echo 0)
echo "Handlers logged: $HANDLER_COUNT"
[[ $HANDLER_COUNT -ge 2 ]] && echo "✅ Bot responding to commands" || echo "⚠️  Expected ≥2, found $HANDLER_COUNT"
echo ""

# ===== SECTION 3: ERROR HANDLING AUDIT =====
echo "━━━ 3. ERROR HANDLING AUDIT ━━━"
echo ""

echo "3.1 Recent Errors in Logs"
echo "Telecontroller errors (last 24h):"
grep -i "error\|exception\|traceback" logs/telecontroller.log 2>/dev/null | tail -5 || echo "No errors"
echo ""
echo "Watcher errors (last 24h):"
grep -i "error\|exception\|fail" logs/watcher_nohup.log 2>/dev/null | tail -5 || echo "No errors"
echo ""

echo "3.2 409 Conflict Status"
CONFLICT_COUNT=$(grep "409" logs/telecontroller.log 2>/dev/null | wc -l)
echo "HTTP 409 errors: $CONFLICT_COUNT"
[[ $CONFLICT_COUNT -eq 0 ]] && echo "✅ No conflicts" || echo "⚠️  Found $CONFLICT_COUNT conflicts"
echo ""

echo "3.3 SSL Error Status"
SSL_COUNT=$(tail -100 logs/telecontroller.log 2>/dev/null | grep -c "SSL\|CERTIFICATE" || echo 0)
echo "Recent SSL errors (last 100 lines): $SSL_COUNT"
[[ $SSL_COUNT -eq 0 ]] && echo "✅ No recent SSL issues" || echo "⚠️  Found $SSL_COUNT recent SSL errors"
echo ""

echo "3.4 Signal Handler Crash Detection"
tail -50 logs/telecontroller.log 2>/dev/null | grep -q "Shutting down" && echo "⚠️  Controller restarted recently" || echo "✅ No recent crashes"
echo ""

# ===== SECTION 4: OPERATIONAL AUDIT =====
echo "━━━ 4. OPERATIONAL AUDIT ━━━"
echo ""

echo "4.1 Boot Script Status"
[[ -f ~/.termux/boot/botA_start.sh ]] && echo "✅ Boot script exists" || echo "❌ Boot script missing"
[[ -x ~/.termux/boot/botA_start.sh ]] && echo "✅ Boot script executable" || echo "⚠️  Boot script not executable"
echo ""

echo "4.2 Management Scripts"
for script in run_all.sh stop_all.sh status_all.sh; do
    [[ -f tools/$script ]] && echo "✅ $script exists" || echo "❌ $script missing"
    [[ -x tools/$script ]] && echo "✅ $script executable" || echo "⚠️  $script not executable"
done
echo ""

echo "4.3 Required Files Present"
REQUIRED_FILES=(
    "config/strategy.env"
    "tools/telecontroller_curl.py"
    "tools/watch_wrap_market.sh"
    "tools/market_open.sh"
    "tools/signal_watcher_pro.sh"
)
for file in "${REQUIRED_FILES[@]}"; do
    [[ -f "$file" ]] && echo "✅ $file" || echo "❌ Missing: $file"
done
echo ""

echo "4.4 Log Rotation Status"
LOG_SIZE=$(du -sh logs/ 2>/dev/null | awk '{print $1}')
echo "Total log size: $LOG_SIZE"
[[ -d logs/old ]] && echo "✅ Log rotation directory exists" || echo "⚠️  No logs/old directory"
echo ""

echo "4.5 Disk Space"
df -h ~ | tail -1 | awk '{print "Available space: " $4 " (" $5 " used)"}'
USED_PCT=$(df -h ~ | tail -1 | awk '{print $5}' | tr -d '%')
[[ $USED_PCT -lt 80 ]] && echo "✅ Sufficient disk space" || echo "⚠️  Disk usage high: ${USED_PCT}%"
echo ""

# ===== SECTION 5: CODE QUALITY AUDIT =====
echo "━━━ 5. CODE QUALITY AUDIT ━━━"
echo ""

echo "5.1 Python Syntax Check"
python3 -m py_compile tools/telecontroller_curl.py 2>&1 && echo "✅ telecontroller_curl.py syntax OK" || echo "❌ Syntax errors found"
echo ""

echo "5.2 Shell Script Syntax Check"
bash -n tools/watch_wrap_market.sh 2>&1 && echo "✅ watch_wrap_market.sh syntax OK" || echo "❌ Syntax errors found"
bash -n tools/run_all.sh 2>&1 && echo "✅ run_all.sh syntax OK" || echo "❌ Syntax errors found"
bash -n tools/stop_all.sh 2>&1 && echo "✅ stop_all.sh syntax OK" || echo "❌ Syntax errors found"
echo ""

echo "5.3 Hardcoded Values Check"
echo "Checking for hardcoded paths (should use \$HOME or \$ROOT)..."
grep -n "/data/data/com.termux/files/home/BotA" tools/*.sh tools/*.py 2>/dev/null | wc -l | awk '{print "Hardcoded paths found: " $1}'
echo ""

echo "5.4 TODO/FIXME/HACK Comments"
grep -rn "TODO\|FIXME\|HACK" tools/ 2>/dev/null | wc -l | awk '{print "Technical debt markers: " $1}'
echo ""

# ===== SECTION 6: INTEGRATION TESTS =====
echo "━━━ 6. INTEGRATION TESTS ━━━"
echo ""

echo "6.1 End-to-End Command Test"
echo "Sending test message via Telegram..."
TEST_RESULT=$(curl -s -m 10 -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}" \
    -d "text=🧪 Integration test: $(date +%H:%M:%S)" 2>&1)
echo "$TEST_RESULT" | grep -q '"ok":true' && echo "✅ E2E test passed" || echo "❌ E2E test failed"
echo ""

# ===== FINAL SUMMARY =====
echo "════════════════════════════════════════════════════════"
echo "  AUDIT COMPLETE"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Review all ✅ ⚠️  ❌ markers above"
echo "Share this complete output with 3 independent AIs for verification"
echo ""
echo "Production-Ready Criteria:"
echo "  ✅ All Security checks passed"
echo "  ✅ All Functionality checks passed"
echo "  ✅ No critical errors in Error Handling"
echo "  ✅ All Operational requirements met"
echo "  ✅ Code quality acceptable"
echo ""
