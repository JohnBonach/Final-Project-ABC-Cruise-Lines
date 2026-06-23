"""Contract tests for forecasting modules."""

from __future__ import annotations

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from src.constants import FORECAST_RESULT_COLUMNS, RESERVATION_CATEGORIES
from src.forecasting.uncertainty import (
    assemble_forecast_result,
    calculate_historical_uncertainty,
)
from src.forecasting.weighted_moving_average import (
    calculate_weighted_moving_average,
)
from src.validation import FieldValidationError, InsufficientHistoryError


class WeightedMovingAverageTests(unittest.TestCase):
    def _build_history(self, rows: list[dict[str, object]]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_applies_largest_weight_to_most_recent_week(self) -> None:
        history = self._build_history(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 1,
                    "standard": 10,
                    "complex_group": 100,
                    "change_cancellation": 7,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 2,
                    "standard": 20,
                    "complex_group": 200,
                    "change_cancellation": 8,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 3,
                    "standard": 30,
                    "complex_group": 300,
                    "change_cancellation": 9,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 4,
                    "standard": 40,
                    "complex_group": 400,
                    "change_cancellation": 10,
                    "staffing_agents": 6,
                },
            ]
        )

        forecast = calculate_weighted_moving_average(
            history,
            [0.4, 0.3, 0.2, 0.1],
        )

        self.assertEqual(
            forecast,
            {
                "simple": 3.0,
                "standard": 30.0,
                "complex_group": 300.0,
                "change_cancellation": 9.0,
            },
        )

    def test_rejects_weights_that_do_not_sum_to_one(self) -> None:
        history = self._build_history(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 10,
                    "standard": 10,
                    "complex_group": 10,
                    "change_cancellation": 10,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 11,
                    "standard": 11,
                    "complex_group": 11,
                    "change_cancellation": 11,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 12,
                    "standard": 12,
                    "complex_group": 12,
                    "change_cancellation": 12,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 13,
                    "standard": 13,
                    "complex_group": 13,
                    "change_cancellation": 13,
                    "staffing_agents": 6,
                },
            ]
        )

        with self.assertRaisesRegex(ValueError, "weights must sum to 1.0"):
            calculate_weighted_moving_average(history, [0.5, 0.3, 0.1, 0.2])

    def test_rejects_weight_lists_that_are_not_four_values_long(self) -> None:
        history = self._build_history(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 10,
                    "standard": 10,
                    "complex_group": 10,
                    "change_cancellation": 10,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 11,
                    "standard": 11,
                    "complex_group": 11,
                    "change_cancellation": 11,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 12,
                    "standard": 12,
                    "complex_group": 12,
                    "change_cancellation": 12,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 13,
                    "standard": 13,
                    "complex_group": 13,
                    "change_cancellation": 13,
                    "staffing_agents": 6,
                },
            ]
        )

        with self.assertRaisesRegex(ValueError, "weights must contain exactly 4 values"):
            calculate_weighted_moving_average(history, [0.5, 0.3, 0.2])

    def test_rejects_negative_weights(self) -> None:
        history = self._build_history(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 10,
                    "standard": 10,
                    "complex_group": 10,
                    "change_cancellation": 10,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 11,
                    "standard": 11,
                    "complex_group": 11,
                    "change_cancellation": 11,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 12,
                    "standard": 12,
                    "complex_group": 12,
                    "change_cancellation": 12,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 13,
                    "standard": 13,
                    "complex_group": 13,
                    "change_cancellation": 13,
                    "staffing_agents": 6,
                },
            ]
        )

        with self.assertRaisesRegex(ValueError, "weights must be between 0.0 and 1.0 inclusive"):
            calculate_weighted_moving_average(history, [0.4, 0.3, 0.2, -0.1])

    def test_rejects_insufficient_history(self) -> None:
        history = self._build_history(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 10,
                    "standard": 10,
                    "complex_group": 10,
                    "change_cancellation": 10,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 11,
                    "standard": 11,
                    "complex_group": 11,
                    "change_cancellation": 11,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 12,
                    "standard": 12,
                    "complex_group": 12,
                    "change_cancellation": 12,
                    "staffing_agents": 6,
                },
            ]
        )

        with self.assertRaises(InsufficientHistoryError):
            calculate_weighted_moving_average(history, [0.4, 0.3, 0.2, 0.1])

    def test_requires_all_canonical_category_columns(self) -> None:
        history = pd.DataFrame(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 10,
                    "standard": 20,
                    "complex_group": 30,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 11,
                    "standard": 21,
                    "complex_group": 31,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 12,
                    "standard": 22,
                    "complex_group": 32,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 13,
                    "standard": 23,
                    "complex_group": 33,
                    "staffing_agents": 6,
                },
            ]
        )

        with self.assertRaisesRegex(
            FieldValidationError,
            "historical data is missing required columns",
        ):
            calculate_weighted_moving_average(history, [0.4, 0.3, 0.2, 0.1])

    def test_returns_all_canonical_categories(self) -> None:
        history = self._build_history(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 10,
                    "standard": 20,
                    "complex_group": 30,
                    "change_cancellation": 40,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 11,
                    "standard": 21,
                    "complex_group": 31,
                    "change_cancellation": 41,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 12,
                    "standard": 22,
                    "complex_group": 32,
                    "change_cancellation": 42,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 13,
                    "standard": 23,
                    "complex_group": 33,
                    "change_cancellation": 43,
                    "staffing_agents": 6,
                },
            ]
        )

        forecast = calculate_weighted_moving_average(
            history,
            [0.4, 0.3, 0.2, 0.1],
        )

        self.assertEqual(tuple(forecast), RESERVATION_CATEGORIES)
        self.assertEqual(set(forecast), set(RESERVATION_CATEGORIES))
        self.assertEqual(forecast["simple"], 12.0)
        self.assertEqual(forecast["standard"], 22.0)
        self.assertEqual(forecast["complex_group"], 32.0)
        self.assertEqual(forecast["change_cancellation"], 42.0)


class HistoricalUncertaintyTests(unittest.TestCase):
    def _build_history(self, rows: list[dict[str, object]]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_calculates_means_stds_and_adjusted_stds_by_category(self) -> None:
        history = self._build_history(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 1,
                    "standard": 10,
                    "complex_group": 5,
                    "change_cancellation": 2,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 2,
                    "standard": 12,
                    "complex_group": 5,
                    "change_cancellation": 4,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 3,
                    "standard": 14,
                    "complex_group": 5,
                    "change_cancellation": 6,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 4,
                    "standard": 16,
                    "complex_group": 5,
                    "change_cancellation": 8,
                    "staffing_agents": 6,
                },
            ]
        )

        uncertainty = calculate_historical_uncertainty(history, 1.25)

        self.assertEqual(tuple(uncertainty.keys()), RESERVATION_CATEGORIES)
        self.assertEqual(
            uncertainty["simple"],
            {
                "historical_mean": 2.5,
                "historical_std": 1.2909944487358056,
                "adjusted_std": 1.613743060919757,
            },
        )
        self.assertEqual(
            uncertainty["standard"],
            {
                "historical_mean": 13.0,
                "historical_std": 2.581988897471611,
                "adjusted_std": 3.2274861218395137,
            },
        )
        self.assertEqual(
            uncertainty["complex_group"],
            {
                "historical_mean": 5.0,
                "historical_std": 0.0,
                "adjusted_std": 0.0,
            },
        )
        self.assertEqual(
            uncertainty["change_cancellation"],
            {
                "historical_mean": 5.0,
                "historical_std": 2.581988897471611,
                "adjusted_std": 3.2274861218395137,
            },
        )

    def test_rejects_invalid_variability_multiplier(self) -> None:
        history = self._build_history(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 1,
                    "standard": 2,
                    "complex_group": 3,
                    "change_cancellation": 4,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 2,
                    "standard": 3,
                    "complex_group": 4,
                    "change_cancellation": 5,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 3,
                    "standard": 4,
                    "complex_group": 5,
                    "change_cancellation": 6,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 4,
                    "standard": 5,
                    "complex_group": 6,
                    "change_cancellation": 7,
                    "staffing_agents": 6,
                },
            ]
        )

        with self.assertRaisesRegex(FieldValidationError, "variability_multiplier must be non-negative"):
            calculate_historical_uncertainty(history, -0.1)

    def test_zero_variability_multiplier_zeroes_adjusted_standard_deviation(self) -> None:
        history = self._build_history(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 1,
                    "standard": 10,
                    "complex_group": 100,
                    "change_cancellation": 7,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 2,
                    "standard": 20,
                    "complex_group": 200,
                    "change_cancellation": 8,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 3,
                    "standard": 30,
                    "complex_group": 300,
                    "change_cancellation": 9,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 4,
                    "standard": 40,
                    "complex_group": 400,
                    "change_cancellation": 10,
                    "staffing_agents": 6,
                },
            ]
        )

        uncertainty = calculate_historical_uncertainty(history, 0.0)

        self.assertTrue(all(values["adjusted_std"] == 0.0 for values in uncertainty.values()))
        self.assertGreater(uncertainty["simple"]["historical_std"], 0.0)
        self.assertGreater(uncertainty["standard"]["historical_std"], 0.0)
        self.assertGreater(uncertainty["complex_group"]["historical_std"], 0.0)
        self.assertGreater(uncertainty["change_cancellation"]["historical_std"], 0.0)

    def test_requires_all_canonical_category_columns(self) -> None:
        history = pd.DataFrame(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 1,
                    "standard": 2,
                    "complex_group": 3,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 2,
                    "standard": 3,
                    "complex_group": 4,
                    "staffing_agents": 5,
                },
            ]
        )

        with self.assertRaisesRegex(
            FieldValidationError,
            "historical data is missing required columns",
        ):
            calculate_historical_uncertainty(history, 1.0)


class ForecastAssemblyTests(unittest.TestCase):
    def _build_history(self, rows: list[dict[str, object]]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_returns_canonical_columns_and_automatic_forecast_rows(self) -> None:
        history = self._build_history(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 10,
                    "standard": 20,
                    "complex_group": 30,
                    "change_cancellation": 40,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 11,
                    "standard": 21,
                    "complex_group": 31,
                    "change_cancellation": 41,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 12,
                    "standard": 22,
                    "complex_group": 32,
                    "change_cancellation": 42,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 13,
                    "standard": 23,
                    "complex_group": 33,
                    "change_cancellation": 43,
                    "staffing_agents": 6,
                },
            ]
        )

        forecast = assemble_forecast_result(
            history,
            [0.4, 0.3, 0.2, 0.1],
            variability_multiplier=1.25,
        )

        self.assertEqual(tuple(forecast.columns), FORECAST_RESULT_COLUMNS)
        self.assertEqual(tuple(forecast["category"]), RESERVATION_CATEGORIES)
        self.assertTrue((forecast["forecast_source"] == "automatic").all())
        self.assertEqual(forecast.loc[0, "point_forecast"], 12.0)
        self.assertEqual(forecast.loc[1, "point_forecast"], 22.0)
        self.assertEqual(forecast.loc[2, "point_forecast"], 32.0)
        self.assertEqual(forecast.loc[3, "point_forecast"], 42.0)
        self.assertEqual(forecast.loc[0, "historical_mean"], 11.5)
        self.assertEqual(forecast.loc[1, "historical_mean"], 21.5)
        self.assertEqual(forecast.loc[2, "historical_mean"], 31.5)
        self.assertEqual(forecast.loc[3, "historical_mean"], 41.5)
        self.assertEqual(forecast.loc[0, "historical_std"], 1.2909944487358056)
        self.assertEqual(forecast.loc[1, "historical_std"], 1.2909944487358056)
        self.assertEqual(forecast.loc[2, "historical_std"], 1.2909944487358056)
        self.assertEqual(forecast.loc[3, "historical_std"], 1.2909944487358056)
        self.assertEqual(forecast.loc[0, "adjusted_std"], 1.613743060919757)
        self.assertEqual(forecast.loc[1, "adjusted_std"], 1.613743060919757)
        self.assertEqual(forecast.loc[2, "adjusted_std"], 1.613743060919757)
        self.assertEqual(forecast.loc[3, "adjusted_std"], 1.613743060919757)

    def test_applies_manual_overrides_without_changing_other_categories(self) -> None:
        history = self._build_history(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 10,
                    "standard": 20,
                    "complex_group": 30,
                    "change_cancellation": 40,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 11,
                    "standard": 21,
                    "complex_group": 31,
                    "change_cancellation": 41,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 12,
                    "standard": 22,
                    "complex_group": 32,
                    "change_cancellation": 42,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 13,
                    "standard": 23,
                    "complex_group": 33,
                    "change_cancellation": 43,
                    "staffing_agents": 6,
                },
            ]
        )

        forecast = assemble_forecast_result(
            history,
            [0.4, 0.3, 0.2, 0.1],
            variability_multiplier=1.0,
            manual_overrides={"standard": 99.0, "change_cancellation": 77.0},
        )

        self.assertEqual(forecast.loc[0, "point_forecast"], 12.0)
        self.assertEqual(forecast.loc[1, "point_forecast"], 99.0)
        self.assertEqual(forecast.loc[2, "point_forecast"], 32.0)
        self.assertEqual(forecast.loc[3, "point_forecast"], 77.0)
        self.assertEqual(forecast.loc[0, "forecast_source"], "automatic")
        self.assertEqual(forecast.loc[1, "forecast_source"], "manual_override")
        self.assertEqual(forecast.loc[2, "forecast_source"], "automatic")
        self.assertEqual(forecast.loc[3, "forecast_source"], "manual_override")
        self.assertEqual(forecast.loc[1, "historical_mean"], 21.5)
        self.assertEqual(forecast.loc[1, "adjusted_std"], 1.2909944487358056)

    def test_rejects_invalid_manual_override_categories_and_values(self) -> None:
        history = self._build_history(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 10,
                    "standard": 20,
                    "complex_group": 30,
                    "change_cancellation": 40,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 11,
                    "standard": 21,
                    "complex_group": 31,
                    "change_cancellation": 41,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 12,
                    "standard": 22,
                    "complex_group": 32,
                    "change_cancellation": 42,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 13,
                    "standard": 23,
                    "complex_group": 33,
                    "change_cancellation": 43,
                    "staffing_agents": 6,
                },
            ]
        )

        with self.assertRaisesRegex(ValueError, "unknown category"):
            assemble_forecast_result(
                history,
                [0.4, 0.3, 0.2, 0.1],
                variability_multiplier=1.0,
                manual_overrides={"vip": 99.0},
            )

        with self.assertRaisesRegex(
            ValueError,
            r"manual_overrides\[standard\] must be non-negative",
        ):
            assemble_forecast_result(
                history,
                [0.4, 0.3, 0.2, 0.1],
                variability_multiplier=1.0,
                manual_overrides={"standard": -1.0},
            )

    def test_rejects_missing_history_for_forecast_assembly(self) -> None:
        history = self._build_history(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 10,
                    "standard": 20,
                    "complex_group": 30,
                    "change_cancellation": 40,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 11,
                    "standard": 21,
                    "complex_group": 31,
                    "change_cancellation": 41,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 12,
                    "standard": 22,
                    "complex_group": 32,
                    "change_cancellation": 42,
                    "staffing_agents": 6,
                },
            ]
        )

        with self.assertRaises(InsufficientHistoryError):
            assemble_forecast_result(
                history,
                [0.4, 0.3, 0.2, 0.1],
                variability_multiplier=1.0,
            )

    def test_reproducible_outputs_for_identical_inputs_and_row_order(self) -> None:
        ordered_history = self._build_history(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 10,
                    "standard": 20,
                    "complex_group": 30,
                    "change_cancellation": 40,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 11,
                    "standard": 21,
                    "complex_group": 31,
                    "change_cancellation": 41,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 12,
                    "standard": 22,
                    "complex_group": 32,
                    "change_cancellation": 42,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 13,
                    "standard": 23,
                    "complex_group": 33,
                    "change_cancellation": 43,
                    "staffing_agents": 6,
                },
            ]
        )
        shuffled_history = self._build_history(
            [
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 12,
                    "standard": 22,
                    "complex_group": 32,
                    "change_cancellation": 42,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 10,
                    "standard": 20,
                    "complex_group": 30,
                    "change_cancellation": 40,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 13,
                    "standard": 23,
                    "complex_group": 33,
                    "change_cancellation": 43,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 11,
                    "standard": 21,
                    "complex_group": 31,
                    "change_cancellation": 41,
                    "staffing_agents": 5,
                },
            ]
        )

        first = assemble_forecast_result(
            ordered_history,
            [0.4, 0.3, 0.2, 0.1],
            variability_multiplier=1.25,
            manual_overrides={"standard": 99.0},
        )
        second = assemble_forecast_result(
            ordered_history,
            [0.4, 0.3, 0.2, 0.1],
            variability_multiplier=1.25,
            manual_overrides={"standard": 99.0},
        )
        reordered = assemble_forecast_result(
            shuffled_history,
            [0.4, 0.3, 0.2, 0.1],
            variability_multiplier=1.25,
            manual_overrides={"standard": 99.0},
        )

        assert_frame_equal(first, second)
        assert_frame_equal(first, reordered)


if __name__ == "__main__":
    unittest.main()
