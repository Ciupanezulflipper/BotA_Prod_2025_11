#!/data/data/com.termux/files/usr/bin/bash
set -eu

# Load token
. "$HOME/bot-a/config/tele.env"

API="https://api.telegram.org/bot${TG_BOT_TOKEN}"

# Define command menu
payload='{
  "commands": [
    {"command":"start","description":"Start the bot loop"},
    {"command":"stop","description":"Stop the bot loop"},
    {"command":"status","description":"Show bot status"},
    {"command":"analyze","description":"Run one analysis now"},
    {"command":"digest","description":"Send daily digest now"},
    {"command":"help","description":"Show commands"}
  ]
}'

curl -sS -X POST "$API/setMyCommands" \
  -H "Content-Type: application/json" \
  -d "$payload"
echo
