#!/bin/bash
# Smart frequency selector based on trading session

get_recommended_tf() {
    local hour=$(date -u +%H)
    
    # Convert to integer
    hour=$((10#$hour))
    
    # London session (7-16 UTC) - Use M15
    if [ $hour -ge 7 ] && [ $hour -lt 16 ]; then
        echo "M15"
        return 0
    fi
    
    # NY-London overlap (12-16 UTC) - Use M5
    if [ $hour -ge 12 ] && [ $hour -lt 16 ]; then
        echo "M5"
        return 0
    fi
    
    # NY session (12-21 UTC) - Use M15
    if [ $hour -ge 12 ] && [ $hour -lt 21 ]; then
        echo "M15"
        return 0
    fi
    
    # Off-hours - Use H1
    echo "H1"
}

# Get recommendation
TF=$(get_recommended_tf)
HOUR=$(date -u +%H:%M)

echo "🕒 UTC Time: $HOUR"
echo "📊 Recommended: $TF"

# Check current bot setting
CURRENT_TF=$(grep "^TIMEFRAME=" "$HOME/bot-a/.env.botA" | cut -d'=' -f2)

if [ "$CURRENT_TF" != "$TF" ]; then
    echo "⚡ Switching from $CURRENT_TF to $TF"
    echo "TIMEFRAME=$TF"
else
    echo "✅ Already on $TF"
fi
