"""Unit tests for finance evaluation helpers."""

from __future__ import annotations

import unittest

import pandas as pd

from src.constants import CATEGORY_ASSUMPTIONS_COLUMNS
from src.constants import RESERVATION_CATEGORIES
from src.constants import STAFFING_EVALUATION_COLUMNS
from src.finance.staffing_evaluator import evaluate_staffing_level


class StaffingEvaluationTests(unittest.TestCase):
    def _build_category_assumptions(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "category": "simple",
                    "handling_time_minutes": 60.0,
                    "average_revenue": 200.0,
                    "contribution_per_reservation": 80.0,
                },
                {
                    "category": "standard",
                    "handling_time_minutes": 30.0,
                    "average_revenue": 150.0,
                    "contribution_per_reservation": 60.0,
                },
                {
                    "category": "complex_group",
                    "handling_time_minutes": 45.0,
                    "average_revenue": 300.0,
                    "contribution_per_reservation": 120.0,
                },
                {
                    "category": "change_cancellation",
                    "handling_time_minutes": 15.0,
                    "average_revenue": 90.0,
                    "contribution_per_reservation": 20.0,
                },
            ],
            columns=CATEGORY_ASSUMPTIONS_COLUMNS,
        )

    def _build_simulated_demand(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "simple": 2.0,
                    "standard": 0.0,
                    "complex_group": 0.0,
                    "change_cancellation": 0.0,
                },
                {
                    "simulation_id": 2,
                    "simple": 6.0,
                    "standard": 0.0,
                    "complex_group": 0.0,
                    "change_cancellation": 0.0,
                },
            ],
            columns=("simulation_id", *RESERVATION_CATEGORIES),
        )

    def _build_workforce_assumptions(self) -> dict[str, float | int]:
        return {
            "paid_hours_per_agent": 4.0,
            "productive_processing_pct": 1.0,
            "regular_hourly_wage": 25.0,
            "overtime_multiplier": 1.5,
            "abandonment_rate": 0.5,
            "planned_staffing_agents": 1,
        }

    def test_evaluate_staffing_level_returns_the_full_contract_schema(self) -> None:
        result = evaluate_staffing_level(
            self._build_simulated_demand(),
            staffing_agents=1,
            category_assumptions=self._build_category_assumptions(),
            workforce_assumptions=self._build_workforce_assumptions(),
        )

        self.assertEqual(tuple(result), STAFFING_EVALUATION_COLUMNS)
        self.assertEqual(result["staffing_agents"], 1)

    def test_zero_abandonment_and_no_overtime_produce_zero_loss_metrics(self) -> None:
        result = evaluate_staffing_level(
            self._build_simulated_demand(),
            staffing_agents=2,
            category_assumptions=self._build_category_assumptions(),
            workforce_assumptions=self._build_workforce_assumptions(),
        )

        self.assertAlmostEqual(result["capacity_confidence"], 1.0)
        self.assertAlmostEqual(result["probability_overtime_required"], 0.0)
        self.assertAlmostEqual(result["expected_overtime_hours"], 0.0)
        self.assertAlmostEqual(result["expected_abandoned_total"], 0.0)
        self.assertAlmostEqual(result["expected_abandoned_simple"], 0.0)
        self.assertAlmostEqual(result["expected_lost_revenue"], 0.0)
        self.assertAlmostEqual(result["expected_lost_contribution"], 0.0)
        self.assertAlmostEqual(result["expected_overtime_cost"], 0.0)
        self.assertAlmostEqual(result["expected_total_economic_cost"], result["regular_labor_cost"])
        self.assertAlmostEqual(result["expected_retained_revenue"], 800.0)
        self.assertAlmostEqual(result["expected_retained_contribution"], 320.0)

    def test_cost_composition_uses_lost_contribution_not_lost_revenue(self) -> None:
        result = evaluate_staffing_level(
            self._build_simulated_demand(),
            staffing_agents=1,
            category_assumptions=self._build_category_assumptions(),
            workforce_assumptions=self._build_workforce_assumptions(),
        )

        self.assertAlmostEqual(result["regular_labor_cost"], 100.0)
        self.assertAlmostEqual(result["expected_overtime_cost"], 18.75)
        self.assertAlmostEqual(result["expected_lost_revenue"], 100.0)
        self.assertAlmostEqual(result["expected_lost_contribution"], 40.0)
        self.assertAlmostEqual(
            result["expected_total_economic_cost"],
            result["regular_labor_cost"]
            + result["expected_overtime_cost"]
            + result["expected_lost_contribution"],
        )
        self.assertNotAlmostEqual(
            result["expected_total_economic_cost"],
            result["regular_labor_cost"]
            + result["expected_overtime_cost"]
            + result["expected_lost_revenue"],
        )

    def test_expected_net_contribution_is_retained_contribution_minus_total_cost(self) -> None:
        result = evaluate_staffing_level(
            self._build_simulated_demand(),
            staffing_agents=1,
            category_assumptions=self._build_category_assumptions(),
            workforce_assumptions=self._build_workforce_assumptions(),
        )

        self.assertAlmostEqual(
            result["expected_net_contribution"],
            result["expected_retained_contribution"] - result["expected_total_economic_cost"],
        )
        self.assertAlmostEqual(result["expected_net_contribution"], 121.25)


if __name__ == "__main__":
    unittest.main()
