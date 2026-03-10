# BotA — Entry Point and Fix Strategy (Simple)

## What is the “entrypoint”?
The entrypoint is **the command that starts BotA’s work** (signals / alerts / status) on your phone.

In Termux, there can be **more than one** entrypoint:
- **Automation entrypoint** (what runs by itself): usually **Cron** (`crontab -l`)
- **Manual entrypoint** (what you run by hand): scripts like `run_signal.sh`, `tools/runmenu.sh`, etc.

So there isn’t always “one true entrypoint” — the **real one is whichever is scheduled/started right now**.

## Based on the output you pasted
### 1) What is ACTUALLY running daily on your phone
Your **active crontab** (`crontab -l`) runs:
- Hourly: `tools/heartbeat.sh`, `tools/autostatus.sh`
- Daily: `tools/daily_summary.sh` (it sources `$HOME/BotA/.env`), and `tools/log_rotate.sh`
- Every 15 min: `tools/signal_accuracy.py`, `tmp/send_candidates_now.py`
- Every 5 min: a guarded command that sources an env file and runs `tools/signal_watcher_pro.sh --once`

That means: **your real automation entrypoint is Cron**, and the “main signal engine” appears to be:
- `tools/signal_watcher_pro.sh --once` (because it runs frequently and is guarded by market-open logic)

### 2) Why `run_signal.sh` is NOT the daily entrypoint (right now)
You have `run_signal.sh`, and the repo `.crontab` file mentions it, but your **active crontab** does **not** call `run_signal.sh`.

So today:
- `run_signal.sh` = exists (manual/alternate)
- `crontab -l` jobs = real day-to-day automation

## Why you keep seeing:
`bash: .../.env.botA: syntax error near unexpected token '('`
That error happens when something does:
- `source .env.botA`  OR  `. .env.botA`

But `.env.botA` contains values like:
`MT5_PASSWORD=fdlp(at0vM`
Parentheses break bash parsing when you source the file unquoted.

So the root cause is simple:
- **Some script or shell startup is still sourcing `.env.botA` directly.**

## My fix strategy for BotA (simple words)
I use a strict “no guessing” method:

1) **Find the real runner**
   - Read `crontab -l` and identify which script actually runs signals.

2) **Find the crash trigger**
   - Search for any `source/. .env.botA` anywhere (scripts + shell startup).

3) **Fix one root cause at a time**
   - Replace the offender to use a safe loader (`tools/env_safe_source.sh`) or quote values properly.
   - Do NOT change 10 things at once.

4) **Prove it works**
   - Run `py_compile` and a smoke script.
   - Confirm Telegram send works and nothing crashes.

5) **Move to the next issue**
   - Only after the previous step is stable.

This prevents circular fixes and “random edits” that break other parts.

## What you should do now (one step)
Run:
`bash tools/entrypoint_map.sh`

It will:
- Tell you the primary entrypoint inferred from your active crontab
- List the exact offender file(s) that still source `.env.botA`
- Check if your shell startup files auto-source `.env.botA`

When you paste that output, the next step is deterministic:
- I will provide a full replacement for the specific offender file(s) (not broad changes).

