Bot A — Telegram Control (no babysitting Termux)

What you get:
- A long-polling controller that listens to Telegram commands and starts/stops the existing alert loop process. No changes to the proven pipeline.
- Commands: /start, /stop, /start_alerts, /pause_alerts, /status, /audit, /help
- /audit uses metrics_verify.sh when available; otherwise a compact fallback.

Boot on demand:
  $HOME/BotA/tools/tele_control.sh
(you can also add this to your Termux boot/cron if desired)

One-time verify:
  $HOME/BotA/tools/phase11_verify.sh

Notes:
- Requires TELEGRAM_BOT_TOKEN exported (use tele_env.sh if you like).
- Chat ID is not needed for control; the bot replies to the chat you use.
- This controller does NOT spam; it only replies to your explicit commands.
- Your alert thresholds & filters remain exactly as before.

