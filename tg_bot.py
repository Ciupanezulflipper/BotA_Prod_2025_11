#!/usr/bin/env python3
# tg_bot.py — Bot A Telegram entrypoint (PTB 22.5, Python 3.12)
# - Loads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from config/tele.env
# - Commands: /ping, /status [advanced], /health
# - Calls tools/status_pretty.py to format output

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

ROOT = Path(os.environ.get("BOTA_ROOT", str(Path(__file__).resolve().parent)))
CONFIG = ROOT / "config" / "tele.env"
PRETTY = ROOT / "tools" / "status_pretty.py"


def load_env_file(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        raise FileNotFoundError(f"{path} missing. Run tools/tele_env_sync.sh first.")
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


async def run_pretty(mode: str = "basic") -> str:
    """
    Run tools/status_pretty.py and return its text.
    Falls back to demo if pretty script is missing.
    """
    script = PRETTY if PRETTY.exists() else (ROOT / "tools" / "status_pretty_demo.py")
    if not script.exists():
        return "⚠️ status_pretty.py not found."
    args = [sys.executable, str(script)]
    if mode:
        args += [mode]
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        out, err = await proc.communicate()
        text = out.decode(errors="ignore").strip()
        if not text:
            text = err.decode(errors="ignore").strip() or "⚠️ No output from status_pretty."
        return text[:3900]  # keep under Telegram limit with buffer
    except Exception as e:
        return f"❌ status_pretty error: {e!r}"


# ==== Handlers ====

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"🏓 Pong — {context.application.bot.name}")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    mode = " ".join(context.args).strip().lower() if context.args else ""
    mode = "advanced" if mode in {"adv", "advanced"} else "basic"
    txt = await run_pretty(mode)
    await update.message.reply_text(txt, disable_web_page_preview=True)

async def health_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Minimal health block; extend as needed
    lines = [
        "🩺 BotA — Health",
        f"root: {ROOT}",
        f"pretty: {'OK' if PRETTY.exists() else 'missing'}",
        f"tele.env: {'OK' if CONFIG.exists() else 'missing'}",
    ]
    await update.message.reply_text("\n".join(lines))


def build_app():
    env = load_env_file(CONFIG)
    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token.startswith("123456789:ABC-"):
        raise RuntimeError("Invalid TELEGRAM_BOT_TOKEN in config/tele.env")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("health", health_cmd))
    return app


def main():
    app = build_app()
    # Polling with sane defaults; no AIORateLimiter to avoid extra dependency
    app.run_polling(
        allowed_updates=None,
        drop_pending_updates=True,
        stop_signals=None,   # PTB handles SIGINT/SIGTERM internally
        close_loop=False,
        poll_interval=1.0
    )


if __name__ == "__main__":
    main()
