import os, requests, datetime as dt

tok=os.environ["TELEGRAM_BOT_TOKEN"]
cid=os.environ["TELEGRAM_CHAT_ID"]

# A weak SELL snapshot (should be BLOCKED by weighted vote/RSI window/conf)
weak = """=== EURUSD snapshot ===
H1: ... RSI14=49.9 ... vote=0
H4: ... RSI14=47.2 ... vote=-1
D1: ... RSI14=51.0 ... vote=0

Signal: SELL
Entry: 1.23456
SL: 1.24176
TP: 1.22256
ATR: 0.0060
Votes: {'H1': 0, 'H4': -1, 'D1': 0}
"""

# A strong SELL snapshot (should be ALLOWED: H1=-1, H4=-1, D1=-1 -> weighted= -6)
strong = """=== GBPUSD snapshot ===
H1: ... RSI14=38.2 ... vote=-1
H4: ... RSI14=41.0 ... vote=-1
D1: ... RSI14=40.4 ... vote=-1

Signal: SELL
Entry: 1.33333
SL: 1.34151
TP: 1.32133
ATR: 0.0061
Votes: {'H1': -1, 'H4': -1, 'D1': -1}
"""

def send(text):
    r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      data={"chat_id":cid,"text":text}, timeout=10)
    print("HTTP", r.status_code, r.text[:120])

print("=== Weak probe (expect BLOCK) ===")
send(weak)
print("=== Strong probe (expect ALLOW) ===")
send(strong)
