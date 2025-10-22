# calendar_tab.py  Economic Calendar tab (TradingEconomics-first)
# Aiogram v3.x router. Paste as-is (no edits required).

from __future__ import annotations

import logging
import time
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta, timezone

import requests
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
logger = logging.getLogger("calendar-tab")

# ------------------------------------------------------------------------------
# Router
# ------------------------------------------------------------------------------
router = Router(name="calendar-tab")

# ------------------------------------------------------------------------------
# Constants & configuration
# ------------------------------------------------------------------------------
ITEMS_PER_PAGE = 8
CACHE_TTL = 180.0               # 3 minutes
STALE_GRACE = 900.0             # 15 minutes
DEBOUNCE_SEC = 1.0              # per-user click debounce

# Default range preset
DEFAULT_RANGE = "next7"         # today | next3 | next7 | thisweek

RANGE_DELTAS: Dict[str, timedelta] = {
    "today": timedelta(days=1),
    "next3": timedelta(days=3),
    "next7": timedelta(days=7),
    "thisweek": None,  # computed dynamically MonSun
}

# Country  currency mapping (extendable)
COUNTRY_TO_CCY = {
    "United States": "USD",
    "Euro Area": "EUR",
    "Eurozone": "EUR",
    "United Kingdom": "GBP",
    "Japan": "JPY",
    "Australia": "AUD",
    "Canada": "CAD",
    "Switzerland": "CHF",
    "New Zealand": "NZD",
    "China": "CNY",
    "Vietnam": "VND",
    "India": "INR",
    "Euro": "EUR",
}

IMPACT_EMOJI = {"high": "", "medium": "", "low": ""}

# Providers registry
PROVIDERS: Dict[str, Dict] = {
    "tradingeconomics": {
        "title": "TradingEconomics",
        "default_enabled": True,
        "fetch": "fetch_tradingeconomics",
        "supports_values": True,
    },
    # Optional/experimental (disabled by default)
    "fxstreet": {
        "title": "FXStreet (RSS)",
        "default_enabled": False,
        "fetch": "fetch_fxstreet_disabled",
        "supports_values": True,
    },
    "dailyfx": {
        "title": "DailyFX (HTML)",
        "default_enabled": False,
        "fetch": "fetch_dailyfx_disabled",
        "supports_values": True,
    },
}

# ------------------------------------------------------------------------------
# Data models & state
# ------------------------------------------------------------------------------
@dataclass
class Event:
    id: str
    provider: str
    datetime_utc: datetime
    country: str
    currency: str
    name: str
    impact: str  # low|medium|high
    previous: Optional[str] = None
    forecast: Optional[str] = None
    actual: Optional[str] = None
    revised: Optional[str] = None
    description: Optional[str] = None


@dataclass
class UserState:
    enabled_providers: Set[str] = field(
        default_factory=lambda: {k for k, v in PROVIDERS.items() if v["default_enabled"]}
    )
    selected_impacts: Set[str] = field(default_factory=lambda: {"high", "medium"})
    selected_currencies: Set[str] = field(default_factory=lambda: {"USD", "EUR", "GBP", "JPY"})
    range_preset: str = DEFAULT_RANGE
    page: int = 0
    open_id: Optional[str] = None
    last_click: float = 0.0


# Per-provider cache: {provider: (timestamp, [Event, ...])}
CACHE: Dict[str, Tuple[float, List[Event]]] = {}

# Per-user state
USER_STATES: Dict[int, UserState] = {}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _start_end_from_preset(preset: str) -> Tuple[datetime, datetime]:
    now = _now_utc()
    if preset == "thisweek":
        # Monday 00:00  next Monday 00:00
        dow = now.weekday()  # Mon=0
        monday = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=dow)
        next_monday = monday + timedelta(days=7)
        start = max(now, monday)
        end = next_monday
        return start, end
    delta = RANGE_DELTAS.get(preset) or RANGE_DELTAS[DEFAULT_RANGE]
    return now, now + delta


def _hash_id(provider: str, when: datetime, country: str, title: str) -> str:
    h = hashlib.md5(f"{provider}|{when.isoformat()}|{country}|{title.strip().lower()}".encode())
    return h.hexdigest()


# ------------------------------------------------------------------------------
# Provider fetchers
# ------------------------------------------------------------------------------

def fetch_tradingeconomics() -> List[Event]:
    """
    Fetch once for a broad window: today  +14 days, cache for CACHE_TTL seconds.
    """
    provider = "tradingeconomics"
    now_ts = time.time()

    ts_events = CACHE.get(provider)
    if ts_events:
        ts, events = ts_events
        if now_ts - ts <= CACHE_TTL:
            return events

    # Broad window so all user ranges are covered by cache
    today = _now_utc().date()
    d1 = today.strftime("%Y-%m-%d")
    d2 = (today + timedelta(days=14)).strftime("%Y-%m-%d")
    url = (
        "https://api.tradingeconomics.com/calendar"
        f"?c=guest:guest&format=json&d1={d1}&d2={d2}"
    )

    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        data = r.json() or []
    except Exception as e:
        # On failure, fall back to stale cache if available
        if ts_events and (now_ts - ts_events[0]) <= STALE_GRACE:
            logger.warning("TradingEconomics fetch failed (%s). Serving stale cache.", e)
            return ts_events[1]
        logger.warning("TradingEconomics fetch failed: %s", e)
        return []

    events: List[Event] = []
    for item in data:
        try:
            raw_date: str = item.get("Date") or item.get("Release") or ""
            if not raw_date:
                continue
            # TE returns ISO without Z sometimes; normalize to UTC
            dt_utc = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=timezone.utc)

            name = item.get("Event") or item.get("Category") or "Economic Event"
            country = item.get("Country") or ""
            currency = (item.get("Currency") or "").strip().upper()
            if not currency and country:
                currency = COUNTRY_TO_CCY.get(country, "")

            imp_num = item.get("Importance")
            impact = {3: "high", 2: "medium", 1: "low"}.get(imp_num, "low")

            ev = Event(
                id=_hash_id(provider, dt_utc, country, name),
                provider="TradingEconomics",
                datetime_utc=dt_utc,
                country=country,
                currency=currency,
                name=name,
                impact=impact,
                previous=(item.get("Previous") or "") or None,
                forecast=(item.get("Consensus") or item.get("Forecast") or "") or None,
                actual=(item.get("Actual") or "") or None,
                revised=(item.get("Revised") or "") or None,
                description=None,
            )
            events.append(ev)
        except Exception:
            # Skip bad rows; continue robustly
            continue

    CACHE[provider] = (now_ts, events)
    logger.info("Fetched %d from tradingeconomics", len(events))
    return events


def fetch_fxstreet_disabled() -> List[Event]:
    logger.warning("FXStreet disabled by default (unreliable RSS).")
    return []


def fetch_dailyfx_disabled() -> List[Event]:
    logger.warning("DailyFX disabled by default (403 without browser).")
    return []


def fetch_provider(provider_key: str) -> List[Event]:
    meta = PROVIDERS.get(provider_key)
    if not meta:
        return []
    fn = globals().get(meta["fetch"])
    if not callable(fn):
        return []
    return fn()


# ------------------------------------------------------------------------------
# Filtering & formatting
# ------------------------------------------------------------------------------

def _matches_topics(ev: Event, impacts: Set[str], currencies: Set[str]) -> bool:
    # Impact filter (if selected)
    if impacts and ev.impact not in impacts:
        return False
    # Currency filter: allow events with inferred/known currency, or pass-through if user kept it broad
    if currencies:
        if ev.currency:
            return ev.currency in currencies
        # Event with no currency: allow only if user hasn't narrowed to a small set (keep inclusive but sensible)
        return len(currencies) >= 6  # majors broad selection  keep
    return True


def filter_events_for_user(state: UserState) -> List[Event]:
    # Aggregate from enabled providers
    all_events: List[Event] = []
    for key in state.enabled_providers:
        all_events.extend(fetch_provider(key))

    # Deduplicate by id (provider-based hash)
    uniq: Dict[str, Event] = {}
    for e in all_events:
        uniq[e.id] = e
    events = list(uniq.values())

    # Time window by preset
    start, end = _start_end_from_preset(state.range_preset)

    # Keep upcoming within window
    events = [e for e in events if (e.datetime_utc >= start and e.datetime_utc < end)]

    # Apply topics (impacts, currencies)
    events = [e for e in events if _matches_topics(e, state.selected_impacts, state.selected_currencies)]

    # Sort
    events.sort(key=lambda e: e.datetime_utc)
    return events


def fmt_event_line(ev: Event) -> str:
    t = ev.datetime_utc.strftime("%Y-%m-%d %H:%M (UTC)")
    imp = IMPACT_EMOJI.get(ev.impact, "")
    vals = []
    if ev.actual:
        vals.append(f"Actual: {ev.actual}")
    if ev.forecast:
        vals.append(f"Fcst: {ev.forecast}")
    if ev.previous:
        vals.append(f"Prev: {ev.previous}")
    vals_s = " | ".join(vals) if vals else ""
    ccy = (ev.currency or "").upper()
    ccy_part = f"{ccy} " if ccy else ""
    line = f"{imp} {t}  {ccy_part}{ev.name}"
    if vals_s:
        line += f"\n   {vals_s}"
    return line


def _page_count(n: int, per_page: int) -> int:
    return max(1, ((n - 1) // per_page) + 1)


# ------------------------------------------------------------------------------
# Keyboards
# ------------------------------------------------------------------------------

def kb_list(state: UserState, page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    rows.append([
        InlineKeyboardButton(text=" Provid", callback_data="cal:providers"),
        InlineKeyboardButton(text=" Impac", callback_data="cal:impacts"),
        InlineKeyboardButton(text=" Curren", callback_data="cal:currencies"),
        InlineKeyboardButton(text=" Range", callback_data="cal:range"),
    ])
    rows.append([
        InlineKeyboardButton(text=" Refresh", callback_data="cal:refresh")
    ])
    prev_cb = "cal:page:prev" if page > 0 else "cal:noop"
    next_cb = "cal:page:next" if page + 1 < total_pages else "cal:noop"
    rows.append([
        InlineKeyboardButton(text=" Prev" if page == 0 else " Prev", callback_data=prev_cb),
        InlineKeyboardButton(text=f"Page {page+1}/{total_pages}", callback_data="cal:noop"),
        InlineKeyboardButton(text=" Next" if page + 1 >= total_pages else "Next ", callback_data=next_cb),
    ])
    rows.append([InlineKeyboardButton(text=" Main Menu", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_providers(state: UserState) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for key, meta in PROVIDERS.items():
        checked = " " if key in state.enabled_providers else " "
        rows.append([InlineKeyboardButton(text=f"{checked}{meta['title']}", callback_data=f"cal:toggleprov:{key}")])
    rows.append([InlineKeyboardButton(text=" Back", callback_data="cal:list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_impacts(state: UserState) -> InlineKeyboardMarkup:
    def label(level: str, title: str) -> str:
        mark = "" if level in state.selected_impacts else ""
        em = IMPACT_EMOJI.get(level, "")
        return f"{mark} {em} {title}"

    rows = [
        [InlineKeyboardButton(text=label("high", "High"), callback_data="cal:toggleimpact:high")],
        [InlineKeyboardButton(text=label("medium", "Medium"), callback_data="cal:toggleimpact:medium")],
        [InlineKeyboardButton(text=label("low", "Low"), callback_data="cal:toggleimpact:low")],
        [InlineKeyboardButton(text=" Back", callback_data="cal:list")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


CURRENCY_ORDER = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "CNY"]


def kb_currencies(state: UserState) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    # two per row for readability
    row: List[InlineKeyboardButton] = []
    for c in CURRENCY_ORDER:
        mark = "" if c in state.selected_currencies else ""
        btn = InlineKeyboardButton(text=f"{mark} {c}", callback_data=f"cal:togglecurr:{c}")
        row.append(btn)
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=" Back", callback_data="cal:list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_range(state: UserState) -> InlineKeyboardMarkup:
    labels = [
        ("today", "Today"),
        ("next3", "Next 3 Days"),
        ("next7", "Next 7 Days"),
        ("thisweek", "This Week"),
    ]
    rows: List[List[InlineKeyboardButton]] = []
    for key, title in labels:
        sel = "" if state.range_preset == key else ""
        rows.append([InlineKeyboardButton(text=f"{sel} {title}", callback_data=f"cal:setrange:{key}")])
    rows.append([InlineKeyboardButton(text=" Back", callback_data="cal:list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_event_detail() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=" Back to List", callback_data="cal:list")],
        [InlineKeyboardButton(text=" Refresh", callback_data="cal:refresh")],
        [InlineKeyboardButton(text=" Main Menu", callback_data="menu:main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ------------------------------------------------------------------------------
# Rendering
# ------------------------------------------------------------------------------

def _header_text(state: UserState, stale: bool) -> str:
    parts = [" <b>Economic Calendar</b>"]
    if stale:
        parts.append("(data may be stale)")
    return " ".join(parts)


def _stale_flag() -> bool:
    # If the primary (TE) cache exists and is older than TTL but newer than GRACE, we call it stale.
    ts_events = CACHE.get("tradingeconomics")
    if not ts_events:
        return False
    ts, _ = ts_events
    age = time.time() - ts
    return CACHE_TTL < age <= STALE_GRACE


def _list_body(state: UserState) -> Tuple[str, InlineKeyboardMarkup]:
    events = filter_events_for_user(state)
    total = len(events)
    total_pages = _page_count(total, ITEMS_PER_PAGE)
    page = max(0, min(state.page, total_pages - 1))
    state.page = page

    if total == 0:
        text = (
            f"{_header_text(state, _stale_flag())}\n"
            " No upcoming economic events found.\n"
            "Try adjusting filters or refreshing."
        )
        return text, kb_list(state, page, total_pages)

    start = page * ITEMS_PER_PAGE
    chunk = events[start : start + ITEMS_PER_PAGE]

    lines = [ _header_text(state, _stale_flag()) ]
    for ev in chunk:
        lines.append(fmt_event_line(ev))
        lines.append("")  # light divider
    text = "\n".join(lines[:-1])  # drop last divider

    return text, kb_list(state, page, total_pages)


def _detail_body(ev: Event) -> Tuple[str, InlineKeyboardMarkup]:
    imp = IMPACT_EMOJI.get(ev.impact, "")
    t = ev.datetime_utc.strftime("%Y-%m-%d %H:%M (UTC)")
    ccy = (ev.currency or "").upper()
    header = f"{imp} <b>{ev.name}</b>"
    sub = f"{ev.country}  {ccy}" if ccy else ev.country
    vals = []
    if ev.actual:
        vals.append(f"<b>Actual:</b> {ev.actual}")
    if ev.forecast:
        vals.append(f"<b>Forecast:</b> {ev.forecast}")
    if ev.previous:
        vals.append(f"<b>Previous:</b> {ev.previous}")
    if ev.revised:
        vals.append(f"<b>Revised:</b> {ev.revised}")
    vals_s = "\n".join(vals) if vals else ""
    desc = ev.description or ""
    text = (
        f"{header}\n"
        f"{sub}\n"
        f" {t}\n\n"
        f"{vals_s}\n\n"
        f"<i>Source: {ev.provider}</i>\n"
        f"{desc}"
    )
    return text, kb_event_detail()


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def _get_state(user_id: int) -> UserState:
    st = USER_STATES.get(user_id)
    if not st:
        st = UserState()
        USER_STATES[user_id] = st
    return st


def _debounced(st: UserState) -> bool:
    now = time.time()
    if now - st.last_click < DEBOUNCE_SEC:
        return True
    st.last_click = now
    return False


def _find_event_by_id(state: UserState, ev_id: str) -> Optional[Event]:
    # Search current filtered list (across pages)
    for e in filter_events_for_user(state):
        if e.id == ev_id:
            return e
    return None


# ------------------------------------------------------------------------------
# Handlers
# ------------------------------------------------------------------------------

@router.callback_query(F.data == "tab:calendar")
async def calendar_entry(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    st.open_id = None
    st.page = 0
    text, markup = _list_body(st)
    await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data == "cal:list")
async def calendar_list(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    text, markup = _list_body(st)
    await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data == "cal:refresh")
async def calendar_refresh(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    if _debounced(st):
        await cb.answer("Up to date", show_alert=False)
        return
    # Bust provider cache by setting timestamp old
    for k in list(CACHE.keys()):
        ts, evs = CACHE[k]
        CACHE[k] = (0.0, evs)
    text, markup = _list_body(st)
    await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer("Refreshed", show_alert=False)


@router.callback_query(F.data.in_({"cal:page:prev", "cal:page:next"}))
async def calendar_page(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    if cb.data.endswith("prev") and st.page > 0:
        st.page -= 1
    elif cb.data.endswith("next"):
        # guard against overflow
        total = len(filter_events_for_user(st))
        total_pages = _page_count(total, ITEMS_PER_PAGE)
        if st.page + 1 < total_pages:
            st.page += 1
    text, markup = _list_body(st)
    await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data == "cal:providers")
async def calendar_providers(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    text = (
        " <b>Providers</b>\n"
        "Toggle sources. Only TradingEconomics is active by default for reliable free data."
    )
    await cb.message.edit_text(text, reply_markup=kb_providers(st))
    await cb.answer()


@router.callback_query(F.data.startswith("cal:toggleprov:"))
async def calendar_toggle_provider(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    key = cb.data.split(":", 2)[2]
    if key in st.enabled_providers:
        st.enabled_providers.remove(key)
    else:
        st.enabled_providers.add(key)
    await cb.message.edit_text(
        " <b>Providers</b>\n"
        "Toggle sources. Only TradingEconomics is active by default for reliable free data.",
        reply_markup=kb_providers(st),
    )
    await cb.answer()


@router.callback_query(F.data == "cal:impacts")
async def calendar_impacts(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    await cb.message.edit_text(" <b>Impact Levels</b>", reply_markup=kb_impacts(st))
    await cb.answer()


@router.callback_query(F.data.startswith("cal:toggleimpact:"))
async def calendar_toggle_impact(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    level = cb.data.split(":", 2)[2]
    if level in st.selected_impacts:
        st.selected_impacts.remove(level)
    else:
        st.selected_impacts.add(level)
    await cb.message.edit_text(" <b>Impact Levels</b>", reply_markup=kb_impacts(st))
    await cb.answer()


@router.callback_query(F.data == "cal:currencies")
async def calendar_currencies(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    await cb.message.edit_text(" <b>Currencies</b>", reply_markup=kb_currencies(st))
    await cb.answer()


@router.callback_query(F.data.startswith("cal:togglecurr:"))
async def calendar_toggle_currency(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    ccy = cb.data.split(":", 2)[2]
    if ccy in st.selected_currencies:
        st.selected_currencies.remove(ccy)
    else:
        st.selected_currencies.add(ccy)
    await cb.message.edit_text(" <b>Currencies</b>", reply_markup=kb_currencies(st))
    await cb.answer()


@router.callback_query(F.data == "cal:range")
async def calendar_range(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    await cb.message.edit_text(" <b>Range</b>", reply_markup=kb_range(st))
    await cb.answer()


@router.callback_query(F.data.startswith("cal:setrange:"))
async def calendar_set_range(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    key = cb.data.split(":", 2)[2]
    if key in RANGE_DELTAS or key == "thisweek":
        st.range_preset = key
        st.page = 0
    await cb.message.edit_text(" <b>Range</b>", reply_markup=kb_range(st))
    await cb.answer()


@router.callback_query(F.data.startswith("cal:event:"))
async def calendar_open_event(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    ev_id = cb.data.split(":", 2)[2]
    ev = _find_event_by_id(st, ev_id)
    if not ev:
        await cb.answer("Event not found (try Refresh).", show_alert=True)
        return
    st.open_id = ev_id
    text, markup = _detail_body(ev)
    await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data == "cal:backtolist")
async def calendar_back_to_list(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    st.open_id = None
    text, markup = _list_body(st)
    await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data == "cal:noop")
async def calendar_noop(cb: CallbackQuery):
    await cb.answer()

# EOF

