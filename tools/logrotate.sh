#!/data/data/com.termux/files/usr/bin/bash
find "$HOME/bot-a/logs" -type f -name "*.log" -size +2M -mtime +7 -delete 2>/dev/null || true
