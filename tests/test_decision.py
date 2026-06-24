"""Decision tests for named plans, recommendation ranking, and narrative output."""

from __future__ import annotations

import unittest

import pandas as pd

from src.constants import CONFIDENCE_TARGET_FIELDS, NAMED_PLAN_COLUMNS, STAFFING_EVALUATION_COLUMNS
from src.decision.narrative import (
    build_manager_comparison_narrative,
    build_recommendation_text,
    build_recommendation_warnings,
)
from src.decision.optimizer import select_financial_recommendation
from src.decision.plans import build_candidate_staffing_list, build_named_plan_table, select_named_plans


class DecisionTests(unittest.TestCase):
    def _build_confidence_targets(self) -> dict[str, float]:
        return {
            "lean": 0.5,
            "balanced": 0.85,
            "conservative": 0.95,
        }

    def test_named_plans_follow_percentiles_under_feasible_staffing(self) -> None:
        selected = select_named_plans(
            [8, 8, 8, 9, 9, 10, 12, 12],
            self._build_confidence_targets(),
        )

        self.assertEqual(tuple(selected.keys()), CONFIDENCE_TARGET_FIELDS)
        self.assertEqual(selected, {"lean": 9, "balanced": 12, "conservative": 12})

        table = build_named_plan_table(selected, self._build_confidence_targets())
        self.assertEqual(tuple(table.columns), NAMED_PLAN_COLUMNS)
        self.assertEqual(table["plan_name"].tolist(), ["Lean", "Balanced", "Conservative"])

    def test_candidate_list_spans_full_feasible_range(self) -> None:
        result = build_candidate_staffing_list(
            8,
            12,
        )

        self.assertEqual(result, [8, 9, 10, 11, 12])

    def test_financial_recommendation_uses_lowest_cost_eligible_plan(self) -> None:
        staffing_evaluations = pd.DataFrame(
            [
                {
                    "staffing_agents": 10,
                    "capacity_confidence": 0.84,
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
            minimum_inhouse_coverage_target=0.85,
            selection_tolerance=0.01,
        )

        self.assertEqual(result["recommended_staffing_agents"], 11)
        self.assertTrue(result["coverage_target_met"])
        self.assertEqual(
            result["selected_minimum_inhouse_coverage_target"],
            0.85,
        )
        self.assertEqual(result["objective_column"], "expected_total_weekly_operating_cost")

    def test_financial_recommendation_one_cent_tie_uses_coverage_then_overflow_then_staffing(self) -> None:
        staffing_evaluations = pd.DataFrame(
            [
                {
                    "staffing_agents": 10,
                    "capacity_confidence": 0.88,
                    "probability_overflow_required": 0.12,
                    "expected_spare_capacity_hours": 5.0,
                    "expected_overflow_workload_hours": 2.0,
                    "expected_overflow_day_cruise": 1.0,
                    "expected_overflow_seven_night_cruise": 1.0,
                    "expected_overflow_nine_night_cruise": 1.0,
                    "regular_labor_cost": 9000.0,
                    "expected_overflow_commission": 1000.0,
                    "expected_total_weekly_operating_cost": 10000.00,
                    "expected_inhouse_booking_value": 100000.0,
                    "expected_overflow_booking_value": 8000.0,
                    "expected_commission_avoided": 12000.0,
                },
                {
                    "staffing_agents": 11,
                    "capacity_confidence": 0.91,
                    "probability_overflow_required": 0.09,
                    "expected_spare_capacity_hours": 6.0,
                    "expected_overflow_workload_hours": 1.5,
                    "expected_overflow_day_cruise": 0.5,
                    "expected_overflow_seven_night_cruise": 0.5,
                    "expected_overflow_nine_night_cruise": 0.5,
                    "regular_labor_cost": 9100.0,
                    "expected_overflow_commission": 900.0,
                    "expected_total_weekly_operating_cost": 10000.01,
                    "expected_inhouse_booking_value": 101000.0,
                    "expected_overflow_booking_value": 7000.0,
                    "expected_commission_avoided": 12100.0,
                },
                {
                    "staffing_agents": 12,
                    "capacity_confidence": 0.91,
                    "probability_overflow_required": 0.09,
                    "expected_spare_capacity_hours": 6.0,
                    "expected_overflow_workload_hours": 1.5,
                    "expected_overflow_day_cruise": 0.5,
                    "expected_overflow_seven_night_cruise": 0.5,
                    "expected_overflow_nine_night_cruise": 0.5,
                    "regular_labor_cost": 9200.0,
                    "expected_overflow_commission": 800.0,
                    "expected_total_weekly_operating_cost": 10000.00,
                    "expected_inhouse_booking_value": 102000.0,
                    "expected_overflow_booking_value": 7000.0,
                    "expected_commission_avoided": 12200.0,
                },
            ],
            columns=STAFFING_EVALUATION_COLUMNS,
        )

        result = select_financial_recommendation(
            staffing_evaluations,
            minimum_inhouse_coverage_target=0.85,
            selection_tolerance=0.01,
        )

        self.assertEqual(result["recommended_staffing_agents"], 11)

    def test_financial_recommendation_tie_tolerance_below_and_above_one_cent(self) -> None:
        base_rows = [
            {
                "staffing_agents": 10,
                "capacity_confidence": 0.90,
                "probability_overflow_required": 0.10,
                "expected_spare_capacity_hours": 5.0,
                "expected_overflow_workload_hours": 2.0,
                "expected_overflow_day_cruise": 0.0,
                "expected_overflow_seven_night_cruise": 0.0,
                "expected_overflow_nine_night_cruise": 0.0,
                "regular_labor_cost": 9000.0,
                "expected_overflow_commission": 1000.0,
                "expected_total_weekly_operating_cost": 10000.00,
                "expected_inhouse_booking_value": 100000.0,
                "expected_overflow_booking_value": 8000.0,
                "expected_commission_avoided": 12000.0,
            },
            {
                "staffing_agents": 11,
                "capacity_confidence": 0.95,
                "probability_overflow_required": 0.05,
                "expected_spare_capacity_hours": 6.0,
                "expected_overflow_workload_hours": 1.0,
                "expected_overflow_day_cruise": 0.0,
                "expected_overflow_seven_night_cruise": 0.0,
                "expected_overflow_nine_night_cruise": 0.0,
                "regular_labor_cost": 9100.0,
                "expected_overflow_commission": 900.0,
                "expected_total_weekly_operating_cost": 10000.00,
                "expected_inhouse_booking_value": 101000.0,
                "expected_overflow_booking_value": 7000.0,
                "expected_commission_avoided": 12100.0,
            },
        ]

        below = pd.DataFrame(
            [
                base_rows[0],
                {**base_rows[1], "expected_total_weekly_operating_cost": 10000.009},
            ],
            columns=STAFFING_EVALUATION_COLUMNS,
        )
        exact = pd.DataFrame(
            [
                base_rows[0],
                {**base_rows[1], "expected_total_weekly_operating_cost": 10000.01},
            ],
            columns=STAFFING_EVALUATION_COLUMNS,
        )
        above = pd.DataFrame(
            [
                base_rows[0],
                {**base_rows[1], "expected_total_weekly_operating_cost": 10000.011},
            ],
            columns=STAFFING_EVALUATION_COLUMNS,
        )

        self.assertEqual(
            select_financial_recommendation(
                below,
                minimum_inhouse_coverage_target=0.85,
                selection_tolerance=0.01,
            )["recommended_staffing_agents"],
            11,
        )
        self.assertEqual(
            select_financial_recommendation(
                exact,
                minimum_inhouse_coverage_target=0.85,
                selection_tolerance=0.01,
            )["recommended_staffing_agents"],
            11,
        )
        self.assertEqual(
            select_financial_recommendation(
                above,
                minimum_inhouse_coverage_target=0.85,
                selection_tolerance=0.01,
            )["recommended_staffing_agents"],
            10,
        )

    def test_financial_recommendation_fallback_uses_maximum_staffing_when_no_level_meets_target(self) -> None:
        staffing_evaluations = pd.DataFrame(
            [
                {
                    "staffing_agents": 8,
                    "capacity_confidence": 0.40,
                    "probability_overflow_required": 0.60,
                    "expected_spare_capacity_hours": 1.0,
                    "expected_overflow_workload_hours": 10.0,
                    "expected_overflow_day_cruise": 5.0,
                    "expected_overflow_seven_night_cruise": 3.0,
                    "expected_overflow_nine_night_cruise": 2.0,
                    "regular_labor_cost": 7000.0,
                    "expected_overflow_commission": 2000.0,
                    "expected_total_weekly_operating_cost": 9000.0,
                    "expected_inhouse_booking_value": 90000.0,
                    "expected_overflow_booking_value": 16000.0,
                    "expected_commission_avoided": 11000.0,
                },
                {
                    "staffing_agents": 12,
                    "capacity_confidence": 0.88,
                    "probability_overflow_required": 0.12,
                    "expected_spare_capacity_hours": 8.0,
                    "expected_overflow_workload_hours": 1.0,
                    "expected_overflow_day_cruise": 0.5,
                    "expected_overflow_seven_night_cruise": 0.3,
                    "expected_overflow_nine_night_cruise": 0.2,
                    "regular_labor_cost": 11000.0,
                    "expected_overflow_commission": 400.0,
                    "expected_total_weekly_operating_cost": 11400.0,
                    "expected_inhouse_booking_value": 104000.0,
                    "expected_overflow_booking_value": 4000.0,
                    "expected_commission_avoided": 13000.0,
                },
            ],
            columns=STAFFING_EVALUATION_COLUMNS,
        )

        result = select_financial_recommendation(
            staffing_evaluations,
            minimum_inhouse_coverage_target=0.95,
            selection_tolerance=0.01,
        )

        self.assertEqual(result["recommended_staffing_agents"], 12)
        self.assertFalse(result["coverage_target_met"])
        self.assertIsNotNone(result["warning"])

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

    def _build_manager_narrative_payload(
        self,
        *,
        staffing_difference: int = -2,
        labor_cost_difference: float = -1760.0,
        overflow_commission_difference: float = 300.0,
        total_cost_difference: float = 120.0,
        manager_feasibility_status: str = "within_operating_range",
        coverage_target_met: bool = True,
        warning: str | None = None,
        manager_warnings: list[str] | None = None,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
        recommended_staffing = 12
        manager_staffing = recommended_staffing + staffing_difference
        recommendation_policy = {
            "minimum_inhouse_coverage_target": 0.85,
            "selection_tolerance": 0.01,
        }
        recommended_plan = {
            "staffing_agents": recommended_staffing,
            "capacity_confidence": 0.88,
            "probability_overflow_required": 0.12,
            "expected_spare_capacity_hours": 8.0,
            "expected_overflow_workload_hours": 1.0,
            "regular_labor_cost": 10560.0,
            "expected_overflow_commission": 691.36,
            "expected_total_weekly_operating_cost": 11251.36,
            "coverage_target_met": coverage_target_met,
            "warning": warning,
        }
        manager_proposal = {
            "staffing_agents": manager_staffing,
            "feasibility_status": manager_feasibility_status,
            "capacity_confidence": 0.84,
            "probability_overflow_required": 0.16,
            "expected_spare_capacity_hours": 4.0,
            "expected_overflow_workload_hours": 3.0,
            "regular_labor_cost": recommended_plan["regular_labor_cost"] + labor_cost_difference,
            "expected_overflow_commission": (
                recommended_plan["expected_overflow_commission"]
                + overflow_commission_difference
            ),
            "expected_total_weekly_operating_cost": (
                recommended_plan["expected_total_weekly_operating_cost"]
                + total_cost_difference
            ),
            "warnings": list(manager_warnings or []),
        }
        comparison = {
            "staffing_difference": staffing_difference,
            "coverage_difference": (
                manager_proposal["capacity_confidence"]
                - recommended_plan["capacity_confidence"]
            ),
            "overflow_probability_difference": (
                manager_proposal["probability_overflow_required"]
                - recommended_plan["probability_overflow_required"]
            ),
            "labor_cost_difference": labor_cost_difference,
            "overflow_commission_difference": overflow_commission_difference,
            "total_cost_difference": total_cost_difference,
            "spare_capacity_difference": (
                manager_proposal["expected_spare_capacity_hours"]
                - recommended_plan["expected_spare_capacity_hours"]
            ),
            "overflow_workload_difference": (
                manager_proposal["expected_overflow_workload_hours"]
                - recommended_plan["expected_overflow_workload_hours"]
            ),
            "manager_feasibility_status": manager_feasibility_status,
        }
        return recommendation_policy, recommended_plan, manager_proposal, comparison

    def test_manager_comparison_narrative_handles_matching_plans(self) -> None:
        payload = self._build_manager_narrative_payload(
            staffing_difference=0,
            labor_cost_difference=0.0,
            overflow_commission_difference=0.0,
            total_cost_difference=0.0,
        )

        narrative = build_manager_comparison_narrative(*payload)

        self.assertIn("matches the model recommendation", narrative["text"])
        self.assertIn("cost-neutral", narrative["text"])

    def test_manager_comparison_narrative_handles_fewer_agents_and_tradeoff(self) -> None:
        payload = self._build_manager_narrative_payload(
            staffing_difference=-2,
            labor_cost_difference=-1760.0,
            overflow_commission_difference=300.0,
            total_cost_difference=120.0,
        )

        narrative = build_manager_comparison_narrative(*payload)

        self.assertIn("uses 2 fewer agents", narrative["text"])
        self.assertIn("lowers regular labor cost but increases expected overflow commission", narrative["text"])
        self.assertIn("increases expected total weekly operating cost", narrative["text"])

    def test_manager_comparison_narrative_handles_more_agents_and_total_cost_reduction(self) -> None:
        payload = self._build_manager_narrative_payload(
            staffing_difference=2,
            labor_cost_difference=1760.0,
            overflow_commission_difference=-300.0,
            total_cost_difference=-120.0,
        )

        narrative = build_manager_comparison_narrative(*payload)

        self.assertIn("uses 2 more agents", narrative["text"])
        self.assertIn("raises regular labor cost while reducing expected overflow commission", narrative["text"])
        self.assertIn("reduces expected total weekly operating cost", narrative["text"])

    def test_manager_comparison_narrative_handles_boundary_warnings(self) -> None:
        below_payload = self._build_manager_narrative_payload(
            manager_feasibility_status="below_operating_floor",
            manager_warnings=["below-floor warning"],
        )
        above_payload = self._build_manager_narrative_payload(
            manager_feasibility_status="above_inhouse_capacity",
            manager_warnings=["above-cap warning"],
        )

        below = build_manager_comparison_narrative(*below_payload)
        above = build_manager_comparison_narrative(*above_payload)

        self.assertIn("below the operating floor", below["text"])
        self.assertIn("below-floor warning", below["warnings"])
        self.assertIn("above the in-house capacity cap", above["text"])
        self.assertIn("above-cap warning", above["warnings"])

    def test_manager_comparison_narrative_handles_unachievable_target_warning(self) -> None:
        payload = self._build_manager_narrative_payload(
            coverage_target_met=False,
            warning="target not achievable",
        )

        narrative = build_manager_comparison_narrative(*payload)

        self.assertIn("not achievable", narrative["text"])
        self.assertIn("target not achievable", narrative["warnings"])


if __name__ == "__main__":
    unittest.main()
