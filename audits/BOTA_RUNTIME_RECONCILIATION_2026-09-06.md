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

## Android runtime — control/observation-only transition PASS

Earlier direct inspection proved Android was an active execution authority with live runit services and advancing BotA pipeline artifacts. That pre-stop evidence is preserved.

On 2026-09-06 the Android BotA execution plane was deliberately disabled after the evidence snapshot.

Persistent resurrection controls:

- one active Termux:Boot BotA watchdog launcher was disabled;
- backup created at `/data/data/com.termux/files/home/.termux/boot/00-termux-services.sh.pre_control_only_20260906_130441`;
- no BotA watchdog cron entry was present.

Watchdog transition:

- live `native_service_daemon_watchdog.py` PID `29976` received SIGTERM;
- watchdog target count: `1`;
- watchdog remaining count: `0`;
- `WATCHDOG_STOP=PASS`.

The following BotA runit services were taken down and independently rechecked as `down`:

- bota-supervisor
- bota-watcher
- bota-updater
- bota-closer
- bota-shadow
- bota-heartbeat

Separate `crond` remained active and was intentionally not changed.

A 90-second no-progress proof was then performed:

- `pipeline_events.jsonl` SHA-256 before/after: `c0c6380dc393dd4aa02d0c2612b14b3b5d85b84eb33ee8ef7fd0e531a933fbf9` / unchanged;
- `pipeline_progress.json` SHA-256 before/after: `8cd0bfd66a5422b82322d6ff0dc4c66ca786e8b3f5b03309cd5e780c4d7fae91` / unchanged;
- `ANDROID_BOTA_PIPELINE_ADVANCING=NO`;
- final `ANDROID_BOTA_WATCHDOG_COUNT=0`.

Current observed classification:

- ANDROID_EXECUTION_AUTHORITY=DISABLED
- ANDROID_ROLE=CONTROL_AND_OBSERVATION_ONLY
- ANDROID_CONTROL_ONLY_TRANSITION=PASS
- HETZNER_EXECUTION_AUTHORITY=ACTIVE
- HETZNER_LOCAL_SINGLETON=PASS
- GLOBAL_SINGLETON=PASS_AT_CURRENT_OBSERVED_TOPOLOGY

This does not by itself prove persistence across every future Android reboot. The known Termux:Boot resurrection path is disabled and no watchdog cron path was present; future reboot persistence may be verified separately if required by the Stage 0 gate.

## Historical Android ledger ordering caution

The preserved Android ledger contains events from multiple boot IDs whose displayed UTC windows can overlap. `pipeline_ledger.py` records the kernel boot ID on each event, while event display time may be either a supplied trusted `server_epoch` or local UTC display-only time.

Therefore overlapping cross-boot displayed timestamps must not be interpreted as proof of simultaneous Android kernels or as a globally ordered measurement stream without reconciling `time_source` and `server_epoch`.

The historical Android ledger remains engineering evidence only.

## Staged hardening lane

A separate R5 lineage branch was created from the exact active Hetzner release rather than from `main`:

- baseline branch: `runtime/r5-baseline-39891b`
- hardening branch: `fix/r5-stage0-measurement-hardening-20260906`
- draft PR: `#129`

PR #129 currently stages a no-secret process-boundary containment for the `RAPIDAPI_CALENDAR_KEY` unbound-variable crash and records the remaining blockers. It is not deployed and must not be merged into `main` as a substitute for proper lineage reconciliation.

The PR's Security Scan and Provider accounting / pipeline ledger checks passed on the staged head after the R5 systemd path was added to the workflow trigger and the new regression test was included in the focused test run.

## Current blocking gates

Android authority is no longer an active blocker at the current observed topology.

Before Stage 0 can begin:

1. D1 sync failure must be diagnosed from real local bundle fields.
2. Provider identity must be captured and proven rather than remaining `unknown`.
3. The R5 calendar crash containment must remain reviewed/green and, if deployment is authorized, be deployed through the exact R5 release process rather than by `git pull`.
4. A complete market-open R5 shadow lifecycle must succeed end-to-end after hardening.
5. Health must not report a false green while required measurement jobs are failing.
6. No unexplained lifecycle gaps may remain.
7. No historical R5 or pre-transition Android observation may be silently counted as confirmatory evidence.

## Review status

A bounded Claude red-team review was completed before this reconciliation. Its useful blocking conclusions were retained, while unsupported overstatements were corrected using P4 cycle correlation.

Codex Replay was not connected for this pass; GitHub CI/security checks and direct runtime evidence remain the available automated cross-checks. No Codex review is claimed.

## Stop condition

Do not declare BotA measurement-ready merely because the VPS or `bota.service` is continuously running. The correct current statement is: Hetzner is the sole observed BotA execution authority after the Android control-only transition, but measurement-valid market-open scanning is not yet proven.
