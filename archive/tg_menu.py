#!/usr/bin/env python3
# tools/tg_menu.py  — PTB 13.x polling menu for Bot A
import os, time, datetime as dt, traceback
from telegram import Update, BotCommand
from telegram.ext import Updater, CommandHandler, CallbackContext

# 1) Load same env as the rest of Bot A
try:
    from tools.env_loader import _loaded  # auto-loads .env.runtime & aliases
except Exception:
    pass

# 2) Resolve token/chat id using the SAME aliases used elsewhere
TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("BOT_TOKEN")
    or os.getenv("TG_BOT_TOKEN")
)
CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID") or "").strip()

if not TOKEN:
    raise SystemExit("tg_menu.py: TELEGRAM_BOT_TOKEN (or alias) is missing.")
if not CHAT_ID:
    # Not fatal: we can still reply to whoever sends commands
    CHAT_ID = None

START_TS = time.time()
LOGF = os.path.expanduser("~/bot-a/logs/tg_menu.log")
os.makedirs(os.path.dirname(LOGF), exist_ok=True)

def log(msg: str):
    with open(LOGF, "a") as f:
        f.write(f"[{dt.datetime.utcnow():%Y-%m-%d %H:%M:%S}Z] {msg}\n")

# ---- command handlers ----
def cmd_start(update: Update, ctx: CallbackContext):
    update.message.reply_text("✅ Bot A menu online.\nCommands: /status /uptime /run_eurusd /digest /help")

def cmd_help(update: Update, ctx: CallbackContext):
    update.message.reply_text(
        "Commands:\n"
        "/status – last hourly result from log\n"
        "/uptime – bot menu uptime\n"
        "/run_eurusd – run H1 EURUSD now and show result (does not change the loop)\n"
        "/digest – send today’s daily summary now\n"
    )

def cmd_uptime(update: Update, ctx: CallbackContext):
    secs = int(time.time() - START_TS)
    h, r = divmod(secs, 3600); m, s = divmod(r, 60)
    update.message.reply_text(f"⏱ Uptime: {h}h {m}m {s}s")

def cmd_status(update: Update, ctx: CallbackContext):
    path = os.path.expanduser("~/bot-a/logs/auto_h1.log")
    try:
        out = os.popen(f"tail -n 30 {path}").read().strip()
        if not out:
            raise RuntimeError("empty")
        update.message.reply_text(f"📄 Last entries:\n{out[-3500:]}")
    except Exception as e:
        update.message.reply_text(f"⚠️ Cannot read log: {e}")

def cmd_run_now(update: Update, ctx: CallbackContext):
    # Immediate, side-effect-free run (dry run)
    cmd = 'PYTHONPATH="$HOME/bot-a" python3 -m tools.runner_confluence --pair EURUSD --tf H1 --bars 200 --dry-run'
    try:
        out = os.popen(cmd).read().strip()
        if not out:
            raise RuntimeError("no output")
        update.message.reply_text(out[-3500:])
    except Exception as e:
        update.message.reply_text(f"⚠️ run_eurusd failed: {e}")

def cmd_digest(update: Update, ctx: CallbackContext):
    cmd = 'PYTHONPATH="$HOME/bot-a" python3 "$HOME/bot-a/tools/daily_summary.py"'
    try:
        out = os.popen(cmd).read().strip()
        update.message.reply_text(out or "Digest invoked.")
    except Exception as e:
        update.message.reply_text(f"⚠️ digest failed: {e}")

def main():
    log("tg_menu starting…")
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start",  cmd_start))
    dp.add_handler(CommandHandler("help",   cmd_help))
    dp.add_handler(CommandHandler("uptime", cmd_uptime))
    dp.add_handler(CommandHandler("status", cmd_status))
    dp.add_handler(CommandHandler("run_eurusd", cmd_run_now))
    dp.add_handler(CommandHandler("digest", cmd_digest))

    # Nice-to-have command hints inside Telegram
    try:
        updater.bot.set_my_commands([
            BotCommand("start","Start menu"),
            BotCommand("status","Tail last entries"),
            BotCommand("uptime","Bot menu uptime"),
            BotCommand("run_eurusd","Immediate H1 dry run"),
            BotCommand("digest","Send daily summary"),
            BotCommand("help","List commands"),
        ])
    except Exception:
        log("set_my_commands failed:\n" + traceback.format_exc())

    updater.start_polling(drop_pending_updates=True)
    log("polling started")
    updater.idle()

if __name__ == "__main__":
    main()
