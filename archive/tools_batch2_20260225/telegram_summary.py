#!/usr/bin/env python3
from __future__ import annotations
import os, csv, json
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
LOGS = HOME / "bot-a" / "logs"
DAILY = LOGS / "daily"

def _today_tag():
    return datetime.now(timezone.utc).strftime("%Y%m%d")

def _load_summary(day: str):
    p = DAILY / f"summary-{day}.csv"
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def _load_news_picks(day: str):
    # show quick picks: latest news items mapped by symbol from the same day file (if exists)
    p = LOGS / f"news-{day}.csv"
    if not p.exists():
        return {}
    out = {}
    with p.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            sym = (r.get("symbol") or "").upper()
            bias = (r.get("bias") or "").capitalize()
            out.setdefault(sym, {"bull":0,"bear":0})
            if bias == "Bullish":
                out[sym]["bull"] += 1
            elif bias == "Bearish":
                out[sym]["bear"] += 1
    return out

def send(chat_id: int, token: str, text: str) -> bool:
    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            _ = resp.read()
        return True
    except Exception:
        return False

def main():
    day = os.getenv("COLLECT_DAY") or _today_tag()
    sums = _load_summary(day)
    picks = _load_news_picks(day)

    total_signals = sum(int(r.get("signals") or 0) for r in sums)
    total_with_news = sum(int(r.get("with_news") or 0) for r in sums)
    avg_all = 0.0
    if total_signals:
        avg_all = sum(float(r.get("avg_score") or 0.0) * int(r.get("signals") or 0) for r in sums) / total_signals

    lines = []
    lines.append(f"📊 <b>Daily recap (UTC) {day[:4]}-{day[4:6]}-{day[6:]}</b>")
    lines.append(f"Total signals: <b>{total_signals}</b>  •  With news impact: <b>{total_with_news}</b>")
    lines.append(f"Average score <i>(news-aware)</i>: <b>{avg_all:.1f}</b>")
    lines.append("")
    lines.append("<b>By symbol</b>")
    if not sums:
        lines.append("• (no signals)")
    else:
        for r in sorted(sums, key=lambda x: (x.get('symbol') or '')):
            sym = r.get("symbol") or "?"
            cnt = int(r.get("signals") or 0)
            bull = int(r.get("bull") or 0)
            bear = int(r.get("bear") or 0)
            neut = int(r.get("neut") or 0)
            avg = float(r.get("avg_score") or 0.0)
            with_n = int(r.get("with_news") or 0)
            lines.append(f"• <b>{sym}</b>: {cnt} signals  |  ({bull}↑, {bear}↓, {neut}•)  |  avg {avg:.1f}  |  with_news {with_n}")

    if picks:
        lines.append("")
        lines.append("📰 <b>News Picks</b>")
        for sym in sorted(picks.keys()):
            bull = picks[sym]["bull"]; bear = picks[sym]["bear"]
            lines.append(f"• <b>{sym}</b>: {bull + bear} picks  ({bull}↑ / {bear}↓)")

    msg = "\n".join(lines)

    # Send if creds present
    chat = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if chat and token:
        ok = send(int(chat), token, msg)
        print("Telegram summary sent." if ok else "Telegram send failed.")
    else:
        print("DRY or missing TELEGRAM env; message would be:\n")
        print(msg)

if __name__ == "__main__":
    raise SystemExit(main())
