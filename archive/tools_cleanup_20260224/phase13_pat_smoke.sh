#!/usr/bin/env bash
# Phase 13 — PAT rotation smoke (dry push)
set -euo pipefail
repo="${1:-$HOME/BotA}"
branch="$(git -C "$repo" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
echo "=== Phase 13: PAT Smoke ==="
"$HOME/BotA/tools/github_token_check.sh" "$repo"
echo "[dry-run] git -C $repo push origin $branch --dry-run"
if git -C "$repo" push origin "$branch" --dry-run >/dev/null 2>&1; then
  echo "✅ DRY-RUN push OK"
else
  echo "❌ DRY-RUN push FAILED"; exit 2
fi
echo "=== Phase 13: PASSED ==="
