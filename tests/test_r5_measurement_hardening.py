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

    def test_fetcher_preserves_historical_implementation_behind_wrapper(self) -> None:
        wrapper = (TOOLS / "data_fetch_candles.sh").read_text(encoding="utf-8")
        legacy = TOOLS / "data_fetch_candles_r5_legacy.sh"
        self.assertTrue(legacy.is_file())
        self.assertIn("data_fetch_candles_r5_legacy.sh", wrapper)
        self.assertIn('"range": "6mo"', wrapper)
        self.assertIn('meta["_provider"] = "yahoo"', wrapper)
        self.assertIn("d1_history_insufficient", wrapper)

    def test_provider_usage_preserves_historical_implementation_behind_shim(self) -> None:
        wrapper = (TOOLS / "provider_usage.py").read_text(encoding="utf-8")
        legacy = TOOLS / "provider_usage_r5_legacy.py"
        self.assertTrue(legacy.is_file())
        self.assertIn("BOTA_MUTABLE_ROOT", wrapper)
        self.assertIn("provider_usage_r5_legacy.py", wrapper)


if __name__ == "__main__":
    unittest.main()
