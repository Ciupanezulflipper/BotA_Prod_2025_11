#!/data/data/com.termux/files/usr/bin/python3
# -*- coding: utf-8 -*-
"""
run_signal_once.py - Stage 1 scalping logic with Telegram alerts

Features:
- Pip-based spike detection
- BUY/SELL/WAIT decisions
- Score scaling (50-70 range)
- Telegram alerts for signals (score > 0), with hard send-gates:
  - DRY_RUN_MODE=true blocks sending entirely
  - TELEGRAM_ENABLED=0 blocks sending entirely
- Cooldown and spread-aware
- Backward compatible with existing BotA shell scripts
"""

import os
import sys
import json
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone
import html


# --- Environment / configuration ---
BASE_DIR = os.environ.get("BASE_DIR", os.path.join(os.environ.get("HOME", ""), "BotA"))

def _env_truthy(val: str) -> bool:
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")

DRY_RUN = _env_truthy(os.environ.get("DRY_RUN_MODE", "true"))
TELEGRAM_ENABLED = _env_truthy(os.environ.get("TELEGRAM_ENABLED", "1"))

ORDER = [
    p.strip()
    for p in os.environ.get("PROVIDER_ORDER", "twelve_data,yahoo,alpha_vantage").split(",")
    if p.strip()
]

TIMEOUT = int(os.environ.get("PROVIDER_TIMEOUT_SECS", "8"))
ALPHAV_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "")
TD_KEY = os.environ.get("TWELVEDATA_API_KEY", "")


# --- Time helpers ---
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _age_minutes(dt: datetime) -> float:
    try:
        return max(0.0, (_utcnow() - dt).total_seconds() / 60.0)
    except Exception:
        return 999.9


# --- Pair / pip helpers ---
def _pair_to_fx_parts(pair: str):
    """
    Robust split of a FX pair into (base, quote).
    Enforces 3+3 currency codes if no '/' separator.
    """
    p = pair.strip().upper()
    base = quote = None

    if "/" in p:
        a, b = p.split("/", 1)
        base, quote = a.strip(), b.strip()
    elif len(p) == 6:
        base, quote = p[:3], p[3:6]
    else:
        raise ValueError(f"Ambiguous currency pair format: {pair}")

    if len(base) != 3 or len(quote) != 3:
        raise ValueError(f"Base or quote currency is not 3 characters: {base}/{quote}")

    return base, quote


def _pip_multiplier(pair: str) -> float:
    """
    Pip multiplier depending on quote currency.
    Default: 1 pip = 0.0001 (10000.0 factor)
    JPY & metals: 1 pip = 0.01 (100.0 factor)
    """
    try:
        _, quote = _pair_to_fx_parts(pair)
    except Exception:
        return 10000.0

    if quote == "JPY":
        return 100.0
    if quote in ("XAU", "XAG", "XPT", "XPD"):
        return 100.0
    return 10000.0


# --- Quota guard wrapper ---
def _guard(provider: str, cost: int = 1) -> bool:
    """
    Consult tools/quota_guard.sh for API usage limits.
    Return False if provider must not be called.
    """
    guard = os.path.join(BASE_DIR, "tools", "quota_guard.sh")
    if not os.path.exists(guard):
        return True

    try:
        r = subprocess.run(
            ["bash", guard, "--provider", provider, "--cost", str(cost)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if r.returncode == 0:
            return True
        if r.returncode == 97:
            return False
        return False
    except Exception as e:
        print(f"[warn] quota_guard failed for {provider}: {e}", file=sys.stderr)
        return False


# --- Providers (HTTP) ---
def fetch_twelve_data(pair: str):
    """
    Fetch last 15m bar close from TwelveData.
    Returns: (provider_name, price, dt_utc)
    """
    if not TD_KEY:
        raise RuntimeError("TwelveData key missing")

    if not _guard("twelve_data", 1):
        raise RuntimeError("TwelveData blocked by quota_guard")

    base, quote = _pair_to_fx_parts(pair)
    symbol = f"{base}/{quote}"

    url = (
        "https://api.twelvedata.com/time_series"
        f"?symbol={symbol}&interval=15min&outputsize=1&apikey={TD_KEY}"
    )

    req = urllib.request.Request(url, headers={"User-Agent": "BotA/td"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8", "ignore"))

    if data.get("status") != "ok":
        raise RuntimeError(data.get("message", "TD error"))

    values = data.get("values") or []
    if not values:
        raise RuntimeError("TD empty values")

    last = values[0]
    dt_str = last.get("datetime")
    close = last.get("close")
    if not dt_str or close is None:
        raise RuntimeError("TD malformed response")

    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return "twelve_data", float(close), dt


def fetch_yahoo(pair: str):
    """
    Fetch last 15m close from Yahoo Finance.
    Returns: (provider_name, price, dt_utc)
    """
    base, quote = _pair_to_fx_parts(pair)
    symbol = f"{base}{quote}=X"

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=15m"
    req = urllib.request.Request(url, headers={"User-Agent": "BotA/yf"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8", "ignore"))

    chart = data.get("chart")
    if not chart:
        raise RuntimeError("yf missing 'chart' key in response")

    res = chart.get("result")
    if not res:
        err = chart.get("error") or {}
        raise RuntimeError(err.get("description", "yf no result"))

    r0 = res[0]
    ts_list = r0.get("timestamp") or []
    ind = (r0.get("indicators") or {}).get("quote") or []

    if not ts_list or not ind:
        raise RuntimeError("yf malformed indicators")

    closes = ind[0].get("close") or []
    i = len(closes) - 1
    while i >= 0 and closes[i] is None:
        i -= 1
    if i < 0:
        raise RuntimeError("yf null closes")

    epoch = int(ts_list[i])
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return "yahoo", float(closes[i]), dt


def fetch_alpha_vantage(pair: str):
    """
    Fetch last 5m FX close from AlphaVantage.
    Returns: (provider_name, price, dt_utc)
    """
    if not ALPHAV_KEY:
        raise RuntimeError("AlphaVantage key missing")

    base, quote = _pair_to_fx_parts(pair)
    url = (
        "https://www.alphavantage.co/query"
        f"?function=FX_INTRADAY&from_symbol={base}&to_symbol={quote}"
        f"&interval=5min&outputsize=compact&apikey={ALPHAV_KEY}"
    )

    req = urllib.request.Request(url, headers={"User-Agent": "BotA/av"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8", "ignore"))

    if any(k in data for k in ("Note", "Information", "Error Message")):
        raise RuntimeError(
            data.get("Note")
            or data.get("Information")
            or data.get("Error Message")
            or "AlphaVantage error"
        )

    ts_key = next((k for k in data.keys() if k.startswith("Time Series FX")), None)
    if not ts_key:
        raise RuntimeError("AlphaVantage missing time series key")

    series = data.get(ts_key) or {}
    if not series:
        raise RuntimeError("AlphaVantage empty time series")

    try:
        tkey = sorted(series.keys())[-1]
    except Exception:
        raise RuntimeError("AlphaVantage time series sorting failed")

    point = series.get(tkey) or {}
    if "4. close" not in point:
        raise RuntimeError("AlphaVantage missing close price")

    close = float(point["4. close"])
    dt = datetime.strptime(tkey, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return "alpha_vantage", close, dt


PROVIDER_FUN = {
    "twelve_data": fetch_twelve_data,
    "yahoo": fetch_yahoo,
    "alpha_vantage": fetch_alpha_vantage,
}


# --- CSV history loader ---
def _load_prev_price(csv_path: str, pair: str, max_age_hours: float = 24.0):
    """
    Load last logged price for this pair from CSV, with max-age filter.
    Returns: (prev_price: float or None, prev_ts: datetime or None)
    """
    if not os.path.exists(csv_path):
        return None, None

    last_price = None
    last_ts = None

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("timestamp"):
                    continue
                parts = line.split(",")
                if len(parts) < 8:
                    continue
                ts, p, decision, score, weak, provider, age_min, price = parts[:8]
                if p != pair:
                    continue
                try:
                    last_price = float(price)
                    last_ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    continue

        if last_ts is not None and last_price is not None:
            age_hours = (_utcnow() - last_ts).total_seconds() / 3600.0
            if age_hours > max_age_hours:
                print(
                    f"[warn] Last price for {pair} is {age_hours:.1f}h old, ignoring",
                    file=sys.stderr,
                )
                return None, None

        return last_price, last_ts

    except Exception as e:
        print(f"[warn] Failed to read previous price from {csv_path}: {e}", file=sys.stderr)
        return None, None


# --- Signal computation (scalping logic) ---
def _compute_signal(pair: str, price: float, prev_price: float, prev_ts: datetime = None):
    """
    Compute BUY/SELL/WAIT based on pip spike.
    Uses:
    - SCALP_PIPS_THRESHOLD
    - WEAK_SIGNAL_THRESHOLD
    - FULL_SIGNAL_THRESHOLD
    - MIN_SIGNAL_GAP_MINUTES
    - DEFAULT_SPREAD_PIPS / SPREAD_<PAIR>
    """
    decision = "WAIT"
    score = 0
    weak = False

    if prev_price is None:
        return decision, score, weak

    # Cooldown
    try:
        min_minutes = float(os.environ.get("MIN_SIGNAL_GAP_MINUTES", "5"))
    except ValueError:
        min_minutes = 5.0

    if prev_ts is not None:
        try:
            minutes_since = (_utcnow() - prev_ts).total_seconds() / 60.0
            if minutes_since < min_minutes:
                return "WAIT", 0, False
        except Exception:
            pass

    try:
        pip_mult = _pip_multiplier(pair)
        pips = abs(price - prev_price) * pip_mult

        try:
            threshold = float(os.environ.get("SCALP_PIPS_THRESHOLD", "8.0"))
        except ValueError:
            threshold = 8.0

        try:
            weak_th = float(os.environ.get("WEAK_SIGNAL_THRESHOLD", "50"))
        except ValueError:
            weak_th = 50.0

        try:
            full_th = float(os.environ.get("FULL_SIGNAL_THRESHOLD", "60"))
        except ValueError:
            full_th = 60.0

        # Spread awareness
        spread_env_key = f"SPREAD_{pair}"
        try:
            spread_pips = float(
                os.environ.get(
                    spread_env_key,
                    os.environ.get("DEFAULT_SPREAD_PIPS", "0.0"),
                )
            )
        except ValueError:
            spread_pips = 0.0

        effective_threshold = threshold + spread_pips

        if pips >= effective_threshold:
            decision = "BUY" if price > prev_price else "SELL"

            extra = max(pips - threshold, 0.0)
            extra = min(extra, 20.0)

            score = int(round(50 + (extra / 20.0) * 20))
            weak = weak_th <= score < full_th

        return decision, score, weak

    except Exception as e:
        print(f"[warn] Failed to compute signal for {pair}: {e}", file=sys.stderr)
        return "WAIT", 0, False


# --- CSV logger ---
def _append_history(
    csv_path: str,
    pair: str,
    decision: str,
    score: int,
    weak: bool,
    provider: str,
    age_min: float,
    price: float,
):
    """
    Append one line to signal_history.csv
    """
    log_dir = os.path.dirname(csv_path)
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception as e:
        print(f"[warn] Failed to create log dir {log_dir}: {e}", file=sys.stderr)

    ts = _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    line = (
        f"{ts},{pair},{decision},{score},{str(weak).lower()},"
        f"{provider},{age_min:.1f},{price:.5f},{str(DRY_RUN).lower()}\n"
    )

    try:
        new_file = not os.path.exists(csv_path)
        with open(csv_path, "a", encoding="utf-8") as f:
            if new_file:
                header = "timestamp,pair,decision,score,weak,provider,age_min,price,dry_run\n"
                f.write(header)
            f.write(line)
    except Exception as e:
        print(f"[warn] Logging to {csv_path} failed: {e}", file=sys.stderr)


# --- Telegram alert function (HTML standardized) ---
def _send_telegram_alert(pair: str, decision: str, score: int, weak: bool,
                         price: float, provider: str, age: float, pips: float):
    """
    Send Telegram alert for BUY/SELL signals (score > 0 only).

    Standard sender: tools/send_tg.sh (underscore), parse_mode=HTML.
    Hard gates:
      - DRY_RUN_MODE=true blocks sending entirely
      - TELEGRAM_ENABLED=0 blocks sending entirely
    """
    if score <= 0:
        return  # Only alert on actual signals

    if not TELEGRAM_ENABLED:
        print(f"[tg] TELEGRAM_ENABLED=0 -> suppressed alert for {decision} {pair}", file=sys.stderr)
        return

    if DRY_RUN:
        print(f"[tg] DRY_RUN_MODE=true -> suppressed alert for {decision} {pair}", file=sys.stderr)
        return

    safe_pair = html.escape(str(pair), quote=False)
    safe_decision = html.escape(str(decision), quote=False)
    safe_provider = html.escape(str(provider), quote=False)

    if decision == "BUY":
        direction_emoji = "🟢"
    elif decision == "SELL":
        direction_emoji = "🔴"
    else:
        direction_emoji = "⚪"

    strength = "weak" if weak else "FULL"
    strength_emoji = "💡" if weak else "⚡"

    threshold_txt = html.escape(str(os.environ.get("SCALP_PIPS_THRESHOLD", "8.0")), quote=False)

    message = (
        f"{direction_emoji} <b>{safe_decision} Signal</b> - <b>{safe_pair}</b>\n"
        f"\n"
        f"{strength_emoji} <i>Score:</i> <b>{int(score)}</b> ({html.escape(str(strength), quote=False)})\n"
        f"💰 <i>Price:</i> <b>{price:.5f}</b>\n"
        f"📊 <i>Move:</i> <b>{pips:.1f}</b> pips\n"
        f"⏰ <i>Time:</i> {_utcnow().strftime('%H:%M UTC')}\n"
        f"📡 <i>Provider:</i> <i>{safe_provider}</i>\n"
        f"⏱️ <i>Age:</i> {age:.1f} min\n"
        f"\n"
        f"🎯 <i>Threshold:</i> {threshold_txt} pips\n"
        f"\n"
        f"⚡ #Live #BotA #Scalper"
    )

    tg_script = os.path.join(BASE_DIR, "tools", "send_tg.sh")
    if not os.path.exists(tg_script):
        print(f"[warn] Telegram script not found: {tg_script}", file=sys.stderr)
        return

    try:
        env = os.environ.copy()
        env["TELEGRAM_PARSE_MODE"] = "HTML"
        result = subprocess.run(
            ["bash", tg_script, "--text", message],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            env=env,
        )
        if result.returncode == 0:
            print(f"[tg] Alert sent for {decision} {pair}", file=sys.stderr)
        else:
            err_snip = (result.stderr or "").strip()
            if len(err_snip) > 300:
                err_snip = err_snip[:300] + "..."
            print(f"[warn] Telegram send failed (rc={result.returncode}): {err_snip}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("[warn] Telegram send timeout", file=sys.stderr)
    except Exception as e:
        print(f"[warn] Telegram error: {e}", file=sys.stderr)


# --- Self-test mode (env-agnostic) ---
def _self_test():
    """
    Basic self-tests for pip multiplier and signal computation.

    IMPORTANT:
    - Temporarily overrides env vars that affect _compute_signal so tests
      are deterministic and not influenced by .env.runtime (spread, cooldown).
    """
    print("[TEST] Running self-tests...")

    # 1) Pip multiplier checks
    assert _pip_multiplier("EURUSD") == 10000.0, "EURUSD pip multiplier mismatch"
    assert _pip_multiplier("USDJPY") == 100.0, "USDJPY pip multiplier mismatch"
    print("✓ Pip multiplier OK")

    # Save old env to restore later
    keys = [
        "SCALP_PIPS_THRESHOLD",
        "WEAK_SIGNAL_THRESHOLD",
        "FULL_SIGNAL_THRESHOLD",
        "MIN_SIGNAL_GAP_MINUTES",
        "DEFAULT_SPREAD_PIPS",
        "SPREAD_EURUSD",
    ]
    old_env = {k: os.environ.get(k) for k in keys}

    try:
        # Make signal logic deterministic for tests
        os.environ["SCALP_PIPS_THRESHOLD"] = "8.0"
        os.environ["WEAK_SIGNAL_THRESHOLD"] = "50"
        os.environ["FULL_SIGNAL_THRESHOLD"] = "60"
        os.environ["MIN_SIGNAL_GAP_MINUTES"] = "0"
        os.environ["DEFAULT_SPREAD_PIPS"] = "0"
        if "SPREAD_EURUSD" in os.environ:
            del os.environ["SPREAD_EURUSD"]

        # 2) Expect BUY when move >= 8 pips
        decision, score, weak = _compute_signal("EURUSD", 1.1000, 1.0992, None)
        assert decision == "BUY", f"Expected BUY, got {decision}"
        assert score >= 50, f"Expected score >= 50, got {score}"
        print(f"✓ Signal generation OK (decision={decision}, score={score})")

        # 3) Expect WAIT on small move below threshold
        decision2, score2, weak2 = _compute_signal("EURUSD", 1.1000, 1.0998, None)
        assert decision2 == "WAIT", f"Expected WAIT for small move, got {decision2}"
        print("✓ Small move WAIT OK")

        print("[TEST] All tests passed!")
    finally:
        # Restore original env
        for k, v in old_env.items():
            if v is None:
                if k in os.environ:
                    del os.environ[k]
            else:
                os.environ[k] = v if isinstance(v, str) else str(v)


# --- Main entrypoint ---
def main():
    # Self-test mode
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        _self_test()
        sys.exit(0)

    if len(sys.argv) < 2:
        print("usage: run_signal_once.py <PAIR>  # or --test", file=sys.stderr)
        sys.exit(2)

    pair = sys.argv[1].strip().upper()

    # 1) Fetch live price from providers
    errs = []
    got = None

    for prov in ORDER:
        fn = PROVIDER_FUN.get(prov)
        if not fn:
            errs.append(f"{prov}: unsupported")
            continue
        try:
            got = fn(pair)
            break
        except Exception as e:
            errs.append(f"{prov}: {e}")

    if not got:
        print(f"[run] {pair} TF15 decision=WAIT score=0 weak=false provider=? age=999.9 price=?")
        if errs:
            print("[warn] providers failed: " + "; ".join(errs), file=sys.stderr)
        sys.exit(0)

    provider, price, dt = got
    age = _age_minutes(dt)

    # 2) Load previous price from CSV
    logs_dir = os.path.join(BASE_DIR, "logs")
    csv_path = os.path.join(logs_dir, "signal_history.csv")

    try:
        max_age_hours = float(os.environ.get("MAX_PRICE_AGE_HOURS", "24"))
    except ValueError:
        max_age_hours = 24.0

    prev_price, prev_ts = _load_prev_price(csv_path, pair, max_age_hours=max_age_hours)

    # 3) Compute decision/score using scalping logic
    decision, score, weak = _compute_signal(pair, price, prev_price, prev_ts)

    # 4) Calculate pips moved for Telegram alert
    if prev_price is not None:
        pip_mult = _pip_multiplier(pair)
        pips_moved = abs(price - prev_price) * pip_mult
    else:
        pips_moved = 0.0

    # 5) Send Telegram alert if signal fired (send function enforces DRY_RUN + TELEGRAM_ENABLED)
    if score > 0:
        _send_telegram_alert(pair, decision, score, weak, price, provider, age, pips_moved)

    # 6) Append to CSV history
    _append_history(
        csv_path=csv_path,
        pair=pair,
        decision=decision,
        score=score,
        weak=weak,
        provider=provider,
        age_min=age,
        price=price,
    )

    # 7) Print summary for shell scripts
    print(
        f"[run] {pair} TF15 decision={decision} score={score} "
        f"weak={str(weak).lower()} provider={provider} age={age:.1f} price={price:.5f}"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
