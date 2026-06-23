"""End-to-end operations tests for deterministic staffing orchestration."""

from __future__ import annotations

from pathlib import Path
import unittest

import pandas as pd

from src.constants import RESERVATION_CATEGORIES
from src.constants import FORECAST_RESULT_COLUMNS, NAMED_PLAN_COLUMNS
from src.constants import SIMULATION_OUTPUT_COLUMNS, STAFFING_EVALUATION_COLUMNS
from src.constants import CONFIDENCE_TARGET_FIELDS
from src.models import (
    CategoryAssumptions,
    ConfidenceTargets,
    ForecastConfiguration,
    SimulationConfiguration,
    WorkforceAssumptions,
)
from src.orchestration import build_application_result
from src.orchestration import calculate_deterministic_staffing
from scripts.run_validation_case import build_validation_case_report
from scripts.run_validation_case import load_validation_case
from scripts.run_case_study import build_case_study_report
from scripts.run_case_study import load_case_study_input


class DeterministicStaffingEndToEndTests(unittest.TestCase):
    def test_calculate_deterministic_staffing_composes_shared_primitives(self) -> None:
        demand_by_category = {
            "simple": 12,
            "standard": 8,
            "complex_group": 4,
            "change_cancellation": 6,
        }
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

        result = calculate_deterministic_staffing(
            demand_by_category,
            category_assumptions,
            workforce_assumptions,
        )

        self.assertEqual(tuple(result["workload_hours_by_category"]), RESERVATION_CATEGORIES)
        self.assertEqual(
            result["workload_hours_by_category"],
            {
                "simple": 2.0,
                "standard": 2.0,
                "complex_group": 2.0,
                "change_cancellation": 2.0,
            },
        )
        self.assertEqual(result["total_workload_hours"], 8.0)
        self.assertEqual(result["productive_hours_per_agent"], 30.0)
        self.assertEqual(result["required_fte"], 8.0 / 30.0)
        self.assertEqual(result["required_agents"], 1)

    def test_calculate_deterministic_staffing_handles_zero_demand(self) -> None:
        demand_by_category = {
            "simple": 0,
            "standard": 0,
            "complex_group": 0,
            "change_cancellation": 0,
        }
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

        result = calculate_deterministic_staffing(
            demand_by_category,
            category_assumptions,
            workforce_assumptions,
        )

        self.assertEqual(tuple(result["workload_hours_by_category"]), RESERVATION_CATEGORIES)
        self.assertEqual(
            result["workload_hours_by_category"],
            {
                "simple": 0.0,
                "standard": 0.0,
                "complex_group": 0.0,
                "change_cancellation": 0.0,
            },
        )
        self.assertEqual(result["total_workload_hours"], 0.0)
        self.assertEqual(result["productive_hours_per_agent"], 30.0)
        self.assertEqual(result["required_fte"], 0.0)
        self.assertEqual(result["required_agents"], 0)

    def test_calculate_deterministic_staffing_supports_one_category_dominance(self) -> None:
        demand_by_category = {
            "simple": 0,
            "standard": 18,
            "complex_group": 0,
            "change_cancellation": 0,
        }
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

        result = calculate_deterministic_staffing(
            demand_by_category,
            category_assumptions,
            workforce_assumptions,
        )

        self.assertEqual(tuple(result["workload_hours_by_category"]), RESERVATION_CATEGORIES)
        self.assertEqual(
            result["workload_hours_by_category"],
            {
                "simple": 0.0,
                "standard": 4.5,
                "complex_group": 0.0,
                "change_cancellation": 0.0,
            },
        )
        self.assertEqual(result["total_workload_hours"], 4.5)
        self.assertEqual(result["productive_hours_per_agent"], 30.0)
        self.assertEqual(result["required_fte"], 4.5 / 30.0)
        self.assertEqual(result["required_agents"], 1)


class ApplicationOrchestrationEndToEndTests(unittest.TestCase):
    def _build_history(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 18,
                    "standard": 26,
                    "complex_group": 8,
                    "change_cancellation": 4,
                    "staffing_agents": 7,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 20,
                    "standard": 27,
                    "complex_group": 9,
                    "change_cancellation": 5,
                    "staffing_agents": 7,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 19,
                    "standard": 28,
                    "complex_group": 9,
                    "change_cancellation": 5,
                    "staffing_agents": 8,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 21,
                    "standard": 29,
                    "complex_group": 10,
                    "change_cancellation": 6,
                    "staffing_agents": 8,
                },
            ]
        )

    def _build_category_assumptions(self) -> tuple[CategoryAssumptions, ...]:
        return (
            CategoryAssumptions(
                category="simple",
                handling_time_minutes=15.0,
                average_revenue=400.0,
                contribution_per_reservation=80.0,
            ),
            CategoryAssumptions(
                category="standard",
                handling_time_minutes=35.0,
                average_revenue=1800.0,
                contribution_per_reservation=360.0,
            ),
            CategoryAssumptions(
                category="complex_group",
                handling_time_minutes=75.0,
                average_revenue=6000.0,
                contribution_per_reservation=1200.0,
            ),
            CategoryAssumptions(
                category="change_cancellation",
                handling_time_minutes=20.0,
                average_revenue=75.0,
                contribution_per_reservation=25.0,
            ),
        )

    def _build_workforce_assumptions(self) -> WorkforceAssumptions:
        return WorkforceAssumptions(
            paid_hours_per_agent=40.0,
            productive_processing_pct=0.85,
            regular_hourly_wage=22.0,
            overtime_multiplier=1.5,
            abandonment_rate=0.10,
            planned_staffing_agents=9,
        )

    def _build_forecast_configuration(self) -> ForecastConfiguration:
        return ForecastConfiguration(
            weights=(0.4, 0.3, 0.2, 0.1),
            variability_multiplier=1.0,
            manual_overrides=None,
        )

    def _build_simulation_configuration(self) -> SimulationConfiguration:
        return SimulationConfiguration(
            iterations=200,
            random_seed=510,
            variability_multiplier=1.0,
            distribution_name="normal",
        )

    def _build_confidence_targets(self) -> ConfidenceTargets:
        return ConfidenceTargets(
            lean=0.5,
            balanced=0.85,
            conservative=0.95,
        )

    def _build_application_result(self, *, seed: int = 510) -> dict[str, object]:
        return build_application_result(
            history=self._build_history(),
            category_assumptions=self._build_category_assumptions(),
            workforce_assumptions=self._build_workforce_assumptions(),
            forecast_configuration=self._build_forecast_configuration(),
            simulation_configuration=SimulationConfiguration(
                iterations=200,
                random_seed=seed,
                variability_multiplier=1.0,
                distribution_name="normal",
            ),
            confidence_targets=self._build_confidence_targets(),
            manual_overrides=None,
        )

    def test_build_application_result_returns_structured_outputs(self) -> None:
        result = self._build_application_result()

        self.assertTrue(result["ok"])
        self.assertEqual(tuple(result["forecast_result"].columns), FORECAST_RESULT_COLUMNS)
        self.assertEqual(
            tuple(result["simulation_distribution"].columns),
            SIMULATION_OUTPUT_COLUMNS,
        )
        self.assertEqual(
            tuple(result["staffing_evaluation_table"].columns),
            STAFFING_EVALUATION_COLUMNS,
        )
        self.assertEqual(
            tuple(result["named_plans"]["table"].columns),
            NAMED_PLAN_COLUMNS,
        )
        self.assertEqual(
            tuple(result["named_plans"]["selected"].keys()),
            CONFIDENCE_TARGET_FIELDS,
        )
        self.assertGreaterEqual(result["deterministic_staffing_result"]["required_agents"], 0)
        self.assertIn(
            result["financial_recommendation"]["recommended_staffing_agents"],
            result["staffing_evaluation_table"]["staffing_agents"].tolist(),
        )
        self.assertIsInstance(result["narrative"]["text"], str)
        self.assertTrue(result["narrative"]["text"])

    def test_build_application_result_is_reproducible_for_a_fixed_seed(self) -> None:
        first = self._build_application_result(seed=123)
        second = self._build_application_result(seed=123)

        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        pd.testing.assert_frame_equal(first["forecast_result"], second["forecast_result"])
        pd.testing.assert_frame_equal(
            first["simulation_distribution"],
            second["simulation_distribution"],
        )
        pd.testing.assert_frame_equal(
            first["staffing_evaluation_table"],
            second["staffing_evaluation_table"],
        )
        pd.testing.assert_frame_equal(
            first["named_plans"]["table"],
            second["named_plans"]["table"],
        )
        pd.testing.assert_frame_equal(
            first["narrative"]["comparison_table"],
            second["narrative"]["comparison_table"],
        )
        self.assertEqual(first["deterministic_staffing_result"], second["deterministic_staffing_result"])
        self.assertEqual(first["financial_recommendation"]["recommended_staffing_agents"], second["financial_recommendation"]["recommended_staffing_agents"])
        self.assertEqual(first["narrative"]["text"], second["narrative"]["text"])
        self.assertEqual(first["narrative"]["warnings"], second["narrative"]["warnings"])

    def test_build_application_result_returns_user_readable_errors(self) -> None:
        bad_history = self._build_history().drop(columns=["staffing_agents"])

        result = build_application_result(
            history=bad_history,
            category_assumptions=self._build_category_assumptions(),
            workforce_assumptions=self._build_workforce_assumptions(),
            forecast_configuration=self._build_forecast_configuration(),
            simulation_configuration=self._build_simulation_configuration(),
            confidence_targets=self._build_confidence_targets(),
            manual_overrides=None,
        )

        self.assertFalse(result["ok"])
        self.assertIn("historical data", result["error"]["message"])


class ManualDeterministicValidationCaseTests(unittest.TestCase):
    def test_validation_case_matches_hand_worked_expectations(self) -> None:
        case_path = Path(__file__).resolve().parents[1] / "data" / "case_study_input.json"
        report = build_validation_case_report(load_validation_case(case_path))

        self.assertTrue(report["passed"])
        self.assertEqual(report["actual"]["forecast"]["point_forecast"]["simple"], 12.0)
        self.assertEqual(report["actual"]["forecast"]["point_forecast"]["standard"], 8.0)
        self.assertEqual(report["actual"]["forecast"]["point_forecast"]["complex_group"], 4.0)
        self.assertEqual(report["actual"]["forecast"]["point_forecast"]["change_cancellation"], 6.0)
        self.assertEqual(report["actual"]["deterministic_staffing"]["required_agents"], 2)
        self.assertAlmostEqual(report["actual"]["deterministic_staffing"]["total_workload_hours"], 40.0)
        self.assertAlmostEqual(report["actual"]["deterministic_staffing"]["productive_hours_per_agent"], 30.0)
        self.assertAlmostEqual(report["actual"]["staffing_evaluation"]["regular_labor_cost"], 800.0)
        self.assertAlmostEqual(report["actual"]["staffing_evaluation"]["expected_overtime_hours"], 5.0)
        self.assertAlmostEqual(report["actual"]["staffing_evaluation"]["expected_abandoned_total"], 3.75)
        self.assertAlmostEqual(report["actual"]["staffing_evaluation"]["expected_lost_contribution"], 375.0)
        self.assertAlmostEqual(report["actual"]["staffing_evaluation"]["expected_total_economic_cost"], 1325.0)


class ProbabilisticCaseStudyTests(unittest.TestCase):
    def test_case_study_report_is_reproducible_and_changes_recommendation(self) -> None:
        case_path = Path(__file__).resolve().parents[1] / "data" / "probabilistic_case_study_input.json"
        payload = load_case_study_input(case_path)

        first = build_case_study_report(payload)
        second = build_case_study_report(payload)

        self.assertTrue(first["passed"])
        self.assertTrue(second["passed"])
        self.assertEqual(first, second)
        self.assertEqual(first["baseline"]["financial_recommendation"]["recommended_staffing_agents"], 9)
        self.assertEqual(first["baseline"]["named_plans"]["selected"], {"lean": 10, "balanced": 10, "conservative": 11})
        self.assertEqual(first["sensitivity"]["financial_recommendation"]["recommended_staffing_agents"], 8)
        self.assertEqual(first["sensitivity"]["named_plans"]["selected"], {"lean": 8, "balanced": 8, "conservative": 9})
        self.assertEqual(first["comparison"]["recommended_staffing_agents"]["delta"], -1)
        self.assertGreater(
            first["baseline"]["financial_recommendation"]["recommended_staffing_record"]["expected_total_economic_cost"],
            first["sensitivity"]["financial_recommendation"]["recommended_staffing_record"]["expected_total_economic_cost"],
        )


if __name__ == "__main__":
    unittest.main()
