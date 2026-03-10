Bot A — No-babysit Autostart

What this delivers
- tools/boot.sh: idempotent starter for alerts + Telegram controller.
- ~/.termux/boot/bota_start.sh: Termux:Boot hook to auto-run boot.sh on device boot.
- phase11_autostart_verify.sh: smoke test to confirm both procs up and logs fresh.

Usage
1) Optional (one-time): export Telegram vars so boot can ping you
   source $HOME/BotA/tools/tele_env.sh <CHAT_ID>

2) Manual check now:
   $HOME/BotA/tools/phase11_autostart_verify.sh

3) Auto at phone boot:
   Install the Termux:Boot app, then reboot the phone once.

Notes
- No changes to your proven pipeline; this only orchestrates processes.
- Safe to run anytime; will not spawn duplicates.
