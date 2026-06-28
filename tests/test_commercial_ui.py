"""Focused tests for the commercial strategy Streamlit renderer."""

from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

import pandas as pd

from src.ui.commercial import (
    _build_channel_business_case,
    _build_channel_scenario_frame,
    _build_weekly_action_frame,
    _build_weekly_control_metrics,
    _build_weekly_display_frame,
    _build_weekly_metrics,
    _format_currency,
    _format_percent,
    _normalize_action_name,
    commercial_control_key,
    render_commercial_strategy,
)


class FakeContextManager:
    def __enter__(self) -> "FakeContextManager":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}
        self.markdown_calls: list[str] = []
        self.caption_calls: list[str] = []
        self.metric_calls: list[tuple[str, str, object, object]] = []
        self.dataframes: list[pd.DataFrame] = []
        self.bar_charts: list[pd.DataFrame] = []
        self.alerts: list[tuple[str, str]] = []
        self.columns_calls: list[object] = []
        self.inputs: dict[str, object] = {}

    def markdown(self, text: str, **kwargs: object) -> None:
        self.markdown_calls.append(text)

    def caption(self, text: str, **kwargs: object) -> None:
        self.caption_calls.append(text)

    def columns(self, spec, gap: str | None = None):
        count = spec if isinstance(spec, int) else len(spec)
        self.columns_calls.append(spec)
        return [FakeContextManager() for _ in range(count)]

    def number_input(self, label: str, **kwargs: object):
        key = kwargs.get("key")
        if key in self.inputs:
            return self.inputs[key]
        return kwargs.get("value")

    def slider(self, label: str, **kwargs: object):
        key = kwargs.get("key")
        if key in self.inputs:
            return self.inputs[key]
        return kwargs.get("value")

    def dataframe(self, frame, **kwargs: object) -> None:
        self.dataframes.append(frame.copy(deep=True))

    def bar_chart(self, frame, **kwargs: object) -> None:
        if isinstance(frame, pd.DataFrame):
            self.bar_charts.append(frame.copy(deep=True))
        else:
            self.bar_charts.append(pd.DataFrame(frame))

    def metric(self, label: str, value, delta=None, help=None) -> None:
        self.metric_calls.append((label, value, delta, help))

    def success(self, text: str, **kwargs: object) -> None:
        self.alerts.append(("success", text))

    def warning(self, text: str, **kwargs: object) -> None:
        self.alerts.append(("warning", text))

    def info(self, text: str, **kwargs: object) -> None:
        self.alerts.append(("info", text))


class CommercialUiHelperTests(unittest.TestCase):
    def test_format_helpers_render_compact_currency_and_percent_strings(self) -> None:
        self.assertEqual(_format_currency(4_000_000), "$4.0M")
        self.assertEqual(_format_currency(2_500), "$2,500")
        self.assertEqual(_format_percent(0.5), "50%")
        self.assertEqual(_format_percent(0.125, places=1), "12.5%")

    def test_business_case_helpers_build_baseline_values(self) -> None:
        business_case = _build_channel_business_case(
            {},
            {},
            annual_commissionable_revenue=80_000_000.0,
            current_direct_capture_rate=0.0,
            target_direct_capture_rate=0.5,
            annual_dss_operating_cost=1_000_000.0,
            commission_rate=0.125,
        )

        self.assertAlmostEqual(business_case["current_commission_paid"], 10_000_000.0)
        self.assertAlmostEqual(business_case["target_commission_paid"], 5_000_000.0)
        self.assertAlmostEqual(business_case["gross_commission_avoided"], 5_000_000.0)
        self.assertAlmostEqual(business_case["net_annual_benefit"], 4_000_000.0)

        scenario_frame = _build_channel_scenario_frame({}, business_case)
        self.assertEqual(scenario_frame["scenario"].tolist(), ["Current", "Target", "Stretch"])
        self.assertAlmostEqual(scenario_frame.loc[1, "commission_paid"], 5_000_000.0)

    def test_weekly_helpers_normalize_actions_and_metrics(self) -> None:
        self.assertEqual(_normalize_action_name("raise price"), "Protect Yield")
        self.assertEqual(_normalize_action_name("discount / promote"), "Promote")
        self.assertEqual(_normalize_action_name(""), "Hold")

        frame = _build_weekly_action_frame(
            {
                "action_comparison": [
                    {
                        "action": "Protect Yield",
                        "expected_net_value": 1200.0,
                        "promotion_cost": 0.0,
                    },
                    {
                        "action": "Hold",
                        "expected_net_value": 900.0,
                        "promotion_cost": 0.0,
                    },
                ]
            }
        )
        metrics = _build_weekly_metrics(
            {"kpis": {"expected_net_value": 1200.0, "direct_capture_rate": 0.5}},
            frame,
            "Protect Yield",
        )

        self.assertEqual(frame["action"].tolist(), ["Protect Yield", "Hold"])
        self.assertGreaterEqual(len(metrics), 2)
        self.assertIn("Expected Net Value", [item["label"] for item in metrics])

    def test_weekly_control_metrics_and_display_frame_expose_live_input_effects(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "action": "Protect Yield",
                    "price_change": 0.10,
                    "expected_bookings": 90.0,
                    "gross_revenue": 110_000.0,
                    "commission_paid": 6_875.0,
                    "campaign_cost": 0.0,
                    "net_revenue_after_channel_cost": 103_125.0,
                    "delta_vs_hold": 3_125.0,
                    "is_recommended": False,
                },
                {
                    "action": "Hold",
                    "price_change": 0.0,
                    "expected_bookings": 100.0,
                    "gross_revenue": 106_667.0,
                    "commission_paid": 6_666.69,
                    "campaign_cost": 0.0,
                    "net_revenue_after_channel_cost": 100_000.31,
                    "delta_vs_hold": 0.0,
                    "is_recommended": True,
                },
                {
                    "action": "Promote",
                    "price_change": -0.08,
                    "expected_bookings": 106.4,
                    "gross_revenue": 104_400.0,
                    "commission_paid": 6_525.0,
                    "campaign_cost": 2_500.0,
                    "net_revenue_after_channel_cost": 95_375.0,
                    "delta_vs_hold": -4_625.31,
                    "is_recommended": False,
                },
            ]
        )

        metrics = _build_weekly_control_metrics(frame)
        display = _build_weekly_display_frame(frame)

        self.assertEqual(len(metrics), 4)
        self.assertEqual(metrics[0]["value"], "$6,667")
        self.assertEqual(metrics[-1]["value"], "+6.4")
        self.assertIn("Net Revenue After Channel Cost", display.columns)
        self.assertNotIn("expected_bookings_by_category", display.columns)
        self.assertEqual(display.loc[1, "Recommended"], "Yes")
        self.assertEqual(display.loc[2, "Fare Change"], "-8%")


class CommercialUiRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_st = FakeStreamlit()
        self.channel_calls: list[dict[str, object]] = []
        self.weekly_calls: list[dict[str, object]] = []

        strategy_package = types.ModuleType("src.strategy")
        strategy_package.__path__ = []  # type: ignore[attr-defined]
        commercial_module = types.ModuleType("src.strategy.commercial")

        def build_channel_strategy(**kwargs):
            self.channel_calls.append(kwargs)
            return {
                "status": "favorable",
                "recommendation": "Proceed with the direct-channel capture target.",
                "commission_scenarios": [
                    {
                        "scenario": "Current",
                        "direct_capture_rate": kwargs["current_capture_rate"],
                        "commission_paid": 10_000_000.0,
                        "commission_avoided": 0.0,
                    },
                    {
                        "scenario": "Target",
                        "direct_capture_rate": kwargs["target_capture_rate"],
                        "commission_paid": 5_000_000.0,
                        "commission_avoided": 5_000_000.0,
                    },
                ],
            }

        def build_weekly_commercial_strategy(application_result, category_assumptions, **kwargs):
            self.weekly_calls.append(kwargs)
            return {
                "recommended_action": "Protect Yield",
                "rationale": "Capacity is tight and yield protection is preferred.",
                "kpis": {
                    "expected_net_value": 1200.0,
                    "direct_capture_rate": kwargs["direct_capture_rate"],
                },
                "action_comparison": [
                    {
                        "action": "Protect Yield",
                        "expected_net_value": 1200.0,
                        "promotion_cost": 0.0,
                    },
                    {
                        "action": "Hold",
                        "expected_net_value": 900.0,
                        "promotion_cost": 0.0,
                    },
                    {
                        "action": "Promote",
                        "expected_net_value": 700.0,
                        "promotion_cost": kwargs["promotion_cost"],
                    },
                ],
            }

        commercial_module.build_channel_strategy = build_channel_strategy
        commercial_module.build_weekly_commercial_strategy = build_weekly_commercial_strategy

        self._module_patches = [
            mock.patch.dict(sys.modules, {"src.strategy": strategy_package, "src.strategy.commercial": commercial_module}),
            mock.patch("src.ui.commercial.st", self.fake_st),
        ]
        for patcher in self._module_patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self._module_patches):
            patcher.stop()

    def test_render_commercial_strategy_calls_backend_and_renders_sections(self) -> None:
        application_result = {"ok": True}
        category_assumptions = [{"category": "day_cruise"}]

        self.fake_st.inputs = {
            commercial_control_key("annual_commissionable_revenue"): 80_000_000.0,
            commercial_control_key("current_direct_capture_percent"): 0.0,
            commercial_control_key("target_direct_capture_percent"): 50.0,
            commercial_control_key("annual_dss_operating_cost"): 1_000_000.0,
            commercial_control_key("weekly_direct_capture_percent"): 50.0,
            commercial_control_key("weekly_price_elasticity"): 0.8,
            commercial_control_key("weekly_promotion_cost"): 2_500.0,
        }

        render_commercial_strategy(application_result, category_assumptions, 0.125)

        self.assertEqual(len(self.channel_calls), 1)
        self.assertEqual(len(self.weekly_calls), 1)
        self.assertAlmostEqual(self.channel_calls[0]["annual_revenue"], 80_000_000.0)
        self.assertAlmostEqual(self.channel_calls[0]["target_capture_rate"], 0.5)
        self.assertAlmostEqual(self.weekly_calls[0]["direct_capture_rate"], 0.5)
        self.assertTrue(any("Scenario estimates" in text for text in self.fake_st.markdown_calls))
        self.assertTrue(any("Protect Yield" in text for text in self.fake_st.markdown_calls))
        self.assertTrue(
            any("share of this week's bookings expected to come through ABC's own direct channels" in text for text in self.fake_st.caption_calls)
        )
        self.assertGreaterEqual(len(self.fake_st.metric_calls), 4)
        self.assertGreaterEqual(len(self.fake_st.dataframes), 2)
        self.assertGreaterEqual(len(self.fake_st.bar_charts), 2)
        self.assertIn(2, self.fake_st.columns_calls)
        self.assertIn(
            ("success", "Proceed with the direct-channel capture target."),
            self.fake_st.alerts,
        )


if __name__ == "__main__":
    unittest.main()
