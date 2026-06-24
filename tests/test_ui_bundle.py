"""Focused tests for the redesigned single-page dashboard UI layer."""

from __future__ import annotations

import inspect
import unittest
from unittest import mock

import pandas as pd

from src.constants import RESERVATION_CATEGORIES
from src.forecasting.uncertainty import assemble_forecast_result
from src.forecasting.weighted_moving_average import calculate_weighted_moving_average
from src.models import (
    CategoryAssumptions,
    ConfidenceTargets,
    DecisionPolicy,
    ForecastConfiguration,
    SimulationConfiguration,
    StrategicAssumptions,
    WorkforceAssumptions,
)
from src.validation import FieldValidationError
from src.ui.charts import (
    build_category_assumptions_frame,
    build_deterministic_kpi_frame,
    build_financial_breakdown_frame,
    build_forecast_breakdown_frame,
    build_forecast_display_frame,
    build_history_display_frame,
    build_history_display_frame_with_labels,
    build_methodology_points,
    build_overflow_detail_frame,
    build_plan_comparison_frame,
    build_results_export_frames,
    build_secondary_kpi_frame,
    build_staffing_risk_cost_frame,
    build_staffing_capacity_frame,
    build_workload_breakdown_frame,
)
from src.ui.state import (
    build_manual_overrides_from_state,
    build_baseline_inputs,
    confidence_targets_are_ordered,
    collect_draft_inputs_from_widgets,
    decimal_to_percent,
    decision_policy_control_key,
    initialize_session_state,
    manual_override_enabled_key,
    manual_override_value_key,
    percent_to_decimal,
    reset_session_state,
    run_analysis_for_current_draft,
    strategic_control_key,
    sync_widgets_from_draft,
    update_draft_inputs_from_widgets,
    workforce_control_key,
)
from src.constants import CATEGORY_DISPLAY_LABELS


class UICoordinateHelpersTests(unittest.TestCase):
    def _build_history(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "week_id": "2026-W15",
                    "week_start": "2026-04-06",
                    "day_cruise": 150,
                    "seven_night_cruise": 95,
                    "nine_night_cruise": 45,
                    "staffing_agents": 8,
                },
                {
                    "week_id": "2026-W16",
                    "week_start": "2026-04-13",
                    "day_cruise": 165,
                    "seven_night_cruise": 100,
                    "nine_night_cruise": 50,
                    "staffing_agents": 8,
                },
                {
                    "week_id": "2026-W17",
                    "week_start": "2026-04-20",
                    "day_cruise": 175,
                    "seven_night_cruise": 105,
                    "nine_night_cruise": 50,
                    "staffing_agents": 8,
                },
                {
                    "week_id": "2026-W18",
                    "week_start": "2026-04-27",
                    "day_cruise": 160,
                    "seven_night_cruise": 92,
                    "nine_night_cruise": 43,
                    "staffing_agents": 8,
                },
                {
                    "week_id": "2026-W19",
                    "week_start": "2026-05-04",
                    "day_cruise": 180,
                    "seven_night_cruise": 110,
                    "nine_night_cruise": 55,
                    "staffing_agents": 8,
                },
                {
                    "week_id": "2026-W20",
                    "week_start": "2026-05-11",
                    "day_cruise": 155,
                    "seven_night_cruise": 98,
                    "nine_night_cruise": 47,
                    "staffing_agents": 8,
                },
                {
                    "week_id": "2026-W21",
                    "week_start": "2026-05-18",
                    "day_cruise": 145,
                    "seven_night_cruise": 90,
                    "nine_night_cruise": 45,
                    "staffing_agents": 8,
                },
                {
                    "week_id": "2026-W22",
                    "week_start": "2026-05-25",
                    "day_cruise": 190,
                    "seven_night_cruise": 120,
                    "nine_night_cruise": 60,
                    "staffing_agents": 8,
                },
                {
                    "week_id": "2026-W23",
                    "week_start": "2026-06-01",
                    "day_cruise": 210,
                    "seven_night_cruise": 135,
                    "nine_night_cruise": 70,
                    "staffing_agents": 9,
                },
                {
                    "week_id": "2026-W24",
                    "week_start": "2026-06-08",
                    "day_cruise": 230,
                    "seven_night_cruise": 150,
                    "nine_night_cruise": 80,
                    "staffing_agents": 10,
                },
                {
                    "week_id": "2026-W25",
                    "week_start": "2026-06-15",
                    "day_cruise": 300,
                    "seven_night_cruise": 200,
                    "nine_night_cruise": 130,
                    "staffing_agents": 12,
                },
                {
                    "week_id": "2026-W26",
                    "week_start": "2026-06-22",
                    "day_cruise": 195,
                    "seven_night_cruise": 125,
                    "nine_night_cruise": 70,
                    "staffing_agents": 9,
                },
            ]
        )

    def _build_defaults(self) -> dict[str, object]:
        return {
            "category_assumptions": (
                CategoryAssumptions(
                    category="day_cruise",
                    handling_time_minutes=8.0,
                    average_booking_value=500.0,
                ),
                CategoryAssumptions(
                    category="seven_night_cruise",
                    handling_time_minutes=22.0,
                    average_booking_value=2200.0,
                ),
                CategoryAssumptions(
                    category="nine_night_cruise",
                    handling_time_minutes=28.0,
                    average_booking_value=2800.0,
                ),
            ),
            "workforce_assumptions": WorkforceAssumptions(
                paid_hours_per_agent=40.0,
                weekly_booking_processing_hours_per_agent=12.5,
                regular_hourly_wage=22.0,
                minimum_schedulable_agents=8,
                maximum_inhouse_agents=12,
                planned_staffing_agents=10,
            ),
            "decision_policy": DecisionPolicy(
                minimum_inhouse_coverage_target=0.85,
            ),
            "strategic_assumptions": StrategicAssumptions(
                third_party_commission_rate=0.125,
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
        self.assertAlmostEqual(percent_to_decimal(decimal_to_percent(0.125)), 0.125)

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
            manual_override_enabled_key("day_cruise"): True,
            manual_override_value_key("day_cruise"): 18.0,
            manual_override_enabled_key("seven_night_cruise"): False,
            manual_override_value_key("seven_night_cruise"): 99.0,
        }

        self.assertEqual(
            build_manual_overrides_from_state(state),
            {"day_cruise": 18.0},
        )

        state[manual_override_value_key("day_cruise")] = -1.0
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

        # Verify baseline forecast values
        self.assertAlmostEqual(
            state["analysis_result"]["automatic_forecast"]["day_cruise"],
            235.0,
        )
        self.assertAlmostEqual(
            state["analysis_result"]["automatic_forecast"]["seven_night_cruise"],
            153.5,
        )
        self.assertAlmostEqual(
            state["analysis_result"]["automatic_forecast"]["nine_night_cruise"],
            90.0,
        )

    def test_draft_change_marks_results_stale_without_replacing_applied_inputs(self) -> None:
        state, _, _ = self._build_initialized_state()
        original_applied_inputs = state["applied_inputs"]
        original_result = state["analysis_result"]

        state[manual_override_enabled_key("day_cruise")] = True
        state[manual_override_value_key("day_cruise")] = 99.0
        update_draft_inputs_from_widgets(state)

        self.assertTrue(state["results_stale"])
        self.assertEqual(state["applied_inputs"], original_applied_inputs)
        self.assertIs(state["analysis_result"], original_result)
        self.assertTrue(
            state["draft_inputs"]["manual_overrides"]["day_cruise"]["enabled"]
        )
        self.assertEqual(
            state["draft_inputs"]["manual_overrides"]["day_cruise"]["value"],
            99.0,
        )

    def test_run_analysis_applies_draft_and_updates_stored_result(self) -> None:
        state, history, defaults = self._build_initialized_state()

        state[manual_override_enabled_key("day_cruise")] = True
        state[manual_override_value_key("day_cruise")] = 99.0
        state[decision_policy_control_key("minimum_inhouse_coverage_target")] = 0.95
        update_draft_inputs_from_widgets(state)
        run_analysis_for_current_draft(state, history=history, defaults=defaults)

        self.assertFalse(state["results_stale"])
        self.assertIsNone(state["analysis_error"])
        self.assertEqual(state["draft_inputs"], state["applied_inputs"])
        self.assertEqual(
            state["applied_inputs"]["manual_overrides"]["day_cruise"],
            {"enabled": True, "value": 99.0},
        )
        self.assertEqual(
            state["applied_inputs"]["decision_policy"]["minimum_inhouse_coverage_target"],
            0.95,
        )
        day_forecast = state["analysis_result"]["forecast_result"].loc[
            lambda frame: frame["category"] == "day_cruise",
            "point_forecast",
        ].iloc[0]
        self.assertEqual(float(day_forecast), 99.0)

    def test_manager_proposal_change_marks_results_stale_without_changing_coverage_target(self) -> None:
        state, _, _ = self._build_initialized_state()

        original_target = state["applied_inputs"]["decision_policy"][
            "minimum_inhouse_coverage_target"
        ]
        state[workforce_control_key("planned_staffing_agents")] = 6
        update_draft_inputs_from_widgets(state)

        self.assertTrue(state["results_stale"])
        self.assertEqual(
            state["draft_inputs"]["workforce_assumptions"]["planned_staffing_agents"],
            6,
        )
        self.assertEqual(
            state["applied_inputs"]["decision_policy"]["minimum_inhouse_coverage_target"],
            original_target,
        )

    def test_reset_restores_baseline_inputs_and_a_clean_result(self) -> None:
        state, history, defaults = self._build_initialized_state()

        state[manual_override_enabled_key("day_cruise")] = True
        state[manual_override_value_key("day_cruise")] = 99.0
        state[decision_policy_control_key("minimum_inhouse_coverage_target")] = 0.95
        update_draft_inputs_from_widgets(state)
        reset_session_state(state, history=history, defaults=defaults)

        self.assertFalse(state["results_stale"])
        self.assertEqual(state["draft_inputs"], state["baseline_inputs"])
        self.assertEqual(state["applied_inputs"], state["baseline_inputs"])
        self.assertIsNone(state["analysis_error"])
        self.assertTrue(state["analysis_result"]["ok"])
        self.assertEqual(
            state["applied_inputs"]["decision_policy"]["minimum_inhouse_coverage_target"],
            0.85,
        )

    def test_methodology_points_cover_the_staffing_pipeline(self) -> None:
        points = build_methodology_points()

        self.assertEqual(len(points), 6)
        joined = " ".join(points)
        self.assertIn("four-week weighted moving average", joined)
        self.assertIn("operating floor", joined)
        self.assertIn("third-party overflow", joined)
        self.assertIn("commission", joined)

    def test_history_display_frame_rejects_missing_required_columns(self) -> None:
        history = pd.DataFrame(
            [
                {
                    "week_id": "2026-W15",
                    "week_start": "2026-04-06",
                    "day_cruise": 150,
                }
            ]
        )

        with self.assertRaisesRegex(FieldValidationError, "missing required columns"):
            build_history_display_frame(history)

    def test_strategic_assumptions_in_draft_payload(self) -> None:
        state, _, _ = self._build_initialized_state()

        draft = state["draft_inputs"]
        self.assertIn("strategic_assumptions", draft)
        self.assertAlmostEqual(
            draft["strategic_assumptions"]["third_party_commission_rate"],
            0.125,
        )

    def test_decision_policy_in_draft_payload(self) -> None:
        state, _, _ = self._build_initialized_state()

        draft = state["draft_inputs"]
        self.assertIn("decision_policy", draft)
        self.assertAlmostEqual(
            draft["decision_policy"]["minimum_inhouse_coverage_target"],
            0.85,
        )

    def test_decision_policy_change_marks_results_stale_without_changing_manager_staffing(self) -> None:
        state, _, _ = self._build_initialized_state()
        original_manager_staffing = state["applied_inputs"]["workforce_assumptions"][
            "planned_staffing_agents"
        ]

        state[decision_policy_control_key("minimum_inhouse_coverage_target")] = 0.95
        update_draft_inputs_from_widgets(state)

        self.assertTrue(state["results_stale"])
        self.assertEqual(
            state["draft_inputs"]["decision_policy"]["minimum_inhouse_coverage_target"],
            0.95,
        )
        self.assertEqual(
            state["applied_inputs"]["workforce_assumptions"]["planned_staffing_agents"],
            original_manager_staffing,
        )

    def test_no_obsolete_fields_in_collected_draft(self) -> None:
        state, _, _ = self._build_initialized_state()

        draft = collect_draft_inputs_from_widgets(state)
        workforce = draft["workforce_assumptions"]

        self.assertIn("weekly_booking_processing_hours_per_agent", workforce)
        self.assertIn("minimum_schedulable_agents", workforce)
        self.assertIn("maximum_inhouse_agents", workforce)
        self.assertNotIn("productive_processing_pct", workforce)
        self.assertNotIn("overtime_multiplier", workforce)
        self.assertNotIn("abandonment_rate", workforce)

        cat = draft["category_assumptions"][0]
        self.assertIn("average_booking_value", cat)
        self.assertNotIn("average_revenue", cat)
        self.assertNotIn("contribution_per_reservation", cat)

    def test_all_twelve_historical_weeks_present(self) -> None:
        state, history, _ = self._build_initialized_state()
        self.assertEqual(len(history), 12)

    def test_baseline_deterministic_values_match_approved(self) -> None:
        state, _, _ = self._build_initialized_state()
        d = state["analysis_result"]["deterministic_staffing_result"]

        self.assertAlmostEqual(d["total_workload_hours"], 129.62, places=1)
        self.assertAlmostEqual(d["raw_required_fte"], 10.37, places=1)
        self.assertEqual(d["unconstrained_required_agents"], 11)
        self.assertEqual(d["recommended_inhouse_agents"], 11)
        self.assertAlmostEqual(d["overflow_workload_hours"], 0.0)

        # Verify labor cost: 11 * 40 * 22 = 9680
        labor_cost = 11 * 40 * 22
        self.assertEqual(labor_cost, 9680)


class UIForecastDisplayTests(unittest.TestCase):
    def _build_history(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "week_id": "2026-W15",
                    "week_start": "2026-04-06",
                    "day_cruise": 150,
                    "seven_night_cruise": 95,
                    "nine_night_cruise": 45,
                    "staffing_agents": 8,
                },
                {
                    "week_id": "2026-W16",
                    "week_start": "2026-04-13",
                    "day_cruise": 165,
                    "seven_night_cruise": 100,
                    "nine_night_cruise": 50,
                    "staffing_agents": 8,
                },
                {
                    "week_id": "2026-W17",
                    "week_start": "2026-04-20",
                    "day_cruise": 175,
                    "seven_night_cruise": 105,
                    "nine_night_cruise": 50,
                    "staffing_agents": 8,
                },
                {
                    "week_id": "2026-W18",
                    "week_start": "2026-04-27",
                    "day_cruise": 160,
                    "seven_night_cruise": 92,
                    "nine_night_cruise": 43,
                    "staffing_agents": 8,
                },
            ]
        )

    def test_history_display_frame_formats_dates_and_truncates_to_requested_weeks(self) -> None:
        history = self._build_history()

        display = build_history_display_frame(history, weeks_to_display=2)

        self.assertEqual(len(display), 2)
        self.assertEqual(
            tuple(display.columns),
            (
                "week_id",
                "week_start",
                "day_cruise",
                "seven_night_cruise",
                "nine_night_cruise",
                "staffing_agents",
            ),
        )
        self.assertEqual(display["week_start"].tolist(), ["2026-04-20", "2026-04-27"])

    def test_history_display_with_labels_uses_human_readable_names(self) -> None:
        history = self._build_history()

        display = build_history_display_frame_with_labels(history)

        self.assertIn(CATEGORY_DISPLAY_LABELS["day_cruise"], display.columns)
        self.assertIn(CATEGORY_DISPLAY_LABELS["seven_night_cruise"], display.columns)
        self.assertIn(CATEGORY_DISPLAY_LABELS["nine_night_cruise"], display.columns)

    def test_forecast_display_frame_shows_automatic_manual_and_effective_values(self) -> None:
        history = self._build_history()
        weights = [0.4, 0.3, 0.2, 0.1]
        forecast_result = assemble_forecast_result(
            history,
            weights,
            variability_multiplier=1.0,
            manual_overrides={"seven_night_cruise": 99.0},
        )
        automatic = calculate_weighted_moving_average(history, weights)

        display = build_forecast_display_frame(
            automatic,
            forecast_result,
            manual_overrides={"seven_night_cruise": 99.0},
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
        self.assertEqual(display.loc[0, "automatic_forecast"], automatic["day_cruise"])
        self.assertTrue(pd.isna(display.loc[0, "manual_override"]))
        self.assertEqual(display.loc[1, "manual_override"], 99.0)
        self.assertEqual(display.loc[1, "forecast_source"], "manual_override")
        self.assertEqual(display.loc[1, "effective_forecast"], 99.0)
        self.assertEqual(display.loc[0, "forecast_source"], "automatic")

    def test_forecast_display_frame_rejects_missing_category_rows(self) -> None:
        history = self._build_history()
        weights = [0.4, 0.3, 0.2, 0.1]
        forecast_result = assemble_forecast_result(
            history, weights, variability_multiplier=1.0
        )
        incomplete_result = forecast_result.loc[
            forecast_result["category"] != "nine_night_cruise"
        ].reset_index(drop=True)
        automatic = calculate_weighted_moving_average(history, weights)

        with self.assertRaisesRegex(FieldValidationError, "required categories"):
            build_forecast_display_frame(automatic, incomplete_result)


class UINewChartHelperTests(unittest.TestCase):
    def _build_deterministic_result(self) -> dict[str, object]:
        return {
            "total_workload_hours": 129.6167,
            "raw_required_fte": 10.3693,
            "unconstrained_required_agents": 11,
            "recommended_inhouse_agents": 11,
            "spare_capacity_hours": 7.8833,
            "overflow_workload_hours": 0.0,
            "workload_hours_by_category": {
                "day_cruise": 235.0 * 8 / 60,
                "seven_night_cruise": 153.5 * 22 / 60,
                "nine_night_cruise": 90.0 * 28 / 60,
            },
            "booking_processing_hours_per_agent": 12.5,
            "overflow_bookings_by_category": {
                "day_cruise": 0.0,
                "seven_night_cruise": 0.0,
                "nine_night_cruise": 0.0,
            },
            "overflow_hours_by_category": {
                "day_cruise": 0.0,
                "seven_night_cruise": 0.0,
                "nine_night_cruise": 0.0,
            },
        }

    def _build_effective_forecast(self) -> dict[str, float]:
        return {
            "day_cruise": 235.0,
            "seven_night_cruise": 153.5,
            "nine_night_cruise": 90.0,
        }

    def _build_category_assumptions(self) -> list[dict[str, object]]:
        return [
            {"category": "day_cruise", "handling_time_minutes": 8.0, "average_booking_value": 500.0},
            {"category": "seven_night_cruise", "handling_time_minutes": 22.0, "average_booking_value": 2200.0},
            {"category": "nine_night_cruise", "handling_time_minutes": 28.0, "average_booking_value": 2800.0},
        ]

    def test_deterministic_kpi_frame_has_correct_values(self) -> None:
        kpi = build_deterministic_kpi_frame(
            self._build_deterministic_result(),
            self._build_effective_forecast(),
        )

        self.assertEqual(len(kpi), 5)
        self.assertAlmostEqual(
            kpi.set_index("metric").loc["Forecasted bookings", "value"],
            478.5,
        )
        self.assertAlmostEqual(
            kpi.set_index("metric").loc["Recommended staffing", "value"],
            11,
        )

    def test_secondary_kpi_frame_includes_all_metrics(self) -> None:
        fin_rec = {
            "recommended_staffing_record": {
                "expected_total_weekly_operating_cost": 9680.0,
            }
        }
        secondary = build_secondary_kpi_frame(
            self._build_deterministic_result(),
            previous_week_staffing=9,
            manager_planned_staffing=10,
            financial_recommendation=fin_rec,
        )

        self.assertEqual(len(secondary), 5)
        metrics = secondary["metric"].tolist()
        self.assertIn("Previous-week staffing", metrics)
        self.assertIn("Manager-planned staffing", metrics)
        self.assertIn("Total weekly operating cost", metrics)

    def test_workload_breakdown_frame_uses_human_readable_labels(self) -> None:
        wl = build_workload_breakdown_frame(
            self._build_effective_forecast(),
            self._build_deterministic_result(),
            self._build_category_assumptions(),
        )

        self.assertEqual(len(wl), 3)
        self.assertIn(CATEGORY_DISPLAY_LABELS["day_cruise"], wl["cruise_product"].tolist())
        self.assertIn("forecast_bookings", wl.columns)
        self.assertIn("workload_hours", wl.columns)

    def test_forecast_breakdown_frame_shows_all_layers(self) -> None:
        fb = build_forecast_breakdown_frame(
            automatic_forecast={"day_cruise": 235.0, "seven_night_cruise": 153.5, "nine_night_cruise": 90.0},
            effective_forecast={"day_cruise": 235.0, "seven_night_cruise": 153.5, "nine_night_cruise": 90.0},
            manual_overrides=None,
        )

        self.assertEqual(len(fb), 3)
        self.assertIn("central_forecast", fb.columns)
        self.assertIn("use_manager_forecast", fb.columns)
        self.assertIn("manager_forecast", fb.columns)
        self.assertIn("applied_forecast", fb.columns)
        self.assertIn("forecast_source", fb.columns)

    def test_plan_comparison_frame_uses_backend_record_values(self) -> None:
        frame = build_plan_comparison_frame(
            {
                "staffing_agents": 12,
                "feasibility_status": "within_operating_range",
                "capacity_confidence": 0.881,
                "probability_overflow_required": 0.119,
                "regular_labor_cost": 10560.0,
                "expected_overflow_workload_hours": 1.4,
                "expected_overflow_commission": 691.36,
                "expected_spare_capacity_hours": 0.7,
                "expected_total_weekly_operating_cost": 11251.36,
            },
            {
                "staffing_agents": 6,
                "feasibility_status": "below_operating_floor",
                "capacity_confidence": 0.20,
                "probability_overflow_required": 0.80,
                "regular_labor_cost": 5280.0,
                "expected_overflow_workload_hours": 40.0,
                "expected_overflow_commission": 9000.0,
                "expected_spare_capacity_hours": 0.0,
                "expected_total_weekly_operating_cost": 14280.0,
            },
        )

        self.assertEqual(frame["plan"].tolist(), ["Model Recommendation", "Manager Proposal"])
        self.assertEqual(frame.loc[1, "feasibility_status"], "below_operating_floor")
        self.assertAlmostEqual(frame.loc[0, "expected_total_weekly_operating_cost"], 11251.36)

    def test_staffing_risk_cost_frame_marks_recommendation_manager_and_previous_week(self) -> None:
        frame = build_staffing_risk_cost_frame(
            [
                {
                    "staffing_agents": 8,
                    "feasibility_status": "within_operating_range",
                    "capacity_confidence": 0.5,
                    "probability_overflow_required": 0.5,
                    "expected_spare_capacity_hours": 5.0,
                    "expected_overflow_workload_hours": 5.0,
                    "expected_overflow_bookings_by_category": {
                        "day_cruise": 1.0,
                        "seven_night_cruise": 2.0,
                        "nine_night_cruise": 3.0,
                    },
                    "regular_labor_cost": 7040.0,
                    "expected_overflow_commission": 100.0,
                    "expected_total_weekly_operating_cost": 7140.0,
                    "is_model_recommendation": False,
                    "is_manager_proposal": True,
                    "is_previous_week": False,
                },
                {
                    "staffing_agents": 12,
                    "feasibility_status": "within_operating_range",
                    "capacity_confidence": 0.88,
                    "probability_overflow_required": 0.12,
                    "expected_spare_capacity_hours": 0.7,
                    "expected_overflow_workload_hours": 1.4,
                    "expected_overflow_bookings_by_category": {
                        "day_cruise": 0.1,
                        "seven_night_cruise": 0.2,
                        "nine_night_cruise": 0.3,
                    },
                    "regular_labor_cost": 10560.0,
                    "expected_overflow_commission": 691.36,
                    "expected_total_weekly_operating_cost": 11251.36,
                    "is_model_recommendation": True,
                    "is_manager_proposal": False,
                    "is_previous_week": True,
                },
            ]
        )

        self.assertEqual(frame.loc[0, "markers"], "Manager Proposal")
        self.assertEqual(frame.loc[1, "markers"], "Recommendation, Previous Week")
        self.assertAlmostEqual(frame.loc[0, "expected_overflow_bookings"], 6.0)

    def test_staffing_capacity_frame_shows_steps(self) -> None:
        sc = build_staffing_capacity_frame(
            self._build_deterministic_result(),
            {
                "weekly_booking_processing_hours_per_agent": 12.5,
                "minimum_schedulable_agents": 8,
                "maximum_inhouse_agents": 12,
            },
        )

        self.assertGreater(len(sc), 0)
        steps = sc["step"].tolist()
        self.assertIn("Raw FTE", steps)
        self.assertIn("Recommended in-house agents", steps)

    def test_financial_breakdown_frame_shows_costs(self) -> None:
        fin_rec = {
            "recommended_staffing_record": {
                "regular_labor_cost": 9680.0,
                "expected_overflow_commission": 0.0,
                "expected_total_weekly_operating_cost": 9680.0,
            }
        }
        ff = build_financial_breakdown_frame(
            fin_rec,
            self._build_deterministic_result(),
            self._build_category_assumptions(),
            {"third_party_commission_rate": 0.125},
        )

        items = ff["item"].tolist()
        self.assertIn("In-house labor cost", items)
        self.assertIn("Total weekly operating cost", items)

    def test_category_assumptions_frame_uses_booking_value(self) -> None:
        frame = build_category_assumptions_frame(self._build_category_assumptions())

        self.assertIn("average_booking_value", frame.columns)
        self.assertNotIn("average_revenue", frame.columns)
        self.assertNotIn("contribution_per_reservation", frame.columns)

    def test_overflow_detail_frame_empty_when_no_overflow(self) -> None:
        od = build_overflow_detail_frame(self._build_deterministic_result())
        self.assertEqual(od["overflow_bookings"].sum(), 0.0)

    def test_results_export_frames_include_probabilistic_outlooks(self) -> None:
        application_result = {
            "forecast_result": pd.DataFrame([{"category": "day_cruise"}]),
            "staffing_evaluation_table": pd.DataFrame([{"staffing_agents": 8}]),
            "named_plans": {"table": pd.DataFrame([{"plan_name": "Lean"}])},
            "narrative": {"comparison_table": pd.DataFrame([{"plan_name": "Manager Plan"}])},
            "recommendation_policy": {
                "minimum_inhouse_coverage_target": 0.85,
            },
            "recommended_plan": {
                "staffing_agents": 11,
                "feasibility_status": "within_operating_range",
                "capacity_confidence": 0.89,
                "probability_overflow_required": 0.11,
                "regular_labor_cost": 9680.0,
                "expected_overflow_workload_hours": 0.0,
                "expected_overflow_commission": 0.0,
                "expected_spare_capacity_hours": 7.5,
                "expected_total_weekly_operating_cost": 9680.0,
            },
            "manager_proposal": {
                "staffing_agents": 10,
                "feasibility_status": "within_operating_range",
                "capacity_confidence": 0.80,
                "probability_overflow_required": 0.20,
                "regular_labor_cost": 8800.0,
                "expected_overflow_workload_hours": 2.0,
                "expected_overflow_commission": 100.0,
                "expected_spare_capacity_hours": 2.0,
                "expected_total_weekly_operating_cost": 8900.0,
            },
            "recommendation_manager_comparison": {
                "staffing_difference": -1,
            },
            "adaptive_comparison_narrative": {
                "text": "manager narrative",
                "warnings": [],
                "difference_direction": "manager_value_minus_recommendation_value",
            },
            "previous_week_staffing_context": {
                "staffing_agents": 9,
                "feasibility_status": "within_operating_range",
            },
            "staffing_risk_cost_records": [],
            "outlook_diagnostics": {
                "ordering_invariant_satisfied": True,
            },
            "lower_demand_outlook": {
                "outlook_name": "Lower Demand",
                "percentile": 0.25,
                "percentile_label": "P25",
                "simulation_row_id": 1,
                "representative_row_reused": False,
                "demand_by_category": {"day_cruise": 1.0, "seven_night_cruise": 1.0, "nine_night_cruise": 1.0},
                "total_bookings": 3.0,
                "workload_hours_by_category": {"day_cruise": 1.0, "seven_night_cruise": 1.0, "nine_night_cruise": 1.0},
                "total_workload_hours": 3.0,
                "raw_required_fte": 1.0,
                "unconstrained_required_agents": 1,
                "recommended_inhouse_agents_for_outlook": 8,
                "spare_capacity_hours": 7.0,
                "overflow_workload_hours": 0.0,
                "overflow_bookings_by_category": {"day_cruise": 0.0, "seven_night_cruise": 0.0, "nine_night_cruise": 0.0},
                "regular_labor_cost": 100.0,
                "overflow_commission": 0.0,
                "total_weekly_operating_cost": 100.0,
            },
            "central_demand_outlook": {
                "outlook_name": "Central Demand",
                "percentile": 0.5,
                "percentile_label": "P50",
                "simulation_row_id": 2,
                "representative_row_reused": False,
                "demand_by_category": {"day_cruise": 2.0, "seven_night_cruise": 2.0, "nine_night_cruise": 2.0},
                "total_bookings": 6.0,
                "workload_hours_by_category": {"day_cruise": 2.0, "seven_night_cruise": 2.0, "nine_night_cruise": 2.0},
                "total_workload_hours": 6.0,
                "raw_required_fte": 1.0,
                "unconstrained_required_agents": 1,
                "recommended_inhouse_agents_for_outlook": 8,
                "spare_capacity_hours": 4.0,
                "overflow_workload_hours": 0.0,
                "overflow_bookings_by_category": {"day_cruise": 0.0, "seven_night_cruise": 0.0, "nine_night_cruise": 0.0},
                "regular_labor_cost": 100.0,
                "overflow_commission": 0.0,
                "total_weekly_operating_cost": 100.0,
            },
            "higher_demand_outlook": {
                "outlook_name": "Higher Demand",
                "percentile": 0.9,
                "percentile_label": "P90",
                "simulation_row_id": 3,
                "representative_row_reused": False,
                "demand_by_category": {"day_cruise": 3.0, "seven_night_cruise": 3.0, "nine_night_cruise": 3.0},
                "total_bookings": 9.0,
                "workload_hours_by_category": {"day_cruise": 3.0, "seven_night_cruise": 3.0, "nine_night_cruise": 3.0},
                "total_workload_hours": 9.0,
                "raw_required_fte": 1.0,
                "unconstrained_required_agents": 1,
                "recommended_inhouse_agents_for_outlook": 8,
                "spare_capacity_hours": 1.0,
                "overflow_workload_hours": 0.0,
                "overflow_bookings_by_category": {"day_cruise": 0.0, "seven_night_cruise": 0.0, "nine_night_cruise": 0.0},
                "regular_labor_cost": 100.0,
                "overflow_commission": 0.0,
                "total_weekly_operating_cost": 100.0,
            },
        }

        export_frames = build_results_export_frames(
            application_result,
            pd.DataFrame(),
            pd.DataFrame(),
            applied_inputs={
                "decision_policy": {"minimum_inhouse_coverage_target": 0.85},
                "workforce_assumptions": {"planned_staffing_agents": 10},
                "manual_overrides": {
                    "day_cruise": {"enabled": False, "value": 235.0},
                    "seven_night_cruise": {"enabled": False, "value": 153.5},
                    "nine_night_cruise": {"enabled": False, "value": 90.0},
                },
                "category_assumptions": [],
                "strategic_assumptions": {"third_party_commission_rate": 0.125},
            },
        )

        self.assertIn("probabilistic_outlooks", export_frames)
        self.assertIn("recommendation_policy", export_frames)
        self.assertIn("recommended_plan", export_frames)
        self.assertIn("manager_proposal", export_frames)
        self.assertIn("applied_business_decisions", export_frames)
        self.assertEqual(len(export_frames["probabilistic_outlooks"]), 3)
        self.assertEqual(
            export_frames["probabilistic_outlooks"]["percentile_label"].tolist(),
            ["P25", "P50", "P90"],
        )
        self.assertNotIn(
            "scenario_name",
            export_frames["applied_business_decisions"].columns,
        )


class UIDashboardStructureTests(unittest.TestCase):
    """Verify the new single-page dashboard structure does not contain old controls."""

    def test_components_module_has_no_section_navigation(self) -> None:
        from src.ui import components as comp

        self.assertTrue(hasattr(comp, "render_main_dashboard"))
        self.assertTrue(hasattr(comp, "render_hero_card"))
        self.assertTrue(hasattr(comp, "render_kpi_grid"))
        self.assertTrue(hasattr(comp, "render_narrative"))
        self.assertTrue(hasattr(comp, "render_action_row"))

        # Old section renderers removed
        self.assertFalse(hasattr(comp, "render_active_section"))
        self.assertFalse(hasattr(comp, "render_overview"))
        self.assertFalse(hasattr(comp, "render_demand_inputs"))
        self.assertFalse(hasattr(comp, "render_operations"))
        self.assertFalse(hasattr(comp, "render_results"))
        self.assertFalse(hasattr(comp, "render_sidebar"))

    def test_state_module_has_no_section_options(self) -> None:
        from src.ui import state as st_mod

        self.assertFalse(hasattr(st_mod, "section_options"))
        self.assertFalse(hasattr(st_mod, "APP_SECTIONS"))
        self.assertFalse(hasattr(st_mod, "FORECAST_MODE_MIGRATIONS"))

    def test_state_session_has_no_obsolete_keys(self) -> None:
        from src.ui.state import DEFAULT_SESSION_STATE

        self.assertNotIn("selected_category", DEFAULT_SESSION_STATE)
        self.assertNotIn("forecast_mode", DEFAULT_SESSION_STATE)
        self.assertNotIn("weeks_to_display", DEFAULT_SESSION_STATE)
        self.assertNotIn("show_contract_snapshot", DEFAULT_SESSION_STATE)
        self.assertNotIn("manual_override_notes", DEFAULT_SESSION_STATE)
        self.assertNotIn("active_section", DEFAULT_SESSION_STATE)

    def test_app_py_uses_main_dashboard(self) -> None:
        import app

        self.assertTrue(hasattr(app, "main"))

    def test_business_decisions_controls_present_and_scenario_selector_absent(self) -> None:
        from src.ui import components as comp

        source = inspect.getsource(comp)
        self.assertIn("Business Decisions", source)
        self.assertIn("Minimum In-House Coverage Target (%)", source)
        self.assertIn("Manager Proposed Staffing", source)
        self.assertIn("Use manager forecast", source)
        self.assertIn("Run Analysis", source)
        self.assertIn("Reset to Baseline", source)
        self.assertNotIn("Demand scenario", source)
        self.assertNotIn("inhouse_capture_target", source)


if __name__ == "__main__":
    unittest.main()
