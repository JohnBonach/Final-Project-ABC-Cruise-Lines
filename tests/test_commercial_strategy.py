"""Tests for commercial strategy helpers."""

from __future__ import annotations

import math
import unittest

import pandas as pd

from src.constants import CATEGORY_ASSUMPTIONS_COLUMNS, RESERVATION_CATEGORIES
from src.models import CategoryAssumptions
from src.strategy import build_channel_strategy, build_weekly_commercial_strategy
from src.validation import FieldValidationError


class CommercialStrategyTests(unittest.TestCase):
    def _build_category_assumptions(self) -> list[dict[str, float | str]]:
        return [
            {
                "category": "day_cruise",
                "handling_time_minutes": 8.0,
                "average_booking_value": 500.0,
            },
            {
                "category": "seven_night_cruise",
                "handling_time_minutes": 22.0,
                "average_booking_value": 2200.0,
            },
            {
                "category": "nine_night_cruise",
                "handling_time_minutes": 28.0,
                "average_booking_value": 2800.0,
            },
        ]

    def _build_application_result(self) -> dict[str, object]:
        return {
            "effective_forecast": {
                "day_cruise": 120.0,
                "seven_night_cruise": 40.0,
                "nine_night_cruise": 20.0,
            },
            "recommended_plan": {
                "probability_overflow_required": 0.12,
                "expected_spare_capacity_hours": 8.0,
            },
            "deterministic_staffing_result": {
                "booking_processing_hours_per_agent": 12.5,
            },
            "strategic_assumptions": {
                "third_party_commission_rate": 0.125,
            },
        }

    def test_build_channel_strategy_baseline_math(self) -> None:
        result = build_channel_strategy()

        self.assertEqual(result["commission_if_all_agent"], 10_000_000.0)
        self.assertEqual(result["commission_paid_target"], 5_000_000.0)
        self.assertEqual(result["gross_commission_avoided"], 5_000_000.0)
        self.assertEqual(result["net_annual_benefit"], 4_000_000.0)
        self.assertEqual(result["capture_gap_percentage_points"], 50.0)
        self.assertEqual(result["status"], "favorable")
        self.assertIn("Proceed", result["recommendation"])

    def test_build_channel_strategy_uses_current_capture_for_incremental_avoidance(self) -> None:
        result = build_channel_strategy(
            annual_revenue=20_000_000.0,
            commission_rate=0.10,
            current_capture_rate=0.25,
            target_capture_rate=0.60,
            annual_operating_cost=500_000.0,
        )

        self.assertAlmostEqual(result["commission_paid_current"], 1_500_000.0)
        self.assertAlmostEqual(result["commission_paid_target"], 800_000.0)
        self.assertAlmostEqual(result["gross_commission_avoided"], 1_200_000.0)
        self.assertAlmostEqual(result["incremental_commission_avoided"], 700_000.0)
        self.assertAlmostEqual(result["net_annual_benefit"], 700_000.0)

    def test_build_channel_strategy_rejects_invalid_money_and_rates(self) -> None:
        with self.assertRaises(FieldValidationError):
            build_channel_strategy(annual_revenue=-1.0)
        with self.assertRaises(FieldValidationError):
            build_channel_strategy(commission_rate=1.2)
        with self.assertRaises(FieldValidationError):
            build_channel_strategy(current_capture_rate=math.nan)

    def test_build_channel_strategy_flags_regressive_and_hold_targets(self) -> None:
        regressive = build_channel_strategy(
            current_capture_rate=0.60,
            target_capture_rate=0.50,
        )
        hold = build_channel_strategy(
            current_capture_rate=0.50,
            target_capture_rate=0.50,
        )

        self.assertEqual(regressive["status"], "regressive")
        self.assertIn("Do not reduce", regressive["recommendation"])
        self.assertEqual(hold["status"], "hold")
        self.assertIn("matches current", hold["recommendation"])

    def test_build_weekly_commercial_strategy_holds_when_pressure_is_moderate(self) -> None:
        result = build_weekly_commercial_strategy(
            self._build_application_result(),
            self._build_category_assumptions(),
        )

        self.assertEqual(result["recommended_action"], "Hold")
        self.assertEqual(result["recommended_price_change"], 0.0)
        self.assertEqual(len(result["actions"]), 3)
        self.assertEqual([action["action"] for action in result["actions"]], ["Protect Yield", "Hold", "Promote"])
        self.assertAlmostEqual(result["base_metrics"]["expected_bookings"], 180.0)
        self.assertAlmostEqual(result["base_metrics"]["gross_revenue"], 204_000.0)
        self.assertAlmostEqual(result["base_metrics"]["commission_paid"], 12_750.0)
        self.assertAlmostEqual(result["base_metrics"]["net_revenue_after_channel_cost"], 191_250.0)
        self.assertIn("scenario estimates", result["scenario_estimate_notice"])
        self.assertIn("guardrails", result["rationale"])

    def test_build_weekly_commercial_strategy_recommends_protect_when_overflow_is_high(self) -> None:
        application_result = self._build_application_result()
        application_result["recommended_plan"] = {
            "probability_overflow_required": 0.20,
            "expected_spare_capacity_hours": 1.0,
        }

        result = build_weekly_commercial_strategy(
            application_result,
            self._build_category_assumptions(),
        )

        self.assertEqual(result["recommended_action"], "Protect Yield")
        self.assertEqual(result["recommended_price_change"], 0.10)
        self.assertAlmostEqual(result["pressure_metrics"]["overflow_guardrail_threshold"], 0.20)
        self.assertTrue(result["actions"][0]["is_recommended"])

    def test_build_weekly_commercial_strategy_recommends_promote_when_capacity_is_spare(self) -> None:
        application_result = self._build_application_result()
        application_result["recommended_plan"] = {
            "probability_overflow_required": 0.05,
            "expected_spare_capacity_hours": 10.0,
        }

        result = build_weekly_commercial_strategy(
            application_result,
            self._build_category_assumptions(),
        )

        self.assertEqual(result["recommended_action"], "Promote")
        self.assertEqual(result["recommended_price_change"], -0.08)
        self.assertTrue(result["actions"][2]["is_recommended"])
        self.assertLess(result["actions"][2]["delta_vs_hold"], 0.0)

    def test_build_weekly_commercial_strategy_uses_application_commission_rate_when_not_overridden(self) -> None:
        application_result = self._build_application_result()
        application_result["strategic_assumptions"] = {
            "third_party_commission_rate": 0.20,
        }

        result = build_weekly_commercial_strategy(
            application_result,
            self._build_category_assumptions(),
            direct_capture_rate=0.5,
        )

        self.assertEqual(result["commission_rate"], 0.20)
        self.assertAlmostEqual(result["base_metrics"]["commission_paid"], 20_400.0)

    def test_build_weekly_commercial_strategy_validates_required_fields(self) -> None:
        with self.assertRaises(FieldValidationError):
            build_weekly_commercial_strategy({}, self._build_category_assumptions())

        bad_application_result = self._build_application_result()
        del bad_application_result["effective_forecast"]
        with self.assertRaises(FieldValidationError):
            build_weekly_commercial_strategy(bad_application_result, self._build_category_assumptions())

    def test_build_weekly_commercial_strategy_accepts_dataframe_category_assumptions(self) -> None:
        category_frame = pd.DataFrame(self._build_category_assumptions(), columns=CATEGORY_ASSUMPTIONS_COLUMNS)
        result = build_weekly_commercial_strategy(
            self._build_application_result(),
            category_frame,
        )

        self.assertEqual(tuple(result["effective_forecast"].keys()), RESERVATION_CATEGORIES)
        self.assertEqual(tuple(result["category_average_booking_value"].keys()), RESERVATION_CATEGORIES)
        self.assertEqual(tuple(result["actions"][0]["expected_bookings_by_category"].keys()), RESERVATION_CATEGORIES)

    def test_build_weekly_commercial_strategy_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(FieldValidationError):
            build_weekly_commercial_strategy(
                self._build_application_result(),
                self._build_category_assumptions(),
                direct_capture_rate=1.5,
            )
        with self.assertRaises(FieldValidationError):
            build_weekly_commercial_strategy(
                self._build_application_result(),
                self._build_category_assumptions(),
                price_elasticity=-0.1,
            )
        with self.assertRaises(FieldValidationError):
            build_weekly_commercial_strategy(
                self._build_application_result(),
                self._build_category_assumptions(),
                promotion_cost=-1.0,
            )


if __name__ == "__main__":
    unittest.main()
