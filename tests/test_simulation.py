"""Simulation and overflow-allocation tests for the restored backend."""

from __future__ import annotations

import unittest

import pandas as pd

from src.constants import FORECAST_RESULT_COLUMNS, RESERVATION_CATEGORIES
from src.simulation.demand_sampler import SIMULATION_OUTPUT_COLUMNS, simulate_weekly_demand
from src.simulation.monte_carlo import (
    OUTLOOK_QUANTILE_CONVENTION,
    SIMULATED_WORKLOAD_OUTPUT_COLUMNS,
    calculate_simulation_summary,
    calculate_simulated_workload_and_staffing,
    select_representative_simulation_rows,
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

    def test_capacity_and_overflow_events_are_complements(self) -> None:
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
        )

        self.assertAlmostEqual(
            result["capacity_confidence"] + result["probability_overflow_required"],
            1.0,
            places=9,
        )

    def test_expected_spare_and_overflow_capacity_are_trial_level_positive_part_means(self) -> None:
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
        )

        self.assertAlmostEqual(result["expected_spare_capacity_hours"], 38.3333333333)
        self.assertAlmostEqual(result["expected_overflow_workload_hours"], 12.0)

    def _build_completed_simulation_for_outlook_tests(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "day_cruise": 10,
                    "seven_night_cruise": 5,
                    "nine_night_cruise": 2,
                    "total_workload_hours": 10.0,
                    "raw_required_fte": 0.8,
                    "unconstrained_required_agents": 1,
                    "recommended_inhouse_agents": 8,
                    "spare_capacity_hours": 90.0,
                    "overflow_workload_hours": 0.0,
                },
                {
                    "simulation_id": 2,
                    "day_cruise": 20,
                    "seven_night_cruise": 10,
                    "nine_night_cruise": 4,
                    "total_workload_hours": 20.0,
                    "raw_required_fte": 1.6,
                    "unconstrained_required_agents": 2,
                    "recommended_inhouse_agents": 8,
                    "spare_capacity_hours": 80.0,
                    "overflow_workload_hours": 0.0,
                },
                {
                    "simulation_id": 3,
                    "day_cruise": 30,
                    "seven_night_cruise": 15,
                    "nine_night_cruise": 6,
                    "total_workload_hours": 30.0,
                    "raw_required_fte": 2.4,
                    "unconstrained_required_agents": 3,
                    "recommended_inhouse_agents": 8,
                    "spare_capacity_hours": 70.0,
                    "overflow_workload_hours": 0.0,
                },
                {
                    "simulation_id": 4,
                    "day_cruise": 40,
                    "seven_night_cruise": 20,
                    "nine_night_cruise": 8,
                    "total_workload_hours": 40.0,
                    "raw_required_fte": 3.2,
                    "unconstrained_required_agents": 4,
                    "recommended_inhouse_agents": 8,
                    "spare_capacity_hours": 60.0,
                    "overflow_workload_hours": 0.0,
                },
                {
                    "simulation_id": 5,
                    "day_cruise": 50,
                    "seven_night_cruise": 25,
                    "nine_night_cruise": 10,
                    "total_workload_hours": 50.0,
                    "raw_required_fte": 4.0,
                    "unconstrained_required_agents": 4,
                    "recommended_inhouse_agents": 8,
                    "spare_capacity_hours": 50.0,
                    "overflow_workload_hours": 0.0,
                },
            ],
            columns=SIMULATED_WORKLOAD_OUTPUT_COLUMNS,
        )

    def test_representative_selection_uses_actual_completed_rows_and_linear_quantiles(self) -> None:
        completed = self._build_completed_simulation_for_outlook_tests()

        result = select_representative_simulation_rows(completed)

        self.assertEqual(
            result["diagnostics"]["quantile_convention"],
            OUTLOOK_QUANTILE_CONVENTION,
        )
        self.assertEqual(
            result["diagnostics"]["selected_row_ids_by_percentile_label"],
            {"P25": 2, "P50": 3, "P90": 5},
        )
        self.assertEqual(
            result["diagnostics"]["selected_total_workload_hours_by_percentile_label"],
            {"P25": 20.0, "P50": 30.0, "P90": 50.0},
        )
        self.assertAlmostEqual(
            result["diagnostics"]["target_total_workload_hours_by_percentile_label"]["P25"],
            20.0,
        )
        self.assertAlmostEqual(
            result["diagnostics"]["target_total_workload_hours_by_percentile_label"]["P50"],
            30.0,
        )
        self.assertAlmostEqual(
            result["diagnostics"]["target_total_workload_hours_by_percentile_label"]["P90"],
            46.0,
        )
        self.assertTrue(result["diagnostics"]["ordering_invariant_satisfied"])

        selected_p50 = next(
            item for item in result["selected_rows"] if item["percentile_label"] == "P50"
        )
        self.assertEqual(selected_p50["simulation_row_id"], 3)
        self.assertEqual(selected_p50["row"]["day_cruise"], 30)
        self.assertEqual(selected_p50["row"]["seven_night_cruise"], 15)
        self.assertEqual(selected_p50["row"]["nine_night_cruise"], 6)

    def test_representative_selection_breaks_equal_distance_ties_by_lower_row_id(self) -> None:
        completed = pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "day_cruise": 10,
                    "seven_night_cruise": 0,
                    "nine_night_cruise": 0,
                    "total_workload_hours": 10.0,
                    "raw_required_fte": 0.8,
                    "unconstrained_required_agents": 1,
                    "recommended_inhouse_agents": 8,
                    "spare_capacity_hours": 90.0,
                    "overflow_workload_hours": 0.0,
                },
                {
                    "simulation_id": 2,
                    "day_cruise": 30,
                    "seven_night_cruise": 0,
                    "nine_night_cruise": 0,
                    "total_workload_hours": 30.0,
                    "raw_required_fte": 2.4,
                    "unconstrained_required_agents": 3,
                    "recommended_inhouse_agents": 8,
                    "spare_capacity_hours": 70.0,
                    "overflow_workload_hours": 0.0,
                },
            ],
            columns=SIMULATED_WORKLOAD_OUTPUT_COLUMNS,
        )

        result = select_representative_simulation_rows(
            completed,
            outlook_requests=(("Central Demand", 0.5, "P50"),),
        )

        self.assertAlmostEqual(
            result["diagnostics"]["target_total_workload_hours_by_percentile_label"]["P50"],
            20.0,
        )
        self.assertEqual(
            result["diagnostics"]["selected_row_ids_by_percentile_label"]["P50"],
            1,
        )

    def test_representative_selection_prefers_distinct_rows_before_reuse(self) -> None:
        completed = pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "day_cruise": 10,
                    "seven_night_cruise": 1,
                    "nine_night_cruise": 1,
                    "total_workload_hours": 10.0,
                    "raw_required_fte": 0.8,
                    "unconstrained_required_agents": 1,
                    "recommended_inhouse_agents": 8,
                    "spare_capacity_hours": 90.0,
                    "overflow_workload_hours": 0.0,
                },
                {
                    "simulation_id": 2,
                    "day_cruise": 11,
                    "seven_night_cruise": 1,
                    "nine_night_cruise": 1,
                    "total_workload_hours": 10.0,
                    "raw_required_fte": 0.8,
                    "unconstrained_required_agents": 1,
                    "recommended_inhouse_agents": 8,
                    "spare_capacity_hours": 90.0,
                    "overflow_workload_hours": 0.0,
                },
                {
                    "simulation_id": 3,
                    "day_cruise": 12,
                    "seven_night_cruise": 1,
                    "nine_night_cruise": 1,
                    "total_workload_hours": 10.0,
                    "raw_required_fte": 0.8,
                    "unconstrained_required_agents": 1,
                    "recommended_inhouse_agents": 8,
                    "spare_capacity_hours": 90.0,
                    "overflow_workload_hours": 0.0,
                },
            ],
            columns=SIMULATED_WORKLOAD_OUTPUT_COLUMNS,
        )

        result = select_representative_simulation_rows(completed)

        self.assertFalse(result["diagnostics"]["row_reuse_detected"])
        self.assertEqual(
            result["diagnostics"]["selected_row_ids_by_percentile_label"],
            {"P25": 1, "P50": 2, "P90": 3},
        )
        self.assertTrue(
            all(not item["representative_row_reused"] for item in result["selected_rows"])
        )

    def test_representative_selection_reports_reuse_when_necessary(self) -> None:
        completed = pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "day_cruise": 10,
                    "seven_night_cruise": 1,
                    "nine_night_cruise": 1,
                    "total_workload_hours": 10.0,
                    "raw_required_fte": 0.8,
                    "unconstrained_required_agents": 1,
                    "recommended_inhouse_agents": 8,
                    "spare_capacity_hours": 90.0,
                    "overflow_workload_hours": 0.0,
                }
            ],
            columns=SIMULATED_WORKLOAD_OUTPUT_COLUMNS,
        )

        result = select_representative_simulation_rows(completed)

        self.assertTrue(result["diagnostics"]["row_reuse_detected"])
        self.assertEqual(
            result["diagnostics"]["selected_row_ids_by_percentile_label"],
            {"P25": 1, "P50": 1, "P90": 1},
        )
        self.assertEqual(len(result["diagnostics"]["reused_simulation_rows"]), 1)
        self.assertTrue(
            all(item["representative_row_reused"] for item in result["selected_rows"])
        )

    def test_representative_selection_is_reproducible_for_seed_510(self) -> None:
        forecast_result = self._build_forecast_result(adjusted_std=8.0)
        first_simulated = simulate_weekly_demand(forecast_result, iterations=20, seed=510)
        second_simulated = simulate_weekly_demand(forecast_result, iterations=20, seed=510)
        handling_times = self._build_handling_times()

        first_completed = calculate_simulated_workload_and_staffing(
            first_simulated,
            handling_times,
            booking_processing_hours_per_agent=12.5,
        )
        second_completed = calculate_simulated_workload_and_staffing(
            second_simulated,
            handling_times,
            booking_processing_hours_per_agent=12.5,
        )

        first_selection = select_representative_simulation_rows(first_completed)
        second_selection = select_representative_simulation_rows(second_completed)

        self.assertEqual(first_selection["diagnostics"], second_selection["diagnostics"])
        self.assertEqual(first_selection["selected_rows"], second_selection["selected_rows"])


if __name__ == "__main__":
    unittest.main()
