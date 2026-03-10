#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
UTC_NOW="$(date -u '+%F %T')"
echo "[$UTC_NOW UTC] digest job start" >> ~/bot-a/logs/digest.log
/data/data/com.termux/files/usr/bin/python3 ~/bot-a/tools/digest_v2.py >> ~/bot-a/logs/digest.log 2>&1 || true
UTC_NOW="$(date -u '+%F %T')"
echo "[$UTC_NOW UTC] digest job end" >> ~/bot-a/logs/digest.log
