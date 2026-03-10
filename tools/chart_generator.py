#!/usr/bin/env python3
"""
chart_generator.py — Pure Python PNG chart generator. Zero external deps.
Usage:
    python3 tools/chart_generator.py EURUSD         (sanity mode)
    python3 tools/chart_generator.py --pair EURUSD --tf M15 --direction BUY \
        --entry 1.0850 --sl 1.0820 --tp 1.0890 --score 75 --out logs/charts/signal.png
"""
import argparse, json, math, os, sys, struct, zlib
from datetime import datetime, timezone
from pathlib import Path

ROOT   = Path(os.environ.get("BOTA_ROOT", Path.home() / "BotA"))
CACHE  = ROOT / "cache"
CHARTS = ROOT / "logs" / "charts"
CHARTS.mkdir(parents=True, exist_ok=True)


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    c = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", c)


def write_png(path: str, pixels: list, width: int, height: int):
    sig  = b"\x89PNG\r\n\x1a\n"
    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    raw  = b""
    for y in range(height):
        raw += b"\x00"
        for x in range(width):
            r, g, b = pixels[y * width + x]
            raw += bytes([r, g, b])
    idat = _png_chunk(b"IDAT", zlib.compress(raw, 0))
    iend = _png_chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(sig + ihdr + idat + iend)


def make_chart_png(out_path, pair, tf, direction, entry, sl, tp, score, candles):
    W, H  = 900, 480
    BG    = (18, 18, 28);  GRID = (40, 40, 60)
    GREEN = (0, 200, 100); RED  = (220, 60, 60)
    BULL  = (0, 180, 90);  BEAR = (200, 50, 50)
    GOLD  = (255, 200, 50)

    pixels = [BG] * (W * H)

    def px(x, y, col):
        if 0 <= x < W and 0 <= y < H:
            pixels[y * W + x] = col

    def hline(y, x0, x1, col, t=1):
        for dt in range(t):
            for x in range(x0, x1 + 1): px(x, y + dt, col)

    def vline(x, y0, y1, col, t=1):
        for dt in range(t):
            for y in range(y0, y1 + 1): px(x + dt, y, col)

    for i in range(0, H, 40): hline(i, 0, W-1, GRID)
    for i in range(0, W, 60): vline(i, 0, H-1, GRID)

    prices = [v for v in [entry, sl, tp] if v]
    for c in candles[-60:]:
        try: prices += [float(c.get("high",0)), float(c.get("low",0))]
        except: pass

    p_min = min(prices)*0.9998 if prices else 1.0
    p_max = max(prices)*1.0002 if prices else 1.001
    p_rng = p_max - p_min or 0.001

    def p2y(p):
        return max(5, min(H-5, int(H-1-(float(p)-p_min)/p_rng*(H-20))-10))

    CL, CR = 10, W-10
    if candles:
        shown = candles[-60:]
        step  = max(1, (CR-CL)//len(shown))
        cw    = max(2, step-1)
        for i, c in enumerate(shown):
            try:
                o=float(c.get("open",0)); h=float(c.get("high",0))
                l=float(c.get("low",0));  cl=float(c.get("close",0))
            except: continue
            if not o: continue
            x   = CL + i*step
            col = BULL if cl >= o else BEAR
            vline(x+cw//2, min(p2y(h),p2y(l)), max(p2y(h),p2y(l)), col)
            y0,y1 = min(p2y(o),p2y(cl)), max(p2y(o),p2y(cl))
            for bx in range(x, min(x+cw, W)):
                for by in range(y0, y1+1): px(bx, by, col)
    else:
        hline(H//2, CL, CR, (80,80,120), 2)

    if entry: hline(p2y(entry), CL, CR, GOLD, 2)
    if sl:    hline(p2y(sl),    CL, CR, RED,   1)
    if tp:    hline(p2y(tp),    CL, CR, GREEN,  1)

    dir_col = GREEN if direction == "BUY" else RED
    hline(2, 0, W-1, dir_col, 6)

    score_w   = int((min(score,100)/100)*W)
    score_col = GREEN if score>=65 else GOLD if score>=62 else RED
    hline(H-4, 0, score_w, score_col, 4)

    write_png(out_path, pixels, W, H)


def sf(v, d=0.0):
    try:
        f=float(v); return d if math.isnan(f) or math.isinf(f) else f
    except: return d


def load_candles(pair, tf):
    path = CACHE / f"{pair}_{tf}.json"
    if not path.exists(): return []
    try:
        with open(path) as f: raw = json.load(f)
        if "rows" in raw: return raw["rows"]
        r = raw.get("chart",{}).get("result",[{}])[0]
        ts = r.get("timestamp",[])
        q  = r.get("indicators",{}).get("quote",[{}])[0]
        return [{"time":t,"open":q.get("open",[None])[i],"high":q.get("high",[None])[i],
                 "low":q.get("low",[None])[i],"close":q.get("close",[None])[i]}
                for i,t in enumerate(ts)]
    except: return []


def main():
    if len(sys.argv)==2 and not sys.argv[1].startswith("-"):
        pair    = sys.argv[1]
        candles = load_candles(pair,"M15")
        entry   = sf(candles[-1].get("close")) if candles else 1.0850
        sl, tp  = entry*0.999, entry*1.002
        out     = str(CHARTS/f"sanity_{pair}.png")
        make_chart_png(out, pair,"M15","BUY",entry,sl,tp,70.0,candles)
        print(f"[chart] OK → {out}")
        return

    ap = argparse.ArgumentParser()
    ap.add_argument("--pair",      default="EURUSD")
    ap.add_argument("--tf",        default="M15")
    ap.add_argument("--direction", default="BUY")
    ap.add_argument("--entry",     type=float, default=0)
    ap.add_argument("--sl",        type=float, default=0)
    ap.add_argument("--tp",        type=float, default=0)
    ap.add_argument("--confidence", type=float, default=65)
    ap.add_argument("--score",     type=float, default=65)
    ap.add_argument("--out",       default="")
    args = ap.parse_args()

    candles = load_candles(args.pair, args.tf)
    if not args.out:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        args.out = str(CHARTS/f"{args.pair}_{args.direction}_{ts}.png")

    make_chart_png(args.out, args.pair, args.tf, args.direction.upper(),
                   args.entry, args.sl, args.tp, args.score, candles)
    print(args.out)


if __name__ == "__main__":
    main()
