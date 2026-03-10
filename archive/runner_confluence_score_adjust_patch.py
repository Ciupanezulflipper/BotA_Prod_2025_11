# … inside decide() adjust thresholds …
rsi_buy  = float(os.getenv("RSI_BUY","50"))
rsi_sell = float(os.getenv("RSI_SELL","50"))
min_score = float(os.getenv("MIN_SCORE","60"))
# Optional: increase weight of momentum candle:
if bull:
    score += 20; parts.append("Bull candle strong")
elif bear:
    score += 20; parts.append("Bear candle strong")
