from pathlib import Path


WATCHER = Path("tools/signal_watcher_core.sh")


def source() -> str:
    return WATCHER.read_text(encoding="utf-8")


def test_calendar_guard_does_not_run_merely_because_file_exists():
    text = source()

    broken = (
        '[[ -f "${TOOLS}/calendar_guard.py" && '
        '-n "${RAPIDAPI_CALENDAR_KEY:-}" ]] || '
        '[[ -f "${TOOLS}/calendar_guard.py" ]]'
    )

    assert broken not in text


def test_calendar_guard_requires_configured_key():
    text = source()

    expected = (
        'if [[ -f "${TOOLS}/calendar_guard.py" && '
        '-n "${RAPIDAPI_CALENDAR_KEY:-}" ]]; then'
    )

    assert expected in text


def test_calendar_key_expansion_is_safe_under_set_u():
    text = source()

    unsafe = 'RAPIDAPI_CALENDAR_KEY="${RAPIDAPI_CALENDAR_KEY}"'
    safe = 'RAPIDAPI_CALENDAR_KEY="${RAPIDAPI_CALENDAR_KEY:-}"'

    assert unsafe not in text
    assert safe in text
