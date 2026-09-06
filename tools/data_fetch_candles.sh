#!/usr/bin/env bash
###############################################################################
# FILE: tools/data_fetch_candles.sh
# ROLE: R5 measurement-hardening compatibility wrapper.
#
# - preserves the historical fetcher verbatim as data_fetch_candles_r5_legacy.sh
# - keeps non-D1 behavior unchanged, then stamps Yahoo provider identity
# - fetches enough D1 history (6mo) to satisfy the existing >=60-bar indicator
#   contract without lowering that contract
# - records provider requests through the mutable-root provider accounting shim
###############################################################################
set -euo pipefail
shopt -s inherit_errexit 2>/dev/null || true

CODE_ROOT="${BOTA_CODE_ROOT:-${BOTA_ROOT:-${HOME}/BotA}}"
MUTABLE_ROOT="${BOTA_MUTABLE_ROOT:-${CODE_ROOT}}"
TOOLS_DIR="${CODE_ROOT}/tools"
CACHE_DIR="${MUTABLE_ROOT}/cache"
DATA_DIR="${MUTABLE_ROOT}/data/candles"
LOG_DIR="${MUTABLE_ROOT}/logs"
LEGACY_FETCHER="${TOOLS_DIR}/data_fetch_candles_r5_legacy.sh"
PROVIDER_USAGE="${TOOLS_DIR}/provider_usage.py"

if [[ "${BOTA_PATH_CONTRACT_CHECK:-0}" == 1 ]]; then
  exec bash "${LEGACY_FETCHER}" "$@"
fi

PAIR_RAW="${1:-}"
TF_RAW="${2:-}"
[[ -z "${PAIR_RAW}" || -z "${TF_RAW}" ]] && {
  printf 'Usage: %s <PAIR> <TF>\n' "$0" >&2
  exit 1
}

PAIR="$(printf '%s' "${PAIR_RAW}" | tr -d '/ ' | tr '[:lower:]' '[:upper:]')"
TF="$(printf '%s' "${TF_RAW}" | tr -d ' ' | tr '[:lower:]' '[:upper:]')"

mkdir -p "${CACHE_DIR}" "${DATA_DIR}" "${LOG_DIR}"

# Preserve the historical environment-loading behavior for the D1 path.
if [[ -f "${CODE_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${CODE_ROOT}/.env"
  set +a
fi

if [[ "${TF}" != "D1" && "${TF}" != "1D" ]]; then
  set +e
  bash "${LEGACY_FETCHER}" "$@"
  rc=$?
  set -e
  [[ "${rc}" -eq 0 ]] || exit "${rc}"

  # Historical Yahoo payloads do not include _provider, while historical OANDA
  # payloads do. Stamp only the missing case so updater decision evidence can
  # identify Yahoo rather than "unknown".
  CACHE_PATH="${CACHE_DIR}/${PAIR}_${TF}.json" python3 <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["CACHE_PATH"])
data = json.loads(path.read_text(encoding="utf-8"))
result = data.get("chart", {}).get("result", [])
if result and isinstance(result[0], dict):
    meta = result[0].setdefault("meta", {})
    if not str(meta.get("_provider") or "").strip():
        meta["_provider"] = "yahoo"
        tmp = path.with_name(f".{path.name}.provider.tmp")
        tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, path)
PY
  exit 0
fi

export PAIR TF CODE_ROOT MUTABLE_ROOT CACHE_DIR DATA_DIR LOG_DIR PROVIDER_USAGE
export OANDA_API_TOKEN="${OANDA_API_TOKEN:-}"
export OANDA_API_URL="${OANDA_API_URL:-https://api-fxpractice.oanda.com}"
export UA="${UA:-Mozilla/5.0 (Linux; Android 13; Termux) AppleWebKit/537.36}"

python3 <<'PY'
from __future__ import annotations

import datetime
import json
import math
import os
import statistics
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

pair = os.environ["PAIR"]
tf = os.environ["TF"]
cache_dir = Path(os.environ["CACHE_DIR"])
data_dir = Path(os.environ["DATA_DIR"])
provider_usage = Path(os.environ["PROVIDER_USAGE"])
token = os.environ.get("OANDA_API_TOKEN", "").strip()
base = os.environ.get("OANDA_API_URL", "https://api-fxpractice.oanda.com").rstrip("/")
ua = os.environ.get("UA", "Mozilla/5.0")

out_json = cache_dir / f"{pair}_D1.json"
out_csv = data_dir / f"{pair}_D1.csv"


def record(provider: str, status: str, note: str = "") -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(provider_usage),
            "record",
            "--provider", provider,
            "--caller", "data_fetch_candles",
            "--pair", pair,
            "--timeframe", "D1",
            "--status", status,
            "--credits", "0",
            "--note", note[:500],
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        message = (result.stderr or "").strip()[:500]
        raise RuntimeError(f"provider_accounting_failed:{provider}:{message}")


def valid_candles_from_chart(data: dict):
    result = data.get("chart", {}).get("result", [])
    if not result or not isinstance(result[0], dict):
        return []
    quote = (result[0].get("indicators", {}) or {}).get("quote", [{}])[0] or {}
    stamps = result[0].get("timestamp", []) or []
    opens = quote.get("open", []) or []
    highs = quote.get("high", []) or []
    lows = quote.get("low", []) or []
    closes = quote.get("close", []) or []
    rows = []
    for values in zip(stamps, opens, highs, lows, closes):
        try:
            stamp = int(values[0])
            o, h, l, c = map(float, values[1:])
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(x) for x in (o, h, l, c)) or c <= 0:
            continue
        rows.append((stamp, o, h, l, c))
    rows.sort()
    return rows


def validate_daily(rows) -> None:
    if len(rows) < 60:
        raise RuntimeError(f"d1_history_insufficient:{len(rows)}")
    deltas = [
        (rows[i][0] - rows[i - 1][0]) / 60.0
        for i in range(1, len(rows))
        if rows[i][0] > rows[i - 1][0]
    ]
    if not deltas:
        raise RuntimeError("d1_history_no_positive_deltas")
    median = statistics.median(deltas)
    if abs(median - 1440.0) > 72.0:
        raise RuntimeError(f"d1_timeframe_mismatch:median_min={median}")


def write_outputs(data: dict, rows) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    tmp_json = out_json.with_name(f".{out_json.name}.tmp.{os.getpid()}")
    tmp_csv = out_csv.with_name(f".{out_csv.name}.tmp.{os.getpid()}")
    tmp_json.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    with tmp_csv.open("w", encoding="utf-8") as handle:
        handle.write("time,open,high,low,close\n")
        for stamp, o, h, l, c in rows[-500:]:
            text = datetime.datetime.fromtimestamp(
                stamp, tz=datetime.timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S")
            handle.write(f"{text},{o:.8f},{h:.8f},{l:.8f},{c:.8f}\n")
    os.replace(tmp_json, out_json)
    os.replace(tmp_csv, out_csv)


def fetch_oanda() -> dict | None:
    if not token:
        return None
    instrument = f"{pair[:3]}_{pair[3:6]}"
    url = f"{base}/v3/instruments/{instrument}/candles?count=500&granularity=D&price=M"
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = json.loads(response.read())
        candles = [c for c in raw.get("candles", []) if c.get("complete", True)]
        stamps, opens, highs, lows, closes = [], [], [], [], []
        for candle in candles:
            try:
                dt = datetime.datetime.fromisoformat(candle["time"].replace("Z", "+00:00"))
                mid = candle["mid"]
                stamps.append(int(dt.timestamp()))
                opens.append(float(mid["o"]))
                highs.append(float(mid["h"]))
                lows.append(float(mid["l"]))
                closes.append(float(mid["c"]))
            except Exception:
                continue
        data = {
            "chart": {
                "result": [{
                    "meta": {"dataGranularity": "D", "_provider": "oanda"},
                    "timestamp": stamps,
                    "indicators": {"quote": [{
                        "open": opens, "high": highs, "low": lows, "close": closes,
                    }]},
                }],
                "error": None,
            }
        }
        rows = valid_candles_from_chart(data)
        validate_daily(rows)
        record("oanda", "success", "granularity=D")
        write_outputs(data, rows)
        print(f"[FETCH-HARDEN] D1 provider=oanda rows={len(rows)}", file=sys.stderr)
        return data
    except Exception as exc:
        try:
            record("oanda", "failure", type(exc).__name__)
        except Exception:
            raise
        print(f"[FETCH-HARDEN] OANDA D1 failed: {type(exc).__name__}; fallback=yahoo", file=sys.stderr)
        return None


def fetch_yahoo() -> None:
    symbol = f"{pair}=X" if len(pair) == 6 else pair
    query = urllib.parse.urlencode({
        "range": "6mo",
        "interval": "1d",
        "includePrePost": "false",
        "events": "div|split",
    })
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read())
        result = data.get("chart", {}).get("result", [])
        if not result or not isinstance(result[0], dict):
            raise RuntimeError("yahoo_d1_missing_result")
        meta = result[0].setdefault("meta", {})
        meta["_provider"] = "yahoo"
        rows = valid_candles_from_chart(data)
        validate_daily(rows)
        record("yahoo", "success", "interval=1d;range=6mo")
        write_outputs(data, rows)
        print(f"[FETCH-HARDEN] D1 provider=yahoo rows={len(rows)} range=6mo", file=sys.stderr)
    except Exception as exc:
        try:
            record("yahoo", "failure", type(exc).__name__)
        except Exception:
            raise
        raise


if fetch_oanda() is None:
    fetch_yahoo()
PY
