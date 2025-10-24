import os, requests, time

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or ""
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID") or ""
if not BOT_TOKEN or not CHAT_ID:
    print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in env")
    raise SystemExit(2)

send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def send(text):
    r = requests.post(send_url, json={"chat_id": CHAT_ID, "text": text})
    print("HTTP", r.status_code, r.text[:120])

# (1) SKewed timestamps (expect BLOCK if TIME_SKEW_SEC <= 3600)
msg_skew = """=== EURUSD snapshot ===
H1: t=2025-10-23T23:00:00Z close=1.16000 EMA9=... RSI14=52.0 MACD_hist=0.0001 vote=+0
H4: t=2025-10-20T23:00:00Z close=1.16000 EMA9=... RSI14=40.0 MACD_hist=-0.0005 vote=-1
D1: t=2025-10-23Z close=1.16000 EMA9=... RSI14=38.0 MACD_hist=-0.0002 vote=-1

Signal: SELL
Entry: 1.16000
SL: 1.16800
TP: 1.14800
ATR: 0.0061
"""

# (2) Clean example (expect ALLOW if within hours & not NEWS_PAUSE)
msg_ok = """=== GBPUSD snapshot ===
H1: t=2025-10-23T23:00:00Z close=1.33300 EMA9=... RSI14=41.2 MACD_hist=-0.0002 vote=-1
H4: t=2025-10-23T23:00:00Z close=1.33300 EMA9=... RSI14=39.5 MACD_hist=-0.0007 vote=-1
D1: t=2025-10-23Z close=1.33300 EMA9=... RSI14=37.0 MACD_hist=-0.0001 vote=-1

Signal: SELL
Entry: 1.33300
SL: 1.34032
TP: 1.32080
ATR: 0.0062
"""

print("=== Skew probe (expect BLOCK if skew > limit) ===")
send(msg_skew)
time.sleep(1)
print("=== Clean probe (expect ALLOW) ===")
send(msg_ok)
