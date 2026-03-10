# BotA — Live Pipeline Architecture
# Last updated: 2026-03-01

## Cron Spine
*/15  → signal_watcher_pro.sh     # Core engine, fires every 15min
13,28,43,58 → indicators_updater.sh # Cache updater, fires before watcher
0 6 * * *   → alerts_to_trades.py  # Daily trade simulation
5 6 * * *   → pause_guard.py       # Daily -3R circuit breaker
0 1 * * 0   → alerts_to_trades.py  # Weekly full run
0 1 * * 0   → signal_accuracy.py   # Weekly accuracy report
59 23 * * * → daily_summary.sh     # Daily digest
4 * * * *   → autostatus.sh        # Hourly status to Telegram

## Signal Flow
signal_watcher_pro.sh
  → market_open.sh          # DST-aware FX gate (dead zone 21:30-23:00 UTC)
  → pause_guard check       # state/pause file per pair (-3R block)
  → news_filter_real.py     # 60min block around NFP/CPI/FOMC
  → scoring_engine.sh       # A3 scorer: EMA+RSI+MACD+ADX, HOLD if ADX<20
  → m15_h1_fusion.sh        # H1 veto + H4/D1 MTF veto + macro6 injection
  → quality_filter.py       # Trend penalty, score gate
  → send_tg.sh              # Dedupe + HTML sanitize + Telegram send

## Data Flow
indicators_updater.sh
  → data_fetch_candles.sh   # Fetches OHLC from TwelveData/Yahoo
  → cache/indicators_*.json # Consumed by scoring_engine.sh

emit_snapshot.py            # H1/H4/D1 EMA/RSI/MACD/vote snapshot
  → used by autostatus.sh and m15_h1_fusion.sh MTF veto

## Key Files
logs/alerts.csv             # All signals (628 clean rows after 2026-02-28 cleanup)
logs/trades.csv             # Simulated trade outcomes
state/pause                 # Pairs blocked by -3R circuit breaker
cache/indicators_*.json     # Live indicator cache

## Gate Stack (in order)
1. Market closed → HOLD
2. Pair paused (-3R) → SKIP
3. News event (60min window) → SKIP
4. ADX < 20 (ranging) → HOLD
5. H1 trend opposite → VETO
6. H4 + D1 both oppose → VETO
7. Score < 62 → REJECT
8. Quality filter → penalty/reject

## Active Pairs
EURUSD, GBPUSD (USDJPY removed 2026-02-26)

## Validated Performance (2026-03-01)
Best config: ADX>=20 + H1 not-opposite + score>=65
WR: 53.3% | Pips: +252.5 | Signals: 91 (from 628 clean)
