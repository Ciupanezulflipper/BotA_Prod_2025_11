#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
git config core.hooksPath .githooks
echo "✅ Git hooks installed (secret guard + main force-push block)."
# Quick self-test (no-op commit + dry-run pre-push):
git commit --allow-empty -m "hooks: install check" >/dev/null
echo "ℹ️  If you ever clone on a new phone: bash tools/install_hooks.sh"
