# Bot-A Product Requirements (PRD)

## Mission
Run a Termux-based Forex assistant that continuously analyzes multiple FX pairs and sends **high-signal** Telegram alerts with a fail-closed pipeline (FETCH → INDICATORS → SCORE → FILTER/GATE → CSV → TELEGRAM).

## Current Operating Scope (as-built)
- **Pairs (baseline set):** EURUSD, GBPUSD, USDJPY, EURJPY
- **Primary alert TF:** M15
- **Context/confirmation TF:** H1 (trend context only; not an execution-grade signal)
- **Data source:** Yahoo Finance chart endpoint (via `tools/data_fetch_candles.sh`)
- **On-device runtime:** Termux (Android), bash + python3

## Non-Negotiables (Fail-Closed Rules)
1) **TF-specific cache only**
   - Canonical candle cache input: `cache/<PAIR>_<TF>.json`
   - Never treat `cache/<PAIR>.json` as TF-authoritative for M15/H1 logic.
   - Legacy `cache/<PAIR>.json` may exist for backward compatibility only, and must be explicitly labeled/used.

2) **Timeframe integrity gate before writing cache**
   - `tools/data_fetch_candles.sh` MUST refuse to write `cache/<PAIR>_<TF>.json` if the median timestamp delta does not match the requested TF (within tolerance).
   - On mismatch: exit code `2`, and do not overwrite cache.

3) **Indicator integrity gate**
   - `tools/build_indicators.py` MUST emit a stable JSON contract and must fail-closed on TF mismatch (`tf_ok=false`, `error=tf_mismatch`, `weak=true`).
   - Indicators must never be computed from candles whose median delta does not match the requested TF.

4) **TF-aware filtering**
   - Quality/execution filters (SL/TP present, rr>0, atr>0, volatility known, score threshold, etc.) apply to **execution TF only** (M15 in this PRD).
   - H1 is **context-only**. H1 may be “confirmable for trend” even if it is not “tradeable as an execution signal”.
   - Therefore: **Do not apply execution-grade quality_filter gates to H1** unless a dedicated H1 filter mode is implemented.

5) **Telegram HTML escaping is environment-correct**
   - Telegram messages use `parse_mode=HTML`.
   - Escape order must be: `&` first, then `<` and `>`.
   - In this Termux bash environment, replacement strings must escape `&` so entities emit literally (`\&lt;`, `\&gt;`, `\&amp;`), as proven by on-device repro.

6) **Gate/Scale Consistency (anti-silent-stall)**
   - The system MUST prove that Telegram gating thresholds are **reachable** by the current scoring scale.
   - A “gate consistency check” MUST run:
     - At process start (before entering the main loop), and
     - At least once every N cycles (default N=50), and
     - After any env reload affecting `TELEGRAM_MIN_SCORE` or scoring mode.
   - The check MUST compute (from the most recent execution-TF score history window):
     - `observed_min_score`, `observed_max_score`, `observed_mean_score`, and `observed_stddev_score`
   - **Gate impossible condition (MISCONFIG_GATE_IMPOSSIBLE):**
     - If there are at least `SAMPLES_MIN` observed scores (default 50), and
     - `TELEGRAM_MIN_SCORE > observed_max_score`,
     - Then the system MUST:
       - Fail-closed for trade alerts (no silent continue),
       - Emit an explicit reason in logs (see Logging section),
       - Mark outputs as `weak=true` with `error=gate_impossible`,
       - And produce a **diagnostic proof-of-life** artifact (heartbeat log entry) so the operator can confirm the bot is alive but blocked.
   - Trade alert gating MUST never result in “no output” without an explicit logged reason.

7) **Non-Degenerate Scoring (anti-pinned-score)**
   - Scoring MUST NOT be constant or near-constant across the execution-TF window unless market is genuinely flat AND indicators justify it.
   - A “degeneracy detector” MUST run on the same rolling score window used for gate checks.
   - **Degenerate scoring condition (SCORING_DEGENERATE):**
     - If there are at least `SAMPLES_MIN` observed scores (default 50), and
     - Either:
       - `(observed_max_score - observed_min_score) < SPREAD_MIN` (default 5), OR
       - `observed_stddev_score < STDDEV_MIN` (default 1.0),
     - Then the system MUST:
       - Fail-closed for trade alerts,
       - Emit explicit reason in logs,
       - Mark outputs as `weak=true` with `error=scoring_degenerate`,
       - And prevent “pretend-high-signal” behavior (no trade alerts until scoring becomes non-degenerate).

## Indicators (M15 + H1)
- RSI (14), MACD (12,26,9 histogram), ADX (14), ATR (14)
- EMA9 / EMA21
- Indicator bundle output file:
  - `cache/indicators_<PAIR>_<TF>.json`

### Indicator Contract (required keys)
All indicator bundles MUST contain at least:
- `pair`, `timeframe`, `price`, `age_min`
- `tf_ok`, `tf_actual_min`
- `weak`, `error`
- `ema9`, `ema21`, `rsi`, `macd_hist`, `adx`, `atr`, `atr_pips`

## Scoring + Fusion Behavior
### M15 scoring
- Produces trade direction (BUY/SELL/HOLD) + score/confidence.
- Must produce execution fields for any non-HOLD direction:
  - `entry`, `sl`, `tp`, plus derived RR and ATR checks (or explicit `filter_rr`, `filter_atr`).

### H1 scoring (context)
- Used only to label trend alignment:
  - `H1_trend_confirmed` / `H1_trend_opposite` / `H1_trend_neutral`
- H1 may omit execution fields (SL/TP/RR) because it is context, not an execution signal.

### Fusion (M15 + H1)
- `tools/m15_h1_fusion.sh` merges:
  - M15 execution signal + macro context + H1 trend label
- Fusion must never “invent” execution fields for H1.
- Fusion must log its decision in `logs/fusion.debug.log`.

## Quality Filter (Critical Clarification)
### Why H1 looked “broken” in the Jan 30, 2026 run
Observed output for all pairs (H1):
- `tf_ok=true`, `age_min` small (fresh)
- Yet quality filter forced: `score=0`, `rejected=true`
- Reasons included:
  - `direction_not_tradeable`
  - `missing_sl_tp_entry`
  - `rr<=0`
  - `atr<=0`
  - `volatility_unknown`
  - `score<70`

This is expected if an execution-grade filter is applied to an H1 context payload that does not carry execution fields.

### PRD Rule
- H1 must have a **separate** acceptance concept:
  - “confirmable trend context” ≠ “tradeable execution signal”
- Until a dedicated H1 filter exists, the watcher/reporting must not interpret H1 `rejected=true` (execution filter) as “H1 unusable”.

## Logging + Artifacts
- Hard errors: `logs/error.log` (append-only; never spam stdout pipelines)
- Alerts CSV: `logs/alerts.csv`
- Telegram send log: `logs/send_tg.log`
- Fusion debug: `logs/fusion.debug.log`
- Candle cache: `cache/<PAIR>_<TF>.json`
- Indicators: `cache/indicators_<PAIR>_<TF>.json`

### New required diagnostic artifacts (must exist)
- Gate/scale stats log: `logs/gate_scale.debug.log`
  - Must include: `min_score`, `max_score`, `mean_score`, `stddev_score`, `samples`, `TELEGRAM_MIN_SCORE`, `gate_possible=true/false`, and a reason string.
- Scoring degeneracy log: `logs/scoring_degeneracy.debug.log`
  - Must include: `spread`, `stddev`, `samples`, and `degenerate=true/false`.

## Smoke / Acceptance Checks (must be runnable on-device)
Minimum checks:
1) Fetch writes TF cache for each pair/TF (no overwrite on mismatch).
2) Indicators updater generates indicator bundles for each pair/TF.
3) M15 fusion emits JSON with required keys and coherent fields.
4) Telegram HTML escaping selftest passes (no `<lt;` corruption).
5) Execution alerts only fire when M15 passes execution gates.
6) Gate/Scale Consistency check produces explicit `gate_possible` status and logs the reason.
7) Degeneracy detector can flag pinned scoring and fail-closed with `error=scoring_degenerate`.

## Learnings (Mistakes to Not Repeat)
1) **Legacy vs TF cache confusion**
   - Logging or code paths that reference `cache/<PAIR>.json` during M15/H1 flows are misleading and cause incorrect debugging decisions.
   - Fix habit: always log the TF-specific cache filename being used (`<PAIR>_<TF>.json`).

2) **Schema drift between indicator bundle generations**
   - Old indicator bundles may lack `tf_ok/tf_actual_min/error` and can silently bypass guards.
   - Fix habit: enforce required keys and reject/mark weak any bundle missing them.

3) **Non–TF-aware filtering**
   - Applying execution-grade filters to context TFs (H1) produced false “everything rejected” diagnostics.
   - Fix habit: define filter modes per TF role (execution vs context), and print the mode in logs.

4) **Environment-specific Telegram escaping**
   - Termux bash replacement rules can corrupt entities if `&` is not handled correctly in replacement strings.
   - Fix habit: keep an on-device selftest for escaping and run it after any change.

5) **Silent stalls (new, forbidden)**
   - A run where signals are computed but no Telegram send attempt occurs MUST be explainable by explicit logged states:
     - `NO_SIGNAL`, `BLOCKED_GATE_IMPOSSIBLE`, `BLOCKED_SCORING_DEGENERATE`, or `REJECTED_EXECUTION_FILTER`.
   - “Nothing happened” without a reason is a defect.

## 3 Action Bullets (Engineering Habit Changes)
- **One cache truth:** in code + logs, treat `cache/<PAIR>_<TF>.json` as the only authoritative TF cache; legacy `cache/<PAIR>.json` must never be used implicitly or mentioned as “the cache” for M15/H1.
- **Contract discipline:** every JSON artifact must obey a stable contract (required keys). Add a gate that marks output `weak=true` with explicit `error` instead of silently defaulting missing fields.
- **TF-aware gating:** separate “execution filter” from “context filter.” Do not judge H1 by execution criteria (SL/TP/RR/ATR gating) unless H1 is explicitly upgraded to an execution-grade signal format.

## Out of Scope
- Full broker execution / auto-trading
- Paid data feeds (unless explicitly approved)
- Multi-asset expansion beyond FX majors (unless explicitly approved)

## Success Metrics
- Bot runs 24/7 on Termux without silent failures.
- TF integrity holds (no M15/H1 label mismatch).
- M15 alerts are clean, readable, and pass execution gates.
- H1 context is visible as confirm/neutral/opposite without being misclassified as “broken” by execution filters.
- All rejections include explicit `filter_reasons` in logs, so debugging is never a black box.
- **No silent stalls:** every cycle ends with an explicit state (SENT / NO_SIGNAL / BLOCKED / REJECTED) recorded in logs.
- **Gate is provably reachable:** if `TELEGRAM_MIN_SCORE` is impossible given observed scoring, it is detected and logged as `MISCONFIG_GATE_IMPOSSIBLE`.

Active Rulebook: `BotA_Rulebook_v2_2.txt`
