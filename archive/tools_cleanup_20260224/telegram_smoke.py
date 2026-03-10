#!/usr/bin/env python3
"""
Telegram smoke test - validates token/chat_id and sends test message.
Usage: python -m BotA.tools.telegram_smoke
"""
import os
import sys


def main():
    # Load environment
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    chat_id_list = os.getenv("TELEGRAM_CHAT_ID_LIST", "").strip()
    verify_ssl = os.getenv("VERIFY_SSL", "true").lower()
    
    print("═══ BotA Telegram Smoke Test ═══")
    print(f"VERIFY_SSL: {verify_ssl}")
    
    # Diagnostic phase
    if not token:
        print("✗ TELEGRAM_BOT_TOKEN is not set")
        print("  Set it in .env or ~/.env.runtime")
        sys.exit(1)
    else:
        print(f"✓ TELEGRAM_BOT_TOKEN: {token[:8]}...{token[-4:]}")
    
    if not chat_id and not chat_id_list:
        print("✗ TELEGRAM_CHAT_ID (or TELEGRAM_CHAT_ID_LIST) is not set")
        print("  Set it in .env or ~/.env.runtime")
        sys.exit(1)
    else:
        target = chat_id_list if chat_id_list else chat_id
        print(f"✓ Target chat(s): {target}")
    
    # Attempt send
    print("\nSending test message...")
    from BotA.tools.telegramalert import send_telegram_message
    
    success, error = send_telegram_message("🤖 *BotA smoke test*\n\nIf you see this, Telegram integration is working!")
    
    if success:
        print("✓ Message sent successfully")
        sys.exit(0)
    else:
        print(f"✗ Send failed: {error}")
        
        # Provide actionable guidance
        if "401 Unauthorized" in error:
            print("\n  → Your TELEGRAM_BOT_TOKEN is invalid or expired")
            print("  → Get a new token from @BotFather on Telegram")
        elif "Bad request" in error or "chat not found" in error.lower():
            print("\n  → Your TELEGRAM_CHAT_ID is incorrect")
            print("  → Forward a message from your channel to @userinfobot to get the correct ID")
        elif "SSL" in error:
            print("\n  → Try: export VERIFY_SSL=false")
        elif "Connection" in error or "timeout" in error.lower():
            print("\n  → Check network connectivity")
            print("  → Try: curl -I https://api.telegram.org")
        
        sys.exit(1)


if __name__ == "__main__":
    main()
