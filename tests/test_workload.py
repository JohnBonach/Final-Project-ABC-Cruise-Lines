"""Operations tests for workload and capacity calculations."""

from __future__ import annotations

import unittest

from src.constants import RESERVATION_CATEGORIES
from src.operations.capacity import (
    calculate_booking_processing_hours_per_agent,
    calculate_capacity_hours,
    calculate_required_agents,
    calculate_required_fte,
    clamp_inhouse_staffing,
)
from src.operations.workload import (
    MINUTES_PER_HOUR,
    calculate_workload_hours,
    calculate_workload_hours_by_category,
    calculate_workload_minutes_by_category,
)


class WorkloadTests(unittest.TestCase):
    def _build_demand(self) -> dict[str, int]:
        return {
            "day_cruise": 300,
            "seven_night_cruise": 200,
            "nine_night_cruise": 130,
        }

    def _build_handling_times(self) -> dict[str, float]:
        return {
            "day_cruise": 8.0,
            "seven_night_cruise": 22.0,
            "nine_night_cruise": 28.0,
        }

    def test_peak_case_workload_matches_approved_result(self) -> None:
        workload_minutes = calculate_workload_minutes_by_category(
            self._build_demand(),
            self._build_handling_times(),
        )
        workload_hours = calculate_workload_hours_by_category(
            self._build_demand(),
            self._build_handling_times(),
        )
        total_workload_hours = calculate_workload_hours(
            self._build_demand(),
            self._build_handling_times(),
        )

        self.assertEqual(tuple(workload_minutes), RESERVATION_CATEGORIES)
        self.assertEqual(tuple(workload_hours), RESERVATION_CATEGORIES)
        self.assertAlmostEqual(workload_minutes["day_cruise"], 2400.0)
        self.assertAlmostEqual(workload_minutes["seven_night_cruise"], 4400.0)
        self.assertAlmostEqual(workload_minutes["nine_night_cruise"], 3640.0)
        self.assertAlmostEqual(workload_hours["day_cruise"], 40.0)
        self.assertAlmostEqual(workload_hours["seven_night_cruise"], 73.3333333333)
        self.assertAlmostEqual(workload_hours["nine_night_cruise"], 60.6666666667)
        self.assertAlmostEqual(total_workload_hours, 174.0)
        self.assertAlmostEqual(total_workload_hours * MINUTES_PER_HOUR, 10440.0)

    def test_capacity_floor_and_cap_match_approved_rules(self) -> None:
        booking_processing_hours_per_agent = calculate_booking_processing_hours_per_agent(12.5)
        raw_required_fte = calculate_required_fte(174.0, booking_processing_hours_per_agent)
        unconstrained_required_agents = calculate_required_agents(raw_required_fte)
        recommended_inhouse_agents = clamp_inhouse_staffing(
            unconstrained_required_agents,
            8,
            12,
        )

        self.assertAlmostEqual(raw_required_fte, 13.92)
        self.assertEqual(unconstrained_required_agents, 14)
        self.assertEqual(recommended_inhouse_agents, 12)
        self.assertAlmostEqual(calculate_capacity_hours(12, 12.5), 150.0)

    def test_low_case_uses_operating_floor(self) -> None:
        workload_hours = calculate_workload_hours(
            {
                "day_cruise": 145,
                "seven_night_cruise": 90,
                "nine_night_cruise": 45,
            },
            self._build_handling_times(),
        )
        raw_required_fte = calculate_required_fte(workload_hours, 12.5)
        unconstrained_required_agents = calculate_required_agents(raw_required_fte)
        recommended_inhouse_agents = clamp_inhouse_staffing(
            unconstrained_required_agents,
            8,
            12,
        )

        self.assertAlmostEqual(workload_hours, 73.3333333333)
        self.assertAlmostEqual(raw_required_fte, 5.8666666667)
        self.assertEqual(unconstrained_required_agents, 6)
        self.assertEqual(recommended_inhouse_agents, 8)


if __name__ == "__main__":
    unittest.main()
