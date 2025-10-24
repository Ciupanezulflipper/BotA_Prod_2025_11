#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"

"$TOOLS/test_emit_snapshot.sh"
"$TOOLS/test_pipeline.sh"

echo "[OK] All smoke tests passed."
