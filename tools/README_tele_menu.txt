BotA — Telegram Menu & Signals (No-babysit)

What you get
- Inline menu with: Analyze Now, Status, Audit, Health, Pause/Resume, Daily Report, and a quick Set Pairs button.
- Slash commands:
  /start or /menu — show the panel
  /analyze [PAIRS…] — pretty signals (e.g., /analyze EURUSD GBPUSD)
  /pairs EURUSD GBPUSD — save default pairs
  /pause — pause alerts (creates state/paused.flag)
  /resume — resume alerts (removes paused.flag)
  /status — metrics snapshot
  /audit — full metrics_verify
  /health — phase10 DRY summary
  /daily — push 24h daily report

Usage
1) Ensure env:
   source "$HOME/BotA/tools/tele_env.sh" <YOUR_CHAT_ID>
2) Start controller:
   "$HOME/BotA/tools/tele_control.sh"
3) In Telegram (your private chat), press /start to see the menu.

Notes
- Pairs preference persists in state/analyze_pairs.txt.
- The controller only responds in your configured chat id (safety).
- It shells out only to your existing tools; no changes to the pipeline.
