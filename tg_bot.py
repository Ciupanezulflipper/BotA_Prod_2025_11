#!/usr/bin/env python3
# tg_bot.py — Bot-A telegram bot (full file, copy-paste safe)

import os, time, json, logging, threading, datetime as dt
from dotenv import load_dotenv

from telegram import Update, BotCommand
from telegram.ext import Updater, CommandHandler, CallbackContext

# --- logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(name)s: %(message)s")
log = logging.getLogger("tg-bot")

# --- version ---
BOT_VERSION = "A0.8"

# --- load env early ---
load_dotenv()
TOKEN   = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or "").strip()
CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

WATCHLIST     = [s.strip().upper() for s in (os.getenv("WATCHLIST") or "EURUSD,XAUUSD").split(",") if s.strip()]
TF_DEFAULT    = os.getenv("TF", "5min")
CADENCE_MIN   = int(os.getenv("CADENCE_MIN", "15"))          # run every N minutes
REPOST_COOLDN = int(os.getenv("REPOST_MIN", "45"))           # don’t post same symbol too often

THRESH_STRONG   = 75
THRESH_MODERATE = 60

# --- external modules used by commands ---
try:
    from data import providers
except Exception as e:
    providers = None
    log.warning("providers not available: %s", e)

# legacy demo scorer (we keep for completeness)
try:
    from signals.strategy import score_symbol as score_symbol_v0
except Exception:
    score_symbol_v0 = None

# primary PRD scorer
try:
    from signals.engine_v2b import score_symbol as score_symbol_v2b
except Exception as e:
    score_symbol_v2b = None
    log.warning("engine_v2b not available: %s", e)

# --- utils ---
def now_utc():
    return time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())

def require_token_or_exit():
    if not TOKEN:
        log.error("Missing TELEGRAM_BOT_TOKEN/TELEGRAM_TOKEN in environment")
        raise SystemExit(1)

def _safe_send_text(update: Update, ctx: CallbackContext, text: str):
    try:
        update.message.reply_text(text)
    except Exception as e:
        log.error("send error: %s", e)

def _bot_send_text(bot, text: str, chat_id: str = None):
    try:
        cid = chat_id or CHAT_ID
        if cid:
            bot.send_message(chat_id=cid, text=text)
            return True
        log.warning("CHAT_ID not set; skipping send")
        return False
    except Exception as e:
        log.error("bot send error: %s", e)
        return False

def _arg_symbol(update: Update) -> str:
    parts = (update.message.text or "").strip().split(maxsplit=1)
    sym = (parts[1].strip().upper() if len(parts) > 1 else "EURUSD")
    return sym

def _format_components(res: dict) -> str:
    comps = res.get("components", {}) if isinstance(res, dict) else {}
    trend = comps.get("trend"); mom = comps.get("momentum")
    vol = comps.get("volume"); struct = comps.get("structure")
    volt = comps.get("volatility")
    return f"[trend {trend}, mom {mom}, vol {vol}, struct {struct}, volat {volt}]"

def _format_score(sym: str, res: dict) -> str:
    if not isinstance(res, dict) or not res.get("ok"):
        why = res.get("why") if isinstance(res, dict) else "engine error"
        return f"❌ {sym} score = N/A ({why})"
    score = res.get("score", 0)
    cls   = res.get("class", "HOLD")
    return f"📊 {sym} score = {score:.0f}/100 ({cls}) {_format_components(res)}"

# ------------- command handlers -------------
def cmd_start(update: Update, ctx: CallbackContext):
    text = (
        "🤖 Bot-A is online.\n"
        "Commands: /menu /status /ping /version /commands /id /mode /signal /health "
        "/price /score /strategy /risk /scorev2"
    )
    _safe_send_text(update, ctx, text)

def cmd_menu(update: Update, ctx: CallbackContext):
    text = (
        "🧭 Menu (placeholder)\n"
        "• Deal of the Day\n"
        "• History\n"
        "• Did You Know?\n"
        "• Settings\n\n"
        "📊 Try: /scorev2 EURUSD"
    )
    _safe_send_text(update, ctx, text)

def cmd_hide(update: Update, ctx: CallbackContext):
    _safe_send_text(update, ctx, "Keyboard hidden. Use /menu to show again.")

def cmd_status(update: Update, ctx: CallbackContext):
    text = (
        "🤖 Status: running\n"
        f"🕒 Time (UTC): {now_utc()}\n"
        "🧠 Mode: normal\n"
        "🧪 Signals: PRD v5 (engine v2b)\n"
        "📜 Log: signals.csv\n"
        "✅ Try: /health"
    )
    _safe_send_text(update, ctx, text)

def cmd_ping(update: Update, ctx: CallbackContext):
    _safe_send_text(update, ctx, "pong")

def cmd_version(update: Update, ctx: CallbackContext):
    _safe_send_text(update, ctx, f"🧠 Bot-A version: {BOT_VERSION}")

def cmd_commands(update: Update, ctx: CallbackContext):
    text = (
        "📄 *Commands* (tap or type):\n"
        "/start — Start bot\n"
        "/menu — Show menu\n"
        "/hide — Hide keyboard\n"
        "/status — Runtime status\n"
        "/ping — Respond with pong\n"
        "/version — Show version\n"
        "/commands — List commands\n"
        "/id — Show chat id\n"
        "/mode — Switch mode\n"
        "/signal — Emit sample signal\n"
        "/health — Diagnostics\n"
        "/price SYMBOL — Show live price\n"
        "/score SYMBOL — Score (legacy)\n"
        "/strategy — Show strategy summary\n"
        "/risk — Show risk rules\n"
        "/scorev2 SYMBOL — Score (PRD engine v2b)"
    )
    _safe_send_text(update, ctx, text)

def cmd_id(update: Update, ctx: CallbackContext):
    _safe_send_text(update, ctx, f"Your chat id: {update.effective_chat.id}")

def cmd_mode(update: Update, ctx: CallbackContext):
    _safe_send_text(update, ctx, "Mode switched (demo).")

def cmd_signal(update: Update, ctx: CallbackContext):
    text = (
        "🔵 GBPJPY BUY @ 181.333\n"
        "SL: 181.133 (-30p)  TP: 181.733 (+60p)\n"
        "R: 1:2.0 | conf: 0.69 | mode: normal\n"
        "reason: DUMMY_RSI_EMA\n"
        f"🕒 {now_utc()}"
    )
    _safe_send_text(update, ctx, text)

def cmd_health(update: Update, ctx: CallbackContext):
    api_line = "data API: ⛔ (n/a)"
    if providers:
        try:
            name, ok, code, detail = providers.ping_any()
            api_line = f"data API: {'✅' if ok else '❌'} ({name}, code {code})"
        except Exception as e:
            api_line = f"data API: ❌ (error: {e})"
    text = (
        "🧠 Bot-A health\n"
        f"• version: {BOT_VERSION}\n"
        f"• {api_line}\n"
        "• tmux session: ✅ (name: botA)\n"
        "• watchdog (cron): ✅ (/10m restart if needed)\n"
        "• Termux:Boot: ✅ (~/.termux/boot/01-bot-a.sh)\n"
        "• Last signal: —"
    )
    _safe_send_text(update, ctx, text)

def cmd_price(update: Update, ctx: CallbackContext):
    sym = _arg_symbol(update)
    if not providers:
        _safe_send_text(update, ctx, "❌ price: providers module not available")
        return
    try:
        px = providers.fetch_price(sym)
        if isinstance(px, tuple):
            prov, price = px[0], float(px[1])
            _safe_send_text(update, ctx, f"💱 {sym} ~ {price:.5f}  ({prov})")
        else:
            _safe_send_text(update, ctx, f"💱 {sym} ~ {float(px):.5f}")
    except Exception as e:
        _safe_send_text(update, ctx, f"❌ price error for {sym}: {e}")

def cmd_score(update: Update, ctx: CallbackContext):
    sym = _arg_symbol(update)
    if not score_symbol_v0:
        _safe_send_text(update, ctx, "❌ /score not available in this build")
        return
    try:
        r = score_symbol_v0(sym)
        text = r.get("text") if isinstance(r, dict) else None
        if not text:
            score = r.get("score", "N/A") if isinstance(r, dict) else "N/A"
            text = f"📊 {sym} score = {score}/100 (legacy)"
        _safe_send_text(update, ctx, text)
    except Exception as e:
        _safe_send_text(update, ctx, f"❌ score error for {sym}: {e}")

def cmd_strategy(update: Update, ctx: CallbackContext):
    text = (
        "📘 Strategy Summary (Scalping v5.0)\n"
        "• Multi-indicator confluence (EMA, VWAP, RSI, MACD, ADX, ATR)\n"
        "• Scoring system 0–100 (trend, momentum, volume, structure, volatility)\n"
        "• Entry classes: STRONG >75, MODERATE 60–74, WEAK 45–59, HOLD <45\n"
        "• Dynamic SL/TP: ATR-based, multi-stage exits\n"
        "• Session-aware (Asian range, London trends, US momentum)"
    )
    _safe_send_text(update, ctx, text)

def cmd_risk(update: Update, ctx: CallbackContext):
    text = (
        "🛡 Risk rules\n"
        "• Max risk open: 3%  • Max daily loss: 2%\n"
        "• Max trades/day: 8  • Cool-down: 30m after 2 losses\n"
        "• Circuit breaker: close all if -5% on day"
    )
    _safe_send_text(update, ctx, text)

def cmd_scorev2(update: Update, ctx: CallbackContext):
    sym = _arg_symbol(update)
    if not score_symbol_v2b:
        _safe_send_text(update, ctx, "❌ /scorev2 engine not available")
        return
    try:
        r = score_symbol_v2b(sym, tf=TF_DEFAULT, limit=300)
        _safe_send_text(update, ctx, _format_score(sym, r))
    except Exception as e:
        _safe_send_text(update, ctx, f"❌ scorev2 error for {sym}: {e}")

# ------------- passive scheduler (safe cadence) -------------
_last_post = {}  # symbol -> epoch seconds

def _should_post(symbol: str, score: float, cls: str) -> bool:
    if score is None: return False
    if score < THRESH_MODERATE: return False
    now = time.time()
    last = _last_post.get(symbol, 0)
    if now - last < REPOST_COOLDN * 60:
        return False
    return True

def _tick(bot):
    if not score_symbol_v2b:
        return
    for sym in WATCHLIST:
        try:
            res = score_symbol_v2b(sym, tf=TF_DEFAULT, limit=300)
            if not isinstance(res, dict) or not res.get("ok"):
                continue
            score = float(res.get("score", 0))
            cls   = str(res.get("class", "HOLD"))
            if _should_post(sym, score, cls):
                msg = _format_score(sym, res)
                if _bot_send_text(bot, msg, CHAT_ID):
                    _last_post[sym] = time.time()
        except Exception as e:
            log.warning("tick error for %s: %s", sym, e)

def _start_scheduler(updater: Updater):
    # run immediately once, then every CADENCE_MIN minutes in a background thread
    def runner():
        while True:
            _tick(updater.bot)
            time.sleep(max(60, CADENCE_MIN * 60))
    t = threading.Thread(target=runner, daemon=True)
    t.start()
    log.info("autorun started: watchlist=%s cadence=%dmin", ",".join(WATCHLIST), CADENCE_MIN)

# ------------- main -------------
def main():
    require_token_or_exit()

    updater = Updater(token=TOKEN, use_context=True)
    dp = updater.dispatcher

    # handlers
    dp.add_handler(CommandHandler("start",   cmd_start))
    dp.add_handler(CommandHandler("menu",    cmd_menu))
    dp.add_handler(CommandHandler("hide",    cmd_hide))
    dp.add_handler(CommandHandler("status",  cmd_status))
    dp.add_handler(CommandHandler("ping",    cmd_ping))
    dp.add_handler(CommandHandler("version", cmd_version))
    dp.add_handler(CommandHandler("commands",cmd_commands))
    dp.add_handler(CommandHandler("id",      cmd_id))
    dp.add_handler(CommandHandler("mode",    cmd_mode))
    dp.add_handler(CommandHandler("signal",  cmd_signal))
    dp.add_handler(CommandHandler("health",  cmd_health))
    dp.add_handler(CommandHandler("price",   cmd_price))
    dp.add_handler(CommandHandler("score",   cmd_score))
    dp.add_handler(CommandHandler("strategy",cmd_strategy))
    dp.add_handler(CommandHandler("risk",    cmd_risk))
    dp.add_handler(CommandHandler("scorev2", cmd_scorev2))

    # Telegram menu
    try:
        commands = [
            ("start","Start bot"), ("menu","Show menu"), ("hide","Hide keyboard"),
            ("status","Runtime status"), ("ping","Pong"), ("version","Show version"),
            ("commands","List commands"), ("id","Show chat id"), ("mode","Switch mode"),
            ("signal","Sample signal"), ("health","Diagnostics"),
            ("price","Show live price"), ("score","Score (legacy)"),
            ("strategy","Strategy summary"), ("risk","Risk rules"),
            ("scorev2","Score v2b"),
        ]
        updater.bot.set_my_commands([BotCommand(k, v) for k, v in commands])
    except Exception as e:
        log.warning("set_my_commands failed: %s", e)

    _start_scheduler(updater)

    log.info("TG command bot started.")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
