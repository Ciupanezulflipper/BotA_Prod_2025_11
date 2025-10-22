[ -f "$HOME/bot-a/tools/env_caps.sh" ] && . "$HOME/bot-a/tools/env_caps.sh"
#!/data/data/com.termux/files/usr/bin/bash
BASE="$HOME/bot-a"
mkdir -p "$BASE/run" "$BASE/logs"

# Export .env to shell
set -a
[ -f "$BASE/.env" ] && . "$BASE/.env"
set +a

# Launch
nohup "$BASE/tools/auto_final.sh" >> "$BASE/logs/auto_final.log" 2>&1 &
echo $! > "$BASE/run/auto_final.pid"
echo "auto_final started. pid: $!"
