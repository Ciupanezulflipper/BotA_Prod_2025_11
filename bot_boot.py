#!/data/data/com.termux/files/usr/bin/python
import logging
import os
from telegram.ext import Updater, CommandHandler

# Load token from .env or direct env
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot_boot")

def start(update, context):
    update.message.reply_text("✅ Bot started!")

def version(update, context):
    update.message.reply_text("🤖 Bot-A version: A0.7")

def commands(update, context):
    update.message.reply_text(
        "📄 *Commands*:\n"
        "/start — Start bot\n"
        "/menu — Show menu\n"
        "/hide — Hide keyboard\n"
        "/status — Runtime status\n"
        "/ping — Respond with pong\n"
        "/version — Show version\n"
        "/commands — List commands\n"
        "/signal — Emit sample signal\n"
        "/price SYMBOL — Show live price\n"
        "/score SYMBOL — Score a symbol\n"
        "/scorev SYMBOL — Score v2\n"
        "/scorev2 SYMBOL — Score v2b\n"
        "/strategy — Show strategy summary\n"
        "/risk — Show risk rules\n"
        "/health — Diagnostics\n"
        "/help — Quick help\n",
        parse_mode="Markdown"
    )

def main():
    if not TOKEN:
        raise SystemExit("❌ TELEGRAM_BOT_TOKEN not set in .env")
    updater = Updater(token=TOKEN, use_context=True)
    dp = updater.dispatcher

    # Register handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("version", version))
    dp.add_handler(CommandHandler("commands", commands))

    log.info("🚀 Bot is running...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
