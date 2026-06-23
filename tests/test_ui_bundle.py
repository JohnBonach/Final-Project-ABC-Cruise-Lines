"""Focused tests for the Streamlit UI helper layer."""

from __future__ import annotations

import unittest
from unittest import mock

import pandas as pd

from src.constants import RESERVATION_CATEGORIES
from src.forecasting.uncertainty import assemble_forecast_result
from src.forecasting.weighted_moving_average import calculate_weighted_moving_average
from src.models import (
    CategoryAssumptions,
    ConfidenceTargets,
    ForecastConfiguration,
    SimulationConfiguration,
    WorkforceAssumptions,
)
from src.orchestration import build_application_result
from src.validation import FieldValidationError
from src.ui.charts import (
    build_forecast_display_frame,
    build_history_display_frame,
    build_methodology_points,
    build_plan_comparison_frame,
    build_recommendation_summary_frame,
    build_results_export_frames,
    build_tradeoff_chart_frames,
)
from src.ui import components
from src.ui.state import (
    build_manual_overrides_from_state,
    confidence_targets_are_ordered,
    decimal_to_percent,
    initialize_session_state,
    manual_override_enabled_key,
    manual_override_value_key,
    refresh_draft_shell_preferences,
    percent_to_decimal,
    reset_session_state,
    run_analysis_for_current_draft,
    update_draft_inputs_from_widgets,
)


class UICoordinateHelpersTests(unittest.TestCase):
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

    def _build_defaults(self) -> dict[str, object]:
        return {
            "category_assumptions": (
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
            ),
            "workforce_assumptions": WorkforceAssumptions(
                paid_hours_per_agent=40.0,
                productive_processing_pct=0.85,
                regular_hourly_wage=22.0,
                overtime_multiplier=1.5,
                abandonment_rate=0.10,
                planned_staffing_agents=9,
            ),
            "forecast_configuration": ForecastConfiguration(
                weights=(0.4, 0.3, 0.2, 0.1),
                variability_multiplier=1.0,
                manual_overrides=None,
            ),
            "simulation_configuration": SimulationConfiguration(
                iterations=200,
                random_seed=510,
                variability_multiplier=1.0,
                distribution_name="normal",
            ),
            "confidence_targets": ConfidenceTargets(
                lean=0.5,
                balanced=0.85,
                conservative=0.95,
            ),
        }

    def _build_initialized_state(self) -> tuple[dict[str, object], pd.DataFrame, dict[str, object]]:
        history = self._build_history()
        defaults = self._build_defaults()
        state: dict[str, object] = {}
        initialize_session_state(state, history=history, defaults=defaults)
        return state, history, defaults

    def test_percent_round_trip_uses_ui_display_and_internal_decimal_values(self) -> None:
        self.assertEqual(decimal_to_percent(0.85), 85.0)
        self.assertAlmostEqual(percent_to_decimal(85.0), 0.85)
        self.assertAlmostEqual(percent_to_decimal(decimal_to_percent(0.03)), 0.03)

    def test_confidence_targets_are_ordered_helper_matches_expected_direction(self) -> None:
        self.assertTrue(
            confidence_targets_are_ordered(
                {"lean": 0.5, "balanced": 0.85, "conservative": 0.95}
            )
        )
        self.assertFalse(
            confidence_targets_are_ordered(
                {"lean": 0.85, "balanced": 0.5, "conservative": 0.95}
            )
        )

    def test_manual_overrides_helper_respects_toggle_and_blocks_invalid_values(self) -> None:
        state = {
            manual_override_enabled_key("simple"): True,
            manual_override_value_key("simple"): 18.0,
            manual_override_enabled_key("standard"): False,
            manual_override_value_key("standard"): 99.0,
        }

        self.assertEqual(build_manual_overrides_from_state(state), {"simple": 18.0})

        state[manual_override_value_key("simple")] = -1.0
        with self.assertRaisesRegex(ValueError, "non-negative"):
            build_manual_overrides_from_state(state)

    def test_initialize_session_state_creates_baseline_draft_applied_and_result(self) -> None:
        state, _, _ = self._build_initialized_state()

        self.assertTrue(state["shell_initialized"])
        self.assertFalse(state["results_stale"])
        self.assertEqual(state["draft_inputs"], state["applied_inputs"])
        self.assertEqual(state["baseline_inputs"], state["applied_inputs"])
        self.assertIsNone(state["analysis_error"])
        self.assertTrue(state["analysis_result"]["ok"])

    def test_draft_change_marks_results_stale_without_replacing_applied_inputs(self) -> None:
        state, _, _ = self._build_initialized_state()
        original_applied_inputs = state["applied_inputs"]
        original_result = state["analysis_result"]

        state[manual_override_enabled_key("simple")] = True
        state[manual_override_value_key("simple")] = 99.0
        update_draft_inputs_from_widgets(state)

        self.assertTrue(state["results_stale"])
        self.assertEqual(state["applied_inputs"], original_applied_inputs)
        self.assertIs(state["analysis_result"], original_result)
        self.assertTrue(state["draft_inputs"]["manual_overrides"]["simple"]["enabled"])
        self.assertEqual(state["draft_inputs"]["manual_overrides"]["simple"]["value"], 99.0)

    def test_run_analysis_applies_draft_and_updates_stored_result(self) -> None:
        state, history, defaults = self._build_initialized_state()

        state[manual_override_enabled_key("simple")] = True
        state[manual_override_value_key("simple")] = 99.0
        update_draft_inputs_from_widgets(state)
        run_analysis_for_current_draft(state, history=history, defaults=defaults)

        self.assertFalse(state["results_stale"])
        self.assertIsNone(state["analysis_error"])
        self.assertEqual(state["draft_inputs"], state["applied_inputs"])
        self.assertEqual(
            state["applied_inputs"]["manual_overrides"]["simple"],
            {"enabled": True, "value": 99.0},
        )
        simple_forecast = state["analysis_result"]["forecast_result"].loc[
            lambda frame: frame["category"] == "simple",
            "point_forecast",
        ].iloc[0]
        self.assertEqual(float(simple_forecast), 99.0)

    def test_navigation_change_does_not_touch_draft_applied_or_result(self) -> None:
        state, _, _ = self._build_initialized_state()
        draft_before = state["draft_inputs"]
        applied_before = state["applied_inputs"]
        result_before = state["analysis_result"]

        state["active_section"] = "Operations"

        self.assertEqual(state["draft_inputs"], draft_before)
        self.assertEqual(state["applied_inputs"], applied_before)
        self.assertIs(state["analysis_result"], result_before)

    def test_shell_preference_change_marks_results_stale_without_touching_navigation(self) -> None:
        state, _, _ = self._build_initialized_state()

        state["active_section"] = "Results"
        state["scenario_label"] = "High Demand"
        refresh_draft_shell_preferences(state)

        self.assertEqual(state["active_section"], "Results")
        self.assertTrue(state["results_stale"])
        self.assertEqual(state["draft_inputs"]["shell"]["scenario_label"], "High Demand")
        self.assertEqual(state["applied_inputs"]["shell"]["scenario_label"], "Expected Demand")

    def test_reset_restores_baseline_inputs_and_a_clean_result(self) -> None:
        state, history, defaults = self._build_initialized_state()

        state["active_section"] = "Results"
        state["scenario_label"] = "High Demand"
        state["selected_category"] = "complex_group"
        state["weeks_to_display"] = 4
        state["show_contract_snapshot"] = True
        state["manual_override_notes"] = "test note"
        state[manual_override_enabled_key("simple")] = True
        state[manual_override_value_key("simple")] = 99.0
        update_draft_inputs_from_widgets(state)
        reset_session_state(state, history=history, defaults=defaults)

        self.assertEqual(state["active_section"], "Overview")
        self.assertEqual(state["selected_category"], RESERVATION_CATEGORIES[0])
        self.assertEqual(state["scenario_label"], "Expected Demand")
        self.assertEqual(state["weeks_to_display"], 12)
        self.assertFalse(state["show_contract_snapshot"])
        self.assertEqual(state["manual_override_notes"], "")
        self.assertFalse(state["results_stale"])
        self.assertEqual(state["draft_inputs"], state["baseline_inputs"])
        self.assertEqual(state["applied_inputs"], state["baseline_inputs"])
        self.assertIsNone(state["analysis_error"])
        self.assertTrue(state["analysis_result"]["ok"])

    def test_methodology_points_summarize_the_recommendation_flow(self) -> None:
        points = build_methodology_points()

        self.assertEqual(len(points), 5)
        joined = " ".join(points)
        self.assertIn("manual overrides", joined)
        self.assertIn("weekly demand forecast", joined)
        self.assertIn("lowest expected weekly economic cost", joined)

    def test_history_display_frame_rejects_missing_required_columns(self) -> None:
        history = pd.DataFrame(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 10,
                    "standard": 20,
                    "complex_group": 30,
                    "change_cancellation": 40,
                }
            ]
        )

        with self.assertRaisesRegex(FieldValidationError, "missing required columns"):
            build_history_display_frame(history)


class UIForecastDisplayTests(unittest.TestCase):
    def _build_history(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "week_id": "2026-W01",
                    "week_start": "2025-12-29",
                    "simple": 10,
                    "standard": 20,
                    "complex_group": 30,
                    "change_cancellation": 40,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W02",
                    "week_start": "2026-01-05",
                    "simple": 11,
                    "standard": 21,
                    "complex_group": 31,
                    "change_cancellation": 41,
                    "staffing_agents": 5,
                },
                {
                    "week_id": "2026-W03",
                    "week_start": "2026-01-12",
                    "simple": 12,
                    "standard": 22,
                    "complex_group": 32,
                    "change_cancellation": 42,
                    "staffing_agents": 6,
                },
                {
                    "week_id": "2026-W04",
                    "week_start": "2026-01-19",
                    "simple": 13,
                    "standard": 23,
                    "complex_group": 33,
                    "change_cancellation": 43,
                    "staffing_agents": 6,
                },
            ]
        )

    def test_history_display_frame_formats_dates_and_truncates_to_requested_weeks(self) -> None:
        history = self._build_history()

        display = build_history_display_frame(history, weeks_to_display=2)

        self.assertEqual(len(display), 2)
        self.assertEqual(tuple(display.columns), (
            "week_id",
            "week_start",
            "simple",
            "standard",
            "complex_group",
            "change_cancellation",
            "staffing_agents",
        ))
        self.assertEqual(display["week_start"].tolist(), ["2026-01-12", "2026-01-19"])

    def test_forecast_display_frame_shows_automatic_manual_and_effective_values(self) -> None:
        history = self._build_history()
        weights = [0.4, 0.3, 0.2, 0.1]
        forecast_result = assemble_forecast_result(
            history,
            weights,
            variability_multiplier=1.0,
            manual_overrides={"standard": 99.0},
        )
        automatic = calculate_weighted_moving_average(history, weights)

        display = build_forecast_display_frame(
            automatic,
            forecast_result,
            manual_overrides={"standard": 99.0},
        )

        self.assertEqual(tuple(display["category"]), RESERVATION_CATEGORIES)
        self.assertEqual(
            tuple(display.columns),
            (
                "category",
                "automatic_forecast",
                "manual_override",
                "effective_forecast",
                "forecast_source",
                "historical_mean",
                "historical_std",
                "adjusted_std",
            ),
        )
        self.assertEqual(display.loc[0, "automatic_forecast"], automatic["simple"])
        self.assertTrue(pd.isna(display.loc[0, "manual_override"]))
        self.assertEqual(display.loc[1, "manual_override"], 99.0)
        self.assertEqual(display.loc[1, "forecast_source"], "manual_override")
        self.assertEqual(display.loc[1, "effective_forecast"], 99.0)
        self.assertEqual(display.loc[0, "forecast_source"], "automatic")

    def test_forecast_display_frame_rejects_missing_category_rows(self) -> None:
        history = self._build_history()
        weights = [0.4, 0.3, 0.2, 0.1]
        forecast_result = assemble_forecast_result(history, weights, variability_multiplier=1.0)
        incomplete_result = forecast_result.loc[
            forecast_result["category"] != "change_cancellation"
        ].reset_index(drop=True)
        automatic = calculate_weighted_moving_average(history, weights)

        with self.assertRaisesRegex(FieldValidationError, "required categories"):
            build_forecast_display_frame(automatic, incomplete_result)

    def test_forecast_display_frame_rejects_missing_automatic_category_values(self) -> None:
        history = self._build_history()
        weights = [0.4, 0.3, 0.2, 0.1]
        forecast_result = assemble_forecast_result(history, weights, variability_multiplier=1.0)
        automatic = calculate_weighted_moving_average(history, weights)
        automatic.pop("simple")

        with self.assertRaisesRegex(FieldValidationError, "automatic_forecast"):
            build_forecast_display_frame(automatic, forecast_result)


class UIRecommendationDisplayTests(unittest.TestCase):
    def _build_comparison_table(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "plan_name": "Previous Week",
                    "staffing_agents": 8,
                    "capacity_confidence": 0.74,
                    "expected_overtime_hours": 4.2,
                    "expected_abandoned_total": 3.6,
                    "expected_total_economic_cost": 420.0,
                },
                {
                    "plan_name": "Manager Plan",
                    "staffing_agents": 9,
                    "capacity_confidence": 0.81,
                    "expected_overtime_hours": 3.0,
                    "expected_abandoned_total": 2.4,
                    "expected_total_economic_cost": 405.0,
                },
                {
                    "plan_name": "Lean",
                    "staffing_agents": 8,
                    "capacity_confidence": 0.76,
                    "expected_overtime_hours": 4.0,
                    "expected_abandoned_total": 3.0,
                    "expected_total_economic_cost": 412.0,
                },
                {
                    "plan_name": "Balanced",
                    "staffing_agents": 9,
                    "capacity_confidence": 0.84,
                    "expected_overtime_hours": 2.6,
                    "expected_abandoned_total": 2.0,
                    "expected_total_economic_cost": 398.0,
                },
                {
                    "plan_name": "Conservative",
                    "staffing_agents": 10,
                    "capacity_confidence": 0.90,
                    "expected_overtime_hours": 1.7,
                    "expected_abandoned_total": 1.0,
                    "expected_total_economic_cost": 401.5,
                },
                {
                    "plan_name": "Financial Recommendation",
                    "staffing_agents": 10,
                    "capacity_confidence": 0.90,
                    "expected_overtime_hours": 1.7,
                    "expected_abandoned_total": 1.0,
                    "expected_total_economic_cost": 401.5,
                },
            ]
        )

    def _build_recommendation(self) -> dict[str, object]:
        return {
            "recommended_staffing_agents": 10,
            "recommended_staffing_record": {
                "staffing_agents": 10,
                "capacity_confidence": 0.90,
                "expected_overtime_hours": 1.7,
                "expected_abandoned_total": 1.0,
                "expected_total_economic_cost": 401.5,
            },
        }

    def test_recommendation_summary_frame_aligns_with_comparison_table(self) -> None:
        comparison_table = self._build_comparison_table()
        recommendation = self._build_recommendation()

        summary_frame = build_recommendation_summary_frame(recommendation, comparison_table)
        comparison_frame = build_plan_comparison_frame(comparison_table)

        self.assertEqual(
            summary_frame["metric"].tolist(),
            [
                "Recommended staffing",
                "Capacity confidence",
                "Expected overtime",
                "Expected abandonment",
                "Expected total economic cost",
                "Difference vs previous week",
                "Difference vs manager plan",
            ],
        )
        self.assertEqual(
            summary_frame.set_index("metric").loc["Recommended staffing", "value"],
            10,
        )
        self.assertEqual(
            summary_frame.set_index("metric").loc["Capacity confidence", "value"],
            90.0,
        )
        self.assertEqual(
            summary_frame.set_index("metric").loc["Difference vs previous week", "value"],
            2,
        )
        self.assertEqual(
            summary_frame.set_index("metric").loc["Difference vs manager plan", "value"],
            1,
        )

        recommended_row = comparison_frame.loc[
            comparison_frame["plan_name"] == "Financial Recommendation"
        ].iloc[0]
        self.assertEqual(recommended_row["staffing_agents"], 10)
        self.assertEqual(recommended_row["capacity_confidence_pct"], 90.0)
        self.assertEqual(recommended_row["expected_overtime_hours"], 1.7)
        self.assertEqual(recommended_row["expected_abandoned_total"], 1.0)
        self.assertEqual(recommended_row["expected_total_economic_cost_usd"], 401.5)
        self.assertEqual(recommended_row["delta_staffing_vs_recommendation"], 0)
        self.assertEqual(
            recommended_row["delta_total_economic_cost_usd_vs_recommendation"],
            0.0,
        )

    def test_plan_comparison_frame_rejects_missing_recommendation_row(self) -> None:
        comparison_table = self._build_comparison_table().loc[
            lambda frame: frame["plan_name"] != "Financial Recommendation"
        ].reset_index(drop=True)

        with self.assertRaisesRegex(FieldValidationError, "Financial Recommendation"):
            build_plan_comparison_frame(comparison_table)

    def test_tradeoff_chart_frames_cover_all_named_plans_and_recommendation(self) -> None:
        comparison_table = self._build_comparison_table()

        frames = build_tradeoff_chart_frames(comparison_table)

        self.assertEqual(set(frames), {"cost", "overtime", "abandonment"})
        for frame in frames.values():
            self.assertEqual(
                frame["plan_name"].tolist(),
                [
                    "Previous Week",
                    "Manager Plan",
                    "Lean",
                    "Balanced",
                    "Conservative",
                    "Financial Recommendation",
                ],
            )
            self.assertEqual(len(frame), 6)

    def test_export_frame_builder_collects_the_core_structured_outputs(self) -> None:
        forecast_result = pd.DataFrame(
            [
                {
                    "category": "simple",
                    "point_forecast": 12.0,
                    "forecast_source": "automatic",
                    "historical_mean": 11.0,
                    "historical_std": 1.0,
                    "adjusted_std": 1.1,
                }
            ]
        )
        staffing_evaluation_table = pd.DataFrame(
            [
                {
                    "staffing_agents": 10,
                    "capacity_confidence": 0.9,
                    "expected_overtime_hours": 1.7,
                    "expected_abandoned_total": 1.0,
                    "expected_total_economic_cost": 401.5,
                }
            ]
        )
        named_plan_table = pd.DataFrame([{"plan_name": "Balanced", "staffing_agents": 9}])
        comparison_table = self._build_comparison_table()
        recommendation_summary = build_recommendation_summary_frame(
            self._build_recommendation(),
            comparison_table,
        )
        comparison_display = build_plan_comparison_frame(comparison_table)

        exports = build_results_export_frames(
            {
                "forecast_result": forecast_result,
                "staffing_evaluation_table": staffing_evaluation_table,
                "named_plans": {"table": named_plan_table},
                "narrative": {"comparison_table": comparison_table},
            },
            recommendation_summary,
            comparison_display,
        )

        self.assertEqual(
            set(exports),
            {
                "forecast_result",
                "staffing_evaluation_table",
                "named_plan_table",
                "comparison_table",
                "plan_comparison_display",
                "recommendation_summary",
            },
        )
        self.assertEqual(exports["forecast_result"].iloc[0]["category"], "simple")
        self.assertIsNot(exports["forecast_result"], forecast_result)
        self.assertEqual(
            exports["plan_comparison_display"]["plan_name"].tolist(),
            [
                "Previous Week",
                "Manager Plan",
                "Lean",
                "Balanced",
                "Conservative",
                "Financial Recommendation",
            ],
        )


class UIDemandRenderingTests(unittest.TestCase):
    class _DummyContext:
        def __enter__(self) -> "UIDemandRenderingTests._DummyContext":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class _DummyColumn(_DummyContext):
        def metric(self, *args: object, **kwargs: object) -> None:
            return None

        def toggle(self, *args: object, key: str, **kwargs: object) -> bool:
            return bool(components.st.session_state[key])

        def form_submit_button(self, *args: object, **kwargs: object) -> bool:
            return False

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

    def _build_application_result(self) -> dict[str, object]:
        return build_application_result(
            history=self._build_history(),
            category_assumptions=(
                CategoryAssumptions("simple", 15.0, 400.0, 80.0),
                CategoryAssumptions("standard", 35.0, 1800.0, 360.0),
                CategoryAssumptions("complex_group", 75.0, 6000.0, 1200.0),
                CategoryAssumptions("change_cancellation", 20.0, 75.0, 25.0),
            ),
            workforce_assumptions=WorkforceAssumptions(40.0, 0.85, 22.0, 1.5, 0.1, 9),
            forecast_configuration=ForecastConfiguration((0.4, 0.3, 0.2, 0.1), 1.0, None),
            simulation_configuration=SimulationConfiguration(200, 510, 1.0, "normal"),
            confidence_targets=ConfidenceTargets(0.5, 0.85, 0.95),
            manual_overrides=None,
        )

    def test_render_demand_inputs_does_not_call_orchestration_for_preview(self) -> None:
        session_state = {
            "forecast_mode": "automatic",
            "weeks_to_display": 12,
            "analysis_result": self._build_application_result(),
            "analysis_error": None,
            "results_stale": False,
            "applied_inputs": {
                "manual_overrides": {
                    category: {"enabled": False, "value": 0.0}
                    for category in RESERVATION_CATEGORIES
                }
            },
        }
        for category in RESERVATION_CATEGORIES:
            session_state[manual_override_enabled_key(category)] = False
            session_state[manual_override_value_key(category)] = 0.0

        dummy_context = self._DummyContext()
        with mock.patch.object(components, "_load_history", return_value=self._build_history()), mock.patch.object(
            components,
            "_load_defaults",
            return_value={
                "forecast_configuration": ForecastConfiguration((0.4, 0.3, 0.2, 0.1), 1.0, None)
            },
        ), mock.patch.object(components, "run_analysis_for_current_draft") as run_mock, mock.patch.object(
            components,
            "update_draft_inputs_from_widgets",
        ) as draft_mock, mock.patch.object(
            components.st,
            "session_state",
            session_state,
        ), mock.patch.object(
            components.st,
            "subheader",
        ), mock.patch.object(
            components.st,
            "write",
        ), mock.patch.object(
            components.st,
            "caption",
        ), mock.patch.object(
            components.st,
            "metric",
        ), mock.patch.object(
            components.st,
            "dataframe",
        ), mock.patch.object(
            components.st,
            "bar_chart",
        ), mock.patch.object(
            components.st,
            "markdown",
        ), mock.patch.object(
            components.st,
            "warning",
        ), mock.patch.object(
            components.st,
            "error",
        ), mock.patch.object(
            components.st,
            "columns",
            side_effect=lambda spec, **kwargs: [self._DummyColumn() for _ in range(len(spec) if isinstance(spec, tuple) else spec)],
        ), mock.patch.object(
            components.st,
            "container",
            return_value=dummy_context,
        ), mock.patch.object(
            components.st,
            "expander",
            return_value=dummy_context,
        ), mock.patch.object(
            components.st,
            "form",
            return_value=dummy_context,
        ), mock.patch.object(
            components.st,
            "number_input",
            side_effect=lambda *args, key, **kwargs: session_state[key],
        ), mock.patch.object(
            components.st,
            "json",
        ):
            components.render_demand_inputs(session_state)

        draft_mock.assert_not_called()
        run_mock.assert_not_called()



if __name__ == "__main__":
    unittest.main()
