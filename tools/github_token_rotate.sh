#!/usr/bin/env bash
# Rotate GitHub Personal Access Token for one or more local repos.
# Usage:
#   export GITHUB_USER='your_user'
#   export GITHUB_EMAIL='you@example.com'
#   export NEW_PAT='ghp_xxx'
#   ./github_token_rotate.sh  ~/BotA  ~/forex_profit_lab
set -euo pipefail

red()  { printf "\033[31m%s\033[0m\n" "$*"; }
grn()  { printf "\033[32m%s\033[0m\n" "$*"; }
ylw()  { printf "\033[33m%s\033[0m\n" "$*"; }
err()  { red "ERROR: $*"; exit 1; }

: "${GITHUB_USER:?Set GITHUB_USER}"
: "${NEW_PAT:?Set NEW_PAT}"
: "${GITHUB_EMAIL:=no-reply@users.noreply.github.com}"

if [ $# -lt 1 ]; then
  err "Pass at least one local repo path. Example: $HOME/BotA"
fi

# 1) Global git settings
git config --global user.name  "$GITHUB_USER"  >/dev/null
git config --global user.email "$GITHUB_EMAIL" >/dev/null
git config --global credential.helper store     >/dev/null

cred="$HOME/.git-credentials"
ts="$(date +%Y%m%d_%H%M%S)"
if [ -f "$cred" ]; then
  cp -f "$cred" "$cred.$ts.bak"
  ylw "Backup saved: $cred.$ts.bak"
fi

# 2) Write a single GitHub credential prefix (clean first)
tmp="$(mktemp)"
# Keep non-github lines if any
grep -v '://.*@github\.com' "$cred" 2>/dev/null || true >"$tmp"
# Add the one canonical GitHub line (prefix match for any GitHub URL)
echo "https://${GITHUB_USER}:${NEW_PAT}@github.com" >> "$tmp"
mv -f "$tmp" "$cred"
chmod 600 "$cred"
grn "Updated $cred"

# 3) Normalize each repo remote to HTTPS and test
for repo in "$@"; do
  if [ ! -d "$repo/.git" ]; then
    ylw "Skip (not a git repo): $repo"
    continue
  fi
  (
    cd "$repo"
    url="$(git remote get-url origin 2>/dev/null || true)"
    if [ -z "$url" ]; then
      err "Repo has no 'origin': $repo"
    fi
    # Convert SSH to HTTPS if needed
    if echo "$url" | grep -q '^git@github.com:'; then
      https_url="https://github.com/${url#git@github.com:}"
      git remote set-url origin "$https_url"
      ylw "Remote converted to HTTPS: $https_url"
    fi
    # Quick auth probe
    if git ls-remote --heads origin >/dev/null 2>&1; then
      grn "[PASS] Auth ok: $repo"
    else
      err "[FAIL] Auth failed: $repo"
    fi
  )
done

grn "Token rotation complete."
