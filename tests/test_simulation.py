"""Contract tests for simulation modules."""

from __future__ import annotations

import unittest

import pandas as pd

from src.constants import FORECAST_RESULT_COLUMNS, RESERVATION_CATEGORIES
from src.models import CategoryAssumptions, WorkforceAssumptions
from src.orchestration import calculate_deterministic_staffing
from src.simulation.demand_sampler import SIMULATION_OUTPUT_COLUMNS, simulate_weekly_demand
from src.simulation.monte_carlo import (
    SIMULATED_WORKLOAD_OUTPUT_COLUMNS,
    calculate_simulation_summary,
    calculate_simulated_workload_and_staffing,
)
from src.simulation.shortage import (
    calculate_abandonment_and_overtime,
    calculate_shortage_allocation_by_category,
)
from src.validation import FieldValidationError


class DemandSamplerTests(unittest.TestCase):
    def _build_forecast_result(self, *, adjusted_std: float = 1.5) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "category": "simple",
                    "point_forecast": 12.2,
                    "historical_mean": 11.5,
                    "historical_std": 1.3,
                    "adjusted_std": adjusted_std,
                    "forecast_source": "automatic",
                },
                {
                    "category": "standard",
                    "point_forecast": 22.7,
                    "historical_mean": 21.5,
                    "historical_std": 1.3,
                    "adjusted_std": adjusted_std,
                    "forecast_source": "automatic",
                },
                {
                    "category": "complex_group",
                    "point_forecast": 32.4,
                    "historical_mean": 31.5,
                    "historical_std": 1.3,
                    "adjusted_std": adjusted_std,
                    "forecast_source": "automatic",
                },
                {
                    "category": "change_cancellation",
                    "point_forecast": 42.6,
                    "historical_mean": 41.5,
                    "historical_std": 1.3,
                    "adjusted_std": adjusted_std,
                    "forecast_source": "automatic",
                },
            ],
            columns=FORECAST_RESULT_COLUMNS,
        )

    def test_returns_canonical_schema_and_simulation_ids(self) -> None:
        forecast_result = self._build_forecast_result()

        result = simulate_weekly_demand(forecast_result, iterations=3, seed=7)

        self.assertEqual(tuple(result.columns), SIMULATION_OUTPUT_COLUMNS)
        self.assertEqual(len(result), 3)
        self.assertEqual(result["simulation_id"].tolist(), [1, 2, 3])
        self.assertEqual(tuple(result.columns[1:]), RESERVATION_CATEGORIES)

    def test_is_reproducible_with_fixed_seed(self) -> None:
        forecast_result = self._build_forecast_result()

        first = simulate_weekly_demand(forecast_result, iterations=5, seed=123)
        second = simulate_weekly_demand(forecast_result, iterations=5, seed=123)

        pd.testing.assert_frame_equal(first, second)

    def test_zero_variability_produces_deterministic_integer_output(self) -> None:
        forecast_result = self._build_forecast_result(adjusted_std=0.0)

        result = simulate_weekly_demand(forecast_result, iterations=2, seed=99)

        expected = pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "simple": 12,
                    "standard": 23,
                    "complex_group": 32,
                    "change_cancellation": 43,
                },
                {
                    "simulation_id": 2,
                    "simple": 12,
                    "standard": 23,
                    "complex_group": 32,
                    "change_cancellation": 43,
                },
            ],
            columns=SIMULATION_OUTPUT_COLUMNS,
        )
        pd.testing.assert_frame_equal(result, expected)

    def test_output_is_non_negative_and_integer_valued(self) -> None:
        forecast_result = self._build_forecast_result(adjusted_std=10.0)

        result = simulate_weekly_demand(forecast_result, iterations=20, seed=5)

        for column in SIMULATION_OUTPUT_COLUMNS:
            self.assertTrue(pd.api.types.is_integer_dtype(result[column]))
        self.assertTrue((result[list(RESERVATION_CATEGORIES)] >= 0).all().all())
        self.assertTrue(
            (result[list(RESERVATION_CATEGORIES)] == result[list(RESERVATION_CATEGORIES)].astype(int)).all().all()
        )

    def test_rejects_invalid_distribution_name(self) -> None:
        forecast_result = self._build_forecast_result()

        with self.assertRaisesRegex(ValueError, "distribution_name must be one of"):
            simulate_weekly_demand(
                forecast_result,
                iterations=1,
                seed=1,
                distribution_name="poisson",
            )

    def test_rejects_malformed_forecast_input(self) -> None:
        malformed_missing_column = self._build_forecast_result().drop(columns=["adjusted_std"])

        with self.assertRaisesRegex(FieldValidationError, "missing columns"):
            simulate_weekly_demand(malformed_missing_column, iterations=1, seed=1)

        malformed_categories = self._build_forecast_result().iloc[[0, 1, 1, 3]].copy()

        with self.assertRaisesRegex(FieldValidationError, "duplicates found"):
            simulate_weekly_demand(malformed_categories, iterations=1, seed=1)


class SimulatedWorkloadTests(unittest.TestCase):
    def _build_single_row_simulation(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "simple": 12,
                    "standard": 8,
                    "complex_group": 4,
                    "change_cancellation": 6,
                }
            ],
            columns=("simulation_id", *RESERVATION_CATEGORIES),
        )

    def _build_handling_times(self) -> dict[str, float]:
        return {
            "simple": 10.0,
            "standard": 15.0,
            "complex_group": 30.0,
            "change_cancellation": 20.0,
        }

    def test_extends_simulated_demand_with_required_staffing_columns(self) -> None:
        simulated_demand = self._build_single_row_simulation()

        result = calculate_simulated_workload_and_staffing(
            simulated_demand,
            self._build_handling_times(),
            productive_hours_per_agent=30.0,
        )

        self.assertEqual(tuple(result.columns), SIMULATED_WORKLOAD_OUTPUT_COLUMNS)
        self.assertEqual(result.loc[0, "total_workload_hours"], 8.0)
        self.assertEqual(result.loc[0, "required_fte"], 8.0 / 30.0)
        self.assertEqual(result.loc[0, "required_agents"], 1)

    def test_matches_deterministic_engine_for_equivalent_single_row(self) -> None:
        simulated_demand = self._build_single_row_simulation()
        category_assumptions = (
            CategoryAssumptions(
                category="simple",
                handling_time_minutes=10.0,
                average_revenue=100.0,
                contribution_per_reservation=60.0,
            ),
            CategoryAssumptions(
                category="standard",
                handling_time_minutes=15.0,
                average_revenue=120.0,
                contribution_per_reservation=70.0,
            ),
            CategoryAssumptions(
                category="complex_group",
                handling_time_minutes=30.0,
                average_revenue=180.0,
                contribution_per_reservation=90.0,
            ),
            CategoryAssumptions(
                category="change_cancellation",
                handling_time_minutes=20.0,
                average_revenue=80.0,
                contribution_per_reservation=40.0,
            ),
        )
        workforce_assumptions = WorkforceAssumptions(
            paid_hours_per_agent=40.0,
            productive_processing_pct=0.75,
            regular_hourly_wage=22.0,
            overtime_multiplier=1.5,
            abandonment_rate=0.05,
            planned_staffing_agents=3,
        )

        deterministic_result = calculate_deterministic_staffing(
            {
                "simple": 12,
                "standard": 8,
                "complex_group": 4,
                "change_cancellation": 6,
            },
            category_assumptions,
            workforce_assumptions,
        )
        simulated_result = calculate_simulated_workload_and_staffing(
            simulated_demand,
            self._build_handling_times(),
            productive_hours_per_agent=30.0,
        )

        self.assertEqual(
            simulated_result.loc[0, "total_workload_hours"],
            deterministic_result["total_workload_hours"],
        )
        self.assertEqual(simulated_result.loc[0, "required_fte"], deterministic_result["required_fte"])
        self.assertEqual(
            simulated_result.loc[0, "required_agents"],
            deterministic_result["required_agents"],
        )

    def test_required_agents_round_up_for_fractional_fte(self) -> None:
        simulated_demand = pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "simple": 1,
                    "standard": 0,
                    "complex_group": 0,
                    "change_cancellation": 0,
                }
            ],
            columns=("simulation_id", *RESERVATION_CATEGORIES),
        )
        handling_times = {
            "simple": 61.0,
            "standard": 15.0,
            "complex_group": 30.0,
            "change_cancellation": 20.0,
        }

        result = calculate_simulated_workload_and_staffing(
            simulated_demand,
            handling_times,
            productive_hours_per_agent=1.0,
        )

        self.assertGreater(result.loc[0, "required_fte"], 1.0)
        self.assertEqual(result.loc[0, "required_agents"], 2)

    def test_zero_demand_produces_zero_workload_and_staffing(self) -> None:
        simulated_demand = pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "simple": 0,
                    "standard": 0,
                    "complex_group": 0,
                    "change_cancellation": 0,
                }
            ],
            columns=("simulation_id", *RESERVATION_CATEGORIES),
        )

        result = calculate_simulated_workload_and_staffing(
            simulated_demand,
            self._build_handling_times(),
            productive_hours_per_agent=30.0,
        )

        self.assertEqual(result.loc[0, "total_workload_hours"], 0.0)
        self.assertEqual(result.loc[0, "required_fte"], 0.0)
        self.assertEqual(result.loc[0, "required_agents"], 0)

    def test_rejects_malformed_simulated_input(self) -> None:
        malformed_missing_column = self._build_single_row_simulation().drop(columns=["standard"])

        with self.assertRaisesRegex(FieldValidationError, "missing columns"):
            calculate_simulated_workload_and_staffing(
                malformed_missing_column,
                self._build_handling_times(),
                productive_hours_per_agent=30.0,
            )

        malformed_handling_times = {
            "simple": 10.0,
            "standard": 15.0,
            "complex_group": 30.0,
        }

        with self.assertRaisesRegex(FieldValidationError, "canonical reservation categories"):
            calculate_simulated_workload_and_staffing(
                self._build_single_row_simulation(),
                malformed_handling_times,
                productive_hours_per_agent=30.0,
            )

    def test_higher_handling_time_increases_expected_workload(self) -> None:
        simulated_demand = self._build_single_row_simulation()
        baseline_handling_times = self._build_handling_times()
        higher_handling_times = {
            "simple": 20.0,
            "standard": 15.0,
            "complex_group": 30.0,
            "change_cancellation": 20.0,
        }

        baseline = calculate_simulated_workload_and_staffing(
            simulated_demand,
            baseline_handling_times,
            productive_hours_per_agent=30.0,
        )
        higher = calculate_simulated_workload_and_staffing(
            simulated_demand,
            higher_handling_times,
            productive_hours_per_agent=30.0,
        )

        self.assertGreater(
            higher.loc[0, "total_workload_hours"],
            baseline.loc[0, "total_workload_hours"],
        )


class ShortageAllocationTests(unittest.TestCase):
    def _build_demand(self) -> dict[str, float]:
        return {
            "simple": 12.0,
            "standard": 8.0,
            "complex_group": 4.0,
            "change_cancellation": 6.0,
        }

    def _build_excess_reservations(self) -> dict[str, float]:
        return {
            "simple": 10.0,
            "standard": 20.0,
            "complex_group": 30.0,
            "change_cancellation": 40.0,
        }

    def _build_handling_times(self) -> dict[str, float]:
        return {
            "simple": 10.0,
            "standard": 15.0,
            "complex_group": 30.0,
            "change_cancellation": 20.0,
        }

    def test_sufficient_capacity_produces_zero_excess(self) -> None:
        result = calculate_shortage_allocation_by_category(
            self._build_demand(),
            self._build_handling_times(),
            staffing_agents=1,
            productive_hours_per_agent=8.0,
        )

        self.assertEqual(tuple(result["completed_reservations_by_category"]), RESERVATION_CATEGORIES)
        self.assertEqual(tuple(result["excess_reservations_by_category"]), RESERVATION_CATEGORIES)
        self.assertEqual(
            result["completed_reservations_by_category"],
            self._build_demand(),
        )
        self.assertEqual(
            result["excess_reservations_by_category"],
            {category: 0.0 for category in RESERVATION_CATEGORIES},
        )
        self.assertEqual(result["shortage_workload_hours"], 0.0)

    def test_shortage_is_allocated_by_workload_share(self) -> None:
        demand = self._build_demand()
        handling_times = self._build_handling_times()

        result = calculate_shortage_allocation_by_category(
            demand,
            handling_times,
            staffing_agents=0,
            productive_hours_per_agent=8.0,
        )

        self.assertAlmostEqual(result["total_workload_hours"], 8.0)
        self.assertAlmostEqual(result["regular_capacity_hours"], 0.0)
        self.assertAlmostEqual(result["shortage_workload_hours"], 8.0)
        self.assertEqual(
            result["excess_reservations_by_category"],
            demand,
        )
        self.assertEqual(
            result["completed_reservations_by_category"],
            {category: 0.0 for category in RESERVATION_CATEGORIES},
        )

    def test_allocated_excess_conserves_shortage_within_tolerance(self) -> None:
        demand = self._build_demand()
        handling_times = self._build_handling_times()

        result = calculate_shortage_allocation_by_category(
            demand,
            handling_times,
            staffing_agents=0,
            productive_hours_per_agent=7.0,
        )

        excess_workload_hours = result["excess_workload_hours_by_category"]
        self.assertAlmostEqual(
            sum(excess_workload_hours.values()),
            result["shortage_workload_hours"],
        )

        for category in RESERVATION_CATEGORIES:
            self.assertLessEqual(
                result["excess_reservations_by_category"][category],
                demand[category],
            )
            self.assertAlmostEqual(
                result["completed_reservations_by_category"][category]
                + result["excess_reservations_by_category"][category],
                demand[category],
            )

    def test_preserves_category_identity_and_order_for_shortage_outputs(self) -> None:
        result = calculate_shortage_allocation_by_category(
            self._build_demand(),
            self._build_handling_times(),
            staffing_agents=0,
            productive_hours_per_agent=8.0,
        )

        self.assertEqual(
            tuple(result["workload_hours_by_category"].keys()),
            RESERVATION_CATEGORIES,
        )
        self.assertEqual(
            tuple(result["completed_reservations_by_category"].keys()),
            RESERVATION_CATEGORIES,
        )
        self.assertEqual(
            tuple(result["excess_reservations_by_category"].keys()),
            RESERVATION_CATEGORIES,
        )
        self.assertEqual(
            tuple(result["excess_workload_hours_by_category"].keys()),
            RESERVATION_CATEGORIES,
        )

    def test_zero_shortage_produces_zero_abandonment_and_overtime(self) -> None:
        result = calculate_abandonment_and_overtime(
            {
                "simple": 0.0,
                "standard": 0.0,
                "complex_group": 0.0,
                "change_cancellation": 0.0,
            },
            self._build_handling_times(),
            abandonment_rate=0.25,
        )

        self.assertEqual(tuple(result["abandoned_reservations_by_category"]), RESERVATION_CATEGORIES)
        self.assertEqual(tuple(result["overtime_reservations_by_category"]), RESERVATION_CATEGORIES)
        self.assertEqual(
            result["abandoned_reservations_by_category"],
            {category: 0.0 for category in RESERVATION_CATEGORIES},
        )
        self.assertEqual(
            result["overtime_reservations_by_category"],
            {category: 0.0 for category in RESERVATION_CATEGORIES},
        )
        self.assertEqual(result["overtime_hours"], 0.0)

    def test_nonzero_shortage_applies_abandonment_rate_before_overtime(self) -> None:
        result = calculate_abandonment_and_overtime(
            self._build_excess_reservations(),
            self._build_handling_times(),
            abandonment_rate=0.10,
        )

        self.assertEqual(
            result["abandoned_reservations_by_category"],
            {
                "simple": 1.0,
                "standard": 2.0,
                "complex_group": 3.0,
                "change_cancellation": 4.0,
            },
        )
        self.assertEqual(
            result["overtime_reservations_by_category"],
            {
                "simple": 9.0,
                "standard": 18.0,
                "complex_group": 27.0,
                "change_cancellation": 36.0,
            },
        )
        self.assertAlmostEqual(result["overtime_hours"], 31.5)

    def test_zero_abandonment_rate_routes_all_excess_to_overtime(self) -> None:
        excess = self._build_excess_reservations()

        result = calculate_abandonment_and_overtime(
            excess,
            self._build_handling_times(),
            abandonment_rate=0.0,
        )

        self.assertEqual(
            result["abandoned_reservations_by_category"],
            {category: 0.0 for category in RESERVATION_CATEGORIES},
        )
        self.assertEqual(result["overtime_reservations_by_category"], excess)

    def test_full_abandonment_rate_routes_all_excess_to_abandonment(self) -> None:
        excess = self._build_excess_reservations()

        result = calculate_abandonment_and_overtime(
            excess,
            self._build_handling_times(),
            abandonment_rate=1.0,
        )

        self.assertEqual(result["abandoned_reservations_by_category"], excess)
        self.assertEqual(
            result["overtime_reservations_by_category"],
            {category: 0.0 for category in RESERVATION_CATEGORIES},
        )
        self.assertEqual(result["overtime_hours"], 0.0)

    def test_preserves_category_identity_and_order(self) -> None:
        result = calculate_abandonment_and_overtime(
            self._build_excess_reservations(),
            self._build_handling_times(),
            abandonment_rate=0.25,
        )

        self.assertEqual(
            tuple(result["abandoned_reservations_by_category"].keys()),
            RESERVATION_CATEGORIES,
        )
        self.assertEqual(
            tuple(result["overtime_reservations_by_category"].keys()),
            RESERVATION_CATEGORIES,
        )

    def test_conserves_excess_across_abandoned_and_overtime_outputs(self) -> None:
        excess = self._build_excess_reservations()
        handling_times = self._build_handling_times()
        result = calculate_abandonment_and_overtime(
            excess,
            handling_times,
            abandonment_rate=0.25,
        )

        abandoned = result["abandoned_reservations_by_category"]
        overtime = result["overtime_reservations_by_category"]
        for category in RESERVATION_CATEGORIES:
            self.assertAlmostEqual(abandoned[category] + overtime[category], excess[category])

        expected_overtime_hours = sum(
            overtime[category] * handling_times[category] for category in RESERVATION_CATEGORIES
        ) / 60.0
        self.assertAlmostEqual(result["overtime_hours"], expected_overtime_hours)


class SimulationAggregationTests(unittest.TestCase):
    def _build_handling_times(self) -> dict[str, float]:
        return {
            "simple": 10.0,
            "standard": 15.0,
            "complex_group": 30.0,
            "change_cancellation": 20.0,
        }

    def _build_variance_completed_simulation(self, simple_counts: list[int]) -> pd.DataFrame:
        simulated_demand = pd.DataFrame(
            [
                {
                    "simulation_id": index + 1,
                    "simple": count,
                    "standard": 0,
                    "complex_group": 0,
                    "change_cancellation": 0,
                }
                for index, count in enumerate(simple_counts)
            ],
            columns=("simulation_id", *RESERVATION_CATEGORIES),
        )
        handling_times = {
            "simple": 60.0,
            "standard": 60.0,
            "complex_group": 60.0,
            "change_cancellation": 60.0,
        }
        return calculate_simulated_workload_and_staffing(
            simulated_demand,
            handling_times,
            productive_hours_per_agent=8.0,
        )

    def _build_completed_simulation(self) -> pd.DataFrame:
        simulated_demand = pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "simple": 12,
                    "standard": 8,
                    "complex_group": 4,
                    "change_cancellation": 6,
                },
                {
                    "simulation_id": 2,
                    "simple": 24,
                    "standard": 16,
                    "complex_group": 8,
                    "change_cancellation": 12,
                },
                {
                    "simulation_id": 3,
                    "simple": 0,
                    "standard": 0,
                    "complex_group": 0,
                    "change_cancellation": 0,
                },
            ],
            columns=("simulation_id", *RESERVATION_CATEGORIES),
        )
        return calculate_simulated_workload_and_staffing(
            simulated_demand,
            self._build_handling_times(),
            productive_hours_per_agent=8.0,
        )

    def test_summarizes_simulation_outcomes_for_one_staffing_level(self) -> None:
        completed_simulation = self._build_completed_simulation()
        handling_times = self._build_handling_times()

        result = calculate_simulation_summary(
            completed_simulation,
            staffing_agents=1,
            handling_times_minutes=handling_times,
            productive_hours_per_agent=8.0,
            abandonment_rate=0.25,
            percentiles=(0.5, 0.75, 0.9, 0.95),
        )

        self.assertEqual(result["staffing_agents"], 1)
        self.assertAlmostEqual(result["capacity_confidence"], 2 / 3)
        self.assertAlmostEqual(result["probability_overtime_required"], 1 / 3)
        self.assertAlmostEqual(result["expected_overtime_hours"], 2.0)
        self.assertEqual(tuple(result["expected_abandoned_by_category"]), RESERVATION_CATEGORIES)
        self.assertAlmostEqual(result["expected_abandoned_by_category"]["simple"], 1.0)
        self.assertAlmostEqual(result["expected_abandoned_by_category"]["standard"], 2.0 / 3.0)
        self.assertAlmostEqual(result["expected_abandoned_by_category"]["complex_group"], 1.0 / 3.0)
        self.assertAlmostEqual(
            result["expected_abandoned_by_category"]["change_cancellation"],
            0.5,
        )
        self.assertAlmostEqual(result["expected_abandoned_total"], 2.5)
        self.assertAlmostEqual(result["expected_abandoned_simple"], 1.0)
        self.assertAlmostEqual(result["expected_abandoned_standard"], 2.0 / 3.0)
        self.assertAlmostEqual(result["expected_abandoned_complex_group"], 1.0 / 3.0)
        self.assertAlmostEqual(result["expected_abandoned_change_cancellation"], 0.5)
        self.assertAlmostEqual(result["expected_unused_regular_hours"], 8.0 / 3.0)
        self.assertEqual(
            result["required_agent_percentiles"],
            {
                0.5: 1,
                0.75: 2,
                0.9: 2,
                0.95: 2,
            },
        )

    def test_more_staff_cannot_reduce_capacity_confidence(self) -> None:
        completed_simulation = self._build_completed_simulation()
        handling_times = self._build_handling_times()

        fewer_staff = calculate_simulation_summary(
            completed_simulation,
            staffing_agents=1,
            handling_times_minutes=handling_times,
            productive_hours_per_agent=8.0,
            abandonment_rate=0.25,
            percentiles=(0.5, 0.75, 0.9, 0.95),
        )
        more_staff = calculate_simulation_summary(
            completed_simulation,
            staffing_agents=2,
            handling_times_minutes=handling_times,
            productive_hours_per_agent=8.0,
            abandonment_rate=0.25,
            percentiles=(0.5, 0.75, 0.9, 0.95),
        )

        self.assertLessEqual(fewer_staff["capacity_confidence"], more_staff["capacity_confidence"])

    def test_more_staff_cannot_increase_expected_overtime_under_identical_demand(self) -> None:
        completed_simulation = self._build_completed_simulation()
        handling_times = self._build_handling_times()

        fewer_staff = calculate_simulation_summary(
            completed_simulation,
            staffing_agents=1,
            handling_times_minutes=handling_times,
            productive_hours_per_agent=8.0,
            abandonment_rate=0.25,
            percentiles=(0.5, 0.75, 0.9, 0.95),
        )
        more_staff = calculate_simulation_summary(
            completed_simulation,
            staffing_agents=2,
            handling_times_minutes=handling_times,
            productive_hours_per_agent=8.0,
            abandonment_rate=0.25,
            percentiles=(0.5, 0.75, 0.9, 0.95),
        )

        self.assertGreaterEqual(fewer_staff["expected_overtime_hours"], more_staff["expected_overtime_hours"])

    def test_higher_variability_does_not_reduce_high_percentile_staffing_requirement(self) -> None:
        low_variability = self._build_variance_completed_simulation([8, 8, 8, 8])
        high_variability = self._build_variance_completed_simulation([0, 0, 8, 24])
        handling_times = {
            "simple": 60.0,
            "standard": 60.0,
            "complex_group": 60.0,
            "change_cancellation": 60.0,
        }

        low_variance_result = calculate_simulation_summary(
            low_variability,
            staffing_agents=1,
            handling_times_minutes=handling_times,
            productive_hours_per_agent=8.0,
            abandonment_rate=0.25,
            percentiles=(0.95,),
        )
        high_variance_result = calculate_simulation_summary(
            high_variability,
            staffing_agents=1,
            handling_times_minutes=handling_times,
            productive_hours_per_agent=8.0,
            abandonment_rate=0.25,
            percentiles=(0.95,),
        )

        self.assertGreaterEqual(
            high_variance_result["required_agent_percentiles"][0.95],
            low_variance_result["required_agent_percentiles"][0.95],
        )

    def test_required_agent_percentiles_are_deterministic_for_a_fixed_fixture(self) -> None:
        completed_simulation = self._build_completed_simulation()
        handling_times = self._build_handling_times()

        first = calculate_simulation_summary(
            completed_simulation,
            staffing_agents=1,
            handling_times_minutes=handling_times,
            productive_hours_per_agent=8.0,
            abandonment_rate=0.25,
            percentiles=(0.5, 0.75, 0.9, 0.95),
        )
        second = calculate_simulation_summary(
            completed_simulation,
            staffing_agents=1,
            handling_times_minutes=handling_times,
            productive_hours_per_agent=8.0,
            abandonment_rate=0.25,
            percentiles=(0.5, 0.75, 0.9, 0.95),
        )

        self.assertEqual(first["required_agent_percentiles"], second["required_agent_percentiles"])

    def test_full_abandonment_can_eliminate_overtime_probability_despite_shortage(self) -> None:
        completed_simulation = self._build_completed_simulation()

        result = calculate_simulation_summary(
            completed_simulation,
            staffing_agents=1,
            handling_times_minutes=self._build_handling_times(),
            productive_hours_per_agent=8.0,
            abandonment_rate=1.0,
            percentiles=(0.5, 0.75, 0.9, 0.95),
        )

        self.assertAlmostEqual(result["capacity_confidence"], 2 / 3)
        self.assertAlmostEqual(result["probability_overtime_required"], 0.0)
        self.assertAlmostEqual(result["expected_overtime_hours"], 0.0)


if __name__ == "__main__":
    unittest.main()
