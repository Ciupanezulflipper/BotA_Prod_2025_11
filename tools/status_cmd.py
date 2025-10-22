import os, sys, time, json, datetime as dt
from .tg_utils import send_message

COOLDOWN_MIN = int(os.getenv("HEARTBEAT_COOLDOWN_MIN","55"))
STATE = os.path.expanduser("~/BotA/.state")
os.makedirs(STATE, exist_ok=True)
STAMP = os.path.join(STATE, "heartbeat.stamp")

def ok_to_send() -> bool:
    try:
        st = os.stat(STAMP)
        age = time.time()-st.st_mtime
        return age >= COOLDOWN_MIN*60
    except Exception:
        return True

def mark_sent():
    try:
        with open(STAMP,"w") as f:
            f.write(str(time.time()))
    except Exception:
        pass

def heartbeat(reason: str):
    if not ok_to_send():
        print("[HB] suppressed (cooldown active).")
        return
    msg = f"🤖 BotA heartbeat • {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC • reason={reason}"
    ok = send_message(msg)
    mark_sent()
    print(f"Heartbeat sent to Telegram, ok={ok}")

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--heartbeat", default="")
    args = ap.parse_args()
    if args.heartbeat:
        heartbeat(args.heartbeat)

if __name__ == "__main__":
    main()
