#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO="${1:-$HOME/BotA}"

if [[ ! -d "$REPO/.git" ]]; then
  echo "❌ Not a git repo: $REPO" >&2
  exit 1
fi

cd "$REPO"

echo "=== Remote & Auth check ==="
git remote -v
git ls-remote --heads origin | sed -n '1,3p' || true

echo
echo "=== Branch & Status ==="
git rev-parse --abbrev-ref HEAD
git status -sb

echo
echo "=== Last 3 commits ==="
git --no-pager log -3 --oneline

echo
echo "=== Dry-run push ==="
git push --dry-run origin HEAD:$(git rev-parse --abbrev-ref HEAD) && echo "OK: dry-run push passed"
