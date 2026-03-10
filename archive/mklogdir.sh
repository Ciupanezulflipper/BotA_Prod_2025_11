#!/bin/bash
# mklogdir.sh — ensure all log dirs exist
set -e
mkdir -p "$HOME/BotA/logs"
chmod 755 "$HOME/BotA/logs"
echo "✅ Log directory ready: $HOME/BotA/logs"
