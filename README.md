# 📈 TomaiSignal – EURUSD M15 Alerts (Termux/Linux)

An institutional-style trading assistant that:
- Fetches EURUSD M15 candles (via TwelveData, with multiple fallbacks).
- Computes **RSI / ADX / MACD** confluence.
- Sends formatted alerts to **Telegram** (BUY / SELL / FLAT with confidence scores).
- Designed for **mobile (Termux)** and **low-cost VPS** deployments.

---

## ⚙️ Features
- **Multi-provider fallback** (TwelveData → AlphaVantage → Finnhub → Polygon → EODHD).
- **Institutional defaults** tuned for EURUSD scalping:
  - `ADX_MIN=14`
  - `RSI_BUY=62`, `RSI_SELL=38`
  - `MACD_MIN=3.5e-05`
  - `CONF_MIN=0.8`
- **Logging** to rotating logfiles (`~/bot-a/logs`).
- **Auto-retry** on API errors / Telegram bounces.
- Lightweight, runs fine on **Termux** (Android) or **Linux VPS**.

---

## 🚀 Quick Start (Termux/Linux)

```bash
# Clone your private repo
git clone git@github.com:<your-user>/<your-private-repo>.git
cd <your-private-repo>

# Copy and edit environment variables
cp .env.example .env
nano .env

# Install dependencies
pip install -r requirements.txt

# Test fetcher
python3 tools/fetch_multi.py    # should print "TwelveData OK: 500 rows"

# Test runner
python3 tools/runner_full.py    # should print "EURUSD M15 FLAT ..."
