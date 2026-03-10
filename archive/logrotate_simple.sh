#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
LOG_DIR="$BASE/logs"
KEEP="${KEEP_ROTATIONS:-7}"
DRY_RUN=1

usage() {
  echo "Usage: $(basename "$0") [--dry-run|--apply] [--keep N]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --apply)   DRY_RUN=0; shift ;;
    --keep)    KEEP="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done
[[ "$KEEP" =~ ^[0-9]+$ ]] || { echo "Invalid KEEP=$KEEP"; exit 2; }

cmd() { if [[ $DRY_RUN -eq 1 ]]; then echo "+ $*"; else eval "$@"; fi; }

rotate_one() {
  local f="$1"
  [[ -f "$f" ]] || { echo "[skip] $f (missing)"; return 0; }

  local size
  size="$( (stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null || wc -c < "$f") 2>/dev/null )"
  [[ "${size:-0}" -gt 0 ]] || { echo "[skip] $f (empty)"; return 0; }

  local ts rotated base pattern
  ts="$(date -u +%Y-%m-%dT%H%M%SZ)"
  rotated="${f}.${ts}.log"
  base="$(basename "$f")"
  pattern="${LOG_DIR}/${base}."

  echo "[rotate] $f -> ${rotated} (keep ${KEEP})"
  cmd "mv \"$f\" \"$rotated\""
  cmd ": > \"$f\""

  if command -v gzip >/dev/null 2>&1; then
    cmd "gzip -f \"$rotated\""
  fi

  mapfile -t TO_PRUNE < <(ls -1t ${pattern}*.log ${pattern}*.log.gz 2>/dev/null | tail -n +$((KEEP+1)) || true)
  if (( ${#TO_PRUNE[@]} )); then
    echo "[prune] removing ${#TO_PRUNE[@]} old files"
    for p in "${TO_PRUNE[@]}"; do cmd "rm -f \"$p\""; done
  else
    echo "[prune] none"
  fi
}

mkdir -p "$LOG_DIR"
FILES=(
  "$LOG_DIR/loop.log"
  "$LOG_DIR/cron.single.log"
  "$LOG_DIR/cron.boot.log"
  "$LOG_DIR/watchdog.log"
  "$LOG_DIR/telecontroller.log"
)

mode=$([[ $DRY_RUN -eq 1 ]] && echo DRY_RUN || echo APPLY)
echo "[logrotate] mode=${mode} keep=${KEEP} dir=${LOG_DIR}"
for f in "${FILES[@]}"; do rotate_one "$f"; done
echo "[logrotate] done."
