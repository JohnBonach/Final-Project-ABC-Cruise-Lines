"""Contract tests for shared data models and constants."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
import unittest

from src.constants import (
    CATEGORY_ASSUMPTIONS_COLUMNS,
    CONFIDENCE_TARGET_FIELDS,
    FORECAST_RESULT_COLUMNS,
    FORECAST_SOURCES,
    HISTORICAL_DEMAND_COLUMNS,
    NAMED_PLAN_COLUMNS,
    RESERVATION_CATEGORIES,
    SIMULATION_CONFIGURATION_FIELDS,
    SIMULATION_OUTPUT_COLUMNS,
    SIMULATION_SUPPORTED_DISTRIBUTIONS,
    STAFFING_EVALUATION_COLUMNS,
    WORKFORCE_ASSUMPTION_FIELDS,
)
from src.data.loader import build_history_diagnostics, load_and_validate_history
from src.models import (
    CategoryAssumptions,
    ConfidenceTargets,
    ForecastConfiguration,
    SimulationConfiguration,
    WorkforceAssumptions,
    validate_confidence_target_name,
    validate_forecast_source,
)


class SharedContractTests(unittest.TestCase):
    def test_reservation_categories_match_contract_exactly(self) -> None:
        self.assertEqual(
            RESERVATION_CATEGORIES,
            (
                "simple",
                "standard",
                "complex_group",
                "change_cancellation",
            ),
        )

    def test_dataframe_column_constants_match_wbs_contracts(self) -> None:
        self.assertEqual(
            HISTORICAL_DEMAND_COLUMNS,
            (
                "week_id",
                "week_start",
                "simple",
                "standard",
                "complex_group",
                "change_cancellation",
                "staffing_agents",
            ),
        )
        self.assertEqual(
            CATEGORY_ASSUMPTIONS_COLUMNS,
            (
                "category",
                "handling_time_minutes",
                "average_revenue",
                "contribution_per_reservation",
            ),
        )
        self.assertEqual(
            WORKFORCE_ASSUMPTION_FIELDS,
            (
                "paid_hours_per_agent",
                "productive_processing_pct",
                "regular_hourly_wage",
                "overtime_multiplier",
                "abandonment_rate",
                "planned_staffing_agents",
            ),
        )
        self.assertEqual(
            FORECAST_RESULT_COLUMNS,
            (
                "category",
                "point_forecast",
                "historical_mean",
                "historical_std",
                "adjusted_std",
                "forecast_source",
            ),
        )
        self.assertEqual(
            SIMULATION_CONFIGURATION_FIELDS,
            (
                "iterations",
                "random_seed",
                "variability_multiplier",
                "distribution_name",
            ),
        )
        self.assertEqual(SIMULATION_SUPPORTED_DISTRIBUTIONS, ("normal",))
        self.assertEqual(
            SIMULATION_OUTPUT_COLUMNS,
            ("simulation_id", *RESERVATION_CATEGORIES),
        )
        self.assertEqual(
            STAFFING_EVALUATION_COLUMNS,
            (
                "staffing_agents",
                "capacity_confidence",
                "probability_overtime_required",
                "expected_overtime_hours",
                "expected_abandoned_total",
                "expected_abandoned_simple",
                "expected_abandoned_standard",
                "expected_abandoned_complex_group",
                "expected_abandoned_change_cancellation",
                "regular_labor_cost",
                "expected_overtime_cost",
                "expected_lost_revenue",
                "expected_lost_contribution",
                "expected_total_economic_cost",
                "expected_retained_revenue",
                "expected_retained_contribution",
                "expected_net_contribution",
                "expected_unused_regular_hours",
            ),
        )
        self.assertEqual(
            NAMED_PLAN_COLUMNS,
            (
                "plan_name",
                "confidence_target",
                "staffing_agents",
                "staffing_evaluation_reference",
            ),
        )

    def test_category_assumptions_round_trip_preserves_section_6_field_names(self) -> None:
        payload = {
            "category": "simple",
            "handling_time_minutes": 9.5,
            "average_revenue": 2200.0,
            "contribution_per_reservation": 500.0,
        }

        model = CategoryAssumptions.from_dict(payload)

        self.assertEqual(model.to_dict(), payload)

    def test_workforce_assumptions_use_decimal_percentages_internally(self) -> None:
        model = WorkforceAssumptions(
            paid_hours_per_agent=40.0,
            productive_processing_pct=0.8,
            regular_hourly_wage=22.0,
            overtime_multiplier=1.5,
            abandonment_rate=0.03,
            planned_staffing_agents=10,
        )

        self.assertEqual(model.productive_processing_pct, 0.8)
        self.assertEqual(model.abandonment_rate, 0.03)

    def test_contract_models_validate_categories_and_decimal_fields(self) -> None:
        invalid_cases = [
            (
                lambda: CategoryAssumptions.from_dict(
                    {
                        "category": "vip",
                        "handling_time_minutes": 15.0,
                        "average_revenue": 1000.0,
                        "contribution_per_reservation": 250.0,
                    }
                ),
                "category must be one of",
            ),
            (
                lambda: WorkforceAssumptions(
                    paid_hours_per_agent=40.0,
                    productive_processing_pct=80.0,
                    regular_hourly_wage=22.0,
                    overtime_multiplier=1.5,
                    abandonment_rate=0.05,
                    planned_staffing_agents=10,
                ),
                "represented internally as a decimal",
            ),
            (
                lambda: WorkforceAssumptions(
                    paid_hours_per_agent=40.0,
                    productive_processing_pct=0.8,
                    regular_hourly_wage=22.0,
                    overtime_multiplier=1.5,
                    abandonment_rate=5.0,
                    planned_staffing_agents=10,
                ),
                "represented internally as a decimal",
            ),
            (
                lambda: ForecastConfiguration(
                    weights=(0.5, 0.3, 0.2, 0.1),
                    variability_multiplier=1.0,
                    manual_overrides=None,
                ),
                "weights must sum to 1.0",
            ),
            (
                lambda: SimulationConfiguration(
                    iterations=1000,
                    random_seed=None,
                    variability_multiplier=1.0,
                    distribution_name="poisson",
                ),
                "distribution_name must be one of",
            ),
            (
                lambda: ConfidenceTargets(lean=0.5, balanced=0.85, conservative=95.0),
                "represented internally as a decimal",
            ),
        ]

        for builder, expected_message in invalid_cases:
            with self.subTest(expected_message=expected_message):
                with self.assertRaisesRegex(ValueError, expected_message):
                    builder()

    def test_models_reject_missing_required_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing keys"):
            CategoryAssumptions.from_dict(
                {
                    "category": "simple",
                    "handling_time_minutes": 10.0,
                    "average_revenue": 2000.0,
                }
            )

        with self.assertRaisesRegex(ValueError, "missing keys"):
            SimulationConfiguration.from_dict(
                {
                    "iterations": 1000,
                    "random_seed": 42,
                    "variability_multiplier": 1.0,
                }
            )

    def test_forecast_configuration_round_trip_and_manual_override_validation(self) -> None:
        payload = {
            "weights": [0.4, 0.3, 0.2, 0.1],
            "variability_multiplier": 1.25,
            "manual_overrides": {
                "simple": 120.0,
                "standard": 80.0,
            },
        }

        model = ForecastConfiguration.from_dict(payload)

        self.assertEqual(model.weights, (0.4, 0.3, 0.2, 0.1))
        self.assertEqual(model.to_dict(), payload)

        with self.assertRaisesRegex(ValueError, "category must be one of"):
            ForecastConfiguration(
                weights=(0.4, 0.3, 0.2, 0.1),
                variability_multiplier=1.0,
                manual_overrides={"vip": 10.0},
            )

    def test_confidence_targets_map_to_stable_downstream_keys(self) -> None:
        targets = ConfidenceTargets(lean=0.5, balanced=0.85, conservative=0.95)

        self.assertEqual(CONFIDENCE_TARGET_FIELDS, ("lean", "balanced", "conservative"))
        self.assertEqual(
            targets.to_dict(),
            {
                "lean": 0.5,
                "balanced": 0.85,
                "conservative": 0.95,
            },
        )

    def test_shared_validators_enforce_contract_enums(self) -> None:
        self.assertEqual(FORECAST_SOURCES, ("automatic", "manual_override"))
        self.assertEqual(validate_forecast_source("automatic"), "automatic")
        self.assertEqual(validate_confidence_target_name("balanced"), "balanced")

        with self.assertRaisesRegex(ValueError, "forecast_source must be one of"):
            validate_forecast_source("spreadsheet")

        with self.assertRaisesRegex(ValueError, "confidence target name must be one of"):
            validate_confidence_target_name("manager")

    def test_models_import_without_importing_streamlit(self) -> None:
        sys.modules.pop("src.models", None)
        sys.modules.pop("streamlit", None)

        importlib.import_module("src.models")

        self.assertNotIn("streamlit", sys.modules)


class HistoricalDataDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.history_path = Path(__file__).resolve().parents[1] / "data" / "synthetic_history.csv"

    def test_build_history_diagnostics_returns_summary_and_quality_checks(self) -> None:
        history = load_and_validate_history(self.history_path)
        diagnostics = build_history_diagnostics(history)

        self.assertEqual(
            tuple(diagnostics),
            (
                "week_count",
                "date_range",
                "category_summary",
                "staffing_summary",
                "recent_four_week_extract",
                "quality_checks",
            ),
        )
        self.assertEqual(diagnostics["week_count"], len(history))
        self.assertEqual(
            diagnostics["date_range"],
            {"start": "2026-04-06", "end": "2026-06-08"},
        )
        self.assertEqual(
            tuple(diagnostics["category_summary"]),
            RESERVATION_CATEGORIES,
        )

        for category in RESERVATION_CATEGORIES:
            expected_summary = {
                "total": int(history[category].sum()),
                "mean": float(history[category].mean()),
                "std": float(history[category].std()),
                "min": int(history[category].min()),
                "max": int(history[category].max()),
            }
            actual_summary = diagnostics["category_summary"][category]
            self.assertEqual(actual_summary["total"], expected_summary["total"])
            self.assertEqual(actual_summary["min"], expected_summary["min"])
            self.assertEqual(actual_summary["max"], expected_summary["max"])
            self.assertAlmostEqual(actual_summary["mean"], expected_summary["mean"])
            self.assertAlmostEqual(actual_summary["std"], expected_summary["std"])

        staffing_summary = diagnostics["staffing_summary"]
        self.assertEqual(staffing_summary["total"], int(history["staffing_agents"].sum()))
        self.assertEqual(staffing_summary["min"], int(history["staffing_agents"].min()))
        self.assertEqual(staffing_summary["max"], int(history["staffing_agents"].max()))
        self.assertAlmostEqual(staffing_summary["mean"], float(history["staffing_agents"].mean()))
        self.assertAlmostEqual(staffing_summary["std"], float(history["staffing_agents"].std()))

        recent_four_week_extract = diagnostics["recent_four_week_extract"]
        self.assertEqual(len(recent_four_week_extract), 4)
        self.assertEqual(
            [row["week_id"] for row in recent_four_week_extract],
            ["2026-W21", "2026-W22", "2026-W23", "2026-W24"],
        )
        self.assertEqual(
            [row["week_start"] for row in recent_four_week_extract],
            ["2026-05-18", "2026-05-25", "2026-06-01", "2026-06-08"],
        )
        self.assertEqual(
            recent_four_week_extract,
            history.tail(4).loc[:, HISTORICAL_DEMAND_COLUMNS]
            .assign(week_start=history.tail(4)["week_start"].dt.strftime("%Y-%m-%d"))
            .to_dict(orient="records"),
        )

        self.assertTrue(all(diagnostics["quality_checks"].values()))

    def test_build_history_diagnostics_reports_gap_and_short_history_flags(self) -> None:
        history = load_and_validate_history(self.history_path)

        gapped_history = history.drop(index=4).reset_index(drop=True)
        gap_diagnostics = build_history_diagnostics(gapped_history)
        self.assertEqual(gap_diagnostics["week_count"], len(gapped_history))
        self.assertFalse(gap_diagnostics["quality_checks"]["weeks_are_contiguous"])
        self.assertTrue(gap_diagnostics["quality_checks"]["meets_minimum_history_weeks"])

        short_history = history.iloc[:3].copy()
        short_diagnostics = build_history_diagnostics(short_history)
        self.assertFalse(short_diagnostics["quality_checks"]["meets_minimum_history_weeks"])


if __name__ == "__main__":
    unittest.main()
