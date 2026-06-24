"""End-to-end backend tests for the restored analytical pipeline."""

from __future__ import annotations

import math
from pathlib import Path
import unittest

from src.constants import FORECAST_RESULT_COLUMNS, NAMED_PLAN_COLUMNS, SIMULATION_OUTPUT_COLUMNS, STAFFING_EVALUATION_COLUMNS
from src.data.loader import load_and_validate_history
from src.models import DecisionPolicy
from src.validation import load_defaults_config
from src.orchestration import build_application_result, calculate_deterministic_staffing


class DeterministicStaffingEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        cls.defaults = load_defaults_config(project_root / "config" / "defaults.json")
        cls.history = load_and_validate_history(project_root / "data" / "synthetic_history.csv")

    def test_peak_case_matches_approved_outputs(self) -> None:
        result = calculate_deterministic_staffing(
            {
                "day_cruise": 300,
                "seven_night_cruise": 200,
                "nine_night_cruise": 130,
            },
            self.defaults["category_assumptions"],
            self.defaults["workforce_assumptions"],
        )

        self.assertAlmostEqual(result["total_workload_hours"], 174.0)
        self.assertAlmostEqual(result["raw_required_fte"], 13.92)
        self.assertEqual(result["unconstrained_required_agents"], 14)
        self.assertEqual(result["recommended_inhouse_agents"], 12)
        self.assertAlmostEqual(result["overflow_workload_hours"], 24.0)
        self.assertAlmostEqual(
            sum(result["overflow_bookings_by_category"].values()),
            86.8965517241,
            places=4,
        )

    def test_low_case_matches_approved_outputs(self) -> None:
        result = calculate_deterministic_staffing(
            {
                "day_cruise": 145,
                "seven_night_cruise": 90,
                "nine_night_cruise": 45,
            },
            self.defaults["category_assumptions"],
            self.defaults["workforce_assumptions"],
        )

        self.assertAlmostEqual(result["total_workload_hours"], 73.3333333333)
        self.assertAlmostEqual(result["raw_required_fte"], 5.8666666667)
        self.assertEqual(result["unconstrained_required_agents"], 6)
        self.assertEqual(result["recommended_inhouse_agents"], 8)
        self.assertAlmostEqual(result["spare_capacity_hours"], 26.6666666667)
        self.assertAlmostEqual(result["overflow_workload_hours"], 0.0)


class ApplicationOrchestrationEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        cls.defaults = load_defaults_config(project_root / "config" / "defaults.json")
        cls.history = load_and_validate_history(project_root / "data" / "synthetic_history.csv")

    def _build_result(
        self,
        *,
        manual_overrides: dict[str, float] | None = None,
        minimum_inhouse_coverage_target: float | None = None,
        manager_planned_staffing: int | None = None,
        previous_week_staffing: int | None = None,
    ) -> dict[str, object]:
        return build_application_result(
            history=self.history,
            category_assumptions=self.defaults["category_assumptions"],
            workforce_assumptions=self.defaults["workforce_assumptions"],
            forecast_configuration=self.defaults["forecast_configuration"],
            simulation_configuration=self.defaults["simulation_configuration"],
            confidence_targets=self.defaults["confidence_targets"],
            strategic_assumptions=self.defaults["strategic_assumptions"],
            decision_policy={
                "minimum_inhouse_coverage_target": (
                    minimum_inhouse_coverage_target
                    if minimum_inhouse_coverage_target is not None
                    else self.defaults["decision_policy"].minimum_inhouse_coverage_target
                )
            },
            manager_planned_staffing=manager_planned_staffing,
            previous_week_staffing=previous_week_staffing,
            manual_overrides=manual_overrides,
        )

    def test_application_result_is_runnable_and_structured(self) -> None:
        result = self._build_result()

        self.assertTrue(result["ok"])
        self.assertEqual(tuple(result["forecast_result"].columns), FORECAST_RESULT_COLUMNS)
        self.assertEqual(tuple(result["simulation_distribution"].columns), SIMULATION_OUTPUT_COLUMNS)
        self.assertEqual(tuple(result["staffing_evaluation_table"].columns), STAFFING_EVALUATION_COLUMNS)
        self.assertEqual(tuple(result["named_plans"]["table"].columns), NAMED_PLAN_COLUMNS)
        self.assertEqual(result["automatic_forecast"], {
            "day_cruise": 235.0,
            "seven_night_cruise": 153.5,
            "nine_night_cruise": 90.0,
        })
        self.assertEqual(result["decision_policy"], {
            "minimum_inhouse_coverage_target": 0.85,
        })
        self.assertEqual(
            result["recommendation_policy"]["candidate_staffing_levels"],
            [8, 9, 10, 11, 12],
        )
        self.assertEqual(
            result["named_plans"]["candidate_staffing_levels"],
            [8, 9, 10, 11, 12],
        )
        self.assertIn("recommended_plan", result)
        self.assertIn("manager_proposal", result)
        self.assertIn("lower_demand_outlook", result)
        self.assertIn("central_demand_outlook", result)
        self.assertIn("higher_demand_outlook", result)
        self.assertIn("outlook_diagnostics", result)
        self.assertIn("previous_week_staffing_context", result)
        self.assertIn("recommendation_manager_comparison", result)
        self.assertIn("adaptive_comparison_narrative", result)
        self.assertIn("staffing_risk_cost_records", result)
        self.assertNotIn("scenario", result)
        self.assertNotIn("scenario_adjusted_forecast", result)
        self.assertNotIn("scenario_compatibility", result)

    def test_defaults_contract_uses_coverage_target_and_preserves_forecast_baseline(self) -> None:
        self.assertEqual(self.defaults["schema_version"], "2.0")
        self.assertTrue(hasattr(self.defaults["decision_policy"], "minimum_inhouse_coverage_target"))
        self.assertEqual(
            self.defaults["decision_policy"].minimum_inhouse_coverage_target,
            0.85,
        )
        self.assertEqual(
            self.defaults["strategic_assumptions"].to_dict(),
            {"third_party_commission_rate": 0.125},
        )

    def test_decision_policy_target_must_remain_between_zero_and_one(self) -> None:
        with self.assertRaisesRegex(ValueError, "minimum_inhouse_coverage_target"):
            DecisionPolicy(minimum_inhouse_coverage_target=1.01)

    def test_manual_override_preserves_exact_manager_value_without_scenario_scaling(self) -> None:
        result = self._build_result(
            manual_overrides={"nine_night_cruise": 120.0},
        )

        self.assertTrue(result["ok"])
        self.assertAlmostEqual(result["forecast_result"].set_index("category").loc["nine_night_cruise", "point_forecast"], 120.0)
        self.assertAlmostEqual(result["effective_forecast"]["nine_night_cruise"], 120.0)
        self.assertNotIn("scenario_adjusted_forecast", result)

    def test_manual_override_changes_central_forecast_distribution_and_outlooks(self) -> None:
        baseline = self._build_result()
        overridden = self._build_result(
            manual_overrides={"day_cruise": 300.0},
        )

        self.assertTrue(baseline["ok"])
        self.assertTrue(overridden["ok"])
        self.assertAlmostEqual(
            baseline["forecast_result"].set_index("category").loc["day_cruise", "point_forecast"],
            235.0,
        )
        self.assertAlmostEqual(
            overridden["forecast_result"].set_index("category").loc["day_cruise", "point_forecast"],
            300.0,
        )
        self.assertEqual(
            baseline["automatic_forecast"]["day_cruise"],
            overridden["automatic_forecast"]["day_cruise"],
        )
        self.assertEqual(
            baseline["simulation_distribution"].equals(overridden["simulation_distribution"]),
            False,
        )
        self.assertNotEqual(
            baseline["central_demand_outlook"]["demand_by_category"]["day_cruise"],
            overridden["central_demand_outlook"]["demand_by_category"]["day_cruise"],
        )

    def test_probabilistic_outlook_objects_reconcile_to_shared_operational_and_financial_logic(self) -> None:
        result = self._build_result()

        self.assertTrue(result["ok"])
        for outlook_key in (
            "lower_demand_outlook",
            "central_demand_outlook",
            "higher_demand_outlook",
        ):
            with self.subTest(outlook_key=outlook_key):
                outlook = result[outlook_key]
                self.assertEqual(
                    set(outlook),
                    {
                        "outlook_name",
                        "percentile",
                        "percentile_label",
                        "simulation_row_id",
                        "representative_row_reused",
                        "demand_by_category",
                        "total_bookings",
                        "workload_hours_by_category",
                        "total_workload_hours",
                        "raw_required_fte",
                        "unconstrained_required_agents",
                        "recommended_inhouse_agents_for_outlook",
                        "spare_capacity_hours",
                        "overflow_workload_hours",
                        "overflow_bookings_by_category",
                        "regular_labor_cost",
                        "overflow_commission",
                        "total_weekly_operating_cost",
                    },
                )
                self.assertAlmostEqual(
                    sum(outlook["demand_by_category"].values()),
                    outlook["total_bookings"],
                )
                self.assertAlmostEqual(
                    sum(outlook["workload_hours_by_category"].values()),
                    outlook["total_workload_hours"],
                    places=9,
                )
                self.assertAlmostEqual(
                    outlook["raw_required_fte"],
                    outlook["total_workload_hours"] / 12.5,
                    places=9,
                )
                self.assertEqual(
                    outlook["unconstrained_required_agents"],
                    math.ceil(outlook["raw_required_fte"]),
                )
                self.assertGreaterEqual(
                    outlook["recommended_inhouse_agents_for_outlook"],
                    8,
                )
                self.assertLessEqual(
                    outlook["recommended_inhouse_agents_for_outlook"],
                    12,
                )
                capacity_hours = outlook["recommended_inhouse_agents_for_outlook"] * 12.5
                self.assertAlmostEqual(
                    outlook["spare_capacity_hours"],
                    max(capacity_hours - outlook["total_workload_hours"], 0.0),
                    places=9,
                )
                self.assertAlmostEqual(
                    outlook["overflow_workload_hours"],
                    max(outlook["total_workload_hours"] - capacity_hours, 0.0),
                    places=9,
                )
                self.assertAlmostEqual(
                    outlook["total_weekly_operating_cost"],
                    outlook["regular_labor_cost"] + outlook["overflow_commission"],
                    places=9,
                )

        self.assertTrue(result["outlook_diagnostics"]["ordering_invariant_satisfied"])
        selected_workloads = result["outlook_diagnostics"]["selected_total_workload_hours_by_percentile_label"]
        self.assertLessEqual(selected_workloads["P25"], selected_workloads["P50"])
        self.assertLessEqual(selected_workloads["P50"], selected_workloads["P90"])

    def test_backend_recommendation_contains_no_active_abandonment_or_overtime_fields(self) -> None:
        result = self._build_result()

        self.assertTrue(result["ok"])
        recommended_record = result["financial_recommendation"]["recommended_staffing_record"]
        forbidden_fields = {
            "expected_overtime_hours",
            "expected_overtime_cost",
            "expected_abandoned_total",
            "expected_lost_revenue",
            "expected_lost_contribution",
            "expected_total_economic_cost",
        }
        self.assertTrue(forbidden_fields.isdisjoint(recommended_record))
        self.assertIn("expected_total_weekly_operating_cost", recommended_record)

    def test_coverage_targets_70_85_and_95_produce_reproducible_outputs(self) -> None:
        expected = {
            0.70: (12, 0.8810, True),
            0.85: (12, 0.8810, True),
            0.95: (12, 0.8810, False),
        }

        for target, (staffing, coverage, met) in expected.items():
            result = self._build_result(
                minimum_inhouse_coverage_target=target,
            )
            self.assertTrue(result["ok"])
            recommendation = result["financial_recommendation"]
            self.assertEqual(recommendation["recommended_staffing_agents"], staffing)
            self.assertAlmostEqual(recommendation["recommended_coverage"], coverage, places=4)
            self.assertEqual(recommendation["coverage_target_met"], met)
        self.assertIsNotNone(
            self._build_result(minimum_inhouse_coverage_target=0.95)["financial_recommendation"]["warning"]
        )

    def test_manager_proposal_is_evaluated_exactly_without_clamping(self) -> None:
        cases = [
            (0, "below_operating_floor"),
            (7, "below_operating_floor"),
            (8, "within_operating_range"),
            (10, "within_operating_range"),
            (12, "within_operating_range"),
            (13, "above_inhouse_capacity"),
            (25, "above_inhouse_capacity"),
        ]

        for staffing_agents, expected_status in cases:
            with self.subTest(staffing_agents=staffing_agents):
                result = self._build_result(manager_planned_staffing=staffing_agents)
                self.assertTrue(result["ok"])
                manager_proposal = result["manager_proposal"]
                self.assertEqual(manager_proposal["staffing_agents"], staffing_agents)
                self.assertEqual(
                    manager_proposal["feasibility_status"],
                    expected_status,
                )
                self.assertAlmostEqual(
                    manager_proposal["capacity_confidence"]
                    + manager_proposal["probability_overflow_required"],
                    1.0,
                    places=9,
                )
                if expected_status == "within_operating_range":
                    self.assertEqual(manager_proposal["warnings"], [])
                else:
                    self.assertGreaterEqual(len(manager_proposal["warnings"]), 1)

    def test_manager_proposal_changes_do_not_change_recommendation_or_candidate_set(self) -> None:
        baseline = self._build_result(manager_planned_staffing=8)
        out_of_range = self._build_result(manager_planned_staffing=25)

        self.assertTrue(baseline["ok"])
        self.assertTrue(out_of_range["ok"])
        self.assertEqual(
            baseline["financial_recommendation"]["recommended_staffing_agents"],
            out_of_range["financial_recommendation"]["recommended_staffing_agents"],
        )
        self.assertEqual(
            baseline["financial_recommendation"]["expected_total_weekly_operating_cost"],
            out_of_range["financial_recommendation"]["expected_total_weekly_operating_cost"],
        )
        self.assertEqual(
            baseline["recommendation_policy"]["candidate_staffing_levels"],
            out_of_range["recommendation_policy"]["candidate_staffing_levels"],
        )
        self.assertEqual(
            baseline["recommendation_policy"]["minimum_inhouse_coverage_target"],
            out_of_range["recommendation_policy"]["minimum_inhouse_coverage_target"],
        )
        self.assertNotIn(
            25,
            out_of_range["recommendation_policy"]["candidate_staffing_levels"],
        )

    def test_previous_week_staffing_context_allows_out_of_range_levels_without_constraining_recommendation(self) -> None:
        within_range = self._build_result(previous_week_staffing=9)
        below_floor = self._build_result(previous_week_staffing=7)
        above_cap = self._build_result(previous_week_staffing=13)

        self.assertEqual(
            within_range["previous_week_staffing_context"]["feasibility_status"],
            "within_operating_range",
        )
        self.assertEqual(
            below_floor["previous_week_staffing_context"]["feasibility_status"],
            "below_operating_floor",
        )
        self.assertEqual(
            above_cap["previous_week_staffing_context"]["feasibility_status"],
            "above_inhouse_capacity",
        )
        self.assertEqual(
            within_range["financial_recommendation"]["recommended_staffing_agents"],
            below_floor["financial_recommendation"]["recommended_staffing_agents"],
        )
        self.assertEqual(
            within_range["financial_recommendation"]["recommended_staffing_agents"],
            above_cap["financial_recommendation"]["recommended_staffing_agents"],
        )

    def test_recommendation_manager_comparison_uses_manager_minus_recommendation_direction(self) -> None:
        result = self._build_result(manager_planned_staffing=10)

        self.assertTrue(result["ok"])
        recommended_plan = result["recommended_plan"]
        manager_proposal = result["manager_proposal"]
        comparison = result["recommendation_manager_comparison"]

        self.assertEqual(comparison["staffing_difference"], -2)
        self.assertAlmostEqual(
            comparison["coverage_difference"],
            manager_proposal["capacity_confidence"] - recommended_plan["capacity_confidence"],
        )
        self.assertAlmostEqual(
            comparison["overflow_probability_difference"],
            manager_proposal["probability_overflow_required"]
            - recommended_plan["probability_overflow_required"],
        )
        self.assertAlmostEqual(
            comparison["labor_cost_difference"],
            manager_proposal["regular_labor_cost"] - recommended_plan["regular_labor_cost"],
        )
        self.assertAlmostEqual(
            comparison["overflow_commission_difference"],
            manager_proposal["expected_overflow_commission"]
            - recommended_plan["expected_overflow_commission"],
        )
        self.assertAlmostEqual(
            comparison["total_cost_difference"],
            manager_proposal["expected_total_weekly_operating_cost"]
            - recommended_plan["expected_total_weekly_operating_cost"],
        )
        self.assertAlmostEqual(
            comparison["spare_capacity_difference"],
            manager_proposal["expected_spare_capacity_hours"]
            - recommended_plan["expected_spare_capacity_hours"],
        )
        self.assertAlmostEqual(
            comparison["overflow_workload_difference"],
            manager_proposal["expected_overflow_workload_hours"]
            - recommended_plan["expected_overflow_workload_hours"],
        )

    def test_staffing_risk_cost_records_include_union_dedup_sorting_and_flags(self) -> None:
        result = self._build_result(
            manager_planned_staffing=0,
            previous_week_staffing=13,
        )

        self.assertTrue(result["ok"])
        records = result["staffing_risk_cost_records"]
        levels = [record["staffing_agents"] for record in records]
        self.assertEqual(levels, [0, 8, 9, 10, 11, 12, 13])

        manager_record = next(
            record for record in records if record["staffing_agents"] == 0
        )
        previous_record = next(
            record for record in records if record["staffing_agents"] == 13
        )
        recommended_record = next(
            record for record in records if record["is_model_recommendation"]
        )

        self.assertTrue(manager_record["is_manager_proposal"])
        self.assertEqual(
            manager_record["feasibility_status"],
            "below_operating_floor",
        )
        self.assertTrue(previous_record["is_previous_week"])
        self.assertEqual(
            previous_record["feasibility_status"],
            "above_inhouse_capacity",
        )
        self.assertEqual(recommended_record["staffing_agents"], 12)

    def test_staffing_risk_cost_records_combine_multiple_flags_on_one_row(self) -> None:
        result = self._build_result(
            manager_planned_staffing=12,
            previous_week_staffing=12,
        )

        self.assertTrue(result["ok"])
        flagged_rows = [
            record
            for record in result["staffing_risk_cost_records"]
            if record["staffing_agents"] == 12
        ]
        self.assertEqual(len(flagged_rows), 1)
        self.assertTrue(flagged_rows[0]["is_model_recommendation"])
        self.assertTrue(flagged_rows[0]["is_manager_proposal"])
        self.assertTrue(flagged_rows[0]["is_previous_week"])

    def test_application_result_contains_no_interactive_scenario_contract_fields(self) -> None:
        result = self._build_result()

        self.assertTrue(result["ok"])
        forbidden_top_level_fields = {
            "scenario",
            "scenario_adjusted_forecast",
            "scenario_compatibility",
        }
        self.assertTrue(forbidden_top_level_fields.isdisjoint(result))


if __name__ == "__main__":
    unittest.main()
