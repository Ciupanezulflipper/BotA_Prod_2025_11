from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "ops" / "systemd" / "bota.service"


def _exec_line(prefix: str) -> str:
    for line in UNIT.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line
    raise AssertionError(f"missing {prefix} in {UNIT}")


def test_r5_service_defines_empty_calendar_key_before_preflight() -> None:
    line = _exec_line("ExecStartPre=")
    assert "/usr/bin/env RAPIDAPI_CALENDAR_KEY=" in line
    assert "RAPIDAPI_CALENDAR_KEY= " in line


def test_r5_service_defines_empty_calendar_key_before_orchestrator() -> None:
    line = _exec_line("ExecStart=")
    assert "/usr/bin/env RAPIDAPI_CALENDAR_KEY=" in line
    assert "RAPIDAPI_CALENDAR_KEY= " in line


def test_r5_service_does_not_embed_calendar_secret() -> None:
    text = UNIT.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith(("ExecStart=", "ExecStartPre=")):
            token = line.split("RAPIDAPI_CALENDAR_KEY=", 1)[1].split(" ", 1)[0]
            assert token == ""
