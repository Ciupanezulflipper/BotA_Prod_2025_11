#!/data/data/com.termux/files/usr/bin/bash
# Auto Confluence Signal Loop

set -euo pipefail

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BOT_DIR"

LOG_FILE="logs/auto_conf.log"
PID_FILE="logs/auto_conf.pid"
HEARTBEAT_FILE="logs/last_heartbeat.txt"

# Store PID
echo $$ > "$PID_FILE"

# Rotate logs if >10MB
rotate_logs() {
    if [ -f "$LOG_FILE" ] && [ $(wc -c < "$LOG_FILE") -gt 10485760 ]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
        echo "[$(date -u '+%Y-%m-%d %H:%M:%S')] Rotated log" > "$LOG_FILE"
    fi
}

# Write heartbeat
heartbeat() {
    date -u '+%Y-%m-%d %H:%M:%S UTC' > "$HEARTBEAT_FILE"
}

# Handle error
handle_error() {
    local msg="$1"
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] ERROR: $msg" >> "$LOG_FILE"
    sleep 60
}

echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Starting loop (PID $$)" >> "$LOG_FILE"

while true; do
    rotate_logs
    heartbeat

    if python3 tools/runner_confluence.py >> "$LOG_FILE" 2>&1; then
        echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Analysis OK" >> "$LOG_FILE"
    else
        handle_error "runner_confluence.py crashed"
        continue
    fi

    # Sleep 30s between runs
    sleep 30
done
