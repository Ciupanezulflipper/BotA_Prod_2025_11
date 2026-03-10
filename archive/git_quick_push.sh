#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO="${1:-$HOME/BotA}"
BRANCH="${2:-main}"
MSG="${3:-chore(bota): sync from phone}"

if [[ ! -d "$REPO/.git" ]]; then
  echo "❌ Not a git repo: $REPO" >&2
  exit 1
fi

cd "$REPO"

# Ensure identity (set once; harmless if already set)
git config user.name  "Toma (BotA on Termux)"
git config user.email "toma+bota@users.noreply.github.com"

# Show what will be committed
git status --short

# Stage & commit if there are changes
if ! git diff --quiet || ! git diff --cached --quiet; then
  git add -A
  git commit -m "$MSG" || true
else
  echo "ℹ️ No changes to commit."
fi

# Push to origin/BRANCH
git push origin "HEAD:$BRANCH"

echo "✅ Push complete -> origin/$BRANCH"
