"""End-to-end backend tests for the restored analytical pipeline."""

from __future__ import annotations

from pathlib import Path
import unittest

from src.constants import FORECAST_RESULT_COLUMNS, NAMED_PLAN_COLUMNS, SIMULATION_OUTPUT_COLUMNS, STAFFING_EVALUATION_COLUMNS
from src.data.loader import load_and_validate_history
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

    def _build_result(self, *, scenario_name: str | None = None, manual_overrides: dict[str, float] | None = None) -> dict[str, object]:
        return build_application_result(
            history=self.history,
            category_assumptions=self.defaults["category_assumptions"],
            workforce_assumptions=self.defaults["workforce_assumptions"],
            forecast_configuration=self.defaults["forecast_configuration"],
            simulation_configuration=self.defaults["simulation_configuration"],
            confidence_targets=self.defaults["confidence_targets"],
            strategic_assumptions=self.defaults["strategic_assumptions"],
            scenario_name=scenario_name,
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
        self.assertEqual(result["scenario"]["scenario_name"], "Expected Demand")

    def test_high_demand_scenario_and_manual_override_follow_required_order(self) -> None:
        result = self._build_result(
            scenario_name="High Demand",
            manual_overrides={"nine_night_cruise": 120.0},
        )

        self.assertTrue(result["ok"])
        self.assertAlmostEqual(result["scenario_adjusted_forecast"]["day_cruise"], 270.25)
        self.assertAlmostEqual(result["scenario_adjusted_forecast"]["seven_night_cruise"], 176.525)
        self.assertAlmostEqual(result["scenario_adjusted_forecast"]["nine_night_cruise"], 103.5)
        self.assertAlmostEqual(result["effective_forecast"]["nine_night_cruise"], 120.0)

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


if __name__ == "__main__":
    unittest.main()
