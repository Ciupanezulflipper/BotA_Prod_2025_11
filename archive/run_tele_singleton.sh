#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$REPO_DIR"

# Load and validate environment
. tools/env_loader.sh

# Health-check before launching
if ! bash tools/go_nogo.sh >/dev/null 2>&1; then
  echo "[launcher] ⚠️ Initial health check failed — starting anyway (will rely on poller)" >> logs/telecontroller.log
fi

# Determine entrypoint
ENTRY=""
for f in telecontroller_curl.py telecontroller.py cloudbot.py telegrambot.py main.py; do
  [ -f "$f" ] && ENTRY="$f" && break
done
[ -n "$ENTRY" ] || { echo "❌ No entrypoint (telecontroller_curl.py/…) found"; exit 1; }

mkdir -p state logs

MASK="$(printf '%s' "$TELEGRAM_TOKEN" | sed -E 's/^([0-9]{3})[0-9]+:([A-Za-z0-9_-]{2}).+$/\1...:\2***/')"
echo "[launcher] entry=$ENTRY token_len=${#TELEGRAM_TOKEN} token_mask=$MASK chat_id=${TELEGRAM_CHAT_ID:-unset}" >> logs/telecontroller.log

exec flock -n state/poller.lock bash -lc '
  MAX_FAILURES=5
  FAIL=0
  BACKOFF=3
  MIN_RUNTIME_OK=120

  while true; do
    START_TS=$(date +%s)
    echo "[launcher] starting attempt=$((FAIL+1)) $(date -Iseconds)" >> logs/telecontroller.log

    python3 "'"$ENTRY"'" >>logs/telecontroller.log 2>&1
    rc=$?
    RUNTIME=$(( $(date +%s) - START_TS ))

    if [ $rc -eq 0 ]; then
      echo "[launcher] clean exit after ${RUNTIME}s (rc=0) — stopping supervisor $(date -Iseconds)" >> logs/telecontroller.log
      break
    fi

    if [ $RUNTIME -gt $MIN_RUNTIME_OK ]; then
      echo "[launcher] ran ${RUNTIME}s — assuming stable, resetting failure/backoff $(date -Iseconds)" >> logs/telecontroller.log
      FAIL=0
      BACKOFF=3
    else
      FAIL=$((FAIL+1))
    fi

    if [ $FAIL -ge $MAX_FAILURES ]; then
      echo "[launcher] ❌ FATAL: $FAIL consecutive fast failures — giving up $(date -Iseconds)" >> logs/telecontroller.log
      echo "[launcher] Check logs/telecontroller.log for errors" >> logs/telecontroller.log
      exit 1
    fi

    echo "[launcher] crash rc=$rc runtime=${RUNTIME}s failure=$FAIL/$MAX_FAILURES — restarting in ${BACKOFF}s $(date -Iseconds)" >> logs/telecontroller.log
    sleep $BACKOFF
    BACKOFF=$(( BACKOFF * 2 ))
    [ $BACKOFF -gt 60 ] && BACKOFF=60
  done

  echo "[launcher] supervisor loop exited $(date -Iseconds)" >> logs/telecontroller.log
'
