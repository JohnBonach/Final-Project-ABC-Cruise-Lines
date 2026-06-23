"""Forecasting tests for the restored three-category backend."""

from __future__ import annotations

from pathlib import Path
import unittest

from src.constants import FORECAST_RESULT_COLUMNS, RESERVATION_CATEGORIES
from src.data.loader import load_and_validate_history
from src.forecasting.uncertainty import assemble_forecast_result, calculate_historical_uncertainty
from src.forecasting.weighted_moving_average import calculate_weighted_moving_average
from src.validation import FieldValidationError


class ForecastingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        history_path = Path(__file__).resolve().parents[1] / "data" / "synthetic_history.csv"
        cls.history = load_and_validate_history(history_path)

    def test_automatic_baseline_forecast_matches_approved_history(self) -> None:
        forecast = calculate_weighted_moving_average(
            self.history,
            [0.4, 0.3, 0.2, 0.1],
        )

        self.assertEqual(tuple(forecast), RESERVATION_CATEGORIES)
        self.assertAlmostEqual(forecast["day_cruise"], 235.0)
        self.assertAlmostEqual(forecast["seven_night_cruise"], 153.5)
        self.assertAlmostEqual(forecast["nine_night_cruise"], 90.0)

    def test_historical_uncertainty_uses_new_categories(self) -> None:
        uncertainty = calculate_historical_uncertainty(self.history, 1.0)

        self.assertEqual(tuple(uncertainty.keys()), RESERVATION_CATEGORIES)
        self.assertGreater(uncertainty["day_cruise"]["historical_std"], 0.0)
        self.assertGreater(uncertainty["seven_night_cruise"]["historical_std"], 0.0)
        self.assertGreater(uncertainty["nine_night_cruise"]["historical_std"], 0.0)

    def test_scenario_multiplier_applies_before_manual_override(self) -> None:
        forecast = assemble_forecast_result(
            self.history,
            [0.4, 0.3, 0.2, 0.1],
            variability_multiplier=1.0,
            demand_multiplier=1.15,
            manual_overrides={"seven_night_cruise": 160.0},
        )
        indexed = forecast.set_index("category")

        self.assertEqual(tuple(forecast.columns), FORECAST_RESULT_COLUMNS)
        self.assertAlmostEqual(indexed.loc["day_cruise", "point_forecast"], 270.25)
        self.assertAlmostEqual(indexed.loc["seven_night_cruise", "point_forecast"], 160.0)
        self.assertAlmostEqual(indexed.loc["nine_night_cruise", "point_forecast"], 103.5)
        self.assertEqual(indexed.loc["seven_night_cruise", "forecast_source"], "manual_override")
        self.assertEqual(indexed.loc["day_cruise", "forecast_source"], "automatic")

    def test_rejects_unknown_manual_override_category(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown category"):
            assemble_forecast_result(
                self.history,
                [0.4, 0.3, 0.2, 0.1],
                variability_multiplier=1.0,
                manual_overrides={"simple": 10.0},
            )

    def test_rejects_negative_variability_multiplier(self) -> None:
        with self.assertRaisesRegex(FieldValidationError, "variability_multiplier must be non-negative"):
            calculate_historical_uncertainty(self.history, -0.1)


if __name__ == "__main__":
    unittest.main()
