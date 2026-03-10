#!/bin/bash

echo "🚀 FINAL SYSTEM CHECK"
echo "===================="
echo ""

# Position sizing
echo "1️⃣ Position Sizing:"
if grep -q "0.006 lot" ~/bot-a/tools/runner_confluence.py; then
    echo "   ✅ 0.006 lots (1.5% risk = $3)"
elif grep -q "0.01 lot" ~/bot-a/tools/runner_confluence.py; then
    echo "   ⚠️ 0.01 lots (2.5% risk = $5)"
else
    echo "   ❌ UNKNOWN lot size!"
fi

# Bot running
echo ""
echo "2️⃣ Bot Status:"
if ps aux | grep -q "[a]uto_h1.sh"; then
    echo "   ✅ Running (PID: $(ps aux | grep "[a]uto_h1.sh" | awk '{print $2}' | head -1))"
else
    echo "   ❌ NOT RUNNING"
fi

# Trade cap (using Python)
echo ""
echo "3️⃣ Trade Cap:"
python3 << 'PYEOF'
import json
try:
    with open('/data/data/com.termux/files/home/bot-a/logs/trade_cap.json') as f:
        data = json.load(f)
    print(f"   Day: {data['day']}")
    print(f"   Used: {data['count']}/3 trades")
    if data['count'] == 0:
        print("   ✅ Fresh start ready")
except Exception as e:
    print(f"   ❌ Error: {e}")
PYEOF

# Safety systems
echo ""
echo "4️⃣ Safety Systems:"
checks=0
grep -q "can_trade()" ~/bot-a/tools/runner_confluence.py && echo "   ✅ Daily loss limit" && ((checks++))
grep -q "check_trade_cap" ~/bot-a/tools/runner_confluence.py && echo "   ✅ Trade cap" && ((checks++))
grep -q "check_news_blackout" ~/bot-a/tools/runner_confluence.py && echo "   ✅ News blackout" && ((checks++))
grep -q "0.25" ~/bot-a/tools/runner_confluence.py && echo "   ✅ Vol filter" && ((checks++))

# Last activity
echo ""
echo "5️⃣ Last Activity:"
tail -3 ~/bot-a/logs/auto_h1.log | grep "Action\|Reason\|UTC" | tail -2

# API test
echo ""
echo "6️⃣ API Test:"
result=$(python3 ~/bot-a/tools/runner_confluence.py --pair EURUSD --tf H1 --bars 50 2>&1 | head -5 | tail -3)
echo "$result" | head -3

echo ""
echo "===================="
if [ $checks -eq 4 ]; then
    echo "✅ ALL SYSTEMS READY!"
else
    echo "⚠️ Some systems missing"
fi
echo ""
