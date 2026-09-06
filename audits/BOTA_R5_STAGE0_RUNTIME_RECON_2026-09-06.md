# BotA R5 Stage 0 Runtime Reconciliation — 2026-09-06

## Scope

Runtime reconciliation and measurement-hardening evidence for the Hetzner R5 lineage before any Stage 0 measurement pilot.

No strategy tuning is authorized by this document. Existing pre-hardening R5 observations do not count toward any confirmatory sample.

## Canonical governance

- BOTA_EDGE_STATUS=UNVALIDATED
- BOTA_SHADOW_RESEARCH=REOPENED_BY_OWNER
- LIVE_MONEY_TRADING=NO
- COMMERCIAL_PROFITLAB=NO
- PRIMARY_RUNTIME_TARGET=HETZNER
- ANDROID_ROLE=CONTROL_AND_OBSERVATION_ONLY
- NEXT_PHASE=STAGE_0_MEASUREMENT_PILOT
- PILOT_COUNTS_TOWARD_CONFIRMATORY_SAMPLE=NO
- STRATEGY_TUNING_DURING_PILOT=NO
- MEASUREMENT_HARDENING_DURING_PILOT=YES

## Hetzner runtime facts

Host: `bota-r5-01`.

Observed live release:

- git commit: `39891b781e10c6939c2101c105d56eca9240b686`
- git tree: `c58b30d831242691afc23f0fef30c61da8c3cb19`
- effective config fingerprint: `c9b636e1597743df11daa439f37b311e2434c7bc2ce7589e306739b6207e1b7b`
- systemd authority: `bota.service`
- R5 shadow required and active
- production Telegram/Supabase side effects suppressed by the R5 boundary
- no competing BotA cron/timer/runit authority found on Hetzner

The live R5 history is diverged from canonical `main`; it is not safe to treat the host as merely behind `main` or to `git pull` it.

## Market-open watcher failure — root cause proven

Pipeline correlation proved:

- 780 distinct market-open watcher cycles
- 780 component-level `INTERNAL_ERROR` terminals
- all 780 market-open cycles failed
- 3 pair decisions emitted per failed cycle (EURUSD, GBPUSD, USDJPY)
- 2340 decision rows total
- all 2340 had provider=`unknown`
- all 2340 had outcome=`no_terminal_outcome`
- Telegram/Supabase result=`not_attempted`

Retained stderr identified the deterministic crash:

`signal_watcher_core.sh: RAPIDAPI_CALENDAR_KEY: unbound variable`

The staged R5 service contract defines `RAPIDAPI_CALENDAR_KEY=` at both `ExecStartPre` and `ExecStart`, avoiding a secret while preventing `set -u` from aborting this historical path.

This containment is repository-only until an exact R5 deployment is separately authorized and proven.

## P5 — D1 failure root cause proven

Direct inspection of the three live D1 indicator bundles showed:

- timeframe identity valid: D1
- `tf_ok=true`
- `tf_actual_min=1440`
- `error=insufficient_data`
- `ema9=0.0`
- `ema21=0.0`
- `weak=true`

Raw D1 Yahoo caches contained 25 daily candles per configured pair. The historical fetcher requests Yahoo D1 with `range=1mo`, while `build_indicators.py` retains an existing minimum of 60 bars before computing the indicator bundle. `sync_d1_trend_cache.py` then correctly rejects the zero EMA values.

Proven causal chain:

`Yahoo D1 range=1mo -> ~25 bars -> min_bars=60 not met -> insufficient_data -> EMA9/EMA21=0 -> d1_sync ValueError`

The hardening branch changes only the Yahoo D1 history request from `1mo` to `6mo`; it does not lower the existing 60-bar indicator requirement.

## P5 — current market-data provider and identity gap

The live R5 logs prove the current provider path is Yahoo because OANDA is skipped when the runtime token is absent. Successful Yahoo fetches are visible for M15/H1/H4/D1 across EURUSD, GBPUSD and USDJPY.

Historical R5 OANDA-normalized payloads include `_provider=oanda`; historical Yahoo payloads do not carry an equivalent marker. The updater reads that marker and falls back to `unknown` when absent.

Therefore the historical `provider=unknown` decisions are explained by an observability defect, not by uncertainty about the observed live fetch path.

The hardening branch persists the actual `PROVIDER_USED` into the normalized cache metadata so the updater can propagate Yahoo/OANDA identity.

## P6 — provider-accounting persistence root cause proven

Under the real R5 environment:

- `BOTA_ROOT=/opt/bota/current`
- `BOTA_MUTABLE_ROOT=/var/lib/bota`

Historical `provider_usage.py` resolves its state/log root from `BOTA_ROOT`, producing:

- `/opt/bota/current/state/provider_usage.json`
- `/opt/bota/current/logs/provider_calls.jsonl`
- `/opt/bota/current/state/provider_usage.lock`

The immutable release is not writable by user `bota`; `/var/lib/bota` and its state/log directories are writable.

Retained errors repeatedly prove the failure:

`PROVIDER_USAGE_ERROR=PermissionError:[Errno 13] Permission denied: '/opt/bota/releases/39891b781e10c6939c2101c105d56eca9240b686/state/provider_usage.lock'`

Provider accounting therefore failed persistently because its root contract ignored `BOTA_MUTABLE_ROOT`. The historical fetch boundary also swallowed accounting failures with `|| true`, allowing successful fetches to hide missing provenance.

The hardening branch:

1. makes `provider_usage.py` prefer `BOTA_MUTABLE_ROOT`, falling back to `BOTA_ROOT`;
2. removes the silent `|| true` from the fetch-boundary provider accounting call so provenance failure is fail-closed for measurement collection;
3. adds regression coverage proving state and event files land under a supplied mutable root.

## Android singleton transition — PASS

Earlier direct inspection proved Android was an active execution authority. After preserving evidence, the Android BotA execution plane was deliberately disabled.

Proven transition:

- one active Termux:Boot BotA watchdog launcher disabled;
- backup preserved at `/data/data/com.termux/files/home/.termux/boot/00-termux-services.sh.pre_control_only_20260906_130441`;
- no BotA watchdog cron path present;
- live `native_service_daemon_watchdog.py` stopped;
- watchdog remaining count=0;
- `bota-supervisor`, `bota-watcher`, `bota-updater`, `bota-closer`, `bota-shadow`, and `bota-heartbeat` verified down;
- separate `crond` left running;
- 90-second before/after hashes for BotA pipeline events/progress remained identical;
- `ANDROID_BOTA_PIPELINE_ADVANCING=NO`.

Current observed topology:

- ANDROID_EXECUTION_AUTHORITY=DISABLED
- ANDROID_ROLE=CONTROL_AND_OBSERVATION_ONLY
- HETZNER_EXECUTION_AUTHORITY=ACTIVE
- HETZNER_LOCAL_SINGLETON=PASS
- GLOBAL_SINGLETON=PASS_AT_CURRENT_OBSERVED_TOPOLOGY

This is not an indefinite proof across every future Android reboot; it is direct evidence for the current topology, with the known boot resurrection path disabled.

## R5 hardening staged on this branch

This branch is rooted directly at the exact live R5 runtime commit `39891b...` and targets `runtime/r5-baseline-39891b`, not `main`.

Net measurement-hardening changes are deliberately narrow:

1. define an empty `RAPIDAPI_CALENDAR_KEY` at the R5 systemd process boundary;
2. request `6mo` instead of `1mo` for Yahoo D1 so the pre-existing 60-bar indicator contract can be satisfied;
3. persist the actual provider marker into normalized cache metadata;
4. route provider accounting to `BOTA_MUTABLE_ROOT`;
5. make provider-accounting failure visible/fail-closed instead of silently ignored;
6. add focused regression tests and CI coverage.

No strategy threshold, score, pair policy, SL/TP, or confirmatory methodology is changed.

## Repository verification

The runtime-affecting hardening change set has passed:

- Provider accounting and pipeline ledger workflow: PASS
- focused regression tests: PASS
- shell syntax checks: PASS
- Python compile checks: PASS
- Security Scan: PASS

Documentation-only commits may advance the branch head. Before deployment, current-head checks must remain green.

These are repository-level proofs only. They do not prove deployment or market-open runtime validity.

## Remaining blockers before Stage 0

Android is no longer an active blocker at the current observed topology.

Before Stage 0 measurement collection can begin:

1. deploy the reviewed R5 hardening through the exact immutable-release procedure, never by `git pull`;
2. prove the deployed release identity/config fingerprint and R5 shadow boundary;
3. prove updater and `d1_sync` complete successfully on the deployed release;
4. prove provider-accounting files are written under `/var/lib/bota` and decision provider identity is non-unknown;
5. prove at least one complete market-open R5 shadow lifecycle with terminal decision outcomes and no unexplained gaps;
6. ensure required-job failure cannot coexist with a misleading overall healthy state;
7. keep all pre-hardening R5 and historical Android observations excluded from confirmatory evidence.

## Stop condition

Do not declare BotA measurement-ready or 24/7 operational merely because the VPS/service remains continuously running or repository CI passes. The next valid promotion requires exact deployment evidence plus successful market-open shadow runtime evidence.
