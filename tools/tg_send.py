#!/usr/bin/env python3
"""
Telegram sender with delivery verification and retry logic
Logs all send attempts and results for audit trail
"""

import os
import sys
import requests
import json
from datetime import datetime
from pathlib import Path

# Add tools to path for imports
TOOLS_DIR = Path(__file__).parent
sys.path.insert(0, str(TOOLS_DIR))

from fetch_with_retry import retry_with_backoff


def get_env_var(key, default=None):
    """Get environment variable from .env.botA or environment"""
    value = os.getenv(key)
    if value:
        return value
    
    env_file = Path.home() / "bot-a" / ".env.botA"
    if not env_file.exists():
        env_file = Path.home() / "BotA" / ".env.botA"
    
    if env_file.exists():
        for line in env_file.read_text().split('\n'):
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    
    return default


def get_log_file():
    """Get telegram send log file path"""
    log_dir = Path.home() / "bot-a" / "logs"
    if not log_dir.exists():
        log_dir = Path.home() / "BotA" / "logs"
    
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "telegram_sends.log"


def log_send(status, message, details=""):
    """Log telegram send attempt to file"""
    log_file = get_log_file()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {status} | {message[:50]}... | {details}\n"
    
    try:
        with open(log_file, "a") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Warning: Could not write to log: {e}")


@retry_with_backoff(
    max_retries=3,
    initial_delay=2.0,
    exceptions=(requests.exceptions.RequestException,),
    check_empty_df=False
)
def send_telegram_message(token, chat_id, message, parse_mode="HTML"):
    """
    Send message to Telegram with retry logic
    
    Args:
        token: Telegram bot token
        chat_id: Chat ID to send to
        message: Message text
        parse_mode: Parse mode (HTML or Markdown)
    
    Returns:
        Response object or None on failure
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode
    }
    
    response = requests.post(url, json=payload, timeout=10)
    
    if response.status_code == 200:
        return response
    else:
        raise requests.exceptions.RequestException(
            f"HTTP {response.status_code}: {response.text[:100]}"
        )


def main():
    """Main function to send telegram message"""
    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:])
    else:
        message = sys.stdin.read().strip()
    
    if not message:
        print("Usage: python3 tg_send.py 'message' or echo 'message' | python3 tg_send.py")
        sys.exit(1)
    
    token = get_env_var("TG_BOT_TOKEN")
    chat_id = get_env_var("TG_CHAT_ID")
    
    if not token or not chat_id:
        error_msg = "Missing TG_BOT_TOKEN or TG_CHAT_ID in environment or .env.botA"
        print(f"ERROR: {error_msg}")
        log_send("FAILED", message, error_msg)
        sys.exit(1)
    
    if not token.count(':') == 1 or len(token.split(':')[0]) < 8:
        error_msg = "Invalid TG_BOT_TOKEN format"
        print(f"ERROR: {error_msg}")
        log_send("FAILED", message, error_msg)
        sys.exit(1)
    
    try:
        print(f"Sending to Telegram (chat_id: {chat_id})...")
        response = send_telegram_message(token, chat_id, message)
        
        if response and response.status_code == 200:
            result = response.json()
            msg_id = result.get('result', {}).get('message_id', 'unknown')
            
            success_msg = f"msg_id={msg_id}"
            print(f"SUCCESS: Message sent (msg_id: {msg_id})")
            log_send("SUCCESS", message, success_msg)
            
            return 0
        else:
            error_msg = f"Unexpected response: {response.status_code if response else 'None'}"
            print(f"FAILED: {error_msg}")
            log_send("FAILED", message, error_msg)
            return 1
            
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)[:100]}"
        print(f"FAILED: {error_msg}")
        log_send("FAILED", message, error_msg)
        return 1


if __name__ == "__main__":
    sys.exit(main())
