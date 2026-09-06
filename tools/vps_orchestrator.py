#!/usr/bin/env python3
"""Single persistent VPS scheduler and bounded child-process owner."""
from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import fcntl
from pathlib import Path
from typing import Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "production-vps.env"
DEPENDENCY_PATH = ROOT / "requirements-runtime.txt"
PYPROJECT_PATH = ROOT / "pyproject.toml"
SOURCE_GENERATION = "0212d9848ecb8e8b464da215c2ac115d62dae2f4"
HEALTH_FILENAME = "vps_orchestrator_health.json"
LOCK_FILENAME = "vps_orchestrator.lock"
RELEASE_MANIFEST_FILENAME = ".bota-release.json"
RELEASE_MANIFEST_SCHEMA = "1.0"
OUTPUT_LIMIT = 32768
# Existing outer envelopes are preserved for updater/watcher/shadow/ProfitLab/
# Market Pulse. Jobs without a source-grounded envelope get a deliberately
# conservative one-hour safety ceiling so normal execution semantics are not
# shortened; overlap prevention remains the cadence-level protection.
CONSERVATIVE_DEADLINE_SECONDS = 3600
UPDATER_ENV = {
    "PAIRS": "EURUSD GBPUSD USDJPY",
    "TIMEFRAMES": "M15 H1 H4 D1",
    "FETCH_RETRIES": "3",
    "FETCH_BACKOFF_BASE": "5",
    "FETCH_BACKOFF_MAX": "20",
    "FETCH_MIN_GAP_SECS": "1",
}
POLICY_KEYS = (
    "PAIRS", "TIMEFRAMES", "POLICY_B_ENABLED", "POLICY_B_SCORE_MIN",
    "POLICY_B_ADX_MAX", "FILTER_SCORE_MIN", "FILTER_SCORE_MIN_ALL",
    "NEWS_ON", "TELEGRAM_MIN_SCORE", "TELEGRAM_TIER_YELLOW_MIN",
    "TELEGRAM_TIER_YELLOW_MIN_INT", "TELEGRAM_TIER_GREEN_MIN",
    "TELEGRAM_TIER_GREEN_MIN_INT", "TELEGRAM_COOLDOWN_SECONDS",
    "CANDLE_MAX_AGE_SECS",
)
REQUIRED_COMMANDS = (
    "bash", "python3", "curl", "env", "flock", "timeout", "git", "systemctl", "jq",
    "cat", "chmod", "date", "find", "grep", "head", "mkdir", "mktemp",
    "rm", "sed", "sort", "stat", "tail", "tee", "tr",
)
PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)$")
ENV_RE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")


class ContractError(RuntimeError):
    """A versioned runtime contract is missing or malformed."""


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def load_frozen_policy(
    path: Path = POLICY_PATH, ambient: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Load the allowlisted policy; versioned values override ambient values."""
    effective = dict(ambient if ambient is not None else os.environ)
    parsed: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = ENV_RE.fullmatch(line)
        if not match:
            raise ContractError(f"policy_malformed:line={number}")
        key, value = match.groups()
        if key not in POLICY_KEYS:
            raise ContractError(f"policy_key_not_allowed:{key}")
        if key in parsed:
            raise ContractError(f"policy_duplicate:{key}")
        parsed[key] = _unquote(value)
    missing = sorted(set(POLICY_KEYS) - parsed.keys())
    if missing:
        raise ContractError(f"policy_missing:{','.join(missing)}")
    effective.update(parsed)
    return {key: effective[key] for key in POLICY_KEYS}


def parse_dependency_manifest(path: Path = DEPENDENCY_PATH) -> list[dict[str, str]]:
    """Parse an exact-pin-only direct production dependency manifest."""
    dependencies: list[dict[str, str]] = []
    seen: set[str] = set()
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN_RE.fullmatch(line)
        if not match:
            raise ContractError(f"dependency_not_exact_pin:line={number}")
        name, version = match.groups()
        normalized = re.sub(r"[-_.]+", "-", name).lower()
        if normalized in seen:
            raise ContractError(f"dependency_duplicate:{normalized}")
        seen.add(normalized)
        dependencies.append({"name": normalized, "version": version})
    if not dependencies:
        raise ContractError("dependency_manifest_empty")
    return sorted(dependencies, key=lambda item: item["name"])


def command_preflight(
    commands: Sequence[str] = REQUIRED_COMMANDS,
    *,
    path: str | None = None,
) -> dict[str, object]:
    """Return fail-closed, machine-readable command availability evidence."""
    resolved = {command: shutil.which(command, path=path) for command in commands}
    missing = sorted(command for command, location in resolved.items() if not location)
    return {
        "schema_version": "1.0",
        "healthy": not missing,
        "commands": {key: resolved[key] for key in sorted(resolved)},
        "missing": missing,
    }


def declared_python_contract(path: Path = PYPROJECT_PATH) -> str:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    try:
        contract = data["project"]["requires-python"]
    except (KeyError, TypeError) as exc:
        raise ContractError("python_contract_missing") from exc
    if contract != ">=3.14,<3.15":
        raise ContractError(f"python_contract_unsupported:{contract}")
    return contract


def runtime_python_result(pyproject_path: Path = PYPROJECT_PATH) -> dict[str, object]:
    healthy = sys.version_info[:2] == (3, 14)
    return {
        "contract": declared_python_contract(pyproject_path),
        "executable": sys.executable,
        "healthy": healthy,
        "version": ".".join(map(str, sys.version_info[:3])),
    }


def release_preflight(code_root: Path) -> dict[str, object]:
    """Validate a staged release without locks, jobs, mutable state, or I/O."""
    checks: dict[str, object] = {}
    try:
        release = load_release_manifest(code_root, allow_staging=True)
        runtime = runtime_python_result(code_root / "pyproject.toml")
        commands = command_preflight()
        dependencies = parse_dependency_manifest(code_root / "requirements-runtime.txt")
        installed = {
            item["name"]: importlib.metadata.version(item["name"]) for item in dependencies
        }
        imported = []
        for item in dependencies:
            importlib.import_module(item["name"].replace("-", "_"))
            imported.append(item["name"])
        versions_ok = all(installed[item["name"]] == item["version"] for item in dependencies)
        policy = load_frozen_policy(code_root / "config" / "production-vps.env", {})
        checks = {"release_manifest": release, "python": runtime,
                  "commands": commands, "dependencies": installed,
                  "required_imports": imported,
                  "dependency_versions_match": versions_ok,
                  "policy_keys": sorted(policy)}
        healthy = bool(runtime["healthy"] and commands["healthy"] and versions_ok)
    except (ContractError, ImportError, OSError, ValueError,
            importlib.metadata.PackageNotFoundError) as exc:
        healthy = False
        checks["failure"] = f"{type(exc).__name__}:{exc}"
    return {"schema_version": "1.0", "healthy": healthy, "checks": checks,
            "side_effects_enabled": False}


def effective_config_document(
    *,
    ambient: Mapping[str, str] | None = None,
    policy_path: Path = POLICY_PATH,
    dependency_path: Path = DEPENDENCY_PATH,
    pyproject_path: Path = PYPROJECT_PATH,
    commands: Sequence[str] = REQUIRED_COMMANDS,
) -> dict[str, object]:
    """Build an allowlist-only document; credential-bearing input is ignored."""
    return {
        "schema_version": "1.0",
        "release": {"source_generation": SOURCE_GENERATION},
        "runtime": {
            "python_contract": declared_python_contract(pyproject_path),
            "dependencies": parse_dependency_manifest(dependency_path),
            "required_commands": sorted(commands),
        },
        "strategy_policy": load_frozen_policy(policy_path, ambient),
    }


def effective_config_evidence(**kwargs: object) -> dict[str, object]:
    document = effective_config_document(**kwargs)
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return {
        "schema_version": "1.0",
        "effective_config": document,
        "fingerprint_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def load_release_manifest(code_root: Path, *, allow_staging: bool = False) -> dict[str, str]:
    """Load and validate deployment identity from the finalized release itself."""
    root = code_root.resolve()
    path = root / RELEASE_MANIFEST_FILENAME
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ContractError("release_manifest_unreadable") from exc
    if not isinstance(value, dict) or value.get("schema_version") != RELEASE_MANIFEST_SCHEMA:
        raise ContractError("release_manifest_schema")
    commit = value.get("git_commit_sha")
    tree = value.get("git_tree_sha")
    fingerprint = value.get("effective_config_fingerprint")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ContractError("release_manifest_commit")
    if not isinstance(tree, str) or not re.fullmatch(r"[0-9a-f]{40}", tree):
        raise ContractError("release_manifest_tree")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ContractError("release_manifest_fingerprint")
    valid_staging = allow_staging and root.name.startswith(f".staging-{commit}-")
    if root.name != commit and not valid_staging:
        raise ContractError("release_manifest_directory_mismatch")
    expected = effective_config_evidence(
        policy_path=root / "config" / "production-vps.env",
        dependency_path=root / "requirements-runtime.txt",
        pyproject_path=root / "pyproject.toml",
    )["fingerprint_sha256"]
    if fingerprint != expected:
        raise ContractError("release_manifest_fingerprint_mismatch")
    return {"git_commit_sha": commit, "git_tree_sha": tree,
            "effective_config_fingerprint": fingerprint}


@dataclass(frozen=True)
class Cadence:
    """UTC wall-clock minute boundaries. Weekday uses Python's Monday=0."""

    minutes: tuple[int, ...]
    hours: tuple[int, ...] = tuple(range(24))
    weekdays: tuple[int, ...] = tuple(range(7))

    def next_after(self, moment: datetime) -> datetime:
        if moment.tzinfo is None:
            raise ValueError("cadence_requires_aware_datetime")
        candidate = moment.astimezone(timezone.utc).replace(second=0, microsecond=0)
        if candidate <= moment.astimezone(timezone.utc):
            candidate += timedelta(minutes=1)
        for _ in range(8 * 24 * 60):
            if (candidate.minute in self.minutes and candidate.hour in self.hours
                    and candidate.weekday() in self.weekdays):
                return candidate
            candidate += timedelta(minutes=1)
        raise RuntimeError("cadence_has_no_boundary")


EVERY_MINUTE = Cadence(tuple(range(60)))
EVERY_5_MINUTES = Cadence(tuple(range(0, 60, 5)))
EVERY_15_MINUTES = Cadence(tuple(range(0, 60, 15)))
UPDATER_MINUTES = Cadence((13, 28, 43, 58))
EVERY_30_MINUTES = Cadence((0, 30))
DAILY_0506 = Cadence((6,), hours=(5,))
HOURLY_MINUTE_04 = Cadence((4,))
SUNDAY_0100 = Cadence((0,), hours=(1,), weekdays=(6,))
HOURLY_MINUTE_10 = Cadence((10,))


@dataclass(frozen=True)
class Job:
    name: str
    commands: tuple[tuple[str, ...], ...]
    cadence: Cadence
    deadline_seconds: float
    stage_deadlines: tuple[float, ...] = ()
    env_overrides: tuple[tuple[str, str], ...] = ()
    stage_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.stage_deadlines and len(self.stage_deadlines) != len(self.commands):
            raise ContractError(f"stage_deadline_count:{self.name}")
        if self.stage_names and len(self.stage_names) != len(self.commands):
            raise ContractError(f"stage_name_count:{self.name}")
        if self.env_overrides and (self.name != "updater"
                                   or dict(self.env_overrides) != UPDATER_ENV):
            raise ContractError(f"job_environment_not_allowed:{self.name}")

    def deadline_for_stage(self, index: int) -> float:
        return self.stage_deadlines[index] if self.stage_deadlines else self.deadline_seconds

    def terminal_grace_seconds(self) -> float:
        return sum(self.stage_deadlines) if self.stage_deadlines else self.deadline_seconds

    def name_for_stage(self, index: int) -> str:
        return self.stage_names[index] if self.stage_names else f"stage_{index + 1}"


def production_jobs(code_root: Path = ROOT) -> tuple[Job, ...]:
    """All retained jobs at their established UTC production cadences."""
    tool = code_root / "tools"
    bash = shutil.which("bash") or "/bin/bash"
    python = sys.executable
    return (
        Job("updater", ((bash, str(tool / "indicators_updater.sh")),
                        (python, str(tool / "sync_d1_trend_cache.py"), "--pairs",
                         "EURUSD", "GBPUSD", "USDJPY")), UPDATER_MINUTES, 600,
            stage_deadlines=(600, CONSERVATIVE_DEADLINE_SECONDS),
            env_overrides=tuple(UPDATER_ENV.items()),
            stage_names=("indicators_updater", "d1_sync")),
        Job("watcher", ((bash, str(tool / "watcher_gated_cycle.sh")),), EVERY_5_MINUTES, 720),
        Job("shadow", ((bash, str(tool / "run_shadow_manager.sh")),), EVERY_15_MINUTES, 720),
        Job("closer", ((bash, str(tool / "run_signal_closer_live.sh")),), EVERY_15_MINUTES,
            CONSERVATIVE_DEADLINE_SECONDS),
        Job("heartbeat", ((bash, str(tool / "heartbeat.sh")),), EVERY_MINUTE,
            CONSERVATIVE_DEADLINE_SECONDS),
        Job("profitlab_delivery", ((python, str(tool / "profitlab_delivery.py")),), EVERY_MINUTE, 45),
        Job("runtime_health_push", ((bash, str(tool / "run_runtime_health_push.sh")),), EVERY_5_MINUTES,
            CONSERVATIVE_DEADLINE_SECONDS),
        Job("market_pulse", ((python, str(tool / "market_pulse_v2.py"), "--scheduled-send"),), EVERY_30_MINUTES, 25),
        Job("alerts_to_trades", ((python, str(tool / "alerts_to_trades.py")),), DAILY_0506,
            CONSERVATIVE_DEADLINE_SECONDS),
        Job("pause_guard", ((python, str(tool / "pause_guard.py")),), DAILY_0506,
            CONSERVATIVE_DEADLINE_SECONDS),
        Job("autostatus", ((bash, str(tool / "autostatus.sh")),), HOURLY_MINUTE_04,
            CONSERVATIVE_DEADLINE_SECONDS),
        Job("signal_accuracy", ((python, str(tool / "signal_accuracy.py")),), SUNDAY_0100,
            CONSERVATIVE_DEADLINE_SECONDS),
        Job("daily_summary_server_gate", ((bash, str(tool / "daily_summary_server_gate.sh")),),
            HOURLY_MINUTE_10, CONSERVATIVE_DEADLINE_SECONDS),
    )


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return "unavailable"


class InstanceLocked(RuntimeError):
    pass


def require_r5_bootstrap(code_root: Path) -> None:
    """Reject R5 startup unless startup auto-loaded this release's bootstrap."""
    required = os.environ.get("BOTA_REQUIRE_R5_SHADOW") == "1"
    active = os.environ.get("BOTA_R5_SHADOW") == "1"
    if required and not active:
        raise ContractError("r5_shadow_required_but_inactive")
    if not active:
        return
    module = sys.modules.get("sitecustomize")
    module_file = getattr(module, "__file__", None) if module is not None else None
    expected = (code_root / "r5_bootstrap" / "sitecustomize.py").resolve()
    try:
        actual = Path(module_file).resolve() if module_file else None
    except OSError:
        actual = None
    if os.environ.get("BOTA_R5_BOOTSTRAP_ACTIVE") != "1" or actual != expected:
        raise ContractError("r5_bootstrap_not_proven")


class Orchestrator:
    """Own scheduling, process groups, reaping, and useful-progress evidence."""

    def __init__(self, code_root: Path, mutable_root: Path,
                 jobs: Sequence[Job] | None = None, *, term_grace: float = 5.0,
                 require_release_manifest: bool = False):
        self.code_root = code_root.resolve()
        self.mutable_root = mutable_root.resolve()
        self.require_release_manifest = require_release_manifest
        self.release_bin = self.code_root / ".venv" / "bin"
        self.state_dir = self.mutable_root / "state"
        self.jobs = tuple(jobs if jobs is not None else production_jobs(self.code_root))
        self.term_grace = term_grace
        self.runtime_instance_id = str(uuid.uuid4())
        self.start_utc = _utc()
        self.start_monotonic = time.monotonic()
        if require_release_manifest:
            self.release = load_release_manifest(self.code_root)
            release_python = self.release_bin / "python3"
            if not release_python.is_file() or not os.access(release_python, os.X_OK):
                raise ContractError("release_python_unusable")
        else:
            self.release = {
                "git_commit_sha": SOURCE_GENERATION,
                "git_tree_sha": "0" * 40,
                "effective_config_fingerprint": effective_config_evidence()["fingerprint_sha256"],
            }
        self.policy = load_frozen_policy(self.code_root / "config" / "production-vps.env")
        canonical_policy = json.dumps(self.policy, sort_keys=True, separators=(",", ":"))
        self.policy_fingerprint = hashlib.sha256(canonical_policy.encode("utf-8")).hexdigest()
        self.stop_event = threading.Event()
        self.guard = threading.RLock()
        self.running: dict[str, subprocess.Popen[bytes]] = {}
        self.active_jobs: set[str] = set()
        self.threads: set[threading.Thread] = set()
        self.latest: dict[str, dict[str, object]] = {}
        self.lock_file = None
        self.health_path = self.state_dir / HEALTH_FILENAME
        self.previous_health: dict[str, object] | None = None
        try:
            loaded = json.loads(self.health_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.previous_health = {
                    "runtime_instance_id": loaded.get("runtime_instance_id"),
                    "lifecycle": loaded.get("lifecycle"),
                    "last_loop_progress_utc": loaded.get("last_loop_progress_utc"),
                    "useful_progress": loaded.get("useful_progress", {}),
                }
        except (OSError, ValueError):
            pass
        self.lifecycle = "STARTING"
        self.last_loop_utc: str | None = None
        for job in self.jobs:
            self.latest[job.name] = {
                "job_name": job.name, "runtime_instance_id": self.runtime_instance_id,
                "invocation_id": None, "scheduled_for_utc": None,
                "started_at_utc": None, "finished_at_utc": None,
                "monotonic_start": None, "monotonic_end": None, "status": "NOT_RUN",
                "exit_code": None, "duration_seconds": None,
                "deadline_seconds": job.deadline_seconds, "failure_class": None,
            }

    def acquire_instance_lock(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file = (self.state_dir / LOCK_FILENAME).open("a+")
        try:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.lock_file.close()
            self.lock_file = None
            raise InstanceLocked("another VPS orchestrator instance owns the lock") from exc
        self.lock_file.seek(0)
        self.lock_file.truncate()
        self.lock_file.write(f"{self.runtime_instance_id} {os.getpid()}\n")
        self.lock_file.flush()

    def child_env(self, job: Job | None = None) -> dict[str, str]:
        env = dict(os.environ)
        env.update(self.policy)
        root = str(self.code_root)
        env.update(BOTA_CODE_ROOT=root, BOTA_ROOT=root,
                   BOTA_MUTABLE_ROOT=str(self.mutable_root),
                   PYTHONPATH=str(self.code_root / "r5_bootstrap"))
        # Shell children must resolve python3 from the same immutable release
        # environment that starts this orchestrator.  Local/unit runs retain
        # their ambient interpreter fallback when no release venv is present.
        if self.release_bin.is_dir():
            env["PATH"] = f"{self.release_bin}{os.pathsep}{env.get('PATH', os.defpath)}"
        elif self.require_release_manifest:
            raise ContractError("release_python_unusable")
        if job is not None:
            env.update(job.env_overrides)
        return env

    def health(self) -> dict[str, object]:
        with self.guard:
            stale = {job.name: self._is_stale(job, self.latest[job.name]) for job in self.jobs}
            return {
                "schema_version": "1.0", "lifecycle": self.lifecycle,
                "runtime_instance_id": self.runtime_instance_id,
                "orchestrator_pid": os.getpid(), "boot_id": _boot_id(),
                "orchestrator_start_utc": self.start_utc,
                "orchestrator_start_monotonic": self.start_monotonic,
                "release_source_generation": SOURCE_GENERATION,
                "release_git_sha": self.release["git_commit_sha"],
                "release_git_tree_sha": self.release["git_tree_sha"],
                "effective_config_fingerprint": self.release["effective_config_fingerprint"],
                "policy_fingerprint": self.policy_fingerprint,
                "last_loop_progress_utc": self.last_loop_utc,
                "process_liveness": self.lifecycle in {"STARTING", "RUNNING", "STOPPING"},
                "useful_progress": dict(self.latest),
                "stale_useful_progress": stale,
                "running_children": {
                    name: {"pid": child.pid, "process_group_id": child.pid}
                    for name, child in sorted(self.running.items())
                },
                "previous_instance": self.previous_health,
                "blocked_job_cadence": [],
            }

    @staticmethod
    def _is_stale(job: Job, record: Mapping[str, object],
                  now: datetime | None = None) -> bool:
        if record.get("status") == "RUNNING":
            started = record.get("monotonic_start")
            deadline = record.get("deadline_seconds", job.deadline_seconds)
            return (isinstance(started, (int, float))
                    and isinstance(deadline, (int, float))
                    and time.monotonic() - started > deadline)
        anchor = record.get("scheduled_for_utc") or record.get("finished_at_utc")
        if not isinstance(anchor, str):
            return True
        try:
            invocation = datetime.fromisoformat(anchor.replace("Z", "+00:00"))
        except ValueError:
            return True
        stale_after = (job.cadence.next_after(invocation)
                       + timedelta(seconds=job.terminal_grace_seconds() + 60))
        return (now or datetime.now(timezone.utc)) > stale_after

    def persist(self) -> None:
        _atomic_json(self.health_path, self.health())

    def launch(self, job: Job, scheduled_for: datetime) -> bool:
        with self.guard:
            if self.stop_event.is_set():
                return False
            if job.name in self.active_jobs:
                record = self._base_record(job, scheduled_for)
                record.update(status="SKIPPED_OVERLAP", finished_at_utc=_utc(),
                              monotonic_end=time.monotonic(), failure_class="OVERLAP")
                record["duration_seconds"] = 0.0
                self.latest[job.name] = record
                self.persist()
                return False
            self.active_jobs.add(job.name)
            thread = threading.Thread(target=self._execute, args=(job, scheduled_for),
                                      name=f"bota-{job.name}", daemon=False)
            self.threads.add(thread)
            thread.start()
            return True

    def _base_record(self, job: Job, scheduled_for: datetime) -> dict[str, object]:
        return {"job_name": job.name, "runtime_instance_id": self.runtime_instance_id,
                "invocation_id": str(uuid.uuid4()),
                "scheduled_for_utc": scheduled_for.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "started_at_utc": None, "finished_at_utc": None,
                "monotonic_start": None, "monotonic_end": None, "status": "NOT_RUN",
                "exit_code": None, "duration_seconds": None,
                "deadline_seconds": job.deadline_seconds, "failure_class": None}

    def _execute(self, job: Job, scheduled_for: datetime) -> None:
        record = self._base_record(job, scheduled_for)
        started = time.monotonic()
        record.update(started_at_utc=_utc(), monotonic_start=started, status="RUNNING")
        with self.guard:
            self.latest[job.name] = record
            self.persist()
        process = None
        exit_code = None
        status, failure = "PASS", None
        output_tail = bytearray()
        stage_results: list[dict[str, object]] = []
        failed_stage = None
        current_stage = None
        try:
            for stage_index, argv in enumerate(job.commands, 1):
                stage_name = job.name_for_stage(stage_index - 1)
                current_stage = stage_name
                stage_deadline = job.deadline_for_stage(stage_index - 1)
                stage_started = time.monotonic()
                record.update(current_stage=stage_name, monotonic_start=stage_started,
                              deadline_seconds=stage_deadline)
                with self.guard:
                    self.latest[job.name] = record
                    self.persist()
                process = subprocess.Popen(argv, cwd=self.code_root, env=self.child_env(job),
                                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                assert process.stdout is not None
                reader = threading.Thread(target=self._drain_output,
                                          args=(process.stdout, output_tail), daemon=True)
                reader.start()
                with self.guard:
                    self.running[job.name] = process
                try:
                    exit_code = process.wait(timeout=stage_deadline)
                except subprocess.TimeoutExpired:
                    self._terminate_group(process)
                    exit_code = process.returncode
                    status, failure = "TIMED_OUT", "DEADLINE"
                    failed_stage = stage_name
                    stage_results.append({"stage": stage_name, "status": status,
                                          "deadline_seconds": stage_deadline,
                                          "exit_code": exit_code})
                    reader.join(timeout=1)
                    break
                reader.join(timeout=1)
                if exit_code != 0:
                    status, failure = "FAILED", "NONZERO_EXIT"
                    failed_stage = stage_name
                    stage_results.append({"stage": stage_name, "status": status,
                                          "deadline_seconds": stage_deadline,
                                          "exit_code": exit_code})
                    break
                stage_results.append({"stage": stage_name, "status": "PASS",
                                      "deadline_seconds": stage_deadline,
                                      "exit_code": exit_code,
                                      "duration_seconds": round(time.monotonic() - stage_started, 6)})
        except (OSError, ValueError) as exc:
            status, failure = "LAUNCH_ERROR", type(exc).__name__
            failed_stage = current_stage
        except subprocess.TimeoutExpired:
            status, failure = "TIMED_OUT", "DEADLINE"
            failed_stage = current_stage
        finally:
            if process is not None and process.poll() is None:
                self._terminate_group(process)
            ended = time.monotonic()
            record.update(status=status, exit_code=exit_code, failure_class=failure,
                          finished_at_utc=_utc(), monotonic_end=ended,
                          duration_seconds=round(ended - started, 6),
                          current_stage=current_stage, failed_stage=failed_stage,
                          stage_results=stage_results,
                          output_tail=output_tail.decode("utf-8", errors="replace"))
            with self.guard:
                self.running.pop(job.name, None)
                self.active_jobs.discard(job.name)
                self.latest[job.name] = record
                self.threads.discard(threading.current_thread())
                self.persist()

    @staticmethod
    def _drain_output(stream: object, tail: bytearray) -> None:
        """Drain continuously while retaining only a bounded diagnostic tail."""
        try:
            while chunk := stream.read(4096):
                tail.extend(chunk)
                if len(tail) > OUTPUT_LIMIT:
                    del tail[:-OUTPUT_LIMIT]
        finally:
            stream.close()

    @staticmethod
    def _process_group_exists(pgid: int) -> bool:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _terminate_group(self, process: subprocess.Popen[bytes]) -> None:
        pgid = process.pid
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            process.wait()
            return

        deadline = time.monotonic() + self.term_grace
        while self._process_group_exists(pgid):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if process.poll() is None:
                try:
                    process.wait(timeout=min(0.05, remaining))
                except subprocess.TimeoutExpired:
                    pass
            else:
                time.sleep(min(0.05, remaining))

        if self._process_group_exists(pgid):
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()

    def shutdown(self) -> None:
        self.stop_event.set()
        with self.guard:
            self.lifecycle = "STOPPING"
            children = list(self.running.values())
            self.persist()
        for child in children:
            self._terminate_group(child)
        for thread in list(self.threads):
            thread.join(timeout=self.term_grace + 2)
        with self.guard:
            self.lifecycle = "STOPPED"
            self.persist()
        if self.lock_file is not None:
            self.lock_file.close()
            self.lock_file = None

    def run(self) -> int:
        self.acquire_instance_lock()
        self.lifecycle = "RUNNING"
        now = datetime.now(timezone.utc)
        due = {job.name: job.cadence.next_after(now - timedelta(minutes=1)) for job in self.jobs}
        self.persist()
        while not self.stop_event.is_set():
            now = datetime.now(timezone.utc)
            for job in self.jobs:
                while due[job.name] <= now:
                    scheduled = due[job.name]
                    self.launch(job, scheduled)
                    due[job.name] = job.cadence.next_after(scheduled)
            self.last_loop_utc = _utc()
            self.persist()
            self.stop_event.wait(0.5)
        self.shutdown()
        return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv if argv is not None else sys.argv[1:])
    code_root = Path(os.environ.get("BOTA_CODE_ROOT") or os.environ.get("BOTA_ROOT") or ROOT)
    try:
        require_r5_bootstrap(code_root.resolve())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        return 78
    if arguments == ["--release-preflight"]:
        result = release_preflight(code_root)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0 if result["healthy"] else 1
    if arguments:
        print("unsupported arguments", file=sys.stderr)
        return 2
    mutable = os.environ.get("BOTA_MUTABLE_ROOT")
    if not mutable:
        print("BOTA_MUTABLE_ROOT is required", file=sys.stderr)
        return 2
    production_release = str(code_root).startswith("/opt/bota/")
    orchestrator = Orchestrator(code_root, Path(mutable),
                                require_release_manifest=production_release)
    def stop(_signum: int, _frame: object) -> None:
        orchestrator.stop_event.set()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        return orchestrator.run()
    except InstanceLocked as exc:
        print(str(exc), file=sys.stderr)
        return 73


if __name__ == "__main__":
    raise SystemExit(main())
