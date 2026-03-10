#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="$(bash "$DIR/telegram_diag.sh")"
echo "$OUT"
echo "$OUT" | grep -q 'getMe -> HTTP:200' || { echo "❌ NO-GO: getMe not 200"; exit 1; }
echo "$OUT" | grep -q 'getUpdates -> HTTP:200' || { echo "❌ NO-GO: getUpdates not 200"; exit 1; }
echo "✅ GO"
