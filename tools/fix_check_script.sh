#!/bin/bash

# Replace the trade cap check section with better parsing
sed -i '
/# 3. Trade cap/,/echo ""/{
  s|cap_count=$(cat ~/bot-a/logs/trade_cap.json | grep -o '"count":[0-9]*' | cut -d: -f2)|cap_count=$(python3 -c "import json; print(json.load(open(\"$HOME/bot-a/logs/trade_cap.json\"))[\"count\"])" 2>/dev/null || echo "0")|
}
' pre_launch_check.sh

echo "✅ Fixed trade cap parsing"
