#!/usr/bin/env python3
"""Provider-specific request accounting and Twelve Data budget reservations.

This module deliberately separates request counts from provider credits. OANDA
and Yahoo requests are recorded for observability but never counted as Twelve
Data credits. Twelve Data callers must reserve credits before a request; the
reservation itself consumes the configured budget so concurrent callers cannot
oversubscribe it.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = "1.0"
KNOWN_PROVIDERS = {"oanda", "yahoo", "twelvedata", "unknown"}


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


def utc_day() -> str:
    """Return the current UTC accounting day."""
    return utc_now().strftime("%Y-%m-%d")


def root_dir() -> Path:
    """Resolve the BotA root, allowing isolated tests through BOTA_ROOT."""
    configured = os.environ.get("BOTA_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parent.parent


def state_path() -> Path:
    """Return the provider usage state path."""
    return root_dir() / "state" / "provider_usage.json"


def events_path() -> Path:
    """Return the append-only provider request ledger path."""
    return root_dir() / "logs" / "provider_calls.jsonl"


def lock_path() -> Path:
    """Return the process-shared accounting lock path."""
    return root_dir() / "state" / "provider_usage.lock"


def provider_template() -> dict[str, int]:
    """Return an empty provider counter record."""
    return {
        "requests": 0,
        "successes": 0,
        "failures": 0,
        "credits_consumed": 0,
    }


def empty_state(day: str | None = None) -> dict[str, Any]:
    """Return a fresh daily state document."""
    return {
        "schema_version": SCHEMA_VERSION,
        "utc_date": day or utc_day(),
        "providers": {},
        "reservations": {},
        "updated_at_utc": utc_now().isoformat(),
    }


def normalize_provider(value: str) -> str:
    """Normalize a provider without mapping unknown names to Twelve Data."""
    provider = str(value or "unknown").strip().lower()
    return provider if provider in KNOWN_PROVIDERS else provider or "unknown"


def load_state_unlocked(path: Path) -> dict[str, Any]:
    """Load state and reset counters when the UTC accounting day changes."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("state is not an object")
    except (OSError, ValueError):
        data = empty_state()

    if data.get("utc_date") != utc_day():
        return empty_state()

    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("providers", {})
    data.setdefault("reservations", {})
    return data


def save_state_unlocked(path: Path, state: dict[str, Any]) -> None:
    """Atomically persist provider usage state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at_utc"] = utc_now().isoformat()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def append_event_unlocked(event: dict[str, Any]) -> None:
    """Append one compact JSON event while the shared lock is held."""
    path = events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(event, separators=(",", ":"), sort_keys=True) + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())


@contextmanager
def locked_state() -> Iterator[tuple[Path, dict[str, Any]]]:
    """Yield the current state under an exclusive cross-process file lock."""
    lock = lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        path = state_path()
        state = load_state_unlocked(path)
        try:
            yield path, state
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def provider_counters(
    state: dict[str, Any],
    provider: str,
) -> dict[str, int]:
    """Return and initialize counters for one provider."""
    providers = state.setdefault("providers", {})
    counters = providers.setdefault(provider, provider_template())
    for key, default in provider_template().items():
        counters.setdefault(key, default)
    return counters


def event_base(
    args: argparse.Namespace,
    provider: str,
    action: str,
) -> dict[str, Any]:
    """Build common immutable event fields."""
    return {
        "event_id": uuid.uuid4().hex,
        "timestamp_utc": utc_now().isoformat(),
        "utc_date": utc_day(),
        "action": action,
        "provider": provider,
        "caller": str(getattr(args, "caller", "") or "unknown"),
        "pair": str(getattr(args, "pair", "") or "").upper(),
        "timeframe": str(getattr(args, "timeframe", "") or "").upper(),
        "status": str(getattr(args, "status", "") or "unknown").lower(),
        "credits": int(getattr(args, "credits", 0) or 0),
        "note": str(getattr(args, "note", "") or "")[:500],
    }


def command_record(args: argparse.Namespace) -> int:
    """Record a completed provider request."""
    provider = normalize_provider(args.provider)
    credit_cost = int(args.credits)
    if credit_cost < 0:
        raise ValueError("credits must be non-negative")
    if provider != "twelvedata" and credit_cost != 0:
        raise ValueError("non-Twelve-Data requests must use credits=0")

    with locked_state() as (path, state):
        counters = provider_counters(state, provider)
        counters["requests"] += 1
        if args.status.lower() == "success":
            counters["successes"] += 1
        else:
            counters["failures"] += 1
        counters["credits_consumed"] += credit_cost

        event = event_base(args, provider, "record")
        append_event_unlocked(event)
        save_state_unlocked(path, state)

    print(json.dumps({"result": "recorded", **event}, sort_keys=True))
    return 0


def budget_values() -> tuple[int, int, int]:
    """Return configured Twelve Data limit, reserve, and usable hard cap."""
    daily_limit = max(
        0,
        int(os.environ.get("TWELVE_DATA_DAILY_LIMIT", "800")),
    )
    reserve = max(
        0,
        int(os.environ.get("TWELVE_DATA_RESERVE_CREDITS", "100")),
    )
    hard_cap = max(0, daily_limit - reserve)
    return daily_limit, reserve, hard_cap


def command_reserve(args: argparse.Namespace) -> int:
    """Atomically reserve Twelve Data credits before an API request."""
    provider = normalize_provider(args.provider)
    credit_cost = int(args.credits)
    if provider != "twelvedata":
        raise ValueError(
            "credit reservations are supported only for provider=twelvedata"
        )
    if credit_cost <= 0:
        raise ValueError("credits must be positive")

    daily_limit, reserve, hard_cap = budget_values()
    reservation_id = uuid.uuid4().hex

    with locked_state() as (path, state):
        counters = provider_counters(state, provider)
        used = int(counters["credits_consumed"])
        allowed = used + credit_cost <= hard_cap
        event = event_base(args, provider, "reserve")
        event.update(
            {
                "reservation_id": reservation_id,
                "allowed": allowed,
                "daily_limit": daily_limit,
                "reserve_credits": reserve,
                "hard_cap": hard_cap,
                "credits_before": used,
                "credits_after": used + credit_cost if allowed else used,
            }
        )

        if allowed:
            counters["credits_consumed"] += credit_cost
            state.setdefault("reservations", {})[reservation_id] = {
                "credits": credit_cost,
                "caller": event["caller"],
                "pair": event["pair"],
                "timeframe": event["timeframe"],
                "created_at_utc": event["timestamp_utc"],
                "status": "reserved",
            }

        append_event_unlocked(event)
        save_state_unlocked(path, state)

    print(json.dumps(event, sort_keys=True))
    return 0 if allowed else 3


def command_complete(args: argparse.Namespace) -> int:
    """Mark a prior reservation completed without charging twice."""
    reservation_id = str(args.reservation_id).strip()
    with locked_state() as (path, state):
        reservation = state.setdefault("reservations", {}).get(reservation_id)
        if not isinstance(reservation, dict):
            print(
                json.dumps(
                    {
                        "result": "missing_reservation",
                        "reservation_id": reservation_id,
                    }
                )
            )
            return 2

        reservation["status"] = args.status.lower()
        reservation["completed_at_utc"] = utc_now().isoformat()
        event = event_base(args, "twelvedata", "complete")
        event["reservation_id"] = reservation_id
        event["credits"] = int(reservation.get("credits", 0))
        append_event_unlocked(event)
        save_state_unlocked(path, state)

    print(json.dumps({"result": "completed", **event}, sort_keys=True))
    return 0


def command_status(args: argparse.Namespace) -> int:
    """Print provider-specific daily accounting."""
    with locked_state() as (path, state):
        save_state_unlocked(path, state)
        snapshot = json.loads(json.dumps(state))

    daily_limit, reserve, hard_cap = budget_values()
    twelve = snapshot.get("providers", {}).get(
        "twelvedata",
        provider_template(),
    )
    snapshot["twelvedata_budget"] = {
        "daily_limit": daily_limit,
        "reserve_credits": reserve,
        "hard_cap": hard_cap,
        "credits_consumed": int(twelve.get("credits_consumed", 0)),
        "credits_remaining_to_hard_cap": max(
            0,
            hard_cap - int(twelve.get("credits_consumed", 0)),
        ),
    }
    if args.json:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
    else:
        providers = snapshot.get("providers", {})
        for name in sorted(providers):
            row = providers[name]
            print(
                f"PROVIDER={name} REQUESTS={row.get('requests', 0)} "
                f"SUCCESS={row.get('successes', 0)} "
                f"FAIL={row.get('failures', 0)} "
                f"CREDITS={row.get('credits_consumed', 0)}"
            )
        print(
            "TWELVE_DATA_BUDGET "
            f"USED={snapshot['twelvedata_budget']['credits_consumed']} "
            f"HARD_CAP={hard_cap} "
            f"DAILY_LIMIT={daily_limit} RESERVE={reserve}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser(
        "record",
        help="record one completed provider request",
    )
    record.add_argument("--provider", required=True)
    record.add_argument("--caller", required=True)
    record.add_argument("--pair", default="")
    record.add_argument("--timeframe", default="")
    record.add_argument(
        "--status",
        choices=("success", "failure", "blocked"),
        required=True,
    )
    record.add_argument("--credits", type=int, default=0)
    record.add_argument("--note", default="")
    record.set_defaults(func=command_record)

    reserve_parser = sub.add_parser(
        "reserve",
        help="reserve Twelve Data credits before a request",
    )
    reserve_parser.add_argument("--provider", default="twelvedata")
    reserve_parser.add_argument("--caller", required=True)
    reserve_parser.add_argument("--pair", default="")
    reserve_parser.add_argument("--timeframe", default="")
    reserve_parser.add_argument("--status", default="reserved")
    reserve_parser.add_argument("--credits", type=int, required=True)
    reserve_parser.add_argument("--note", default="")
    reserve_parser.set_defaults(func=command_reserve)

    complete = sub.add_parser(
        "complete",
        help="complete a prior reservation",
    )
    complete.add_argument("--reservation-id", required=True)
    complete.add_argument("--caller", default="unknown")
    complete.add_argument("--pair", default="")
    complete.add_argument("--timeframe", default="")
    complete.add_argument(
        "--status",
        choices=("success", "failure"),
        required=True,
    )
    complete.add_argument("--credits", type=int, default=0)
    complete.add_argument("--note", default="")
    complete.set_defaults(func=command_complete)

    status = sub.add_parser(
        "status",
        help="show current provider-specific usage",
    )
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=command_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the selected provider-usage command."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (OSError, ValueError) as exc:
        print(
            f"PROVIDER_USAGE_ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
