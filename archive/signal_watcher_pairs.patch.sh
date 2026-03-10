#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

FILE="/data/data/com.termux/files/home/BotA/tools/signal_watcher_pro.sh"
BACKUP="${FILE}.backup_$(date +%Y%m%d_%H%M%S)"

cp "$FILE" "$BACKUP"

tmp="$(mktemp)"
awk '
  /case "\${p}" in/ {
    print "  case \"${p}\" in"
    print "    EURUSD|GBPUSD|XAUUSD|USDJPY|EURJPY) : ;;"
    print "    *)"
    print "      echo \"[ERROR " "'" "$(date -Iseconds)" "'" "] Pair not allowed by BotA policy: ${p}\" >&2"
    print "      return 1"
    print "      ;;"
    print "  esac"
    skip=1
    next
  }
  skip && /\besac\b/ { skip=0; next }
  !skip { print }
' "$FILE" > "$tmp"

mv "$tmp" "$FILE"
chmod +x "$FILE"

echo "✅ Updated pair policy in signal_watcher_pro.sh"
echo "   Backup saved as: $BACKUP"
