#!/bin/bash
# Enable M15 during London/NY sessions

HOUR=$(date -u +%H)
HOUR=$((10#$HOUR))

# London (7-16 UTC) or NY (12-21 UTC)
if [ $HOUR -ge 7 ] && [ $HOUR -lt 21 ]; then
    echo "🔥 High activity session - Enabling M15"
    sed -i 's/TIMEFRAME=H1/TIMEFRAME=M15/' ~/bot-a/.env.botA
    echo "✅ Switched to M15"
else
    echo "💤 Low activity - Using H1"
    sed -i 's/TIMEFRAME=M15/TIMEFRAME=H1/' ~/bot-a/.env.botA
    echo "✅ Staying on H1"
fi
