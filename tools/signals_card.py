#!/usr/bin/env python3
import os, json, time, requests
from pathlib import Path

BASE = Path.home() / "bot-a"
ACC  = BASE / "data" / "accuracy_daily.json"

BOT  = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")

def send(msg):
  if not (BOT and CHAT):
    print("No Telegram env; printing:\n", msg); return
  url = f"https://api.telegram.org/bot{BOT}/sendMessage"
  requests.post(url, json={"chat_id": CHAT, "text": msg, "parse_mode":"HTML"})

def main():
  now = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
  if ACC.exists():
    d = eval(ACC.read_text())
  else:
    d = dict(analyzed=0,wins=0,winrate=0.0,horizon_min=240,take_pips=15)
  msg = []
  msg.append("📊 <b>Signals Performance</b>")
  msg.append(f"🕒 {now}")
  msg.append(f"• Analyzed: {d['analyzed']}")
  msg.append(f"• Wins: {d['wins']}")
  msg.append(f"• Win rate: {d['winrate']}%")
  msg.append(f"• Horizon: {d['horizon_min']} min, Take: {d['take_pips']} pips")
  send("\n".join(msg))

if __name__ == "__main__":
  main()
