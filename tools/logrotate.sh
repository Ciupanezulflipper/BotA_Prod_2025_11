#!/data/data/com.termux/files/usr/bin/bash
# Phase 10: Log rotation & retention for BotA logs.
# Env (optional):
#   MAX_KB=2048           # rotate when size > MAX_KB
#   KEEP=5                # keep last N rotated files
#   FORCE=0               # set 1 to force rotation now
#   DRY=0                 # set 1 to print actions only
set -euo pipefail

ROOT="$HOME/BotA"
LOGS=("$ROOT/run.log" "$ROOT/alert.log")
MAX_KB="${MAX_KB:-2048}"
KEEP="${KEEP:-5}"
FORCE="${FORCE:-0}"
DRY="${DRY:-0}"

ts_now="$(date -u '+%Y%m%d_%H%M%S')"

rotate_one() {
  local f="$1"
  [ -f "$f" ] || return 0
  local kb
  kb="$(du -k "$f" | awk '{print $1}')"
  if [ "${FORCE}" = "1" ] || [ "${kb:-0}" -gt "${MAX_KB}" ]; then
    local rot="${f}.${ts_now}"
    if [ "$DRY" = "1" ]; then
      echo "[logrotate] would rotate $f (${kb}KB) -> ${rot}.gz"
    else
      mv "$f" "$rot"
      gzip -9 "$rot"
      echo "[logrotate] rotated $f (${kb}KB) -> ${rot}.gz"
      : > "$f"
    fi
    # prune old
    local count=0
    for old in $(ls -1t "${f}."*".gz" 2>/dev/null || true); do
      count=$((count+1))
      if [ "$count" -gt "$KEEP" ]; then
        if [ "$DRY" = "1" ]; then
          echo "[logrotate] would remove $old"
        else
          rm -f "$old"
        fi
      fi
    done
  else
    echo "[logrotate] skip $f (${kb}KB <= ${MAX_KB}KB)"
  fi
}

for f in "${LOGS[@]}"; do
  # ensure file exists
  [ -f "$f" ] || : > "$f"
  rotate_one "$f"
done
