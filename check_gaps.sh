#!/bin/bash

echo "🔍 BOT INTEGRITY CHECK"
echo "===================="
echo ""

cd ~/bot-a

# Critical files that MUST exist
critical_files=(
    "runner_confluence.py"
    "tools/offline_queue_system.py"
    "tools/tg_send.py"
    ".env.botA"
    "logs/trade_cap.json"
)

echo "1️⃣ CRITICAL FILES:"
for file in "${critical_files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ MISSING: $file"
    fi
done

echo ""
echo "2️⃣ QUEUE SYSTEM:"
ls -lh queue/pending/ queue/sent/ 2>/dev/null || echo "  ⚠️ Queue directories not found"

echo ""
echo "3️⃣ TMUX SESSION:"
tmux ls 2>/dev/null | grep botA || echo "  ⚠️ No botA tmux session"

echo ""
echo "4️⃣ RUNNER LOCATION:"
ls -lh runner_confluence.py 2>/dev/null || ls -lh */runner_confluence.py 2>/dev/null || echo "  ⚠️ Runner not found in expected location"

echo ""
echo "5️⃣ IMPORTS CHECK (potential circular dependencies):"
grep -r "^import\|^from" --include="*.py" ~/bot-a/tools/ ~/bot-a/*.py 2>/dev/null | head -20

echo ""
echo "6️⃣ CONFIGURATION:"
[ -f .env.botA ] && echo "  ✅ .env.botA exists" || echo "  ❌ .env.botA missing"
[ -f tools/start_botA.sh ] && echo "  ✅ start_botA.sh exists" || echo "  ❌ start_botA.sh missing"

