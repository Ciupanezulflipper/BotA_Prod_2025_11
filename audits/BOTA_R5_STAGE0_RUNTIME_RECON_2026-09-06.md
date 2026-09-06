# BotA R5 Stage 0 Runtime Reconciliation — 2026-09-06

## Scope

Read-only runtime reconciliation of Hetzner R5 plus Android singleton state before any Stage 0 measurement pilot.

No strategy tuning is authorized by this document. Existing R5 observations do not count toward any confirmatory sample.

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

## Hetzner facts

Host: `bota-r5-01`.

Observed runtime release:

- git commit: `39891b781e10c6939c2101c105d56eca9240b686`
- git tree: `c58b30d831242691afc23f0fef30c61da8c3cb19`
- effective config fingerprint: `c9b636e1597743df11daa439f37b311e2434c7bc2ce7589e306739b6207e1b7b`
- systemd authority: `bota.service`
- R5 shadow required and active
- side effects disabled by R5 shadow preflight
- no BotA cron/timer/runit authority on Hetzner

The active R5 history is diverged from canonical `main`; it is not safe to treat the host as merely behind `main` or to `git pull` it.

## Market-open watcher failure

Pipeline correlation proved:

- 780 distinct market-open watcher cycles
- 780 component-level `INTERNAL_ERROR` terminals
- all 780 market-open cycles failed
- 3 decision rows were emitted per failed cycle (EURUSD, GBPUSD, USDJPY)
- all 2340 decision rows were `provider=unknown`
- all 2340 decision rows were `no_terminal_outcome`
- Telegram and Supabase results were `not_attempted`

Retained stderr identified the deterministic crash:

`signal_watcher_core.sh: RAPIDAPI_CALENDAR_KEY: unbound variable`

This repeated across the observed market-open dates. Therefore the existing R5 dataset is engineering/runtime evidence only and is not measurement-valid.

## Updater failure

The orchestrator records the updater job as failed because its `d1_sync` stage exits non-zero.

The indicators-updater stage itself reports successful fetch/build for 12 pair/timeframe bundles but provider identity is currently `unknown`. The subsequent D1 local-sync stage fails for all configured pairs with `ValueError`.

This requires a separate data-contract inspection before modification. Do not guess the D1 failure cause.

## Android singleton finding

Android currently has live runit service processes for:

- bota-watcher
- bota-updater
- bota-closer
- bota-shadow
- bota-heartbeat
- bota-supervisor

Android BotA pipeline/runtime files are also advancing. Therefore Android is an active BotA execution authority and the intended topology is not currently satisfied.

Classification:

- HETZNER_LOCAL_SINGLETON=PASS
- GLOBAL_SINGLETON=FAIL
- ANDROID_EXECUTION_AUTHORITY=ACTIVE
- STAGE_0_BLOCKED=YES

## R5 calendar crash containment staged on this branch

This branch is rooted directly at the active R5 runtime commit `39891b...`.

The R5 systemd unit now forces `RAPIDAPI_CALENDAR_KEY` to a defined empty value at both `ExecStartPre` and `ExecStart` using `/usr/bin/env`.

Purpose:

- eliminate the `set -u` unbound-variable crash without embedding any secret;
- preserve the current R5 process hierarchy and child-environment inheritance;
- avoid strategy-threshold changes;
- keep the existing R5 shadow boundary in force.

This is a staged repository change only. It is NOT deployed by this commit.

## Remaining blockers before Stage 0

1. Android execution plane must be disabled and verified control/observation-only.
2. Hetzner D1 sync failure must be diagnosed from actual local indicator bundles.
3. Provider identity must be captured correctly.
4. One market-open R5 shadow cycle must complete end-to-end after hardening.
5. No unexplained lifecycle gaps may remain.
6. Existing observations remain excluded from confirmatory evidence.

## Stop condition

Do not deploy or start Stage 0 merely because systemd reports `active` or scheduler jobs report PASS. Measurement readiness requires valid market-open lifecycle evidence and a proven global singleton.
