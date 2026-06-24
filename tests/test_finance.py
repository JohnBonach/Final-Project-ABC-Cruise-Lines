"""Finance tests for overflow commission and weekly operating cost."""

from __future__ import annotations

import unittest

import pandas as pd

from src.constants import CATEGORY_ASSUMPTIONS_COLUMNS, SIMULATION_OUTPUT_COLUMNS, STAFFING_EVALUATION_COLUMNS
from src.finance.economics import calculate_weekly_operating_financials
from src.finance.staffing_evaluator import evaluate_staffing_level


class FinanceTests(unittest.TestCase):
    def _build_category_assumptions(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "category": "day_cruise",
                    "handling_time_minutes": 8.0,
                    "average_booking_value": 500.0,
                },
                {
                    "category": "seven_night_cruise",
                    "handling_time_minutes": 22.0,
                    "average_booking_value": 2200.0,
                },
                {
                    "category": "nine_night_cruise",
                    "handling_time_minutes": 28.0,
                    "average_booking_value": 2800.0,
                },
            ],
            columns=CATEGORY_ASSUMPTIONS_COLUMNS,
        )

    def _build_workforce_assumptions(self) -> dict[str, float | int]:
        return {
            "paid_hours_per_agent": 40.0,
            "weekly_booking_processing_hours_per_agent": 12.5,
            "regular_hourly_wage": 22.0,
            "minimum_schedulable_agents": 8,
            "maximum_inhouse_agents": 12,
            "planned_staffing_agents": 10,
        }

    def _build_strategic_assumptions(self) -> dict[str, float]:
        return {
            "third_party_commission_rate": 0.125,
        }

    def test_category_financials_reconcile_booking_value_and_commission(self) -> None:
        result = calculate_weekly_operating_financials(
            {
                "day_cruise": 258.6206896552,
                "seven_night_cruise": 172.4137931034,
                "nine_night_cruise": 112.0689655172,
            },
            {
                "day_cruise": 41.3793103448,
                "seven_night_cruise": 27.5862068966,
                "nine_night_cruise": 17.9310344828,
            },
            self._build_category_assumptions().to_dict(orient="records"),
            0.125,
        )

        self.assertAlmostEqual(result["total_overflow_commission"], 16448.2758621, places=4)
        self.assertAlmostEqual(result["total_overflow_booking_value"], 131586.2068966, places=4)
        self.assertAlmostEqual(result["total_commission_avoided"], 102801.7241379, places=4)

    def test_staffing_evaluation_matches_peak_case_costs(self) -> None:
        simulated_demand = pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "day_cruise": 300.0,
                    "seven_night_cruise": 200.0,
                    "nine_night_cruise": 130.0,
                }
            ],
            columns=SIMULATION_OUTPUT_COLUMNS,
        )

        result = evaluate_staffing_level(
            simulated_demand,
            staffing_agents=12,
            category_assumptions=self._build_category_assumptions(),
            workforce_assumptions=self._build_workforce_assumptions(),
            strategic_assumptions=self._build_strategic_assumptions(),
        )

        self.assertEqual(tuple(result), STAFFING_EVALUATION_COLUMNS)
        self.assertAlmostEqual(result["regular_labor_cost"], 10560.0)
        self.assertAlmostEqual(result["expected_overflow_commission"], 16448.2758621, places=4)
        self.assertAlmostEqual(result["expected_total_weekly_operating_cost"], 27008.2758621, places=4)
        self.assertAlmostEqual(result["expected_overflow_workload_hours"], 24.0)
        self.assertAlmostEqual(result["expected_overflow_day_cruise"], 41.3793103448, places=4)

    def test_low_case_has_zero_overflow_commission(self) -> None:
        simulated_demand = pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "day_cruise": 145.0,
                    "seven_night_cruise": 90.0,
                    "nine_night_cruise": 45.0,
                }
            ],
            columns=SIMULATION_OUTPUT_COLUMNS,
        )

        result = evaluate_staffing_level(
            simulated_demand,
            staffing_agents=8,
            category_assumptions=self._build_category_assumptions(),
            workforce_assumptions=self._build_workforce_assumptions(),
            strategic_assumptions=self._build_strategic_assumptions(),
        )

        self.assertAlmostEqual(result["expected_spare_capacity_hours"], 26.6666666667)
        self.assertAlmostEqual(result["expected_overflow_workload_hours"], 0.0)
        self.assertAlmostEqual(result["expected_overflow_commission"], 0.0)
        self.assertAlmostEqual(result["regular_labor_cost"], 7040.0)
        self.assertAlmostEqual(result["expected_total_weekly_operating_cost"], 7040.0)


if __name__ == "__main__":
    unittest.main()
