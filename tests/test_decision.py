"""Unit tests for decision-plan selection helpers."""

from __future__ import annotations

import unittest

import pandas as pd

from src.constants import CATEGORY_ASSUMPTIONS_COLUMNS
from src.constants import CONFIDENCE_TARGET_FIELDS, NAMED_PLAN_COLUMNS
from src.constants import SIMULATION_OUTPUT_COLUMNS
from src.constants import STAFFING_EVALUATION_COLUMNS
from src.decision.plans import (
    build_candidate_staffing_list,
    build_named_plan_table,
    select_named_plans,
)
from src.decision.optimizer import select_financial_recommendation
from src.decision.narrative import build_recommendation_text
from src.decision.narrative import build_recommendation_warnings
from src.finance.staffing_evaluator import evaluate_staffing_level
from src.validation import FieldValidationError


class DecisionPlanTests(unittest.TestCase):
    def _build_required_agents(self) -> list[int]:
        return [5, 6, 7, 7, 8, 9, 9, 10]

    def _build_confidence_targets(self) -> dict[str, float]:
        return {
            "lean": 0.5,
            "balanced": 0.85,
            "conservative": 0.95,
        }

    def test_select_named_plans_maps_percentiles_to_whole_agent_staffing(self) -> None:
        result = select_named_plans(
            self._build_required_agents(),
            self._build_confidence_targets(),
        )

        self.assertEqual(tuple(result.keys()), CONFIDENCE_TARGET_FIELDS)
        self.assertEqual(
            result,
            {
                "lean": 7,
                "balanced": 9,
                "conservative": 10,
            },
        )

    def test_build_named_plan_table_uses_canonical_schema_and_plan_names(self) -> None:
        named_plans = select_named_plans(
            self._build_required_agents(),
            self._build_confidence_targets(),
        )

        result = build_named_plan_table(
            named_plans,
            self._build_confidence_targets(),
            staffing_evaluation_references={7: "eval_7", 9: "eval_9", 10: "eval_10"},
        )

        self.assertEqual(tuple(result.columns), NAMED_PLAN_COLUMNS)
        self.assertEqual(result["plan_name"].tolist(), ["Lean", "Balanced", "Conservative"])
        self.assertEqual(result["confidence_target"].tolist(), [0.5, 0.85, 0.95])
        self.assertEqual(result["staffing_agents"].tolist(), [7, 9, 10])
        self.assertEqual(
            result["staffing_evaluation_reference"].tolist(),
            ["eval_7", "eval_9", "eval_10"],
        )

    def test_duplicate_staffing_is_preserved_in_named_plans_but_deduplicated_in_candidates(self) -> None:
        required_agents = [7, 7, 7, 8]
        confidence_targets = self._build_confidence_targets()

        named_plans = select_named_plans(required_agents, confidence_targets)
        self.assertEqual(
            named_plans,
            {
                "lean": 7,
                "balanced": 8,
                "conservative": 8,
            },
        )

        candidate_list = build_candidate_staffing_list(
            required_agents,
            candidate_low_percentile=0.5,
            candidate_high_percentile=0.95,
        )
        self.assertEqual(candidate_list, [7, 8])

        named_plan_table = build_named_plan_table(named_plans, confidence_targets)
        self.assertEqual(named_plan_table["staffing_agents"].tolist(), [7, 8, 8])
        self.assertEqual(
            named_plan_table["plan_name"].tolist(),
            ["Lean", "Balanced", "Conservative"],
        )

    def test_candidate_list_includes_previous_week_and_manager_plan_outside_default_range(self) -> None:
        result = build_candidate_staffing_list(
            self._build_required_agents(),
            previous_week_staffing=4,
            manager_planned_staffing=12,
            candidate_low_percentile=0.5,
            candidate_high_percentile=0.85,
        )

        self.assertEqual(result, [4, 7, 8, 9, 12])

    def test_rejects_invalid_confidence_targets_and_percentile_bounds(self) -> None:
        with self.assertRaisesRegex(FieldValidationError, "canonical order"):
            select_named_plans(
                self._build_required_agents(),
                {
                    "balanced": 0.85,
                    "lean": 0.5,
                    "conservative": 0.95,
                },
            )

        with self.assertRaisesRegex(FieldValidationError, "less than or equal"):
            build_candidate_staffing_list(
                self._build_required_agents(),
                candidate_low_percentile=0.95,
                candidate_high_percentile=0.5,
            )

    def _build_staffing_evaluation_table(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "staffing_agents": 10,
                    "capacity_confidence": 0.80,
                    "probability_overtime_required": 0.12,
                    "expected_overtime_hours": 3.0,
                    "expected_abandoned_total": 9.0,
                    "expected_abandoned_simple": 3.0,
                    "expected_abandoned_standard": 2.0,
                    "expected_abandoned_complex_group": 2.0,
                    "expected_abandoned_change_cancellation": 2.0,
                    "regular_labor_cost": 320.0,
                    "expected_overtime_cost": 18.0,
                    "expected_lost_revenue": 45.0,
                    "expected_lost_contribution": 180.0,
                    "expected_total_economic_cost": 518.0,
                    "expected_retained_revenue": 900.0,
                    "expected_retained_contribution": 520.0,
                    "expected_net_contribution": 2.0,
                    "expected_unused_regular_hours": 5.0,
                },
                {
                    "staffing_agents": 9,
                    "capacity_confidence": 0.90,
                    "probability_overtime_required": 0.10,
                    "expected_overtime_hours": 2.0,
                    "expected_abandoned_total": 7.0,
                    "expected_abandoned_simple": 2.0,
                    "expected_abandoned_standard": 2.0,
                    "expected_abandoned_complex_group": 2.0,
                    "expected_abandoned_change_cancellation": 1.0,
                    "regular_labor_cost": 300.0,
                    "expected_overtime_cost": 15.0,
                    "expected_lost_revenue": 250.0,
                    "expected_lost_contribution": 20.0,
                    "expected_total_economic_cost": 400.0,
                    "expected_retained_revenue": 950.0,
                    "expected_retained_contribution": 540.0,
                    "expected_net_contribution": 140.0,
                    "expected_unused_regular_hours": 6.0,
                },
            ],
            columns=STAFFING_EVALUATION_COLUMNS,
        )

    def _build_financial_scenario_rows(
        self,
        *,
        contributions: tuple[float, float, float, float],
        overtime_multiplier: float,
        abandonment_rate: float,
        staffing_agents: tuple[int, int] = (1, 2),
    ) -> pd.DataFrame:
        simulated_demand = pd.DataFrame(
            [
                {
                    "simulation_id": 1,
                    "simple": 8.0,
                    "standard": 0.0,
                    "complex_group": 0.0,
                    "change_cancellation": 0.0,
                }
            ],
            columns=SIMULATION_OUTPUT_COLUMNS,
        )
        category_assumptions = pd.DataFrame(
            [
                {
                    "category": "simple",
                    "handling_time_minutes": 60.0,
                    "average_revenue": 200.0,
                    "contribution_per_reservation": contributions[0],
                },
                {
                    "category": "standard",
                    "handling_time_minutes": 30.0,
                    "average_revenue": 150.0,
                    "contribution_per_reservation": contributions[1],
                },
                {
                    "category": "complex_group",
                    "handling_time_minutes": 45.0,
                    "average_revenue": 300.0,
                    "contribution_per_reservation": contributions[2],
                },
                {
                    "category": "change_cancellation",
                    "handling_time_minutes": 15.0,
                    "average_revenue": 90.0,
                    "contribution_per_reservation": contributions[3],
                },
            ],
            columns=CATEGORY_ASSUMPTIONS_COLUMNS,
        )
        workforce_assumptions = {
            "paid_hours_per_agent": 4.0,
            "productive_processing_pct": 1.0,
            "regular_hourly_wage": 25.0,
            "overtime_multiplier": overtime_multiplier,
            "abandonment_rate": abandonment_rate,
            "planned_staffing_agents": 1,
        }

        rows = [
            evaluate_staffing_level(
                simulated_demand,
                staffing,
                category_assumptions,
                workforce_assumptions,
            )
            for staffing in staffing_agents
        ]
        return pd.DataFrame(rows, columns=STAFFING_EVALUATION_COLUMNS)

    def test_select_financial_recommendation_uses_total_cost_not_gross_lost_revenue(self) -> None:
        result = select_financial_recommendation(self._build_staffing_evaluation_table())

        self.assertEqual(result["recommended_staffing_agents"], 9)
        self.assertEqual(result["recommended_staffing_record"]["staffing_agents"], 9)
        self.assertEqual(
            tuple(result["candidate_ranking"].columns),
            ("financial_rank", *STAFFING_EVALUATION_COLUMNS),
        )
        self.assertEqual(
            result["candidate_ranking"]["staffing_agents"].tolist(),
            [9, 10],
        )
        self.assertEqual(
            result["candidate_ranking"]["financial_rank"].tolist(),
            [1, 2],
        )

        ranked_records = result["candidate_ranking"][list(STAFFING_EVALUATION_COLUMNS)].to_dict(
            orient="records"
        )
        self.assertIn(result["recommended_staffing_record"], ranked_records)

    def test_higher_contribution_can_make_additional_staffing_financially_preferable(self) -> None:
        low_contribution_rows = self._build_financial_scenario_rows(
            contributions=(10.0, 6.0, 12.0, 4.0),
            overtime_multiplier=1.5,
            abandonment_rate=0.5,
        )
        high_contribution_rows = self._build_financial_scenario_rows(
            contributions=(200.0, 120.0, 240.0, 80.0),
            overtime_multiplier=1.5,
            abandonment_rate=0.5,
        )

        low_contribution_result = select_financial_recommendation(low_contribution_rows)
        high_contribution_result = select_financial_recommendation(high_contribution_rows)

        self.assertEqual(low_contribution_result["recommended_staffing_agents"], 1)
        self.assertEqual(high_contribution_result["recommended_staffing_agents"], 2)
        self.assertLess(
            low_contribution_result["candidate_ranking"].iloc[0]["expected_total_economic_cost"],
            low_contribution_result["candidate_ranking"].iloc[1]["expected_total_economic_cost"],
        )
        self.assertLess(
            high_contribution_result["candidate_ranking"].iloc[0]["expected_total_economic_cost"],
            high_contribution_result["candidate_ranking"].iloc[1]["expected_total_economic_cost"],
        )

    def test_higher_overtime_cost_can_make_additional_regular_staffing_preferable(self) -> None:
        low_overtime_rows = self._build_financial_scenario_rows(
            contributions=(10.0, 6.0, 12.0, 4.0),
            overtime_multiplier=1.1,
            abandonment_rate=0.5,
        )
        high_overtime_rows = self._build_financial_scenario_rows(
            contributions=(10.0, 6.0, 12.0, 4.0),
            overtime_multiplier=2.0,
            abandonment_rate=0.5,
        )

        low_overtime_result = select_financial_recommendation(low_overtime_rows)
        high_overtime_result = select_financial_recommendation(high_overtime_rows)

        self.assertEqual(low_overtime_result["recommended_staffing_agents"], 1)
        self.assertEqual(high_overtime_result["recommended_staffing_agents"], 2)
        self.assertLess(
            low_overtime_rows.iloc[0]["expected_overtime_cost"],
            high_overtime_rows.iloc[0]["expected_overtime_cost"],
        )

    def test_higher_abandonment_increases_lost_contribution(self) -> None:
        low_abandonment_rows = self._build_financial_scenario_rows(
            contributions=(10.0, 6.0, 12.0, 4.0),
            overtime_multiplier=1.5,
            abandonment_rate=0.0,
            staffing_agents=(1,),
        )
        high_abandonment_rows = self._build_financial_scenario_rows(
            contributions=(10.0, 6.0, 12.0, 4.0),
            overtime_multiplier=1.5,
            abandonment_rate=0.5,
            staffing_agents=(1,),
        )

        self.assertEqual(low_abandonment_rows.iloc[0]["expected_abandoned_total"], 0.0)
        self.assertEqual(low_abandonment_rows.iloc[0]["expected_lost_contribution"], 0.0)
        self.assertGreater(
            high_abandonment_rows.iloc[0]["expected_abandoned_total"],
            low_abandonment_rows.iloc[0]["expected_abandoned_total"],
        )
        self.assertGreater(
            high_abandonment_rows.iloc[0]["expected_lost_contribution"],
            low_abandonment_rows.iloc[0]["expected_lost_contribution"],
        )

    def test_select_financial_recommendation_breaks_ties_deterministically(self) -> None:
        staffing_evaluations = pd.DataFrame(
            [
                {
                    "staffing_agents": 10,
                    "capacity_confidence": 0.80,
                    "probability_overtime_required": 0.40,
                    "expected_overtime_hours": 4.0,
                    "expected_abandoned_total": 9.0,
                    "expected_abandoned_simple": 4.0,
                    "expected_abandoned_standard": 2.0,
                    "expected_abandoned_complex_group": 2.0,
                    "expected_abandoned_change_cancellation": 1.0,
                    "regular_labor_cost": 320.0,
                    "expected_overtime_cost": 24.0,
                    "expected_lost_revenue": 90.0,
                    "expected_lost_contribution": 36.0,
                    "expected_total_economic_cost": 380.0,
                    "expected_retained_revenue": 900.0,
                    "expected_retained_contribution": 540.0,
                    "expected_net_contribution": 160.0,
                    "expected_unused_regular_hours": 4.0,
                },
                {
                    "staffing_agents": 9,
                    "capacity_confidence": 0.90,
                    "probability_overtime_required": 0.30,
                    "expected_overtime_hours": 3.0,
                    "expected_abandoned_total": 7.0,
                    "expected_abandoned_simple": 3.0,
                    "expected_abandoned_standard": 2.0,
                    "expected_abandoned_complex_group": 1.0,
                    "expected_abandoned_change_cancellation": 1.0,
                    "regular_labor_cost": 300.0,
                    "expected_overtime_cost": 18.0,
                    "expected_lost_revenue": 80.0,
                    "expected_lost_contribution": 32.0,
                    "expected_total_economic_cost": 350.0,
                    "expected_retained_revenue": 940.0,
                    "expected_retained_contribution": 560.0,
                    "expected_net_contribution": 210.0,
                    "expected_unused_regular_hours": 5.0,
                },
                {
                    "staffing_agents": 8,
                    "capacity_confidence": 0.90,
                    "probability_overtime_required": 0.20,
                    "expected_overtime_hours": 2.0,
                    "expected_abandoned_total": 6.0,
                    "expected_abandoned_simple": 2.0,
                    "expected_abandoned_standard": 2.0,
                    "expected_abandoned_complex_group": 1.0,
                    "expected_abandoned_change_cancellation": 1.0,
                    "regular_labor_cost": 280.0,
                    "expected_overtime_cost": 12.0,
                    "expected_lost_revenue": 70.0,
                    "expected_lost_contribution": 28.0,
                    "expected_total_economic_cost": 349.995,
                    "expected_retained_revenue": 960.0,
                    "expected_retained_contribution": 568.0,
                    "expected_net_contribution": 239.0,
                    "expected_unused_regular_hours": 6.0,
                },
                {
                    "staffing_agents": 7,
                    "capacity_confidence": 0.90,
                    "probability_overtime_required": 0.10,
                    "expected_overtime_hours": 1.0,
                    "expected_abandoned_total": 6.0,
                    "expected_abandoned_simple": 2.0,
                    "expected_abandoned_standard": 2.0,
                    "expected_abandoned_complex_group": 1.0,
                    "expected_abandoned_change_cancellation": 1.0,
                    "regular_labor_cost": 260.0,
                    "expected_overtime_cost": 6.0,
                    "expected_lost_revenue": 60.0,
                    "expected_lost_contribution": 24.0,
                    "expected_total_economic_cost": 349.998,
                    "expected_retained_revenue": 970.0,
                    "expected_retained_contribution": 572.0,
                    "expected_net_contribution": 246.0,
                    "expected_unused_regular_hours": 7.0,
                },
            ],
            columns=STAFFING_EVALUATION_COLUMNS,
        )

        result = select_financial_recommendation(
            staffing_evaluations,
            selection_tolerance=0.01,
        )

        self.assertEqual(result["recommended_staffing_agents"], 7)
        self.assertEqual(
            result["candidate_ranking"]["staffing_agents"].tolist(),
            [7, 8, 9, 10],
        )

    def test_select_financial_recommendation_rejects_malformed_input(self) -> None:
        malformed = self._build_staffing_evaluation_table()[list(reversed(STAFFING_EVALUATION_COLUMNS))]

        with self.assertRaisesRegex(FieldValidationError, "match the shared contract exactly"):
            select_financial_recommendation(malformed)

    def _build_recommendation_context(self) -> tuple[dict[str, object], pd.DataFrame]:
        recommendation = {
            "recommended_staffing_record": {
                "staffing_agents": 9,
                "capacity_confidence": 0.853,
                "expected_overtime_hours": 3.5,
                "expected_abandoned_total": 1.2,
                "expected_total_economic_cost": 412.35,
            }
        }
        comparison_table = pd.DataFrame(
            [
                {
                    "plan_name": "Previous Week",
                    "staffing_agents": 7,
                    "capacity_confidence": 0.81,
                    "expected_overtime_hours": 4.0,
                    "expected_abandoned_total": 2.0,
                    "expected_total_economic_cost": 430.00,
                },
                {
                    "plan_name": "Manager Plan",
                    "staffing_agents": 8,
                    "capacity_confidence": 0.84,
                    "expected_overtime_hours": 3.8,
                    "expected_abandoned_total": 1.6,
                    "expected_total_economic_cost": 420.00,
                },
                {
                    "plan_name": "Lean",
                    "staffing_agents": 9,
                    "capacity_confidence": 0.82,
                    "expected_overtime_hours": 4.1,
                    "expected_abandoned_total": 2.2,
                    "expected_total_economic_cost": 425.00,
                },
                {
                    "plan_name": "Balanced",
                    "staffing_agents": 10,
                    "capacity_confidence": 0.88,
                    "expected_overtime_hours": 3.2,
                    "expected_abandoned_total": 1.1,
                    "expected_total_economic_cost": 415.00,
                },
                {
                    "plan_name": "Conservative",
                    "staffing_agents": 11,
                    "capacity_confidence": 0.92,
                    "expected_overtime_hours": 2.7,
                    "expected_abandoned_total": 0.8,
                    "expected_total_economic_cost": 418.00,
                },
            ],
            columns=[
                "plan_name",
                "staffing_agents",
                "capacity_confidence",
                "expected_overtime_hours",
                "expected_abandoned_total",
                "expected_total_economic_cost",
            ],
        )
        return recommendation, comparison_table

    def test_build_recommendation_text_includes_core_metrics_and_deltas(self) -> None:
        recommendation, comparison_table = self._build_recommendation_context()

        text = build_recommendation_text(recommendation, comparison_table)

        self.assertIn("Schedule 9 reservation agents", text)
        self.assertIn("85.3% capacity confidence", text)
        self.assertIn("expected overtime of 3.5 hours", text)
        self.assertIn("expected abandonment of 1.2 reservations", text)
        self.assertIn("expected total economic cost of $412.35", text)
        self.assertIn("Compared with previous-week staffing, the recommended change is +2 agents", text)
        self.assertIn("compared with the manager plan, the change is +1 agents", text)

    def test_build_recommendation_text_changes_when_inputs_change(self) -> None:
        recommendation, comparison_table = self._build_recommendation_context()
        changed_recommendation = {
            "recommended_staffing_record": {
                "staffing_agents": 10,
                "capacity_confidence": 0.901,
                "expected_overtime_hours": 2.4,
                "expected_abandoned_total": 0.6,
                "expected_total_economic_cost": 399.99,
            }
        }

        original_text = build_recommendation_text(recommendation, comparison_table)
        changed_text = build_recommendation_text(changed_recommendation, comparison_table)

        self.assertNotEqual(original_text, changed_text)
        self.assertIn("Schedule 9 reservation agents", original_text)
        self.assertIn("Schedule 10 reservation agents", changed_text)

    def test_build_recommendation_warnings_flag_abandonment_and_duplicate_named_plans(self) -> None:
        recommendation = {
            "recommended_staffing_record": {
                "staffing_agents": 9,
                "capacity_confidence": 0.853,
                "expected_overtime_hours": 3.5,
                "expected_abandoned_total": 1.2,
                "expected_total_economic_cost": 412.35,
            }
        }
        comparison_table = pd.DataFrame(
            [
                {
                    "plan_name": "Lean",
                    "staffing_agents": 9,
                    "capacity_confidence": 0.82,
                    "expected_overtime_hours": 4.1,
                    "expected_abandoned_total": 2.2,
                    "expected_total_economic_cost": 425.00,
                },
                {
                    "plan_name": "Balanced",
                    "staffing_agents": 9,
                    "capacity_confidence": 0.88,
                    "expected_overtime_hours": 3.2,
                    "expected_abandoned_total": 1.1,
                    "expected_total_economic_cost": 415.00,
                },
                {
                    "plan_name": "Conservative",
                    "staffing_agents": 11,
                    "capacity_confidence": 0.92,
                    "expected_overtime_hours": 2.7,
                    "expected_abandoned_total": 0.8,
                    "expected_total_economic_cost": 418.00,
                },
            ],
            columns=[
                "plan_name",
                "staffing_agents",
                "capacity_confidence",
                "expected_overtime_hours",
                "expected_abandoned_total",
                "expected_total_economic_cost",
            ],
        )

        warnings = build_recommendation_warnings(recommendation, comparison_table)

        self.assertEqual(len(warnings), 2)
        self.assertTrue(
            any("Expected abandonment remains above zero" in warning for warning in warnings)
        )
        self.assertTrue(
            any("Multiple named plans map to the same staffing level" in warning for warning in warnings)
        )

    def test_build_recommendation_text_rejects_malformed_input(self) -> None:
        recommendation, comparison_table = self._build_recommendation_context()

        with self.assertRaisesRegex(FieldValidationError, "must be an integer"):
            build_recommendation_text(
                {
                    "recommended_staffing_record": {
                        **recommendation["recommended_staffing_record"],
                        "staffing_agents": "nine",
                    }
                },
                comparison_table,
            )

        with self.assertRaisesRegex(FieldValidationError, "must be a pandas DataFrame"):
            build_recommendation_text(recommendation, comparison_table.to_dict(orient="records"))


if __name__ == "__main__":
    unittest.main()
