import sys, os
from analyzers_core import latest_indicators

def main():
    pair = sys.argv[1] if len(sys.argv)>1 else "EURUSD"
    tf   = sys.argv[2] if len(sys.argv)>2 else "M15"
    base = "/data/data/com.termux/files/home/bot-a/data/candles"
    path = f"{base}/{pair}_{tf}.csv"
    ind = latest_indicators(path)
    macd = ind["macd"]; rsi = ind["rsi"]; adx = ind["adx"]
    print(f"=== Explain {pair} {tf} (patched) ===")
    print("rows:", ind["rows"])
    print("MACD(12,26,9):", macd)
    print("RSI(14):", rsi)
    print("ADX(14):", adx)
    # Simple score preview like your tags:
    score = 0.0
    if macd and macd[0] > macd[1]: score += 0.6   # MACD up
    if isinstance(rsi, float) and rsi >= 60: score += 0.3
    if isinstance(adx, float) and adx >= 22: score += 0.3
    print(f"Score preview: {score:.2f}")
    print("Decision preview:", "SEND" if score>=1.8 else "NO SEND")
if __name__=="__main__":
    main()
