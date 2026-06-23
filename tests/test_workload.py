"""Operations tests for deterministic workload and capacity calculations."""

from __future__ import annotations

import unittest

from src.constants import RESERVATION_CATEGORIES
from src.operations.capacity import (
    calculate_productive_hours_per_agent,
    calculate_required_agents,
    calculate_required_fte,
)
from src.operations.workload import (
    MINUTES_PER_HOUR,
    calculate_workload_hours,
    calculate_workload_hours_by_category,
    calculate_workload_minutes_by_category,
)


class WorkloadTests(unittest.TestCase):
    def test_workload_is_calculated_by_category_in_canonical_order(self) -> None:
        demand_by_category = {
            "simple": 12,
            "standard": 8,
            "complex_group": 4,
            "change_cancellation": 6,
        }
        handling_times_minutes = {
            "simple": 10,
            "standard": 15,
            "complex_group": 30,
            "change_cancellation": 20,
        }

        workload_minutes = calculate_workload_minutes_by_category(
            demand_by_category,
            handling_times_minutes,
        )
        workload_hours = calculate_workload_hours_by_category(
            demand_by_category,
            handling_times_minutes,
        )

        self.assertEqual(tuple(workload_minutes), RESERVATION_CATEGORIES)
        self.assertEqual(tuple(workload_hours), RESERVATION_CATEGORIES)
        self.assertEqual(
            workload_minutes,
            {
                "simple": 120.0,
                "standard": 120.0,
                "complex_group": 120.0,
                "change_cancellation": 120.0,
            },
        )
        self.assertEqual(
            workload_hours,
            {
                "simple": 2.0,
                "standard": 2.0,
                "complex_group": 2.0,
                "change_cancellation": 2.0,
            },
        )

    def test_zero_demand_returns_zero_workload_for_every_category(self) -> None:
        demand_by_category = {
            "simple": 0,
            "standard": 0,
            "complex_group": 0,
            "change_cancellation": 0,
        }
        handling_times_minutes = {
            "simple": 10,
            "standard": 15,
            "complex_group": 30,
            "change_cancellation": 20,
        }

        workload_minutes = calculate_workload_minutes_by_category(
            demand_by_category,
            handling_times_minutes,
        )
        workload_hours = calculate_workload_hours_by_category(
            demand_by_category,
            handling_times_minutes,
        )
        total_workload_hours = calculate_workload_hours(
            demand_by_category,
            handling_times_minutes,
        )

        self.assertEqual(tuple(workload_minutes), RESERVATION_CATEGORIES)
        self.assertEqual(tuple(workload_hours), RESERVATION_CATEGORIES)
        self.assertEqual(
            workload_minutes,
            {
                "simple": 0.0,
                "standard": 0.0,
                "complex_group": 0.0,
                "change_cancellation": 0.0,
            },
        )
        self.assertEqual(
            workload_hours,
            {
                "simple": 0.0,
                "standard": 0.0,
                "complex_group": 0.0,
                "change_cancellation": 0.0,
            },
        )
        self.assertEqual(total_workload_hours, 0.0)

    def test_one_category_only_case_keeps_canonical_keys(self) -> None:
        demand_by_category = {
            "simple": 20,
            "standard": 0,
            "complex_group": 0,
            "change_cancellation": 0,
        }
        handling_times_minutes = {
            "simple": 12,
            "standard": 15,
            "complex_group": 30,
            "change_cancellation": 20,
        }

        workload_hours = calculate_workload_hours_by_category(
            demand_by_category,
            handling_times_minutes,
        )

        self.assertEqual(tuple(workload_hours), RESERVATION_CATEGORIES)
        self.assertEqual(
            workload_hours,
            {
                "simple": 4.0,
                "standard": 0.0,
                "complex_group": 0.0,
                "change_cancellation": 0.0,
            },
        )
        self.assertEqual(
            calculate_workload_hours(demand_by_category, handling_times_minutes),
            4.0,
        )

    def test_total_workload_hours_sum_category_hours(self) -> None:
        demand_by_category = {
            "simple": 12,
            "standard": 8,
            "complex_group": 4,
            "change_cancellation": 6,
        }
        handling_times_minutes = {
            "simple": 10,
            "standard": 15,
            "complex_group": 30,
            "change_cancellation": 20,
        }

        workload_hours = calculate_workload_hours(
            demand_by_category,
            handling_times_minutes,
        )

        self.assertEqual(workload_hours, 8.0)
        self.assertEqual(
            workload_hours,
            sum(
                calculate_workload_hours_by_category(
                    demand_by_category,
                    handling_times_minutes,
                ).values()
            ),
        )
        self.assertEqual(workload_hours * MINUTES_PER_HOUR, 480.0)

    def test_productive_hours_fte_and_rounding_behave_as_expected(self) -> None:
        productive_hours_per_agent = calculate_productive_hours_per_agent(40.0, 0.75)
        required_fte = calculate_required_fte(8.0, productive_hours_per_agent)

        self.assertEqual(productive_hours_per_agent, 30.0)
        self.assertAlmostEqual(required_fte, 8.0 / 30.0)
        self.assertEqual(calculate_required_agents(required_fte), 1)

    def test_productive_hours_reject_invalid_percentage(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 0.0 and 1.0 inclusive"):
            calculate_productive_hours_per_agent(40.0, 1.2)

    def test_productive_hours_reject_zero_capacity(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "productive hours per agent must be greater than 0",
        ):
            calculate_productive_hours_per_agent(40.0, 0.0)

    def test_required_agents_rounds_up_to_next_whole_agent(self) -> None:
        self.assertEqual(calculate_required_agents(2.0), 2)
        self.assertEqual(calculate_required_agents(2.01), 3)


if __name__ == "__main__":
    unittest.main()
