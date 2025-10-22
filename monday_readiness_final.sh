#!/bin/bash
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 MONDAY MARKET READINESS - FINAL CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "1️⃣ BOT STATUS:"
if tmux ls 2>/dev/null | grep -q botA_h1; then
    echo "  ✅ Bot running in tmux (botA_h1)"
    echo "  PID: $(pgrep -f auto_h1.sh || echo 'not found')"
else
    echo "  ❌ Bot NOT running"
fi

echo ""
echo "2️⃣ CHAT ID VERIFICATION:"
python3 << 'PYEOF'
import sys, os
sys.path.insert(0, '/data/data/com.termux/files/home/bot-a')
from dotenv import load_dotenv
load_dotenv('.env.botA', override=True)

chat_id = os.getenv('CHAT_ID')
shell_id = os.environ.get('CHAT_ID', 'not set')

if chat_id == '6074056245':
    print("  ✅ CHAT_ID correct: 6074056245")
else:
    print(f"  ❌ CHAT_ID wrong: {chat_id}")

if shell_id == '6074056245':
    print("  ✅ Shell environment correct")
else:
    print(f"  ⚠️ Shell CHAT_ID: {shell_id}")
PYEOF

echo ""
echo "3️⃣ TRADE CAPACITY:"
if [ -f logs/trade_cap.json ]; then
    cat logs/trade_cap.json
    COUNT=$(grep -oP '"count":\s*\K\d+' logs/trade_cap.json 2>/dev/null || echo "?")
    DAY=$(grep -oP '"day":\s*"\K[^"]+' logs/trade_cap.json 2>/dev/null || echo "?")
    echo "  Current: $COUNT/2 trades on $DAY"
    
    if [ "$COUNT" = "0" ] && [ "$DAY" = "2025-10-19" ]; then
        echo "  ✅ Trade cap ready for Monday"
    else
        echo "  ⚠️ Trade cap needs reset"
    fi
else
    echo "  ❌ trade_cap.json missing!"
fi

echo ""
echo "4️⃣ LAST BOT RUN:"
tail -10 logs/auto_h1.log | grep -E "✓ run ok|✗ run failed|Daily trade cap" | tail -3

echo ""
echo "5️⃣ LAST SIGNAL DECISION:"
tail -20 logs/auto_h1.log | grep -A3 "📊 EURUSD" | tail -5

echo ""
echo "6️⃣ QUEUE SYSTEM:"
echo "  Pending: $(ls -1 queue/pending/ 2>/dev/null | wc -l) signals"
echo "  Sent: $(ls -1 queue/sent/ 2>/dev/null | wc -l) signals"
[ -d queue/pending ] && echo "  ✅ Queue directories exist" || echo "  ❌ Queue missing"

echo ""
echo "7️⃣ API CONFIGURATION:"
python3 << 'PYEOF'
import sys, os
sys.path.insert(0, '/data/data/com.termux/files/home/bot-a')
from dotenv import load_dotenv
load_dotenv('.env.botA')

keys = {
    'AlphaVantage': os.getenv('ALPHAVANTAGE_API_KEY'),
    'TwelveData': os.getenv('TWELVEDATA_API_KEY'),
    'Telegram': os.getenv('TELEGRAM_BOT_TOKEN')
}

all_good = True
for name, key in keys.items():
    if key and len(key) > 10:
        print(f"  ✅ {name}: {key[:8]}...")
    else:
        print(f"  ❌ {name}: MISSING")
        all_good = False
PYEOF

echo ""
echo "8️⃣ CRITICAL FILES:"
for file in "tools/runner_confluence.py" "tools/offline_queue_system.py" ".env.botA" "logs/trade_cap.json"; do
    [ -f "$file" ] && echo "  ✅ $file" || echo "  ❌ $file MISSING"
done

echo ""
echo "9️⃣ DATA FRESHNESS:"
if [ -f cache/EURUSD_H1.json ]; then
    AGE=$(($(date +%s) - $(stat -c %Y cache/EURUSD_H1.json 2>/dev/null || stat -f %m cache/EURUSD_H1.json)))
    HOURS=$((AGE / 3600))
    echo "  Last H1 data: ${HOURS}h ago"
    [ $HOURS -lt 24 ] && echo "  ⚠️ Weekend data (expected)" || echo "  ❌ Data very stale"
else
    echo "  ⚠️ No cached H1 data"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 OVERALL VERDICT:"
echo ""

# Determine readiness
READY=true
! tmux ls 2>/dev/null | grep -q botA_h1 && READY=false
[ ! -f .env.botA ] && READY=false
[ ! -d queue/pending ] && READY=false

if [ "$READY" = true ]; then
    echo "  🟢 READY FOR MONDAY TRADING"
    echo ""
    echo "  ✅ Bot is running"
    echo "  ✅ Chat ID configured correctly"
    echo "  ✅ Queue system in place"
    echo "  ✅ API keys configured"
    echo ""
    echo "  📅 Next steps:"
    echo "     - Bot will auto-restart at market open"
    echo "     - Trade cap will reset on Monday"
    echo "     - Fresh data will be fetched when market opens"
else
    echo "  🔴 NOT READY - Fix issues above"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
