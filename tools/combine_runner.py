### BEGIN FILE: tools/combine_runner.py
#!/data/data/com.termux/files/usr/bin/python3
# Combines news + tech to a single decision gate
# Robust parsing for news/tech card text; tolerant to format drifts.

import os, re, json, sys, subprocess, datetime as dt
from typing import Optional, Tuple

BASE   = os.environ.get("HOME", "/data/data/com.termux/files/home") + "/bot-a"
LOGDIR = f"{BASE}/logs"
os.makedirs(LOGDIR, exist_ok=True)

MIN_CONF = float(os.environ.get("MIN_CONF", "6.0"))
TIMEFRAME = os.environ.get("TIMEFRAME", "4h")

def _now_utc_hm() -> str:
    return dt.datetime.utcnow().strftime("UTC %H:%M")

def _run_news(symbol: str) -> Tuple[float, str]:
    """
    Run news_sentiment.py --symbol SYMBOL --dry and parse score + why.
    Accepts formats like:
      'Confidence: *6.3/10*' OR 'Confidence: 6.3/10' OR 'Confidence: 6.3'
      'News: **6.0/10**' also ok.
    Returns (score, why)
    """
    cmd = [
        "python", f"{BASE}/tools/news_sentiment.py",
        "--symbol", symbol,
        "--dry"
    ]
    try:
        raw = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=60)
    except Exception as e:
        with open(f"{LOGDIR}/combine_runner.log","a") as lf:
            lf.write(f"[{_now_utc_hm()}] news_sentiment failed: {e}\n")
        return 0.0, "—"

    # Try multiple tolerant patterns
    score = 0.0
    patterns = [
        r"Confidence:\s*\*?([0-9]+(?:\.[0-9]+)?)\s*/\s*10\*?",
        r"News:\s*\*{0,2}([0-9]+(?:\.[0-9]+)?)\s*/\s*10\*{0,2}",
        r"Confidence:\s*\*?([0-9]+(?:\.[0-9]+)?)\*?"   # plain number fallback
    ]
    for p in patterns:
        m = re.search(p, raw)
        if m:
            try: score = float(m.group(1)); break
            except: pass

    # WHY line (first bullet or explicit why)
    why = "—"
    mw = re.search(r"(?mi)^\*?Why\*?.*?\n(?:•\s*|\-\s*)(.+)$", raw)
    if mw:
        why = mw.group(1).strip()
    else:
        # fallback: pick first line containing '(news'
        alt = re.search(r"(.+?\(news.*?\))", raw, flags=re.IGNORECASE|re.DOTALL)
        if alt: why = alt.group(1).strip()

    if score == 0.0:
        # Log raw for debugging when parse fails
        with open(f"{LOGDIR}/combine_runner_failed_news.txt","w") as df:
            df.write(raw)

    return score, why or "—"

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    news_score, why = _run_news(args.symbol)

    # Decision purely by MIN_CONF here (tech fusion is done in final_runner.py)
    if news_score < MIN_CONF:
        print(f"[combine_runner] skipped (weak): {args.symbol}  (MIN_CONF={MIN_CONF}, got {news_score})")
        return

    print(f"[combine_runner] OK: {args.symbol}  (news_score={news_score})")
    # This runner no longer sends; final fusion is in final_runner.py

if __name__ == "__main__":
    sys.exit(main())
### END FILE
