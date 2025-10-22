# Bot-A Product Requirements (PRD)

## Mission
Run a Termux-based Forex assistant that analyzes EURUSD and sends Telegram alerts.

## Scope
- Use EURUSD candles (M5, M15, H1, H4, D1).
- Indicators: RSI (14), MACD (12,26,9), ADX (14).
- Simple confluence scoring.
- Telegram alerts with emojis.

## Out of Scope
- Full broker execution
- Multi-pair beyond EURUSD (for now)

## Success Metrics
- Bot runs 24/7 on Termux.
- Sends clean signals to Telegram.
- Logs every signal in `/bot-a/logs`.
