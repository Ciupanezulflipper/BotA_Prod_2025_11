import os, csv, math, pathlib
from statistics import mean

DATA_DIR = str(pathlib.Path.home() / "bot-a" / "data" / "candles")

def _read_closes(csv_path, n=120):
    rows = []
    with open(csv_path, newline="") as f:
        r = csv.reader(f)
        for row in r:
            if not row: 
                continue
            try:
                # ts, open, high, low, close
                rows.append(float(row[4]))
            except Exception:
                continue
    return rows[-n:] if n and len(rows) >= n else rows

def _ema(vals, period):
    if len(vals) < period:
        return None
    k = 2 / (period + 1)
    ema = vals[0]
    for v in vals[1:]:
        ema = v * k + ema * (1 - k)
    return ema

def _rsi(closes, period=14):
    if len(closes) <= period:
        return 50.0
    gains, losses = [], []
    for i in range(1, period + 1):
        ch = closes[i] - closes[i-1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_gain = mean(gains)
    avg_loss = mean(losses) if sum(losses) > 0 else 0.0
    rs = avg_gain / avg_loss if avg_loss != 0 else float("inf")

    for i in range(period + 1, len(closes)):
        ch = closes[i] - closes[i-1]
        gain = max(ch, 0.0)
        loss = max(-ch, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else float("inf")

    rsi = 100 - (100 / (1 + rs))
    # clamp to sane range
    return max(0.0, min(100.0, rsi))

def _macd_diff(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal + 5:
        return 0.0
    # build EMAs progressively for stability
    def ema_series(vals, p):
        out = []
        k = 2 / (p + 1)
        e = vals[0]
        out.append(e)
        for v in vals[1:]:
            e = v * k + e * (1 - k)
            out.append(e)
        return out
    ema_fast = ema_series(closes, fast)
    ema_slow = ema_series(closes, slow)
    macd = [f - s for f, s in zip(ema_fast[-len(ema_slow):], ema_slow)]
    signal_line = ema_series(macd, signal)
    return macd[-1] - signal_line[-1]

def _adx_like_from_closes(closes, period=14):
    """
    Very lightweight ADX-like proxy from close-only data.
    Scaled to something intuitive for FX: ~[5 .. 60].
    """
    if len(closes) < period + 2:
        return 10.0
    tr = sum(abs(closes[i] - closes[i-1]) for i in range(1, period+1)) / period
    denom = (sum(abs(c) for c in closes[-period:]) / period) or 1.0
    level = (tr / denom) * 10000.0
    return max(5.0, min(60.0, level))

def latest_indicators(csv_path):
    closes = _read_closes(csv_path, n=200)
    rsi = _rsi(closes, 14)
    md  = _macd_diff(closes, 12, 26, 9)
    adx = _adx_like_from_closes(closes, 14)
    return {"rsi": rsi, "macd_diff": md, "adx": adx}

def _trend_up(csv_path):
    c = _read_closes(csv_path, n=60)
    if len(c) < 25:
        return None
    ema20_now = _ema(c, 20)
    ema20_prev = _ema(c[:-1], 20)
    if ema20_now is None or ema20_prev is None:
        return None
    return c[-1] > ema20_now or c[-2] > ema20_prev

def htf_flags(pair, data_dir=DATA_DIR):
    p = pair.upper()
    h1 = os.path.join(data_dir, f"{p}_H1.csv")
    h4 = os.path.join(data_dir, f"{p}_H4.csv")
    return {
        "h1_trend_up": _trend_up(h1),
        "h4_trend_up": _trend_up(h4)
    }

def explain(pair, tf, conf_min=2.6):
    p = pair.upper()
    csvp = os.path.join(DATA_DIR, f"{p}_{tf}.csv")
    ind = latest_indicators(csvp)
    htf = htf_flags(p)

    # additive scoring
    score = 0.0
    notes = []

    # RSI: oversold/overbought
    if ind["rsi"] <= 35.0:
        score += 1.0
        notes.append("RSI≤35 +1.0")
    elif ind["rsi"] >= 65.0:
        score += 1.0
        notes.append("RSI≥65 +1.0")
    else:
        notes.append("RSI mid")

    # ADX strength threshold ~22
    if ind["adx"] >= 22.0:
        score += 0.4
        notes.append("ADX strong +0.4")
    else:
        notes.append("ADX weak")

    # HTF alignment bonus (+0.6) if H1/H4 trend agrees with direction later
    htf_bonus = 0.6

    # Direction by RSI primarily, fallback to MACD diff sign, else FLAT
    direction = "FLAT"
    if ind["rsi"] <= 35.0:
        direction = "SELL"
        if htf["h1_trend_up"] is False and htf["h4_trend_up"] is False:
            score += htf_bonus
            notes.append("HTF↓ +0.6")
    elif ind["rsi"] >= 65.0:
        direction = "BUY"
        if htf["h1_trend_up"] is True and htf["h4_trend_up"] is True:
            score += htf_bonus
            notes.append("HTF↑ +0.6")
    else:
        # neutral RSI: peek at MACD diff for a tiny nudge (no score)
        if ind["macd_diff"] > 0:
            direction = "BUY"
        elif ind["macd_diff"] < 0:
            direction = "SELL"

    # print human view (used by your CLI checks)
    print(f"== Explain {p} {tf} ==")
    print(f"Score: {score:.2f} | Send: {score >= conf_min} | Conf_Min: {conf_min}")
    print("--- Components (additive) ---")
    print(f"RSI {ind[rsi]:.2f} • ADX {ind[adx]:.2f} • ΔMACD {ind[macd_diff]:.6f}")
    print(f"HTF: H1↑={htf[h1_trend_up]} H4↑={htf[h4_trend_up]}")
    print("Notes:", "; ".join(notes))

    return {
        "pair": p, "tf": tf, "score": score, "direction": direction,
        "rsi": ind["rsi"], "adx": ind["adx"], "macd_diff": ind["macd_diff"],
        "send": score >= conf_min, "notes": notes,
        "h1_trend_up": htf["h1_trend_up"], "h4_trend_up": htf["h4_trend_up"]
    }

if __name__ == "__main__":
    # quick manual check: python3 explain_signal.py EURUSD M15
    import sys
    pair = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    tf   = sys.argv[2] if len(sys.argv) > 2 else "M15"
    explain(pair, tf)
