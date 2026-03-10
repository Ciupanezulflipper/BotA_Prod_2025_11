#!/bin/bash
source ~/bot-a/config/tele.env

MSG="✅ Telegram test from Bot-A at $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
     -d chat_id="${TELEGRAM_CHAT_ID}" \
     -d text="$MSG"
