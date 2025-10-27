#!/usr/bin/env python3
# BotA — One-shot Analyzer (pretty “signal card” + multi-pair)
# Robust parser: walks run.log forward, groups TF lines under the most
# recent "=== SYMBOL snapshot ===" header to avoid cross-symbol bleed.

import os, sys, re, datetime
from pathlib import Path
from typing import Dict, Optional

# ----- Config (non-breaking) -----
MIN_WEIGHT = int(os.getenv("MIN_WEIGHT", "2"))
RUN_LOG = Path(os.getenv("BOTA_RUNLOG", str(Path.home() / "BotA" / "run.log")))

PIP_SIZE = {
    "EURUSD": 0.0001, "GBPUSD": 0.0001, "AUDUSD": 0.0001, "NZDUSD": 0.0001,
    "USDJPY": 0.01,   "GBPJPY": 0.01,   "EURJPY": 0.01,   "CADJPY": 0.01,
}
DEFAULT_PIPS = {
    "EURUSD": 30, "GBPUSD": 35, "AUDUSD": 25, "NZDUSD": 25,
    "USDJPY": 40, "GBPJPY": 50, "EURJPY": 45, "CADJPY": 35,
}

HDR_RE = re.compile(r"^===\s*([A-Z]{6})\s+snapshot\s*===\s*$", re.I)
TF_RE  = re.compile(
    r"^(H1|H4|D1):\s*t=([0-9\-:\sTZ]+)\s+close=([0-9.]+).*?RSI14=([0-9.]+).*?vote=([+\-]?\d+)",
    re.I,
)

def _read_tail(path: Path, max_bytes: int = 300_000) -> str:
    try:
        with path.open('rb') as f:
            f.seek(0, 2)
            end = f.tell()
            f.seek(max(0, end - max_bytes))
            return f.read().decode(errors="ignore")
    except Exception:
        return ""

def parse_latest_by_symbol() -> Dict[str, Dict[str, dict]]:
    """
    Traverse run.log forward, grouping TF rows under the most recent
    '=== SYMBOL snapshot ===' header. Returns {SYM: {"H1": {...}, ...}}
    using ONLY the last complete set encountered per symbol.
    """
    text = _read_tail(RUN_LOG)
    current_sym: Optional[str] = None
    latest: Dict[str, Dict[str, dict]] = {}

    for line in text.splitlines():
        m_hdr = HDR_RE.match(line)
        if m_hdr:
            current_sym = m_hdr.group(1).upper()
            # start fresh section; we will overwrite to keep it "most recent"
            latest[current_sym] = {}
            continue

        m_tf = TF_RE.match(line)
        if m_tf and current_sym:
            tf, t, close, rsi, vote = m_tf.groups()
            latest[current_sym][tf.upper()] = {
                "t": t.strip(),
                "close": float(close),
                "rsi": float(rsi),
                "vote": int(vote),
            }

    # keep only symbols with at least one TF parsed
    return {k: v for k, v in latest.items() if v}

def decide_bias(tf_data: Dict[str, dict]) -> str:
    votes = [d["vote"] for d in tf_data.values() if d]
    score = sum(votes) if votes else 0
    if score >= MIN_WEIGHT:  return "BUY"
    if score <= -MIN_WEIGHT: return "SELL"
    return "NEUTRAL"

def tp_sl(symbol: str, direction: str, price: float):
    pip = PIP_SIZE.get(symbol.upper(), 0.0001)
    pips = DEFAULT_PIPS.get(symbol.upper(), 30)
    delta = pip * pips
    if direction == "BUY":
        return round(price + delta, 5), round(price - delta*0.6, 5)
    if direction == "SELL":
        return round(price - delta, 5), round(price + delta*0.6, 5)
    return round(price + delta, 5), round(price - delta, 5)

def tf_row(name: str, d: Optional[dict]) -> str:
    if not d: return f"{name}: n/a"
    return f"{name}: t={d['t']} close={d['close']:.5f} RSI14={d['rsi']:.2f} vote={d['vote']:+d}"

def render_card(symbol: str, tf_data: Dict[str, dict]) -> str:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    bias = decide_bias(tf_data)
    entry = (tf_data.get("H1") or tf_data.get("D1") or next(iter(tf_data.values()))).get("close", None)

    if entry is None:
        return (
            "🔎 <b>BotA — One-shot Analyze</b>\n"
            f"{ts}\nMIN_WEIGHT={MIN_WEIGHT}\n"
            f"<b>{symbol}</b>: no recent snapshot found"
        )

    tgt, sl = tp_sl(symbol, bias, entry)
    hdr_emoji = "🟢" if bias == "BUY" else "🔴" if bias == "SELL" else "⚪"

    parts = [
        "🔎 <b>BotA — One-shot Analyze</b>",
        ts,
        f"MIN_WEIGHT={MIN_WEIGHT}",
        f"🧭 <b>#{symbol} {bias} BIAS</b>",
        f"📊 <b>{symbol[:3]}/{symbol[3:]} SIGNAL</b>",
        ("✅" if bias=="BUY" else "❌" if bias=="SELL" else "☑️") +
            f" Trade Direction: {'long' if bias=='BUY' else 'short' if bias=='SELL' else 'neutral'}",
        f"✅ Entry Level: {entry:.5f}",
        f"✅ Target Level: {tgt:.5f}",
        f"✅ Stop Loss: {sl:.5f}",
        "",
        "<code>"+tf_row("H1", tf_data.get("H1"))+"</code>",
        "<code>"+tf_row("H4", tf_data.get("H4"))+"</code>",
        "<code>"+tf_row("D1", tf_data.get("D1"))+"</code>",
    ]
    return "\n".join(parts)

def main():
    symbols = [s.upper() for s in sys.argv[1:]] or os.getenv("ANALYZE_PAIRS","EURUSD GBPUSD").replace(',', ' ').split()
    latest = parse_latest_by_symbol()
    blocks = []
    for sym in symbols:
        tf_data = latest.get(sym)
        if not tf_data:
            ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            blocks.append(f"🔎 <b>BotA — One-shot Analyze</b>\n{ts}\nMIN_WEIGHT={MIN_WEIGHT}\n<b>{sym}</b>: no recent snapshot found")
            continue
        blocks.append(render_card(sym, tf_data))
    print("\n\n".join(blocks))

if __name__ == "__main__":
    main()
