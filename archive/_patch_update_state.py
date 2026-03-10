path = "/data/data/com.termux/files/home/BotA/tools/update_state.sh"
with open(path) as f:
    src = f.read()

old = '''# --- 5. Append crontab snapshot with date stamp ---
python3 - << PY
import os, datetime

state_path = os.path.expanduser("~/BotA/BOTA_STATE.md")
with open(state_path) as f:
    src = f.read()

cron = """${CRON_BLOCK}""".replace("\\%", "%")'''

new = '''# --- 5. Append crontab snapshot with date stamp ---
crontab -l 2>/dev/null > /tmp/bota_cron_snapshot.txt
python3 - << PY
import os

state_path = os.path.expanduser("~/BotA/BOTA_STATE.md")
with open(state_path) as f:
    src = f.read()

with open("/tmp/bota_cron_snapshot.txt") as cf:
    cron = cf.read()'''

if old in src:
    src = src.replace(old, new)
    with open(path, 'w') as f:
        f.write(src)
    print("PATCHED OK")
else:
    print("PATTERN NOT FOUND — printing relevant lines:")
    for i, line in enumerate(src.splitlines(), 1):
        if 'CRON_BLOCK' in line or 'cron =' in line:
            print(f"  {i}: {line}")
