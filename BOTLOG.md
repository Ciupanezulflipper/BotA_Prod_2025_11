# BotA — Master Log
# Single source of truth. Read this at the start of every session.
# Update after every fix: state, assumptions, changelog, issues.

---

## CURRENT STATE (2026-03-01)
- Bot: READY for Monday market open
- Pairs: EURUSD, GBPUSD
- Sanity: 18/18 PASS
- Last commit: 3e4aa1e
- alerts.csv: 628 clean rows (backup: alerts.csv.bak_20260228)
- Validated WR: 53.3% | +252.5 pips (ADX>=20 + H1 not-opposite + score>=65)

---

## ACTIVE CONFIG
- FILTER_SCORE_MIN=62 | TELEGRAM_TIER_GREEN_MIN=65
- ADX gate: HOLD if ADX<20 (scoring_engine.sh line 367)
- H1 veto + H4/D1 MTF veto (m15_h1_fusion.sh line 259)
- News gate: 60min block NFP/CPI/FOMC (news_filter_real.py)
- Pause guard: cron 06:05 (-3R circuit breaker)
- Pip caps: 20 SL / 40 TP (scoring_engine.sh)

---

## GATE STACK (in order)
1. Market closed → HOLD
2. Pair paused (-3R) → SKIP
3. News event 60min window → SKIP
4. ADX < 20 ranging → HOLD
5. H1 trend opposite → VETO
6. H4 + D1 both oppose → VETO
7. Score < 62 → REJECT
8. Quality filter penalty/reject

---

## PROTECTED FILES — never edit without reading first + sanity after
- tools/signal_watcher_pro.sh
- tools/scoring_engine.sh
- tools/m15_h1_fusion.sh
- tools/quality_filter.py
- tools/send_tg.sh
- logs/alerts.csv

---

## ISSUES

| ID | Sev | Status | Component | Description | Fixed |
|----|-----|--------|-----------|-------------|-------|
| I-F01 | 🔴 | FIXED | scoring_engine | _adx_regime unbound crash | 2026-02-26 |
| I-F02 | 🔴 | FIXED | cron | USDJPY causing losses | 2026-02-26 |
| I-F03 | 🔴 | FIXED | cron | FILTER_SCORE_MIN not set | 2026-02-26 |
| I-F04 | 🟡 | FIXED | market_open | Dead zone 21:30-23:00 missing | 2026-02-26 |
| I-F05 | 🟡 | FIXED | quality_filter | Trend penalty missing | 2026-02-26 |
| I-F06 | 🟡 | FIXED | indicators_updater | Updater firing after watcher | 2026-02-26 |
| I-02 | 🔴 | FIXED | alerts_to_trades | --since filter — already correct | 2026-02-28 |
| I-03 | 🔴 | FIXED | alerts.csv | 24 duplicate rows removed | 2026-02-28 |
| I-04 | 🔴 | FIXED | scoring_engine | ADX hard gate HOLD if ADX<20 | 2026-02-28 |
| I-05 | 🟡 | FIXED | cache_show | Schema mismatch fixed | 2026-03-01 |
| I-06 | 🟡 | WONT_FIX | indicators_updater | Weekend STALE correct behavior | 2026-03-01 |
| I-07 | 🟡 | WONT_FIX | alerts.csv | SL/TP formats consistent 0 mismatches | 2026-03-01 |
| I-08 | 🟡 | WONT_FIX | signal pipeline | 1 divergence in 181 signals | 2026-03-01 |
| I-09 | 🟡 | FIXED | alerts.csv | 4372 contaminated rows removed | 2026-02-28 |
| I-10 | 🟡 | FIXED | pause_guard | -3R circuit breaker wired | 2026-02-28 |
| I-11 | 🟡 | FIXED | news gate | NFP/CPI/FOMC blocked | 2026-02-28 |
| I-12 | 🟢 | WONT_FIX | TOOLS_REGISTRY | Substring bug cosmetic only | 2026-02-27 |
| I-13 | 🟢 | FIXED | alerts.csv | USDJPY/EURJPY 1168 rows removed | 2026-02-28 |
| I-14 | 🟢 | FIXED | alerts.csv | 448 UNKNOWN/HOLD rows removed | 2026-02-28 |

---

## CHANGELOG

### 2026-03-01 — SESSION END (final)
- Deleted 158 legacy files / 86,680 lines from root (pre-audit artifacts, old runners, junk)
- Fixed signal_watcher_pro.sh PAIRS default (removed USDJPY/EURJPY)
- All old notes reviewed and erased — everything integrated into BOTLOG.md
- Repo root now clean: tools/ logs/ cache/ config/ docs/ archive/ BOTLOG.md GEMS.md

### 2026-03-01 — SESSION END (updated)
- Fixed signal_watcher_pro.sh line 121: PAIRS default had stale USDJPY/EURJPY
- All old notes reviewed and erased — everything integrated into BOTLOG.md

### 2026-03-01 — SESSION END
- Wired: ADX gate, pause guard, news gate, pip caps, MTF H4+D1
- Fixed: autostatus 2025 dummy data, strategy.env stale config
- Cleaned: alerts.csv 5000→628 rows
- Closed: I-02,03,04,05,06,07,08,09,10,11,13,14 (10 issues)
- Validated: 53.3% WR +252.5 pips backtest
- Consolidated: BOTLOG.md single source of truth
- Sanity: 18/18 PASS
- Next session: monitor Monday live signals, check ADX/news/MTF gate logs, review first real WR

### 2026-03-01
- Fixed strategy.env: PAIRS cleaned (removed USDJPY/EURJPY/XAUUSD), TELEGRAM_MIN_SCORE 20→62
- Added coding rule to BOTLOG: always wrap Python in python3 << EOF block
- Fixed autostatus.sh: wired emit_snapshot.py, was showing hardcoded 2025 dummy data
- Closed I-05, I-06, I-07, I-08
- Backtest validated: 53.3% WR +252.5 pips
- Created BOTLOG.md (consolidated SESSION/ISSUES/CHANGELOG/ASSUMPTIONS)

### 2026-02-28
- Wired GEM 89 ADX hard gate, GEM 60 pause guard, GEM 37 news gate
- Wired GEM 53 pip caps, GEM 14/20 MTF H4+D1 veto
- Cleaned alerts.csv 5000→628 rows
- Closed I-02, I-03, I-04, I-09, I-10, I-11, I-13, I-14

### 2026-02-26/27
- Full 519-file audit complete, 97 gems catalogued
- Fixed I-F01 through I-F06
- GEMS.md, ISSUES.md created

---

## CODING RULES — MISTAKES TO AVOID
| Date | Mistake | Fix |
|------|---------|-----|
| 2026-03-01 | Sent Python code without python3 << EOF wrapper — ran as bash, exploded | Always wrap multi-line Python in: python3 << 'EOF' ... EOF |
| 2026-03-01 | strategy.env had stale PAIRS and wrong TELEGRAM_MIN_SCORE — never checked | Always verify config files match cron at session start |
| 2026-03-01 | Python code sent without python3 << EOF wrapper — ran as bash twice | Always write Python to ~/script.py first, then python3 ~/script.py. Never use python3 << EOF in chat |
| 2026-03-01 | Comment inside heredoc broke Python syntax | Never put plain text comments inside python3 << EOF blocks |
| 2026-03-01 | Used /tmp/ path — does not exist in Termux | Always use ~/  for temp files in Termux, never /tmp/ |
| 2026-03-01 | grep "429" matched "429 rows" not HTTP 429 | Always grep for "HTTP.*429" or "status.*429" not bare "429" |
| 2026-03-01 | Stated wrong market open times multiple times across instances | Never guess time — always call user_time tool first. Forex sessions: Sydney 22:00, Tokyo 00:00, London 08:00, NY 13:00, Close 22:00 UTC |
| 2026-03-01 | JSON appended into Python code stream via heredoc | Never mix JSON/bash variables into python3 heredoc blocks |

## ASSUMPTIONS LOG
| Date | Assumption | Verified | Result |
|------|-----------|----------|--------|
| 2026-03-01 | I-02 already fixed | YES | Confirmed |
| 2026-03-01 | I-06 weekend STALE not a bug | YES | Confirmed |
| 2026-03-01 | I-07 SL/TP formats consistent | YES | 0 mismatches |
| 2026-03-01 | I-08 divergence not a problem | YES | 1 in 181 |
| 2026-03-01 | autostatus showing dummy data | YES | status_pretty.py hardcoded |

---


---

## LESSONS FROM HISTORY — Cross-Project Audit
Extracted from TomaForexBot/BotA/CloudBot retrospectives. Integrated 2026-03-01.

### Recurring failure patterns (proven across all projects)
| Pattern | What happened | Prevention |
|---------|--------------|------------|
| Config gate blindness | TELEGRAM_MIN_SCORE=95 while scores pinned at 60 — no alerts | Compare score distribution vs threshold before blaming Telegram |
| Score pinning | scoring_engine hard-returned score=60 for all signals | After any scoring change: print min/avg/max of last 50 scores |
| Silent parameter ignore | run_fusion() ignored tf param — timeframe logic silently wrong | Any function taking (pair,tf) must use tf or explicitly reject it |
| Payload contract drift | engine output schema differed from fusion input | Validate payload keys at each hop: engine to fusion to filter to telegram |
| Multiple senders | Same signal sent by 2 scripts — Telegram spam | One canonical sender send_tg.sh — all others banned |
| Env var at import time | API key warning printed before .env loaded | Never read env vars at import time — use lazy getters |
| Threshold not calibrated | Gate set without measuring score distribution | On every scoring change: log distribution, warn if gate starves alerts |
| Feature creep before stable base | Charts/sentiment added while data fetch still broken | No new features until minimal pipeline works end-to-end |
| Demo keys used as proof | Logic correct but never proven with real keys | Always prove with real keys on Termux |
| Partial edits / patching | Mixed versions, circular fixes, repeated loops | Full file replacement only — never patch inline |

### Payload Contract (required keys at each hop)
| Stage | Required keys |
|-------|--------------|
| scoring_engine output | pair, tf, direction, score, confidence, entry, sl, tp, provider, reasons |
| m15_h1_fusion output | above + filter_rejected, filter_reasons, macro6, h1_trend |
| quality_filter output | above + tier |
| send_tg input | pair, tf, direction, score, confidence, entry, sl, tp, tier, reasons |

### Provider fallback rule
- Provider failure = HTTP error OR missing keys OR empty list OR parse exception
- Must try next provider and log which succeeded
- Never treat no data as success

### One proof artifact per debugging step
- Every fix must produce: command run + output snippet + PASS/FAIL
- It should work is never a proof

## SESSION RULES
1. Read BOTLOG.md before touching anything — state current bot status out loud
2. Verify with terminal output before editing — never assume
3. Run sanity_check.sh before AND after every change (must be 18/18)
4. Update BOTLOG.md (issues + changelog + assumptions) after every fix
5. Git commit after every fix with descriptive message referencing issue/gem
6. If uncertain about anything — check the source file before proceeding
7. After every fix — identify all downstream consumers and verify them too
8. Never assume a previous fix is still in place — grep/cat to confirm it exists
9. Never close a session with a FAIL or WARN in sanity_check.sh
10. End every session with a summary appended to BOTLOG.md changelog

## PROMPT FOR CLAUDE AT SESSION START
"Read ~/BotA/BOTLOG.md before doing anything. State current bot status, active config, and any open issues. Do not assume — verify with terminal. After every fix update BOTLOG.md, run sanity_check.sh 18/18, git commit."

### 2026-03-03 — LIVE SESSION FIXES
**Evidence-based changes from live market observation:**

| Fix | Before | After | Evidence |
|-----|--------|-------|----------|
| Cooldown | 3600s | 1800s | EURUSD score=95 blocked by cooldown during strong move |
| H1 veto override | hard veto | bypass if score≥85 AND ADX≥40 | GBPUSD score=98.20 blocked, ADX=50.8, RSI=15 |
| Sanity check | 18/18 | 19/19 | Added API credit tracker check |
| API tracker | none | api_credit_tracker.py | Basic 8 plan has no usage endpoint — local counter |

**Market conditions when fixes applied:**
- EURUSD: price=1.16252 ADX=52.6 RSI=15.3 — extreme trend
- GBPUSD: price=1.33019 ADX=50.8 RSI=15.1 — extreme trend
- Both pairs STRONG BEAR -9/9

**GEM-98 status:** Partially addressed. H1 veto now bypassed for score≥85/ADX≥40.
Full review still pending for session-open candle timing issue.

---

## 2026-03-03 — API AUDIT SESSION

### What We Investigated
Full audit of all forex data API providers configured or available for BotA.
Triggered by: discovering `data_fetch_candles.sh` uses Yahoo as primary source,
not Twelve Data as assumed from `PROVIDER_ORDER=twelve_data` in .env.

---

### CRITICAL DISCOVERY: Data Pipeline Architecture
**The bot has TWO separate data pipelines — they do NOT share the same source:**

| Pipeline | File | Provider | Used For |
|----------|------|----------|----------|
| Candle fetch | `tools/data_fetch_candles.sh` | **Yahoo Finance** (hardcoded) | Raw OHLCV cache |
| Indicator fetch | `tools/emit_snapshot.py`, `multi_tf.py`, `providers.py` | **Twelve Data** | H1/H4/D1 indicators, autostatus |

`PROVIDER_ORDER=twelve_data` in .env and `INTRADAY_ORDER` in `provider_mux.py`
are **never called** by the main signal pipeline. `provider_mux.py` exists but
is not wired into `data_fetch_candles.sh`.

**Risk:** Yahoo is the single point of failure for raw M15 candles.
**Action Required:** Rewrite `data_fetch_candles.sh` to use Twelve Data as primary.
Logged as GEM-100 — dedicated session needed.

---

### API Live Test Results — 2026-03-03 ~19:30 UTC

Tested against GBPUSD M15:

| Provider | Key Present | Result | Reason |
|----------|-------------|--------|--------|
| Yahoo Finance | No key needed | ✅ OK close=1.34016 | Unofficial scrape, working |
| Twelve Data | YES (len=32) | ❌ 403 Forbidden | Rate limit hit (66+ credits used today) |
| Alpha Vantage | YES (len=16) | ❌ Premium only | FX_INTRADAY endpoint is NOT free |
| Finnhub | YES (len=40) | ❌ 403 Forbidden | Forex candles paywalled on free tier |

**Note on Twelve Data 403:** This is a daily rate limit, NOT a plan restriction.
The same endpoint powered all signals today. Test ran after 66+ credits consumed.
Confirmed working endpoint: `api.twelvedata.com/time_series`

---

### Provider Verdicts

**✅ Twelve Data (Primary — keep)**
- Plan: Basic 8 (8 calls/min, 800/day)
- Works: M15/H1/H4/D1 indicators, autostatus, emit_snapshot.py
- Does NOT work: `api_usage` endpoint (403 on free tier — use local tracker)
- Reliability: 4.3/5 Trustpilot, ~99.95% uptime
- Action: Wire into data_fetch_candles.sh as primary (GEM-100)

**⚠️ Yahoo Finance (Emergency fallback only)**
- No API key needed — unofficial scrape of query1.finance.yahoo.com
- Currently primary for raw M15 candles (data_fetch_candles.sh)
- Breaks ~monthly, violates Yahoo ToS, cloud IPs often blocked
- Requires cookie+crumb+TLS fingerprint workarounds since mid-2023
- NEVER rely on as primary. Keep as last-resort fallback only.

**❌ Alpha Vantage (Remove from M15 pipeline)**
- Key present: YES (len=16)
- FX_INTRADAY endpoint = PREMIUM ONLY (not free)
- Free tier only supports: daily FX rates (FX_DAILY) — usable for D1 only
- Rate limit: 25 req/day on free tier
- Use case: D1 confirmation only, not M15

**❌ Finnhub (Remove from forex pipeline)**
- Key present: YES (len=40)
- Forex candles endpoint: PAYWALLED on free tier (403 confirmed)
- Data quality issues documented: random no_data, unpredictable candle counts
- Good for: stock data only
- Action: Remove from INTRADAY_ORDER in provider_mux.py

**⚠️ TraderMade (Not yet integrated — consider for H4/D1)**
- Free tier: 1,000 req/month (~33/day)
- M15 candles: supported but too few free calls for regular polling
- H4/D1: feasible — 2 pairs × 1 fetch/day = 60 calls/month
- Data source: Tier 1 bank aggregate, institutional quality
- Action: Evaluate for H4/D1 fallback if Twelve Data has issues

---

### Current Endpoint Map (As-Built)
M15 candles  → data_fetch_candles.sh → Yahoo (⚠️ fragile)
H1 indicators → emit_snapshot.py     → Twelve Data (✅ stable)
H4 indicators → multi_tf.py          → Twelve Data (✅ stable)
D1 indicators → runner_confluence.py → Twelve Data (✅ stable)
News filter   → news_filter_real.py  → Finnhub economic calendar (✅ free)
### Target Endpoint Map (After GEM-100)
M15 candles  → data_fetch_candles.sh → Twelve Data (primary) → Yahoo (fallback)
H1 indicators → emit_snapshot.py     → Twelve Data (✅ no change)
H4 indicators → multi_tf.py          → Twelve Data (✅ no change)
D1 indicators → runner_confluence.py → Twelve Data (✅ no change)
News filter   → news_filter_real.py  → Finnhub economic calendar (✅ no change)
---

### What To Avoid

1. **Never use Alpha Vantage for intraday forex** — FX_INTRADAY is premium
2. **Never use Finnhub for forex candles** — paywalled, bad data quality
3. **Never rely on Yahoo as primary** — ToS violation, breaks monthly
4. **Never assume PROVIDER_ORDER in .env controls data_fetch_candles.sh** — it does not
5. **Never test Twelve Data after heavy signal session** — 403 = rate limit not plan block
6. **Never use TraderMade for M15 polling** — 1,000/month is insufficient

---

### GEMs Raised This Session

- **GEM-100** | HIGH | Rewrite data_fetch_candles.sh to use Twelve Data primary,
  Yahoo fallback. Current Yahoo-only pipeline is single point of failure.
  Evidence: 2026-03-03 audit confirmed architecture gap. | PENDING


### 2026-03-04 — GBPUSD Deep Audit Findings

**GBPUSD direction today: BUY (diverged from EURUSD SELL)**
- GBPUSD ran opposite to EURUSD all day — genuine market divergence
- GBP strong vs USD while EUR weak vs USD
- Bot correctly identified BUY signals on GBPUSD

**GBPUSD signal log today:**
| Time | Score | Direction | Result |
|------|-------|-----------|--------|
| 09:30 | 70.30 | BUY | ❌ vetoed_by_H4_D1 |
| 09:45 | 81.30 | BUY | ❌ vetoed_by_H4_D1 |
| 10:00 | 79.40 | BUY | ❌ vetoed_by_H4_D1 |
| 10:15 | 74.20 | BUY | ❌ vetoed_by_H4_D1 |
| 13:30 | 89.80 | BUY | ✅ SENT (chart confirmed, text unconfirmed) |
| 13:45 | 79.90 | BUY | ❌ cooldown |
| 14:00 | 64.40 | BUY | ❌ vetoed_by_H4_D1 |
| 14:17 | 74.00 | BUY | ✅ SENT (chart confirmed, text unconfirmed) |
| 14:45 | 53.30 | BUY | ❌ score<62 |
| 15:00 | 0.00  | HOLD | ❌ no direction |

**PENDING INVESTIGATION: chart sent but no TELEGRAM signal text confirmed**
Need to verify if BUY signal text messages reached Telegram.

**CRITICAL: Yahoo stale bug confirmed in production**
- 2026-02-20 23:45 → stuck until 2026-02-22 (36+ hours stale)
- 2026-02-27 23:45 → stuck until 2026-03-02 (48+ hours stale)
- Bot running on days-old GBPUSD candles during these periods
- Confirms GEM-100 is URGENT — Yahoo single point of failure proven in prod


### 2026-03-04 — Chart threshold confirmed
Chart only sends for GREEN tier (score≥65).
Confirmed in signal_watcher_pro.sh line 875 and chart_generator.py line 180.
YELLOW signals (62-64) send text only, no chart image. Correct behavior.

### 2026-03-06 — Known Issue: sed multiline replacement fails on Termux
Attempted to use sed -i with \n for multiline string replacement.
Result: garbled output — \n not interpreted correctly by sed on Android/Termux.
Fix: always use Python for multiline string replacements in shell files.
Restored from .bak, fixed via Python replace().

### 2026-03-06 — Score thresholds restored to validated values
Found .env had unvalidated thresholds: FILTER_SCORE_MIN=55, TELEGRAM_TIER_GREEN_MIN=60.
Backtest was validated at 62/65 — these lower values were never tested.
Origin unknown — .env was untracked since commit 3dffe1e, change history lost.
Impact: this week's signals below 62 (YELLOW tier, no entry/SL/TP) fired on unvalidated config.
Restored: FILTER_SCORE_MIN=62, FILTER_SCORE_MIN_ALL=62, TELEGRAM_MIN_SCORE=62, TELEGRAM_TIER_YELLOW_MIN=62, TELEGRAM_TIER_GREEN_MIN=65.
Action: add .env.example to repo with correct validated values for reference.

### 2026-03-09 — GEM-100 IMPLEMENTED: OANDA primary provider
Replaced Yahoo-only data_fetch_candles.sh with OANDA primary + Yahoo fallback.
OANDA: api-fxpractice.oanda.com, account 101-001-38298682-001, M15 granularity confirmed.
Yahoo stale bug (36-48h confirmed twice in prod) now mitigated.
Provider logged in output: [FETCH] OK provider=oanda
Fallback triggers automatically if OANDA_API_TOKEN missing or fetch fails.
Credentials in .env: OANDA_API_TOKEN, OANDA_ACCOUNT_ID, OANDA_API_URL.

---
### 2026-03-10 — TERMUX RECOVERY SESSION

**Crisis:** Google Play Termux removed + F-Droid reinstall → BotA silent. All runtime state lost.

**What was lost:** .env, crontab, logs/alerts.csv, logs/ directory

**Recovery steps:**
1. Restored .env from memory + screenshots (Telegram token revoked + regenerated)
2. Installed cronie (already present, crond running as PID 32003)
3. Restored crontab from archive/cron/prod.crontab + tmp_bota_cron.txt
4. Created config/strategy.env + logs/alerts.csv (empty with correct header)
5. Rewrote tools/auditor.py — stdlib only (pandas not installable on Termux aarch64)
6. Rewrote tools/alerts_to_trades.py — stdlib only
7. Rewrote tools/chart_generator.py — pure Python PNG, no matplotlib
8. Patched chart_generator: added --confidence arg, canvas 900x480, zlib level 0

**Result:** sanity_check.sh 19/19 PASS. Bot sending signals to Telegram. ✅

**Known regressions:**
- chart_generator.py: basic candle chart only (no EMA/RSI/MACD overlays)
  Original matplotlib version in GitHub. Restore when matplotlib available.
- alerts_to_trades.py: WR=0% (0 resolved) — alerts.csv was wiped, only 60 new rows, none resolved yet

**Credentials status:**
- TELEGRAM_BOT_TOKEN: regenerated 2026-03-10 (old token revoked)
- OANDA_API_TOKEN: EXPOSED in chat — rotate at hub.oanda.com
- GitHub PAT (ghp_4vxm...): EXPOSED in chat — rotate at github.com settings
- All other API keys: EXPOSED in chat — rotate when possible

**Active signals confirmed:**
- EURUSD M15 BUY score=82 entry=1.16549 SL=1.16407 TP=1.16786 (11:30 UTC)
- GBPUSD M15 BUY score=71 entry=1.34646 SL=1.34476 TP=1.34930 (11:34 UTC)

**Next session priorities:**
1. Rotate all exposed API keys
2. Restore matplotlib chart_generator from GitHub (pip or pkg when available)
3. Monitor alerts.csv growth + WR tracking resumption
4. Git commit + push all changes from this session

### 2026-03-10 — GEM-101 IMPLEMENTED: SL/TP Hit Monitor
- tools/sltp_monitor.py — real-time SL/TP hit detection + daily summary
- Runs every 15min via cron (same cadence as signal watcher)
- Sends Telegram alert immediately when TP or SL is hit
- Daily summary at 23:50 UTC with W/L/pips/WR
- State persisted in logs/sltp_monitor_state.json (dedup safe)
- Reads only non-rejected BUY/SELL from alerts.csv
- 24h lookback window — ignores signals older than 24h
