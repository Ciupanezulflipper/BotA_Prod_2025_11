#!/bin/bash
# Preflight check for Bot-A
echo "== Bot-A Preflight =="

# Check Python
python3 --version || exit 1

# Check pip packages
for pkg in requests pandas numpy; do
    python3 -c "import $pkg" 2>/dev/null || echo "Missing: $pkg"
done

# Check .env
if [ -f ../.env ]; then
    echo ".env found"
else
    echo "!! Missing .env file"
fi

# Check candles
ls -lh ../data/candles/EURUSD_*.csv 2>/dev/null || echo "!! Missing EURUSD CSV candles"

echo "== DONE =="
