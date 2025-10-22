#!/data/data/com.termux/files/usr/bin/bash
# Relaunch bot if tmux session missing
if ! tmux has-session -t botA 2>/dev/null; then
  "$HOME/bot-a/run_bot.sh"
fi
