#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${BOTA_ROOT:-$HOME/BotA}"
WRAPPER="$ROOT/tools/run_with_env.sh"

# Canonical env file for NEWS settings (do NOT guess). Default: $HOME/.env
ENV_FILE="${ENV_FILE:-$HOME/.env}"

echo "=== STEP2_SANITY ==="
echo "ROOT=$ROOT"
echo "PWD=$(pwd)"
echo "ENV_FILE=$ENV_FILE"
echo

if [ ! -d "$ROOT" ]; then
  echo "FAIL: BotA root not found: $ROOT"
  exit 1
fi

if [ ! -x "$WRAPPER" ]; then
  echo "FAIL: Wrapper missing or not executable: $WRAPPER"
  echo "HINT: ls -la \"$ROOT/tools/run_with_env.sh\""
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "FAIL: ENV_FILE does not exist: $ENV_FILE"
  echo "HINT: export ENV_FILE=\"\$HOME/.env\"   (or the correct file) ثم rerun"
  exit 1
fi

echo "=== 1) HARD VALIDATE ENV_FILE FORMAT (must be clean) ==="
# Allowed lines:
#   - blank
#   - comments starting with #
#   - KEY=value (no spaces)
#   - KEY="value with spaces"
#   - KEY='value with spaces'
# Also block common paste-garbage tokens that must never be in .env
bad="$(
awk '
  function badline(n, s) { printf("%d:%s\n", n, s) }

  /^[[:space:]]*$/ { next }
  /^[[:space:]]*#/ { next }

  {
    line=$0

    # Block known paste artifacts / command text
    if (line ~ /```/ || line ~ /ACCEPTANCE CRITERIA/ || line ~ /\/tools\/news_sentiment\.py/ ||
        line ~ /(^|[[:space:]])cd([[:space:]]|$)/ || line ~ /(^|[[:space:]])python3([[:space:]]|$)/ ||
        line ~ /(^|[[:space:]])grep([[:space:]]|$)/ || line ~ // || line ~ //) {
      badline(NR, line); next
    }

    # Must look like KEY=...
    if (line !~ /^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=/) {
      badline(NR, line); next
    }

    # Strict forms
    if (line ~ /^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*="[^"]*"$/) next
    if (line ~ /^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*='\''[^'\'']*'\''$/) next
    if (line ~ /^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]+$/) next

    # Otherwise unsafe (spaces / extra tokens / broken quotes)
    badline(NR, line)
  }
' "$ENV_FILE" 2>/dev/null || true
)"

if [ -n "$bad" ]; then
  echo "FAIL: ENV_FILE contains unsafe lines (this CAN trigger 'Usage: grep ...' when sourced)."
  echo "-----"
  echo "$bad"
  echo "-----"
  echo "ACTION: Restore ENV_FILE from a known-good backup, then rerun this script."
  exit 1
fi

echo "PASS: ENV_FILE format is clean."
echo

echo "=== 2) SHOW NEWS_* KEYS INSIDE ENV_FILE (for human confirmation) ==="
grep -nE '^(NEWS_[A-Za-z0-9_]+)=' "$ENV_FILE" || echo "(none found)"
echo

echo "=== 3) WRAPPER SMOKE TEST (should NOT print grep usage) ==="
# run_with_env.sh must NOT source a dirty .env. We already validated ENV_FILE above.
export ENV_FILE
# Print only NEWS_ vars from the wrapper-executed env
bash "$WRAPPER" env | sed -n '/^NEWS_/p'
echo

echo "=== 4) COMPILE news_sentiment.py (no output = PASS) ==="
python3 -m py_compile "$ROOT/tools/news_sentiment.py"
echo "PASS: py_compile"
echo

echo "=== 5) RUN news_sentiment via wrapper (expect normal output, NOT grep usage) ==="
NEWS_ON=1 NEWS_LOOKBACK_MIN=10080 bash "$WRAPPER" python3 "$ROOT/tools/news_sentiment.py" EURUSD --debug | sed -n '1,200p'
echo
echo "=== STEP2_SANITY DONE (if you saw no grep usage lines, wrapper path + ENV_FILE are sane) ==="
