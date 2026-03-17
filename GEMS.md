# BotA GEMS LIST — 39 gems as of batch 10 (98 files reviewed)
# Format: # | SOURCE FILE | WHAT | PRIORITY
# Priority: 🔴 HIGH | 🟡 MED | 🟢 LOW | 📖 REF
# Status: CANDIDATE | ⭐KEPT

1  | news.py              | Event risk flag — detect NFP/CPI/FOMC in live news          | 🔴 HIGH
2  | scoring.py           | EMA200 macro trend filter                                    | 🟡 MED
3  | scoring.py           | Struct component — swing deviation proxy, noise filter       | 🟡 MED
4  | chart.py             | EMA20/50/200 overlays on Telegram charts                     | 🟢 LOW
5  | news.py              | Historical event impact CSV — mean pips per event type       | 🟢 LOW
6  | news_providers.py    | Google News RSS — no API key, per-symbol queries             | 🟢 LOW
7  | news_weight.py       | Time-weighted news decay — fresh news counts more            | 🟡 MED
8  | news_log.py          | News CSV logging schema with event_risk column               | 🟡 MED
9  | sanitize_csv.py      | CSV repair tool — fixes malformed rows, atomic write         | 🟢 LOW
10 | tilt_apply.py        | News-tilted combined scoring — tech + news blend             | 🟡 MED
11 | card_templates.py    | Rich Telegram cards with stars, icons, bold, entry/TP/SL    | 🔴 HIGH
12 | signal_logger.py     | Append-only JSON signal log per day per source               | 🟢 LOW
14 | multi_tf.py          | H1/H4/D1 EMA20/50 + RSI snapshot — MTF foundation           | 🔴 HIGH
15 | risk_filter.py       | Pip-level SL/TP validation — min pips, min RR, max spread   | 🟡 MED
16 | news_fetch.py        | In-process per-provider per-minute rate throttle             | 🟢 LOW
17 | tech_engine.py       | Low-limit MTF bar counts — H1=20, H4=20, D1=100             | 📖 REF
18 | signal_h5_sent.py    | MTF scoring 0-16 across 5m/1h/5h/1d — A5 blueprint          | 🔴 HIGH
19 | smart_signal.py      | Fibonacci scoring + H4 ATR TP/SL + direction flip cooldown   | 🟡 MED
20 | tf_confluence.py     | MTF confluence merger — clean JSON in/out contract           | 🔴 HIGH
21 | digest_utils.py      | Duplicate-proof daily digest with SHA256 checksum            | 🟢 LOW
22 | market_clock.py      | Zero-dep countdown to London/NY open                         | 🟢 LOW
23 | lib_utils.py         | Atomic JSON writes, file lock, FX hours, dedup hash          | 🔴 HIGH ⭐KEPT
24 | status_card.py       | Full bot health card with PID, heartbeat, countdowns         | 🔴 HIGH ⭐KEPT
25 | weekend_guard.py     | Rollover mute 21:59-22:05 UTC — surgical 6 minutes           | 🟡 MED
26 | anti_dupe_gate.py    | Pair+tf+direction duplicate gate with JSON state             | 🟡 MED
27 | signal_format.py     | format_brief() with "+N more" tag truncation                 | 🟢 LOW
28 | tz_helper.py         | Android timezone via getprop — Termux local time             | 🟢 LOW
29 | fetch_candles.py.bak | Yahoo/TwelveData/AlphaVantage/Finnhub/Stooq reference        | 📖 REF
30 | telegrambot.py       | Pure stdlib urllib Telegram sender — zero deps               | 🟢 LOW
31 | fetch_multi.py       | EODHD + Polygon providers — 2 new free/cheap sources         | 🔴 HIGH
32 | analyze_last50.py    | Signal blocker diagnostic — shows why ADX/RSI/MACD blocked  | 🟡 MED
33 | backtest_params.py   | Multi-config backtester — Current/Institutional/Aggressive   | 🟡 MED
34 | runner_backtest.py   | Full Wilder ADX backtester — matches production exactly      | 🔴 HIGH
35 | duplicates.py        | Candle-time + direction duplicate suppressor, atomic JSON    | 🟡 MED
36 | market_hours.py      | is_market_open() with holiday file support                   | 🟡 MED
37 | news_filter_real.py  | Finnhub news gate — blocks 60min around red events           | 🔴 HIGH
38 | risk_reward.py       | Pure numpy ATR + RR gate — lightweight, no pandas            | 🟡 MED
39 | ind_bridge.py        | normalize_for_card() — universal indicator payload bridge    | 🟡 MED

# SUMMARY
# 🔴 HIGH (11): 1,11,14,18,20,23,24,31,34,37,39... move the needle
# 🟡 MED (14): 2,3,7,8,10,15,19,25,26,32,33,35,36,38
# 🟢 LOW (12): 4,5,6,9,12,16,21,22,27,28,30
# 📖 REF  (2): 17,29
# REVIEWED: 98 files | REMAINING: 421 | NEXT BATCH: 11

40 | indicators_ext.py | Stable analyze_indicators() API — pandas/numpy, could replace scoring_engine inline Python | 🔴 HIGH
41 | net_mode.py       | Ship/land/cache network toggle — zero deps, Termux-aware                                  | 🟡 MED
42 | ohlc_fix.py       | Robust OHLC payload normalizer across providers — needed for GEM 31 (EODHD/Polygon)        | 🟡 MED
43 | risk_engine.py    | Position sizing dataclass — balance, risk%, lot size, SL/ATR mult                          | 🟡 MED

# SUMMARY UPDATE
# Batch 11 complete: 12 files reviewed, 4 gems, 8 archived
# REVIEWED: 110 files | REMAINING: 409 | NEXT BATCH: 12
44 | recalc_targets.py | ATR-based SL/TP1/TP2/TP3 recalculator with env overrides — useful for target optimization | 🟡 MED
45 | data_quality.py   | TF-to-minutes mapper + data validation — clean reusable utility                            | 🟡 MED
46 | trades_report.py  | R-multiple/ATR/score bucketing report — complements trade_summary.py                       | 🟡 MED
47 | env_loader.py     | Authoritative env loader, normalizes key aliases — solves TOKEN aliasing problem              | 🔴 HIGH

# SUMMARY UPDATE
# Batch 12 complete: 11 files reviewed, 4 gems, 7 archived
# REVIEWED: 121 files | REMAINING: 398 | NEXT BATCH: 13

48 | final_runner.py       | Full MTF signal generator — H1/H4/D1 votes, inside-day, ADX, breakout, news gate, SL/TP | 🔴 HIGH
49 | providers.py          | Unified OHLC fetcher — Yahoo/AV/TwelveData, retry, cache, SSL toggle, PROVIDER_ORDER env  | 🔴 HIGH
50 | adaptive_frequency.py | ATR-based TF switcher H1→M15→M5→M1 with API quota guard — extract THRESHOLDS only        | 🟡 MED
51 | news_monitor.py       | Hardcoded NFP/CPI/FOMC schedule with UTC times — feeds GEM 37 news gate                   | 🔴 HIGH

# SUMMARY UPDATE
# Batch 13 complete: 10 files reviewed, 4 gems, 6 archived
# REVIEWED: 131 files | REMAINING: 388 | NEXT BATCH: 14

52 | tg_control.py         | Single-instance lock + heartbeat stale alert (1hr cooldown) — extract watchdog pattern | 🟡 MED
53 | atr_sltp_conservative.py | ATR SL/TP with pip caps (max 20 SL/40 TP) — protects against NFP spike SL blowout  | 🟡 MED

# SUMMARY UPDATE
# Batch 14 complete: 10 files reviewed, 2 gems, 8 archived
# REVIEWED: 141 files | REMAINING: 378 | NEXT BATCH: 15

54 | backtest_with_rsi.py | RSI extremes filter — skip BUY>70/SELL<30, comparison vs baseline | 🟡 MED

# SUMMARY UPDATE
# Batch 15 complete: 10 files reviewed, 1 gem, 9 archived
# REVIEWED: 151 files | REMAINING: 368 | NEXT BATCH: 16

55 | strategy_v2_hybrid.py | H4 trend + Bollinger Band entry (buy lower BB dip / sell upper BB rally) + vol guard | 🟡 MED

# SUMMARY UPDATE
# Batch 16 complete: 10 files reviewed, 1 gem, 9 archived
# REVIEWED: 161 files | REMAINING: 358 | NEXT BATCH: 17

56 | performance_tracker.py          | Daily/weekly/monthly P&L tracker with profit factor + Telegram formatter | 🟡 MED
57 | backtest_eurusd_sessions.py      | Session filter analysis — London/NY 13-17 UTC, hour distribution chart   | 🟡 MED
58 | backtest_gbpusd_eurusd_params.py | Cross-pair param validation — BB+RSI+ADX with profit factor comparison   | 🟡 MED
59 | backtest_v2_extended.py          | 5000-bar backtest with max drawdown via cumulative.cummax()              | 🟡 MED

# SUMMARY UPDATE
# Batch 17 complete: 10 files reviewed, 4 gems, 6 archived
# REVIEWED: 171 files | REMAINING: 348 | NEXT BATCH: 18

60 | pause_guard.py | Daily R-based trading pause — writes pause file if pair hits -3R today | 🔴 HIGH
61 | cache_show.py  | Cache debug viewer — lists all cache JSON files with timestamp/vote/close | 🟢 LOW

# SUMMARY UPDATE
# Batch 18 complete: 10 files reviewed, 2 gems, 8 archived
# REVIEWED: 181 files | REMAINING: 338 | NEXT BATCH: 19

62 | data_fetch.py    | Parses run.log for H1/H4/D1 snapshot blocks, writes cache/{PAIR}.txt | 🟡 MED
63 | tp_sl_policy.py  | Snaps ATR SL/TP to nearest 3-point swing within 0.5×ATR window       | 🟡 MED
64 | diag_twelvedata.py | TwelveData diagnostic — tests both EURUSD/EUR/USD formats, H1/H4/D1 | 🟢 LOW

# SUMMARY UPDATE
# Batch 19 complete: 10 files reviewed, 3 gems, 7 archived
# REVIEWED: 191 files | REMAINING: 328 | NEXT BATCH: 20

65 | telegram_push.py  | Dual-transport Telegram sender (requests+urllib fallback), stdin/argv | 🟡 MED
66 | diag_yahoo.py     | Yahoo Finance diagnostic — stdlib only, mirrors GEM64 for Yahoo       | 🟢 LOW
67 | metrics_signals.py | alert.log actionability rate, median/p95 weight, live candidate count | 🟡 MED

# SUMMARY UPDATE
# Batch 20 complete: 10 files reviewed, 3 gems, 1 keep, 6 archived
# REVIEWED: 201 files | REMAINING: 318 | NEXT BATCH: 21

68 | status_pretty.py | PairSnapshot dataclass formatter — basic/advanced Telegram output, 4096 safety trim | 🟡 MED
69 | ta_calc.py        | Pure-Python TA engine — EMA9/21 RSI14 MACD weighted score, no deps, CLI          | 🔴 HIGH

# SUMMARY UPDATE
# Batch 21 complete: 10 files reviewed, 2 gems, 8 archived
# REVIEWED: 211 files | REMAINING: 308 | NEXT BATCH: 22

70 | indicators.py                 | Pure Python EMA+RSI with Wilder smoothing, no deps, library form        | 🟡 MED
71 | provider_limits.py            | Per-provider rate-limit registry, JSON persistence, atomic write        | 🟡 MED
72 | data_provider_alphavantage.py | AV FX_INTRADAY provider, handles Note/Information rate-limit responses  | 🟡 MED
73 | data_provider_finnhub.py      | Finnhub OANDA provider, retry+backoff, epoch timestamps                 | 🟡 MED
74 | data_provider_twelvedata.py   | TwelveData stdlib-only, status:error handling, newest-first reversal   | 🟡 MED
75 | runner_confluence.py          | M15 signal runner with daily trade cap, provider chain TwelveData→AV→Yahoo | 🔴 HIGH

# SUMMARY UPDATE
# Batch 22 complete: 10 files reviewed, 6 gems, 4 archived
# REVIEWED: 221 files | REMAINING: 298 | NEXT BATCH: 23

76 | risk_manager.py   | 4-AI audited config module — daily cap, weekend guard, market block, news blackout as env flags, UTC-safe | 🟡 MED
77 | provider_mux.py   | 4-AI audited full provider mux — Finnhub/TwelveData/Yahoo, TwelveData quota 8/min, symbol normalization, retry | 🔴 HIGH
78 | signal_engine.py  | Provider fallback chain + schema-stable compute_signal() — guaranteed keys, normalizes all provider formats    | 🟡 MED

# SUMMARY UPDATE
# Batch 23 complete: 12 files reviewed, 3 gems, 9 archived
# REVIEWED: 233 files | REMAINING: 286 | NEXT BATCH: 24

79 | quota_guard.sh | Token-bucket + daily-cap guard for API providers — called by run_signal_once.py, exit codes 0=allowed | 🟡 MED

80 | emit_snapshot.py    | Resilient snapshot emitter, called by run_pair.sh, dual-symbol TwelveData+Yahoo, 238 lines | 🟡 MED
81 | run_signal_once.py  | Core Stage-1 scalping logic with Telegram alerts, called by run_signal_routed.sh, 653 lines | 🔴 HIGH

82 | send_tg.sh          | Telegram sender with dedupe + HTML sanitization, called by run_signal_once.py, 223 lines | 🔴 HIGH
83 | data_fetch_candles.sh | Candle data fetcher, called by indicators_updater.sh (live cron), 333 lines | 🟡 MED

84 | indicators_updater.sh | Core cache updater, directly in cron 13,28,43,58, calls data_fetch_candles.sh, 229 lines | 🔴 HIGH

85 | market_open.sh      | DST-aware FX market gate, in cron */15 gating watcher, called by scoring_engine.sh, sanity protected, 58 lines | 🔴 HIGH
86 | quality_filter.py   | Signal quality filter, called by signal_watcher_pro.sh + m15_h1_fusion.sh, sanity protected, 291 lines | 🔴 HIGH
87 | signal_accuracy.py  | Weekly accuracy reporter, cron Sunday 01:00, sanity protected, 342 lines | 🟡 MED

88 | signal_watcher_pro.sh  | Core signal engine, cron */15, 925 lines | 🔴 HIGH
89 | scoring_engine.sh      | Signal scorer, called by signal_watcher_pro + m15_h1_fusion, 412 lines | 🔴 HIGH
90 | m15_h1_fusion.sh       | M15/H1 fusion engine, called by signal_watcher_pro, 266 lines | 🔴 HIGH
91 | alerts_to_trades.py    | Trade simulator, cron Sunday + daily 06:00, 101 lines | 🔴 HIGH
92 | chart_generator.py     | Chart PNG generator, sanity protected, 4 callers, 271 lines | 🟡 MED
93 | daily_summary.sh       | Daily digest, cron 23:59, 163 lines | 🟡 MED
94 | provider_health_check.sh | Provider health checker, cron after updater, 27 lines | 🟡 MED
95 | news_sentiment.py      | RSS macro sentiment engine, called by m15_h1_fusion, 873 lines | 🟡 MED
96 | sanity_check.sh        | Full system sanity checker, 18 tests, session protected, 287 lines | 🔴 HIGH
97 | auditor.py             | Trade simulator engine, called by alerts_to_trades.py, 444 lines | 🟡 MED
GEM-98 | HIGH ✅ IMPLEMENTED 2026-03-03 | H1 veto may block valid high-score signals (91.00 blocked 2026-03-03 London open) — Basic 8 plan = real-time data, no delay. H1 veto issue is last-closed-candle timing at session open. Rate limit 6-8/min is borderline — monitor for silent rejections | PENDING
GEM-99 | MED ⏳ PENDING 1/5 confirmations | RSI exhaustion filter — high score (90+) with RSI<20 on H4 may indicate move exhaustion not continuation. Evidence: signal #13 2026-03-03 score=95.90 entry=1.15540 SL hit after bounce from low. Consider adding RSI floor warning when H4 RSI<22 | PENDING

## GEM-110: H1_neutral veto (2026-03-10)
Blocking H1_trend_neutral signals was the single biggest quality fix.
Previously veto="false" on neutral — signals fired with no H1 confirmation.
Change: m15_h1_fusion.sh line 245, veto="true" under H1_trend_neutral block.
Expected to cut signal volume 60-70% but improve win rate significantly.

## GEM-111: Score threshold raised to 70/75 (2026-03-10)
strategy.env: YELLOW=70, GREEN=75 (was 62/65)
Eliminates dead zone signals that were borderline quality.

## GEM-112: supabase_publish.py (2026-03-10)
stdlib-only urllib, no pip needed. Called from signal_watcher_pro.sh
after successful Telegram send. Uses SUPABASE_SERVICE_KEY from strategy.env.

## GEM-113: H1_neutral veto had TWO missing branches (2026-03-10)
First patch only fixed the h1_dir=HOLD branch (line 247).
Second patch fixed h1_filter_rejected branch (line 216).
Both branches were leaving veto="false" when H1 data was rejected or neutral.
Always check ALL branches when patching veto logic — grep for every
occurrence of the tag being patched, not just the one you expect.

## GEM-114: printf format string corruption (2026-03-13)
When patching bash files via python3 -c with heredoc strings, printf format
strings like '%s\n' can get corrupted to '%s     ' (trailing spaces).
The spaces cause arithmetic comparisons to silently fail — variable gets
set to "85   " and (( 85    >= 85 )) evaluates false in bash.
Always verify printf patterns after patching: grep -n "printf.*varname" file.sh
Fix: always deliver full file via cat <<'EOF' instead of in-place python patches.

## GEM-115: Session filtering added (2026-03-16)
Restricted signal generation to London + NY sessions only (07:00-20:00 UTC).
All logic moved to UTC to avoid DST/timezone confusion bugs.
Previously signals fired during Asian session — low liquidity, range-bound.
Override: SKIP_SESSION_FILTER=1 in strategy.env for testing.
Expected improvement: +5-10% win rate.

## GEM-116: Bollinger Bands scoring added (2026-03-16)
Added bb_comp to scoring_engine.sh (max +8, min -10).
BB values computed in build_indicators.py (20-period, 2 std).
Backtest result: EURUSD +4.8% WR, GBPUSD +5.1% WR over 90 days.
Logic: squeeze=-10, band_touch+confluence=+8, midline_align=+3, counter=-5.

## GEM-117: H4 guard on H1 neutral override (2026-03-16)
H1 neutral override at score>=85 was allowing M15 signals against H4 trend.
Fixed: pre-fetch H4 direction from indicators cache before H1 fusion logic.
Override now blocked when H4 opposes M15 direction regardless of score.
Lesson: today's EURUSD BUY at 1.15018 fired against H4 SELL — was a loss.

## GEM-118: Tier 1 scoring improvements (2026-03-17)
Added 3 new scoring components to live bot:
1. News alignment: macro6 → asymmetric score adj (-15 to +10) in m15_h1_fusion.sh
2. Session quality: overlap=+5, single session=+2, edge=0 in scoring_engine.sh
3. Tick volume: high=+5, low=-3, normal=0 in scoring_engine.sh
Backtest result (30 days): GBPUSD -112p → +54p (+166p), WR 28.6% → 41.7%

## GEM-119: OANDA Labs calendar requires live account (2026-03-17)
calendar_guard.py built but OANDA /labs/v1/calendar returns 403 on practice accounts.
Script fails open (block=false) so trading is not affected.
Alternative: Forex Factory RSS calendar parsing — defer to post-ship.

## GEM-120: Calendar guard v3 live (2026-03-17)
Uses Global Economic Calendar API (RapidAPI/serifcolakel) free tier.
50 events checked per call. Blocks HIGH (30min before/60min after) and
MEDIUM (15min before/30min after) impact events for pair currencies.
Key stored as RAPIDAPI_CALENDAR_KEY in all 3 env files.
Wired into signal_watcher_pro.sh after news_filter_real.py gate.
Fails open if API unavailable — trading continues unaffected.

## GEM-121: Calendar guard v4 — TradingEconomics guest (2026-03-17)
Primary: TradingEconomics guest:guest — completely free, no key needed.
Returns HIGH impact events only (importance=3). 3 events checked per call.
Fallback: RapidAPI (RAPIDAPI_CALENDAR_KEY) if TE returns empty.
Expected WR improvement from calendar blocking: +2-5%.

## GEM-122: S/R proximity scoring (2026-03-17)
sr_score.py detects swing highs/lows from H1 cache.
Score: +8 at key level, +5 near, +3 mild, 0 neutral, -5/-8 opposing zone.
Pre-computed in bash as SR_COMP, read by Python scoring block via os.environ.
Only activates when ADX>20 (regime gate) — correct behavior.
