#!/bin/bash
# Run this at 22:30 when internet returns

echo "🔄 Checking for queued signals..."
python3 ~/bot-a/tools/offline_queue_system.py send

echo ""
echo "📊 Checking bot status..."
ps aux | grep auto_h1 | grep -v grep

echo ""
echo "✅ Reconnection complete!"
