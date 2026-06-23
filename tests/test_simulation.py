"""Simulation and overflow-allocation tests for the restored backend."""

from __future__ import annotations

import unittest

import pandas as pd

from src.constants import FORECAST_RESULT_COLUMNS, RESERVATION_CATEGORIES
from src.simulation.demand_sampler import SIMULATION_OUTPUT_COLUMNS, simulate_weekly_demand
from src.simulation.monte_carlo import (
    SIMULATED_WORKLOAD_OUTPUT_COLUMNS,
    calculate_simulation_summary,
    calculate_simulated_workload_and_staffing,
)
from src.simulation.shortage import calculate_overflow_allocation_by_category


class DemandSamplerTests(unittest.TestCase):
    def _build_forecast_result(self, *, adjusted_std: float = 0.0) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "category": "day_cruise",
                    "point_forecast": 235.0,
                    "historical_mean": 196.25,
                    "historical_std": 45.0,
                    "adjusted_std": adjusted_std,
                    "forecast_source": "automatic",
                },
                {
                    "category": "seven_night_cruise",
                    "point_forecast": 153.5,
                    "historical_mean": 126.6667,
                    "historical_std": 34.0,
                    "adjusted_std": adjusted_std,
                    "forecast_source": "automatic",
                },
                {
                    "category": "nine_night_cruise",
                    "point_forecast": 90.0,
                    "historical_mean": 62.0833,
                    "historical_std": 26.0,
                    "adjusted_std": adjusted_std,
                    "forecast_source": "automatic",
                },
            ],
            columns=FORECAST_RESULT_COLUMNS,
        )

    def test_simulation_is_reproducible_with_seed_510(self) -> None:
        forecast_result = self._build_forecast_result(adjusted_std=8.0)

        first = simulate_weekly_demand(forecast_result, iterations=5, seed=510)
        second = simulate_weekly_demand(forecast_result, iterations=5, seed=510)

        pd.testing.assert_frame_equal(first, second)
        self.assertEqual(tuple(first.columns), SIMULATION_OUTPUT_COLUMNS)

    def test_zero_variability_produces_deterministic_integer_output(self) -> None:
        forecast_result = self._build_forecast_result(adjusted_std=0.0)

        result = simulate_weekly_demand(forecast_result, iterations=2, seed=510)
        expected = pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "day_cruise": 235,
                    "seven_night_cruise": 154,
                    "nine_night_cruise": 90,
                },
                {
                    "simulation_id": 2,
                    "day_cruise": 235,
                    "seven_night_cruise": 154,
                    "nine_night_cruise": 90,
                },
            ],
            columns=SIMULATION_OUTPUT_COLUMNS,
        )
        pd.testing.assert_frame_equal(result, expected)


class OverflowAndSimulationWorkloadTests(unittest.TestCase):
    def _build_handling_times(self) -> dict[str, float]:
        return {
            "day_cruise": 8.0,
            "seven_night_cruise": 22.0,
            "nine_night_cruise": 28.0,
        }

    def test_peak_case_overflow_allocation_reconciles(self) -> None:
        result = calculate_overflow_allocation_by_category(
            {
                "day_cruise": 300.0,
                "seven_night_cruise": 200.0,
                "nine_night_cruise": 130.0,
            },
            self._build_handling_times(),
            staffing_agents=12,
            booking_processing_hours_per_agent=12.5,
        )

        self.assertAlmostEqual(result["total_workload_hours"], 174.0)
        self.assertAlmostEqual(result["overflow_workload_hours"], 24.0)
        self.assertAlmostEqual(sum(result["overflow_hours_by_category"].values()), 24.0)
        self.assertAlmostEqual(
            sum(result["overflow_bookings_by_category"].values()),
            86.8965517241,
        )

    def test_completed_simulation_preserves_raw_and_clamped_staffing_fields(self) -> None:
        simulated_demand = pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "day_cruise": 300,
                    "seven_night_cruise": 200,
                    "nine_night_cruise": 130,
                },
                {
                    "simulation_id": 2,
                    "day_cruise": 145,
                    "seven_night_cruise": 90,
                    "nine_night_cruise": 45,
                },
            ],
            columns=SIMULATION_OUTPUT_COLUMNS,
        )

        result = calculate_simulated_workload_and_staffing(
            simulated_demand,
            self._build_handling_times(),
            booking_processing_hours_per_agent=12.5,
            minimum_schedulable_agents=8,
            maximum_inhouse_agents=12,
        )

        self.assertEqual(tuple(result.columns), SIMULATED_WORKLOAD_OUTPUT_COLUMNS)
        self.assertAlmostEqual(result.loc[0, "total_workload_hours"], 174.0)
        self.assertAlmostEqual(result.loc[0, "raw_required_fte"], 13.92)
        self.assertEqual(result.loc[0, "unconstrained_required_agents"], 14)
        self.assertEqual(result.loc[0, "recommended_inhouse_agents"], 12)
        self.assertAlmostEqual(result.loc[0, "overflow_workload_hours"], 24.0)
        self.assertAlmostEqual(result.loc[1, "total_workload_hours"], 73.3333333333)
        self.assertEqual(result.loc[1, "unconstrained_required_agents"], 6)
        self.assertEqual(result.loc[1, "recommended_inhouse_agents"], 8)
        self.assertAlmostEqual(result.loc[1, "spare_capacity_hours"], 26.6666666667)

    def test_simulation_summary_uses_overflow_not_abandonment(self) -> None:
        simulated_demand = pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "day_cruise": 300,
                    "seven_night_cruise": 200,
                    "nine_night_cruise": 130,
                },
                {
                    "simulation_id": 2,
                    "day_cruise": 145,
                    "seven_night_cruise": 90,
                    "nine_night_cruise": 45,
                },
            ],
            columns=SIMULATION_OUTPUT_COLUMNS,
        )
        completed = calculate_simulated_workload_and_staffing(
            simulated_demand,
            self._build_handling_times(),
            booking_processing_hours_per_agent=12.5,
        )

        result = calculate_simulation_summary(
            completed,
            staffing_agents=12,
            handling_times_minutes=self._build_handling_times(),
            booking_processing_hours_per_agent=12.5,
            percentiles=(0.5, 0.95),
        )

        self.assertAlmostEqual(result["capacity_confidence"], 0.5)
        self.assertAlmostEqual(result["probability_overflow_required"], 0.5)
        self.assertAlmostEqual(result["expected_overflow_workload_hours"], 12.0)
        self.assertEqual(result["required_agent_percentiles"], {0.5: 6, 0.95: 14})


if __name__ == "__main__":
    unittest.main()
