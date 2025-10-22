#!/bin/bash
# Run this tomorrow morning to start weekend work

echo "🎯 SATURDAY BACKTEST WORKFLOW"
echo "=============================="
echo ""
echo "Step 1: Review plan"
cat ~/bot-a/tools/WEEKEND_TASKS.md | head -50
echo ""
echo "Step 2: Run framework"
python3 ~/bot-a/tools/backtest_v2.py
echo ""
echo "Step 3: Start coding!"
echo "Ready to build! 🚀"
