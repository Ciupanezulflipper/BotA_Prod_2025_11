#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_NAME="BotA_Prod_2025_11"
OWNER="Ciupanezulflipper"
REMOTE_SSH="git@github.com:${OWNER}/${REPO_NAME}.git"

# 0) Identity (safe to rerun)
git config --global user.name  "Ciupanezulflipper"
git config --global user.email "tomagm2010@gmail.com"

# 1) Ignore secrets/state
cat > .gitignore <<'GI'
.env
config/strategy.env
*.log
logs/
cache/
__pycache__/
*.pyc
.termux/
GI

# 2) Init + first commit
[ -d .git ] || git init
git add .gitignore .
git add -A
git commit -m "Initial backup: BotA production-ready (Termux)"

# 3) Point to your new PRIVATE repo via SSH
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE_SSH"

# 4) Push
git push -u origin main

# 5) Sanity checks
echo
echo "---- REMOTE ----"
git remote -v
echo
echo "---- HEAD ----"
git log --oneline -1
echo
echo "✅ Push complete. Open: https://github.com/${OWNER}/${REPO_NAME}"
