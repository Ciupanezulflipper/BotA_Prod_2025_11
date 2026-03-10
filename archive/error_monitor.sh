#!/data/data/com.termux/files/usr/bin/bash
# BotA/tools/error_monitor.sh
# Central error & health logger for BotA.
#
# Usage examples:
#   bash tools/error_monitor.sh "simple message"
#   bash tools/error_monitor.sh ERROR WATCHER "yahoo failed, fallback to cache"
#   bash tools/error_monitor.sh WARN TELEGRAM "rate-limited, retry later"
#
# This script NEVER crashes BotA — if logging fails, it quietly ignores the error.

LOG_ROOT="${HOME}/BotA"
LOG_DIR="${LOG_ROOT}/logs"
LOG_FILE="${LOG_DIR}/error.log"

# Ensure log directory exists
mkdir -p "$LOG_DIR" 2>/dev/null || true

ts="$(date -Iseconds)"

# Argument handling:
# 0 args  → INFO  GENERIC "(no message)"
# 1 arg   → INFO  GENERIC "<msg>"
# 2 args  → <lvl> GENERIC "<msg>"
# ≥3 args → <lvl> <module> "<rest as message>"
if [[ $# -eq 0 ]]; then
  level="INFO"
  module="GENERIC"
  msg="(no message)"
elif [[ $# -eq 1 ]]; then
  level="INFO"
  module="GENERIC"
  msg="$1"
elif [[ $# -eq 2 ]]; then
  level="$1"
  module="GENERIC"
  msg="$2"
else
  level="$1"
  module="$2"
  shift 2
  msg="$*"
fi

# Normalize level to UPPERCASE for readability
level="$(echo "$level" | tr '[:lower:]' '[:upper:]')"

line="[$ts] [$level] [$module] $msg"

# Append to error.log; never let logging kill caller
{
  echo "$line" >> "$LOG_FILE"
} 2>/dev/null || true

# Also mirror to stdout for interactive debugging
echo "$line"
