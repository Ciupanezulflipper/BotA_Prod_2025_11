#!/data/data/com.termux/files/usr/bin/bash
# ---------------------------------------------------------
#  Clean Signal Viewer for BotA
#  Shows only BUY/SELL (score>0) with aligned formatting.
#  Safe: does NOT modify any other files.
# ---------------------------------------------------------

HISTORY_FILE="logs/signal_history.csv"

if [ ! -f "$HISTORY_FILE" ]; then
    echo "❌ No signal history found at $HISTORY_FILE"
    exit 1
fi

echo "📈 Last 20 BUY/SELL Signals"
echo "----------------------------------------------"
echo "TIME (UTC)               PAIR     DIR   SCORE   PRICE      PROVIDER"
echo "----------------------------------------------"

# Skip header, show only score>0
tail -n 200 "$HISTORY_FILE" \
    | awk -F',' 'NR>1 && $4 > 0 {
        printf "%-23s %-7s %-5s %-6s %-9s %-12s\n",
               $1, $2, $3, $4, $8, $6
    }' \
    | tail -n 20

echo "----------------------------------------------"
echo "Done."
