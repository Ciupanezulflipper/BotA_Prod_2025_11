#!/data/data/com.termux/files/usr/bin/bash
# update_state.sh — Refreshes dynamic sections of BOTA_STATE.md
# Run at end of every session before git commit.
# Does NOT overwrite manually written sections — only updates marked blocks.

ROOT="${BOTA_ROOT:-$HOME/BotA}"
STATE="${ROOT}/BOTA_STATE.md"
TMPFILE="${ROOT}/logs/tmp/state_update.tmp"

# --- 1. Update crontab block ---
CRON_BLOCK="$(crontab -l 2>/dev/null)"

# --- 2. Update last modified timestamp ---
TS="$(date -u +%Y-%m-%d)"

# --- 3. Pull last win rate from trades.csv if exists ---
if [[ -f "${ROOT}/logs/trades.csv" ]]; then
    WR_LINE="$(python3 - << 'PY'
import csv, os
path = os.path.expanduser("~/BotA/logs/trades.csv")
try:
    rows = list(csv.DictReader(open(path)))
    resolved = [r for r in rows if r.get("outcome") in ("WIN","LOSS")]
    wins = sum(1 for r in resolved if r["outcome"] == "WIN")
    wr = wins / len(resolved) * 100 if resolved else 0
    print(f"WR={wr:.1f}% on {len(resolved)} resolved signals")
except Exception as e:
    print(f"WR=unknown ({e})")
PY
)"
else
    WR_LINE="WR=unknown (trades.csv not yet generated)"
fi

# --- 4. Rewrite header timestamp and crontab block in state file ---
python3 - << PY
import re, os

state_path = os.path.expanduser("~/BotA/BOTA_STATE.md")
with open(state_path) as f:
    src = f.read()

# Update timestamp line
src = re.sub(r"# Updated: .*", f"# Updated: ${TS}", src)

# Update win rate line
src = re.sub(r"Next review:.*", 
    "Next review: Sunday $(date -u -d 'next sunday' +%Y-%m-%d 2>/dev/null || echo 'see calendar')",
    src)

with open(state_path, "w") as f:
    f.write(src)

print("BOTA_STATE.md timestamp updated")
PY

# --- 5. Append crontab snapshot with date stamp ---
crontab -l 2>/dev/null > /data/data/com.termux/files/home/BotA/logs/tmp/bota_cron_snap.txt
python3 - << PY
import os, datetime

state_path = os.path.expanduser("~/BotA/BOTA_STATE.md")
with open(state_path) as f:
    src = f.read()

with open("/data/data/com.termux/files/home/BotA/logs/tmp/bota_cron_snap.txt") as _cf:
    cron = _cf.read()
ts = "${TS}"

# Replace everything between crontab markers
import re
new_block = f"## LIVE CRONTAB (exact, as of {ts})\n{cron}\n"
src = re.sub(
    r"## LIVE CRONTAB \(exact.*?\n---",
    new_block + "---",
    src,
    flags=re.DOTALL
)

with open(state_path, "w") as f:
    f.write(src)

print("LIVE CRONTAB block updated")
PY

echo "[update_state] Done. WR: ${WR_LINE}"
echo "Run: git add BOTA_STATE.md && git commit -m 'State update' && git push"
