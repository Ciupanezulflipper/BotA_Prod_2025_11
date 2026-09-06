from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"


class R5MeasurementHardeningTests(unittest.TestCase):
    def test_provider_usage_routes_runtime_state_to_mutable_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            mutable = Path(temp)
            env = {
                **os.environ,
                "BOTA_CODE_ROOT": str(REPO),
                "BOTA_ROOT": str(REPO),
                "BOTA_MUTABLE_ROOT": str(mutable),
            }
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOLS / "provider_usage.py"),
                    "record",
                    "--provider",
                    "yahoo",
                    "--caller",
                    "test_r5_mutable_root",
                    "--pair",
                    "EURUSD",
                    "--timeframe",
                    "M15",
                    "--status",
                    "success",
                    "--credits",
                    "0",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            state = mutable / "state" / "provider_usage.json"
            events = mutable / "logs" / "provider_calls.jsonl"
            self.assertTrue(state.is_file())
            self.assertTrue(events.is_file())
            data = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(data["providers"]["yahoo"]["successes"], 1)

    def test_provider_usage_prefers_mutable_root_in_source_contract(self) -> None:
        source = (TOOLS / "provider_usage.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("BOTA_MUTABLE_ROOT", "").strip()', source)
        self.assertIn('or os.environ.get("BOTA_ROOT", "").strip()', source)

    def test_yahoo_d1_history_window_satisfies_existing_indicator_minimum(self) -> None:
        source = (TOOLS / "data_fetch_candles.sh").read_text(encoding="utf-8")
        self.assertIn('D1|1D) echo "6mo"', source)
        self.assertNotIn('D1|1D) echo "1mo"', source)

    def test_fetcher_persists_actual_provider_marker(self) -> None:
        source = (TOOLS / "data_fetch_candles.sh").read_text(encoding="utf-8")
        self.assertIn('result.setdefault("meta", {})["_provider"] = provider', source)
        self.assertIn('"${PROVIDER_USED}" <<\'PY\'', source)

    def test_provider_accounting_is_not_silently_ignored_at_fetch_boundary(self) -> None:
        source = (TOOLS / "data_fetch_candles.sh").read_text(encoding="utf-8")
        provider_function = source.split("provider_record() {", 1)[1].split("}\n\nPAIR_RAW", 1)[0]
        self.assertNotIn("|| true", provider_function)


if __name__ == "__main__":
    unittest.main()
