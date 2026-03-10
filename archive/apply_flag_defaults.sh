#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
SAMPLE="config/strategy.env.sample"; REAL="config/strategy.env"
[ -f "$REAL" ] || { echo "❌ $REAL not found"; exit 1; }
while IFS= read -r line; do
  [[ -z "$line" || "$line" =~ ^# ]] && continue
  key="${line%%=*}"
  grep -q "^${key}=" "$REAL" || { echo "$line" >> "$REAL"; echo "➕ added $key"; }
done < <(grep -E '^[A-Z0-9_]+=' "$SAMPLE")
chmod 600 "$REAL"
echo "✅ Flags synced to $REAL"
