"""Decision tests for named plans, recommendation ranking, and narrative output."""

from __future__ import annotations

import unittest

import pandas as pd

from src.constants import CONFIDENCE_TARGET_FIELDS, NAMED_PLAN_COLUMNS, STAFFING_EVALUATION_COLUMNS
from src.decision.narrative import build_recommendation_text, build_recommendation_warnings
from src.decision.optimizer import select_financial_recommendation
from src.decision.plans import build_candidate_staffing_list, build_named_plan_table, select_named_plans


class DecisionTests(unittest.TestCase):
    def _build_required_agents(self) -> list[int]:
        return [8, 8, 8, 9, 9, 10, 12, 12]

    def _build_confidence_targets(self) -> dict[str, float]:
        return {
            "lean": 0.5,
            "balanced": 0.85,
            "conservative": 0.95,
        }

    def test_named_plans_follow_percentiles_under_feasible_staffing(self) -> None:
        selected = select_named_plans(
            self._build_required_agents(),
            self._build_confidence_targets(),
        )

        self.assertEqual(tuple(selected.keys()), CONFIDENCE_TARGET_FIELDS)
        self.assertEqual(selected, {"lean": 9, "balanced": 12, "conservative": 12})

        table = build_named_plan_table(selected, self._build_confidence_targets())
        self.assertEqual(tuple(table.columns), NAMED_PLAN_COLUMNS)
        self.assertEqual(table["plan_name"].tolist(), ["Lean", "Balanced", "Conservative"])

    def test_candidate_list_includes_previous_week_and_manager_plan(self) -> None:
        result = build_candidate_staffing_list(
            self._build_required_agents(),
            previous_week_staffing=9,
            manager_planned_staffing=10,
            candidate_low_percentile=0.5,
            candidate_high_percentile=0.95,
        )

        self.assertEqual(result, [9, 10, 11, 12])

    def test_financial_recommendation_uses_weekly_operating_cost_then_capacity(self) -> None:
        staffing_evaluations = pd.DataFrame(
            [
                {
                    "staffing_agents": 10,
                    "capacity_confidence": 0.80,
                    "probability_overflow_required": 0.40,
                    "expected_spare_capacity_hours": 6.0,
                    "expected_overflow_workload_hours": 4.0,
                    "expected_overflow_day_cruise": 10.0,
                    "expected_overflow_seven_night_cruise": 5.0,
                    "expected_overflow_nine_night_cruise": 2.0,
                    "regular_labor_cost": 8800.0,
                    "expected_overflow_commission": 3000.0,
                    "expected_total_weekly_operating_cost": 11800.0,
                    "expected_inhouse_booking_value": 100000.0,
                    "expected_overflow_booking_value": 24000.0,
                    "expected_commission_avoided": 12500.0,
                },
                {
                    "staffing_agents": 11,
                    "capacity_confidence": 0.90,
                    "probability_overflow_required": 0.20,
                    "expected_spare_capacity_hours": 4.0,
                    "expected_overflow_workload_hours": 1.0,
                    "expected_overflow_day_cruise": 2.0,
                    "expected_overflow_seven_night_cruise": 1.0,
                    "expected_overflow_nine_night_cruise": 0.5,
                    "regular_labor_cost": 9680.0,
                    "expected_overflow_commission": 2120.0,
                    "expected_total_weekly_operating_cost": 11800.0,
                    "expected_inhouse_booking_value": 110000.0,
                    "expected_overflow_booking_value": 16960.0,
                    "expected_commission_avoided": 13750.0,
                },
            ],
            columns=STAFFING_EVALUATION_COLUMNS,
        )

        result = select_financial_recommendation(
            staffing_evaluations,
            selection_tolerance=1e-9,
        )

        self.assertEqual(result["recommended_staffing_agents"], 11)
        self.assertEqual(
            tuple(result["candidate_ranking"].columns),
            ("financial_rank", *STAFFING_EVALUATION_COLUMNS),
        )
        self.assertEqual(result["objective_column"], "expected_total_weekly_operating_cost")

    def test_narrative_mentions_spare_capacity_or_overflow(self) -> None:
        recommendation = {
            "recommended_staffing_record": {
                "staffing_agents": 8,
                "capacity_confidence": 0.90,
                "expected_spare_capacity_hours": 26.6667,
                "expected_overflow_workload_hours": 0.0,
                "expected_total_weekly_operating_cost": 7040.0,
            }
        }
        comparison_table = pd.DataFrame(
            [
                {
                    "plan_name": "Previous Week",
                    "staffing_agents": 9,
                    "capacity_confidence": 0.93,
                    "expected_spare_capacity_hours": 39.1667,
                    "expected_overflow_workload_hours": 0.0,
                    "expected_total_weekly_operating_cost": 7920.0,
                },
                {
                    "plan_name": "Manager Plan",
                    "staffing_agents": 10,
                    "capacity_confidence": 0.95,
                    "expected_spare_capacity_hours": 51.6667,
                    "expected_overflow_workload_hours": 0.0,
                    "expected_total_weekly_operating_cost": 8800.0,
                },
            ]
        )

        text = build_recommendation_text(recommendation, comparison_table)
        warnings = build_recommendation_warnings(recommendation, comparison_table)

        self.assertIn("Schedule 8 reservation agents", text)
        self.assertIn("90.0% capacity confidence", text)
        self.assertIn("Expected spare capacity is 26.7 workload hours", text)
        self.assertIn("$7040.00", text)
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
