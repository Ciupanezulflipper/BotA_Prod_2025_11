#!/bin/bash
# Quick bot health check

echo "🏥 BOT HEALTH CHECK"
echo "===================="
echo ""

# 1. Process
echo "📍 Process:"
if ps aux | grep -q "[a]uto_h1.sh"; then
    echo "   ✅ Running"
else
    echo "   ❌ NOT RUNNING!"
fi
echo ""

# 2. Last activity
echo "⏰ Last Activity:"
tail -3 ~/bot-a/logs/auto_h1.log | grep "UTC\|Action\|Reason"
echo ""

# 3. Performance
echo "📊 Performance:"
python3 ~/bot-a/tools/pnl_tracker.py
echo ""

# 4. Queue
echo "📬 Queue:"
queued=$(ls ~/bot-a/queue/*.json 2>/dev/null | wc -l)
sent=$(ls ~/bot-a/queue/sent/*.json 2>/dev/null | wc -l)
echo "   Queued: $queued"
echo "   Sent: $sent"
echo ""

# 5. Disk
echo "💾 Disk:"
df -h ~ | tail -1 | awk '{print "   Available: "$4}'
echo ""

echo "✅ Health check complete!"
