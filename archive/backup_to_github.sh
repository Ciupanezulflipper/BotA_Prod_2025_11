#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$HOME/BotA"

# Don’t include secrets; .gitignore already handles runtime files
git add -A
if ! git diff --cached --quiet; then
  msg="chore(backup): nightly snapshot $(date -u +'%F %T UTC')"
  git commit -m "$msg" || true
  git push || exit 1
  echo "[backup] pushed: $msg"
else
  echo "[backup] nothing to commit"
fi
