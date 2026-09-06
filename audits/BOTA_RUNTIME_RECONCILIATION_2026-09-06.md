# BotA Runtime Reconciliation — 2026-09-06

## Purpose

Durable correction of runtime truth after direct Hetzner and Android inspection.

This document supersedes any earlier assumption that Android was already observation-only or that the current Hetzner runtime state was still unknown.

## Governance remains unchanged

- BOTA_EDGE_STATUS=UNVALIDATED
- BOTA_SHADOW_RESEARCH=REOPENED_BY_OWNER
- HISTORICAL_RETROSPECTIVE_VALIDATION_PROJECT=CLOSED
- LIVE_MONEY_TRADING=NO
- COMMERCIAL_PROFITLAB=NO
- PRIVATE_PROFITLAB_ANALYTICS=YES
- PRIMARY_RUNTIME_TARGET=HETZNER
- INTENDED_ANDROID_ROLE=CONTROL_AND_OBSERVATION_ONLY
- NEXT_PHASE=STAGE_0_MEASUREMENT_PILOT
- PILOT_COUNTS_TOWARD_CONFIRMATORY_SAMPLE=NO
- STRATEGY_TUNING_DURING_PILOT=NO
- MEASUREMENT_HARDENING_DURING_PILOT=YES

## Hetzner runtime — directly proven

Host: `bota-r5-01`.

Observed facts:

- Ubuntu 26.04, UTC, NTP synchronized.
- `bota.service` is active and is the sole BotA execution authority found on Hetzner.
- No BotA cron, systemd timer, or runit authority was found on Hetzner.
- Active immutable release: `39891b781e10c6939c2101c105d56eca9240b686`.
- Release tree: `c58b30d831242691afc23f0fef30c61da8c3cb19`.
- Effective config fingerprint: `c9b636e1597743df11daa439f37b311e2434c7bc2ce7589e306739b6207e1b7b`.
- R5 shadow mode is required and active.
- R5 preflight reports production side effects disabled and production secrets absent.
- The active R5 lineage is diverged from canonical `main`; it must not be treated as a checkout that can be safely updated with `git pull`.

## Market-open measurement validity — FAIL

The pipeline ledger contains 780 distinct market-open watcher cycles.

All 780 ended as watcher component `INTERNAL_ERROR`.

Every failed market-open cycle emitted three pair decision records, giving 2340 total decision records:

- EURUSD: 780
- GBPUSD: 780
- USDJPY: 780

All 2340 have:

- provider=`unknown`
- outcome=`no_terminal_outcome`
- Telegram=`not_attempted`
- Supabase=`not_attempted`

Retained watcher stderr proves the repeated deterministic failure:

`RAPIDAPI_CALENDAR_KEY: unbound variable`

The source path is the calendar-guard invocation in `tools/signal_watcher_core.sh` under strict shell mode.

Therefore:

- MARKET_OPEN_CYCLES_OBSERVED=YES
- VALID_MARKET_OPEN_CYCLES=0
- EXISTING_R5_DATA_MEASUREMENT_VALID=NO
- EXISTING_R5_DATA_COUNTS_TOWARD_CONFIRMATORY_SAMPLE=NO

## Updater state

The active R5 orchestrator currently reports the updater job as failed because the `d1_sync` stage exits non-zero.

The earlier indicator-update stage reports 12 fetch/build successes but records provider identity as `unknown`. The local D1 sync then fails with `ValueError` for all configured pairs.

The exact local D1 bundle defect is not yet proven. Do not assign a cause until the actual bundle fields are inspected.

## Android runtime — direct contradiction to intended topology

Android currently has live runit service processes for:

- bota-watcher
- bota-updater
- bota-closer
- bota-shadow
- bota-heartbeat
- bota-supervisor

Android BotA pipeline and closer artifacts are also advancing.

Therefore the durable current classification is:

- ANDROID_EXECUTION_AUTHORITY=ACTIVE
- ANDROID_CURRENT_ROLE_MATCH=NO
- HETZNER_EXECUTION_AUTHORITY=ACTIVE
- HETZNER_LOCAL_SINGLETON=PASS
- GLOBAL_SINGLETON=FAIL
- STAGE_0_BLOCKED=YES

The intended topology remains:

- Hetzner = authoritative scanner/runtime
- Android = control and observation only
- laptop = administration/development

## Staged hardening lane

A separate R5 lineage branch was created from the exact active Hetzner release rather than from `main`:

- baseline branch: `runtime/r5-baseline-39891b`
- hardening branch: `fix/r5-stage0-measurement-hardening-20260906`
- draft PR: `#129`

PR #129 currently stages a no-secret process-boundary containment for the `RAPIDAPI_CALENDAR_KEY` unbound-variable crash and records the remaining blockers. It is not deployed and must not be merged into `main` as a substitute for proper lineage reconciliation.

## Current blocking gates

Before Stage 0 can begin:

1. Android execution authority must be disabled and verified observation-only.
2. The R5 calendar crash containment must pass review/CI and then be deployed through the exact R5 release process, not by `git pull`.
3. D1 sync failure must be diagnosed from real local bundle fields.
4. Provider identity must be non-unknown for market-open decisions.
5. A complete market-open R5 shadow lifecycle must succeed end-to-end.
6. Health must not report a false green while required measurement jobs are failing.
7. No historical R5 observation may be silently counted as confirmatory evidence.

## Review status

A bounded Claude red-team review was completed before this reconciliation. Its useful blocking conclusions were retained, while unsupported overstatements were corrected using P4 cycle correlation.

An independent Codex replay remains optional review evidence and must not replace direct runtime proof or CI.

## Stop condition

Do not declare BotA 24/7 operational merely because the VPS or `bota.service` is continuously running. The correct current statement is: the Hetzner scheduler is persistent, but measurement-valid market-open scanning is not yet proven and global singleton currently fails.
