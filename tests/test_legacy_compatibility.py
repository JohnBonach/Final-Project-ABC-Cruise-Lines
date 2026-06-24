"""Compatibility tests for artifacts older deployments may still request."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


class LegacyCompatibilityTests(unittest.TestCase):
    def test_legacy_scenarios_file_exists_with_expected_shape(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        scenarios_path = project_root / "config" / "scenarios.json"

        self.assertTrue(scenarios_path.exists())
        payload = json.loads(scenarios_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(
            [scenario["scenario_name"] for scenario in payload["scenarios"]],
            ["Low Demand", "Expected Demand", "High Demand"],
        )


if __name__ == "__main__":
    unittest.main()
