# Bot-A: Modules and Flow

**Data**
- **/data/candles/EURUSD_M5.csv** (optional), **EURUSD_M15.csv**, **EURUSD_H1.csv**, **EURUSD_H4.csv**, **EURUSD_D1.csv**
- **fetch_candles.py** → pulls from TwelveData (working)
- Gaps: none for EURUSD candles (working); optional WebSocket not implemented.

**Signals (compute-only)**
- **explain_signal.py** — indicator math + now **latest_indicators()** and **htf_flags()** (present)
- **runner_light.py** — simple, additive scoring; sends Telegram (present)
- **runner_confluence.py** — strict original (present, OFF during training)

**Messaging**
- **Telegram**: BOT_TOKEN / CHAT_ID in `.env` (present)
- SMS: not implemented (optional)

**News logic**
- Minimal tags via Finnhub headline (present but not used in light runner)
- Missing: news veto/boost rules and provider fallback.

**Ops**
- **preflight.sh** — checks keys, data freshness, recent errors, PRD presence (present)
- Logs: `/bot-a/logs/runner_light.log` (present)
- Missing: evaluation/export of sent signals CSV.

**Config**
- `.env` — contains keys & thresholds (present)
- Missing: single `config.yaml` to centralize training thresholds and news rules.

# Missing items to finalize
- **[Missing]** Signals export: `sends.csv` append for every alert (ts,pair,tf,score,dir,notes)
- **[Missing]** News veto/boost: simple rules table (keywords + +/- score, time window)
- **[Missing]** Optional SMS sender (Twilio/other)
- **[Missing]** Backtest notebook (offline on CSV) to tune CONF_MIN
