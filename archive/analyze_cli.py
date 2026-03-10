#!/usr/bin/env python3
import argparse, sys, datetime as dt
import pandas as pd

def try_import_yf():
    try:
        import yfinance as yf
        return yf
    except Exception as e:
        print("❌ Missing dependency: yfinance\nInstall: pip install --upgrade yfinance pandas", file=sys.stderr)
        sys.exit(2)

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.clip(lower=0)).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def map_symbol(sym: str) -> str:
    # Minimal mapping for Yahoo tickers
    sym = sym.upper().replace("/", "")
    if sym == "XAUUSD" or sym == "GOLD": return "GC=F"      # Gold futures
    if sym == "SILVER" or sym == "XAGUSD": return "SI=F"
    if sym == "EURUSD": return "EURUSD=X"
    if sym == "GBPUSD": return "GBPUSD=X"
    if sym == "USDJPY": return "JPY=X"
    if sym == "NAS100" or sym == "NDX" or sym == "QQQ": return "^NDX"
    return sym  # try raw

def tf_to_period(tf: str):
    tf = tf.upper()
    if tf == "H1": return "1h", "30d"
    if tf == "H4": return "4h", "120d"
    if tf in ("D1","1D","D"): return "1d", "2y"
    return "1h", "30d"

def analyze(sym: str, tf: str):
    yf = try_import_yf()
    interval, period = tf_to_period(tf)
    ticker = map_symbol(sym)

    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if df is None or df.empty:
        return f"❌ No data for {sym} ({ticker}) {tf}"

    close = df['Close'].dropna()
    ema9 = ema(close, 9)
    ema21 = ema(close, 21)
    r = rsi(close, 14)

    last = close.iloc[-1]
    e9 = ema9.iloc[-1]
    e21 = ema21.iloc[-1]
    rlast = r.iloc[-1]

    # Simple signal
    if e9 > e21 and rlast >= 45:
        bias = "BUY"
    elif e9 < e21 and rlast <= 55:
        bias = "SELL"
    else:
        bias = "WAIT"

    ts = df.index[-1].to_pydatetime().replace(tzinfo=None).isoformat(timespec="minutes")
    msg = (
        f"*{sym} {tf}*\n"
        f"Price: `{last:.5f}`  •  EMA9: `{e9:.5f}`  •  EMA21: `{e21:.5f}`\n"
        f"RSI(14): `{rlast:.1f}`  •  Time: `{ts}`\n\n"
        f"**Signal:** *{bias}*  \n"
        f"_Logic:_ EMA9/EMA21 trend + RSI filter (14)."
    )
    return msg

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--tf", default="H1")
    a = p.parse_args()
    print(analyze(a.symbol, a.tf))

if __name__ == "__main__":
    main()
