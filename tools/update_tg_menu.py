#!/usr/bin/env python3
"""
Update Telegram menu with trading-focused commands
"""

import os
import requests
import json
from pathlib import Path

# Load bot token
def get_token():
    env_file = Path.home() / "bot-a" / ".env.botA"
    for line in env_file.read_text().split('\n'):
        if line.startswith('TG_BOT_TOKEN='):
            return line.split('=')[1].strip()
    return None

token = get_token()

if not token:
    print("❌ Token not found")
    exit(1)

# New command list (trading focused)
commands = [
    {"command": "status", "description": "🟢 Check bot status (running/paused)"},
    {"command": "analyze", "description": "📊 Run analysis NOW (force signal)"},
    {"command": "balance", "description": "💰 Show account balance & risk"},
    {"command": "signals", "description": "📈 Last 10 signals (BUY/SELL/WAIT)"},
    {"command": "performance", "description": "📊 Win rate & P&L stats"},
    {"command": "digest", "description": "📝 Daily summary report"},
    {"command": "pause", "description": "⏸️ Pause trading (monitoring continues)"},
    {"command": "resume", "description": "▶️ Resume trading"},
    {"command": "help", "description": "❓ Show all commands"}
]

# Set commands
url = f"https://api.telegram.org/bot{token}/setMyCommands"
response = requests.post(url, json={"commands": commands})

if response.ok:
    print("✅ Telegram menu updated with trading commands!")
    print("\nNew menu:")
    for cmd in commands:
        print(f"  /{cmd['command']} - {cmd['description']}")
else:
    print(f"❌ Failed: {response.text}")
