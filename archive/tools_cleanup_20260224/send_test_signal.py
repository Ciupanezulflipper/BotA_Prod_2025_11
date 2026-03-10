#!/usr/bin/env python3
import os, time, requests
from datetime import datetime, timezone

token = os.environ.get("TELEGRAM_BOT_TOKEN")
chat  = os.environ.get("TELEGRAM_CHAT_ID")
if not token or not chat:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in env")

pair   = os.environ.get("PAIR", "EURUSD")
tf     = os.environ.get("TF", "M15")
score  = float(os.environ.get("SCORE", "0.95"))
conf   = float(os.environ.get("CONF", "9.0"))
reason = os.environ.get("REASON", "test-send")

signal_id = f"TEST-{int(time.time())}"
ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

msg = (
    "✅ TEST STRONG SIGNAL\n"
    f"Pair: {pair}\nTF: {tf}\n"
    f"Score: {score:.2f}\nConfidence: {conf:.1f}/10\n"
    f"Reason: {reason}\nID: {signal_id}\n{ts}"
)

# send to Telegram
requests.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    data={"chat_id": chat, "text": msg},
    timeout=20
)

# journal it
jn = os.path.expanduser("~/bot-a/data/signal_journal.csv")
header = "ts_utc,event,pair,tf,score,conf,reason,signal_id,source,log_line_no\n"
try:
    need_header = not os.path.exists(jn) or os.path.getsize(jn) == 0
except FileNotFoundError:
    need_header = True

os.makedirs(os.path.dirname(jn), exist_ok=True)
with open(jn, "a+") as f:
    if need_header:
        f.write(header)
    f.write(",".join([
        ts, "TEST_SENT", pair, tf,
        f"{score}", f"{conf}", reason,
        signal_id, "send_test_signal.py", "0"
    ]) + "\n")

print("Sent test to Telegram and journaled.")
