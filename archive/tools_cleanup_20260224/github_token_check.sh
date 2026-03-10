#!/usr/bin/env bash
# Read-only auth smoke for one repo (defaults to ~/BotA).
set -euo pipefail
repo="${1:-$HOME/BotA}"
if [ ! -d "$repo/.git" ]; then
  echo "Repo not found: $repo" >&2; exit 1
fi
cd "$repo"
remote="$(git remote get-url origin)"
echo "[check] repo=$repo"
echo "[check] origin=$remote"
if git ls-remote --heads origin >/dev/null 2>&1; then
  echo "✅ PASS — GitHub auth OK"
else
  echo "❌ FAIL — GitHub auth FAILED"; exit 2
fi
