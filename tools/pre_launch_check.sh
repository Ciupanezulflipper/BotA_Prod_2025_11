#!/bin/bash

echo "🚀 MONDAY PRE-LAUNCH CHECKLIST"
echo "=============================="
echo ""

# 1. Position sizing
echo "1️⃣ Position Sizing:"
pos_size=$(grep -o "0\.[0-9]*\s*lot" runner_confluence.py | head -1)
echo "   Current: $pos_size"
if echo "$pos_size" | grep -q "0.006"; then
    echo "   ✅ CORRECT (1.5% risk)"
else
    echo "   ❌ WRONG! Should be 0.006 lots"
fi
echo ""

# 2. Bot running
echo "2️⃣ Bot Status:"
if ps aux | grep -q "[a]uto_h1.sh"; then
    echo "   ✅ Running"
else
    echo "   ❌ NOT RUNNING!"
fi
echo ""

# 3. Trade cap reset
echo "3️⃣ Trade Cap:"
if [ -f ~/bot-a/logs/trade_cap.json ]; then
    cap_count=$(cat ~/bot-a/logs/trade_cap.json | grep -o '"count":[0-9]*' | cut -d: -f2)
    echo "   Trades today: $cap_count/3"
    if [ "$cap_count" = "0" ]; then
        echo "   ✅ Reset for new day"
    else
        echo "   ⚠️ Already used $cap_count trades"
    fi
else
    echo "   ❌ Cap file missing!"
fi
echo ""

# 4. Safety systems
echo "4️⃣ Safety Systems:"
safety_checks=0
grep -q "can_trade()" runner_confluence.py && echo "   ✅ Daily loss limit" && ((safety_checks++))
grep -q "check_trade_cap" runner_confluence.py && echo "   ✅ Trade cap (3/day)" && ((safety_checks++))
grep -q "check_news_blackout" runner_confluence.py && echo "   ✅ News blackout" && ((safety_checks++))
grep -q "0.25" runner_confluence.py && echo "   ✅ Volatility filter" && ((safety_checks++))

if [ $safety_checks -eq 4 ]; then
    echo "   ✅ All systems active"
else
    echo "   ⚠️ Missing $((4-safety_checks)) systems"
fi
echo ""

# 5. Last log check
echo "5️⃣ Recent Activity:"
tail -5 ~/bot-a/logs/auto_h1.log | grep -E "Action|Reason|UTC"
echo ""

# 6. API status
echo "6️⃣ API Check:"
echo "   Testing TwelveData..."
python3 runner_confluence.py --pair EURUSD --tf H1 --bars 50 2>&1 | head -5
echo ""

echo "=============================="
echo "✅ Pre-launch check complete!"
echo ""
echo "⚠️ BEFORE TRADING:"
echo "   1. Verify 0.006 lots in xTB platform"
echo "   2. Test demo order if possible"  
echo "   3. Check margin requirements"
echo "   4. Confirm SL = ~$3 risk in platform"
echo ""
