from __future__ import annotations
import os, sys, json, subprocess
from datetime import datetime

BOT_ROOT = os.path.expanduser("~/BotA")
if BOT_ROOT not in sys.path:
    sys.path.insert(0, BOT_ROOT)

def _short_env(keys):
    out={}
    for k in keys:
        v=os.getenv(k)
        if v:
            out[k]=(v[:4]+"…"+v[-3:]) if len(v)>10 else v
    return out

def _cmd(cmd):
    try:
        out=subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True, timeout=12)
        return True, out.strip()
    except Exception as e:
        return False, str(e)

def main():
    checks={"python_version": sys.version}
    for mod in ("tools.indicators_ext","tools.scoring_v2","tools.signal_card","tools.runner_confluence","tools.providers","tools.indicators_patch"):
        try:
            __import__(mod)
            checks[f"import:{mod}"]="ok"
        except Exception as e:
            checks[f"import:{mod}"]=f"FAIL: {e}"

    checks["env"]=_short_env(["TELEGRAM_BOT_TOKEN","TELEGRAM_CHAT_ID","TWELVE_DATA_API_KEY","ALPHA_VANTAGE_API_KEY","FINNHUB_API_KEY"])

    ok,out=_cmd("grep -n \"reason=hourly\" ~/.termux/cron.d/bota_heartbeat")
    checks["cron_file"]={"ok":ok,"out":out}
    ok,out=_cmd("ps -Af | grep -i '[c]rond' || true")
    checks["crond_ps"]={"ok":ok,"out":out}
    ok,out=_cmd("tmux ls || true")
    checks["tmux_ls"]={"ok":ok,"out":out}

    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        ok,out=_cmd("curl -sS https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe >/dev/null && echo OK || echo FAIL")
        checks["ping_tg"]={"ok":True,"out":out}
    else:
        checks["ping_tg"]={"ok":True,"out":"ENV not set"}

    for name,cmdline in {
        "twelvedata": 'curl -sS "https://api.twelvedata.com/time_series?symbol=EUR/USD&interval=15min&outputsize=3&apikey=${TWELVE_DATA_API_KEY}" | head -c 240',
        "alphavantage": 'curl -sS "https://www.alphavantage.co/query?function=FX_DAILY&from_symbol=EUR&to_symbol=USD&apikey=${ALPHA_VANTAGE_API_KEY}" | head -c 240',
    }.items():
        ok,out=_cmd(cmdline)
        checks[name]={"ok":ok,"out":out}

    for tag, path in {"bot_log_tail":"~/BotA/logs/bot.log","tg_log_tail":"~/BotA/logs/tg_bot.log","hb_log_tail":"~/BotA/logs/statusd.log"}.items():
        ok,out=_cmd(f"tail -n 40 {path} || true")
        checks[tag]={"ok":ok,"out":out}

    print("=== SELF CHECK ===")
    print(json.dumps({"timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), "checks":checks}, indent=2))

    print("\n=== PRD CARD SMOKE (DRY RUN) ===")
    ok,out=_cmd('cd ~/BotA && export $(grep -v ^# .env | xargs) || true; python -m tools.runner_confluence --pair EURUSD --tf M15 --force --dry-run=true')
    print(out if ok else f"[FATAL] runner error: {out}")
if __name__=="__main__": main()
