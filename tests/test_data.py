"""Focused data and contract tests for the restored three-category backend."""

from __future__ import annotations

from pathlib import Path
import unittest

import pandas as pd

from src.constants import HISTORICAL_DEMAND_COLUMNS, RESERVATION_CATEGORIES
from src.data.generator import APPROVED_SYNTHETIC_HISTORY_ROWS, generate_synthetic_history
from src.data.loader import build_history_diagnostics, load_and_validate_history
from src.validation import load_defaults_config


class HistoryDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        cls.history_path = project_root / "data" / "synthetic_history.csv"
        cls.defaults_path = project_root / "config" / "defaults.json"

    def test_defaults_load_successfully(self) -> None:
        defaults = load_defaults_config(self.defaults_path)

        self.assertEqual(tuple(item.category for item in defaults["category_assumptions"]), RESERVATION_CATEGORIES)
        self.assertAlmostEqual(
            defaults["workforce_assumptions"].direct_booking_share,
            0.3125,
        )

    def test_exact_history_file_loads_with_twelve_weeks(self) -> None:
        history = load_and_validate_history(self.history_path)

        self.assertEqual(tuple(history.columns), HISTORICAL_DEMAND_COLUMNS)
        self.assertEqual(len(history), 12)
        self.assertEqual(history.iloc[0]["week_id"], "2026-W15")
        self.assertEqual(history.iloc[-1]["week_id"], "2026-W26")
        self.assertEqual(history.iloc[-1]["staffing_agents"], 9)

    def test_generator_reproduces_the_exact_approved_dataset(self) -> None:
        generated = generate_synthetic_history()
        expected = pd.DataFrame(APPROVED_SYNTHETIC_HISTORY_ROWS, columns=HISTORICAL_DEMAND_COLUMNS)
        expected[list(RESERVATION_CATEGORIES) + ["staffing_agents"]] = expected[
            list(RESERVATION_CATEGORIES) + ["staffing_agents"]
        ].astype("int64")
        expected["week_start"] = expected["week_start"].astype("string")

        pd.testing.assert_frame_equal(generated, expected)

    def test_history_diagnostics_report_recent_window_and_quality_checks(self) -> None:
        history = load_and_validate_history(self.history_path)
        diagnostics = build_history_diagnostics(history)

        self.assertEqual(diagnostics["week_count"], 12)
        self.assertEqual(
            diagnostics["date_range"],
            {"start": "2026-04-06", "end": "2026-06-22"},
        )
        self.assertEqual(
            [row["week_id"] for row in diagnostics["recent_four_week_extract"]],
            ["2026-W23", "2026-W24", "2026-W25", "2026-W26"],
        )
        self.assertTrue(all(diagnostics["quality_checks"].values()))


if __name__ == "__main__":
    unittest.main()
