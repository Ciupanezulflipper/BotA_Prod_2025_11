# BotA — Forex Signal Bot

Live production bot running on Android (Termux).

## Active Config
- Pairs: EURUSD, GBPUSD
- Timeframe: M15
- Gate stack: ADX≥20 → News gate → H1 veto → H4/D1 MTF veto → Score≥62
- Pause guard: -3R daily circuit breaker
- Validated: 53.3% WR, +252.5 pips (backtest 2026-03-01)

## Documentation
- `BOTLOG.md` — master state, issues, changelog, session rules
- `GEMS.md` — 97 gems catalogued (27 HIGH, 49 MED)
- `docs/architecture.md` — full pipeline map
- `docs/backtest_20260301.md` — backtest results

## Session Start Prompt
Read ~/BotA/BOTLOG.md before doing anything. State current bot
status, active config, and open issues. After every fix: update
BOTLOG.md, run sanity_check.sh 18/18, git commit and push.

## Status
18/18 sanity checks passing. Last updated: 2026-03-01.
