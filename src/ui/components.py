"""Reusable Streamlit components for the single-page manager dashboard."""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.constants import CATEGORY_DISPLAY_LABELS, RESERVATION_CATEGORIES
from src.data.loader import load_and_validate_history
from src.validation import load_defaults_config


def _load_ui_module(module_name: str, required_attrs: tuple[str, ...]):
    """Load a fresh UI helper module if Streamlit cached a partial import."""
    module = importlib.import_module(module_name)
    if all(hasattr(module, attr_name) for attr_name in required_attrs):
        return module

    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


charts = _load_ui_module(
    "src.ui.charts",
    (
        "build_financial_breakdown_frame",
        "build_forecast_breakdown_frame",
        "build_history_display_frame_with_labels",
        "build_methodology_points",
        "build_overflow_detail_frame",
        "build_plan_comparison_frame",
        "build_results_export_frames",
        "build_staffing_capacity_frame",
        "build_staffing_risk_cost_frame",
        "build_workload_breakdown_frame",
    ),
)
state = _load_ui_module(
    "src.ui.state",
    (
        "category_assumption_key",
        "decision_policy_control_key",
        "decimal_to_percent",
        "initialize_session_state",
        "manual_override_enabled_key",
        "manual_override_value_key",
        "reset_session_state",
        "run_analysis_for_current_draft",
        "simulation_control_key",
        "strategic_control_key",
        "update_draft_inputs_from_widgets",
        "workforce_control_key",
    ),
)

build_financial_breakdown_frame = charts.build_financial_breakdown_frame
build_forecast_breakdown_frame = charts.build_forecast_breakdown_frame
build_history_display_frame_with_labels = charts.build_history_display_frame_with_labels
build_methodology_points = charts.build_methodology_points
build_overflow_detail_frame = charts.build_overflow_detail_frame
build_plan_comparison_frame = charts.build_plan_comparison_frame
build_results_export_frames = charts.build_results_export_frames
build_staffing_capacity_frame = charts.build_staffing_capacity_frame
build_staffing_risk_cost_frame = charts.build_staffing_risk_cost_frame
build_workload_breakdown_frame = charts.build_workload_breakdown_frame

category_assumption_key = state.category_assumption_key
decision_policy_control_key = state.decision_policy_control_key
decimal_to_percent = state.decimal_to_percent
initialize_session_state = state.initialize_session_state
manual_override_enabled_key = state.manual_override_enabled_key
manual_override_value_key = state.manual_override_value_key
reset_session_state = state.reset_session_state
run_analysis_for_current_draft = state.run_analysis_for_current_draft
simulation_control_key = state.simulation_control_key
strategic_control_key = state.strategic_control_key
update_draft_inputs_from_widgets = state.update_draft_inputs_from_widgets
workforce_control_key = state.workforce_control_key

BASE_PATH = Path(__file__).resolve().parents[2]
HISTORY_PATH = BASE_PATH / "data" / "synthetic_history.csv"
DEFAULTS_PATH = BASE_PATH / "config" / "defaults.json"

COVERAGE_TARGET_PERCENT_KEY = "ui_minimum_inhouse_coverage_target_percent"
COMMISSION_RATE_PERCENT_KEY = "ui_third_party_commission_rate_percent"


@st.cache_data(show_spinner=False)
def _load_history() -> pd.DataFrame:
    return load_and_validate_history(HISTORY_PATH)


@st.cache_data(show_spinner=False)
def _load_defaults() -> dict[str, Any]:
    return load_defaults_config(DEFAULTS_PATH)


def _format_percent(value: float) -> str:
    return f"{float(value) * 100.0:.1f}%"


def _format_currency(value: float) -> str:
    return f"${float(value):,.0f}"


def _sync_display_percent_keys() -> None:
    st.session_state[COVERAGE_TARGET_PERCENT_KEY] = float(
        st.session_state[decision_policy_control_key("minimum_inhouse_coverage_target")]
    ) * 100.0
    st.session_state[COMMISSION_RATE_PERCENT_KEY] = float(
        st.session_state[strategic_control_key("third_party_commission_rate")]
    ) * 100.0


def _on_decision_control_change() -> None:
    st.session_state[decision_policy_control_key("minimum_inhouse_coverage_target")] = (
        float(st.session_state[COVERAGE_TARGET_PERCENT_KEY]) / 100.0
    )
    update_draft_inputs_from_widgets(st.session_state)


def _on_commission_rate_change() -> None:
    st.session_state[strategic_control_key("third_party_commission_rate")] = (
        float(st.session_state[COMMISSION_RATE_PERCENT_KEY]) / 100.0
    )
    update_draft_inputs_from_widgets(st.session_state)


def _on_widget_change() -> None:
    update_draft_inputs_from_widgets(st.session_state)


def _build_export_payload(
    application_result: Mapping[str, Any],
    applied_inputs: Mapping[str, Any],
) -> str:
    export_frames = build_results_export_frames(
        application_result,
        applied_inputs=applied_inputs,
    )
    payload = {
        frame_name: frame.to_dict(orient="records")
        for frame_name, frame in export_frames.items()
    }
    return json.dumps(payload, indent=2)


def _build_summary_csv(
    application_result: Mapping[str, Any],
) -> str:
    return build_staffing_risk_cost_frame(
        application_result["staffing_risk_cost_records"]
    ).to_csv(index=False)


def _build_hero_reason(
    recommended_plan: Mapping[str, Any],
) -> str:
    target_text = _format_percent(
        recommended_plan["selected_minimum_inhouse_coverage_target"]
    )
    coverage_text = _format_percent(recommended_plan["recommended_coverage"])
    if bool(recommended_plan["coverage_target_met"]):
        return (
            f"Meets the selected {target_text} minimum in-house coverage target "
            f"at the lowest expected total weekly operating cost. Actual modeled coverage: {coverage_text}."
        )
    return (
        f"The selected {target_text} minimum in-house coverage target is not achievable within the current "
        f"in-house range. This recommendation uses the maximum feasible staffing level with actual modeled "
        f"coverage of {coverage_text}."
    )


def _build_previous_week_context(
    recommended_plan: Mapping[str, Any],
    previous_week_staffing_context: Mapping[str, Any],
) -> str:
    delta = int(recommended_plan["staffing_agents"]) - int(
        previous_week_staffing_context["staffing_agents"]
    )
    if delta > 0:
        return f"The recommendation is {delta} agent{'s' if delta != 1 else ''} above the previous week."
    if delta < 0:
        return f"The recommendation is {abs(delta)} agent{'s' if abs(delta) != 1 else ''} below the previous week."
    return "The recommendation matches the previous-week staffing level."


def _render_warning_list(warnings: list[str]) -> None:
    for warning in warnings:
        st.warning(warning)


def _current_manager_warning_text() -> str | None:
    manager_staffing = int(st.session_state[workforce_control_key("planned_staffing_agents")])
    minimum_staffing = int(st.session_state[workforce_control_key("minimum_schedulable_agents")])
    maximum_staffing = int(st.session_state[workforce_control_key("maximum_inhouse_agents")])
    if manager_staffing < minimum_staffing:
        return (
            f"Manager Proposed Staffing is below the operating floor of {minimum_staffing} agents "
            "and will be evaluated as an exact what-if plan only."
        )
    if manager_staffing > maximum_staffing:
        return (
            f"Manager Proposed Staffing is above the in-house capacity cap of {maximum_staffing} agents "
            "and will be evaluated as an exact what-if plan only."
        )
    return None


def _inject_dashboard_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            color-scheme: light;
        }
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stHeader"],
        [data-testid="stMainBlockContainer"] {
            color: #17324D !important;
        }
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(0, 105, 148, 0.10), transparent 28%),
                linear-gradient(180deg, #F6FAFC 0%, #EEF3F7 100%);
        }
        [data-testid="stHeader"] {
            background: transparent !important;
        }
        [data-testid="stToolbar"] {
            color: #17324D !important;
        }
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] span,
        [data-testid="stCaptionContainer"],
        label,
        .stSelectbox label,
        .stNumberInput label,
        .stCheckbox label,
        .stRadio label,
        .stTextInput label {
            color: #17324D !important;
        }
        h1, h2, h3 {
            color: #17324D;
        }
        .section-title {
            font-size: 1.2rem;
            font-weight: 700;
            color: #17324D;
            margin: 30px 0 12px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid #0B6E8A;
        }
        .hero-card {
            background: linear-gradient(135deg, #17324D 0%, #0B6E8A 100%);
            border-radius: 18px;
            padding: 30px 34px;
            margin: 12px 0 20px 0;
            color: #FFFFFF;
            box-shadow: 0 12px 30px rgba(23, 50, 77, 0.18);
        }
        .hero-eyebrow {
            color: rgba(255,255,255,0.82);
            font-size: 0.95rem;
            letter-spacing: 0.02em;
            text-transform: uppercase;
        }
        .hero-number {
            font-size: 3.2rem;
            font-weight: 800;
            line-height: 1.0;
            margin: 10px 0 8px 0;
        }
        .hero-detail {
            color: #E7F5FB;
            font-size: 0.98rem;
            line-height: 1.55;
            margin-top: 14px;
        }
        .hero-card,
        .hero-card * {
            color: #FFFFFF !important;
        }
        .hero-card .hero-eyebrow {
            color: rgba(255,255,255,0.82) !important;
        }
        .hero-card .hero-detail {
            color: #E7F5FB !important;
        }
        .surface-card {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid #D8E3EA;
            border-radius: 16px;
            padding: 20px 22px;
            box-shadow: 0 6px 18px rgba(17, 43, 60, 0.05);
        }
        .outlook-card {
            background: rgba(255, 255, 255, 0.95);
            border: 1px solid #D8E3EA;
            border-radius: 16px;
            padding: 18px 18px 10px 18px;
            min-height: 100%;
        }
        .outlook-card.central {
            border: 2px solid #0B6E8A;
            box-shadow: 0 10px 24px rgba(11, 110, 138, 0.10);
        }
        .outlook-title {
            font-size: 1.02rem;
            font-weight: 700;
            color: #17324D;
            margin-bottom: 8px;
        }
        .outlook-caption {
            font-size: 0.88rem;
            color: #5B7185;
            margin-bottom: 12px;
        }
        .mini-note {
            font-size: 0.88rem;
            color: #5B7185;
        }
        div[data-testid="stMetric"] {
            background: rgba(255,255,255,0.92);
            border-radius: 12px;
            padding: 12px 14px;
            border: 1px solid #D8E3EA;
        }
        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] [data-testid="stMetricValue"],
        div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
            color: #17324D !important;
        }
        div[data-testid="stDataFrame"],
        div[data-testid="stTable"] {
            background: rgba(255, 255, 255, 0.96);
            color: #17324D !important;
        }
        div[data-baseweb="input"] input,
        div[data-baseweb="base-input"] input,
        textarea {
            color: #17324D !important;
            background: #FFFFFF !important;
        }
        button[kind="primary"] {
            background-color: #0B6E8A !important;
            border-color: #0B6E8A !important;
        }
        .stButton button {
            border-radius: 8px;
        }
        .stButton button,
        .stDownloadButton button {
            color: #17324D !important;
            background: #FFFFFF !important;
            border: 1px solid #C9D6DF !important;
        }
        .stButton button[kind="primary"] {
            color: #FFFFFF !important;
            background-color: #0B6E8A !important;
            border-color: #0B6E8A !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:16px; margin-bottom:4px;">
            <div style="font-size:2rem;">&#x1F6A2;</div>
            <div>
                <h1 style="margin:0; font-size:1.75rem;">ABC Cruise Lines</h1>
                <p style="margin:2px 0 0 0; color:#5B7185; font-size:1rem;">
                    Reservation Staffing Decision Support System
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Run a weekly reservation staffing analysis, compare the model recommendation with a manager proposal, and review lower, central, and higher demand planning outlooks."
    )
    st.divider()


def render_action_row(session_state: Mapping[str, Any]) -> None:
    history = _load_history()
    defaults = _load_defaults()
    application_result = session_state.get("analysis_result")
    applied_inputs = session_state.get("applied_inputs")

    col1, col2, col3, col4 = st.columns([1.2, 1.0, 1.0, 4.2], gap="small")

    with col1:
        if st.button("Run Analysis", type="primary", use_container_width=True):
            run_analysis_for_current_draft(
                st.session_state,
                history=history,
                defaults=defaults,
            )
            st.rerun()

    with col2:
        if st.button("Reset to Baseline", use_container_width=True):
            reset_session_state(
                st.session_state,
                history=history,
                defaults=defaults,
            )
            st.rerun()

    with col3:
        if application_result and applied_inputs:
            st.download_button(
                "Export Summary",
                data=_build_summary_csv(application_result),
                file_name="abc_cruise_staffing_summary.csv",
                mime="text/csv",
                use_container_width=True,
            )

    with col4:
        if application_result and applied_inputs:
            st.download_button(
                "Export Full Result (JSON)",
                data=_build_export_payload(application_result, applied_inputs),
                file_name="abc_cruise_staffing_full_result.json",
                mime="application/json",
                use_container_width=False,
            )

    if session_state.get("results_stale", False):
        st.warning("Draft inputs have changed. Run Analysis to refresh the recommendation while keeping the current applied result visible.")

    analysis_error = session_state.get("analysis_error")
    if analysis_error:
        st.error(str(analysis_error["message"]))


def render_hero_card(session_state: Mapping[str, Any]) -> None:
    application_result = session_state.get("analysis_result")
    if not application_result:
        return

    recommended_plan = application_result["recommended_plan"]
    html = f"""
    <div class="hero-card">
        <div class="hero-eyebrow">Recommended In-House Staffing</div>
        <div class="hero-number">{int(recommended_plan["staffing_agents"])} agents</div>
        <div class="hero-detail">{_build_hero_reason(recommended_plan)}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

    if recommended_plan.get("warning"):
        st.warning(str(recommended_plan["warning"]))


def render_kpi_grid(session_state: Mapping[str, Any]) -> None:
    application_result = session_state.get("analysis_result")
    if not application_result:
        return

    recommended_plan = application_result["recommended_plan"]
    previous_week_context = application_result["previous_week_staffing_context"]
    total_bookings = float(application_result["central_demand_outlook"]["total_bookings"])

    st.markdown('<p class="section-title">Recommendation Snapshot</p>', unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns(5, gap="small")
    col1.metric("Selected Coverage Target", _format_percent(
        recommended_plan["selected_minimum_inhouse_coverage_target"]
    ))
    col2.metric("In-House Coverage Probability", _format_percent(
        recommended_plan["capacity_confidence"]
    ))
    col3.metric("Probability Overflow Is Required", _format_percent(
        recommended_plan["probability_overflow_required"]
    ))
    col4.metric("Central Forecast Bookings", f"{total_bookings:.1f}")
    col5.metric("Total Weekly Operating Cost", _format_currency(
        recommended_plan["expected_total_weekly_operating_cost"]
    ))

    col1, col2, col3, col4 = st.columns(4, gap="small")
    col1.metric("Manager Proposal", f"{int(application_result['manager_proposal']['staffing_agents'])} agents")
    col2.metric("Previous Week", f"{int(previous_week_context['staffing_agents'])} agents")
    col3.metric("Expected Spare Capacity", f"{float(recommended_plan['expected_spare_capacity_hours']):.1f} hrs")
    col4.metric("Expected Overflow Commission", _format_currency(
        recommended_plan["expected_overflow_commission"]
    ))


def render_narrative(session_state: Mapping[str, Any]) -> None:
    application_result = session_state.get("analysis_result")
    if not application_result:
        return

    st.markdown("#### Decision Interpretation")
    st.markdown(
        _build_previous_week_context(
            application_result["recommended_plan"],
            application_result["previous_week_staffing_context"],
        )
    )
    st.markdown(application_result["adaptive_comparison_narrative"]["text"])
    _render_warning_list(application_result["adaptive_comparison_narrative"]["warnings"])


def render_business_decisions_section() -> None:
    st.markdown('<p class="section-title">Business Decisions</p>', unsafe_allow_html=True)
    st.caption(
        "Adjust the recommendation policy, enter a manager staffing proposal, and choose whether to apply manager forecasts by category. Changes update the draft immediately and apply on the next Run Analysis."
    )

    left, right = st.columns([1.2, 1.4], gap="large")

    with left:
        st.markdown("#### Recommendation Policy")
        st.number_input(
            "Minimum In-House Coverage Target (%)",
            min_value=50.0,
            max_value=99.0,
            step=1.0,
            key=COVERAGE_TARGET_PERCENT_KEY,
            help="Manager-facing target for the probability that weekly demand can be processed entirely in-house without third-party overflow.",
            on_change=_on_decision_control_change,
        )

        st.markdown("#### Manager Proposal")
        st.number_input(
            "Manager Proposed Staffing",
            min_value=0,
            max_value=30,
            step=1,
            key=workforce_control_key("planned_staffing_agents"),
            help="Exact staffing plan to evaluate independently from the model recommendation.",
            on_change=_on_widget_change,
        )
        warning_text = _current_manager_warning_text()
        if warning_text is not None:
            st.warning(warning_text)

    with right:
        st.markdown("#### Forecast Adjustments")
        automatic_forecast = (
            st.session_state.get("analysis_result", {}).get(
                "automatic_forecast",
                {category: 0.0 for category in RESERVATION_CATEGORIES},
            )
        )
        for category in RESERVATION_CATEGORIES:
            card_left, card_right = st.columns([1.0, 1.2], gap="small")
            with card_left:
                st.caption(CATEGORY_DISPLAY_LABELS[category])
                st.metric("Model central forecast", f"{float(automatic_forecast[category]):.1f}")
                st.checkbox(
                    "Use manager forecast",
                    key=manual_override_enabled_key(category),
                    on_change=_on_widget_change,
                )
            with card_right:
                st.number_input(
                    "Manager forecast value",
                    min_value=0.0,
                    step=1.0,
                    key=manual_override_value_key(category),
                    help="Typed values stay available in the draft. The checkbox determines whether the manager value replaces the model central forecast.",
                    on_change=_on_widget_change,
                )


def render_business_assumptions_expander() -> None:
    defaults = _load_defaults()
    with st.expander("Business Assumptions", expanded=False):
        st.caption(
            "Editable modeling assumptions that participate in draft, applied, stale, reset, and rerun behavior."
        )

        st.markdown("##### Category Assumptions")
        category_defaults = defaults["category_assumptions"]
        cat_cols = st.columns(len(RESERVATION_CATEGORIES), gap="small")
        for idx, category in enumerate(RESERVATION_CATEGORIES):
            with cat_cols[idx]:
                _ = next(item for item in category_defaults if item.category == category)
                st.caption(CATEGORY_DISPLAY_LABELS[category])
                st.number_input(
                    "Handling time (min)",
                    min_value=0.1,
                    step=1.0,
                    key=category_assumption_key(category, "handling_time_minutes"),
                    help="Average minutes to process one reservation in this category.",
                    on_change=_on_widget_change,
                )
                st.number_input(
                    "Average booking value ($)",
                    min_value=0.0,
                    step=25.0,
                    key=category_assumption_key(category, "average_booking_value"),
                    help="Average booking value used for overflow commission calculations.",
                    on_change=_on_widget_change,
                )

        st.markdown("##### Workforce Assumptions")
        col1, col2, col3 = st.columns(3, gap="small")
        col1.number_input(
            "Paid hours per agent",
            min_value=1.0,
            step=1.0,
            key=workforce_control_key("paid_hours_per_agent"),
            on_change=_on_widget_change,
        )
        col2.number_input(
            "Weekly booking-processing hours per agent",
            min_value=0.1,
            step=0.5,
            key=workforce_control_key("weekly_booking_processing_hours_per_agent"),
            on_change=_on_widget_change,
        )
        col3.number_input(
            "Hourly labor rate ($)",
            min_value=0.0,
            step=1.0,
            key=workforce_control_key("regular_hourly_wage"),
            on_change=_on_widget_change,
        )
        col1, col2, col3 = st.columns(3, gap="small")
        col1.number_input(
            "Minimum schedulable agents",
            min_value=0,
            step=1,
            key=workforce_control_key("minimum_schedulable_agents"),
            on_change=_on_widget_change,
        )
        col2.number_input(
            "Maximum in-house agents",
            min_value=0,
            step=1,
            key=workforce_control_key("maximum_inhouse_agents"),
            on_change=_on_widget_change,
        )
        col3.number_input(
            "Third-party commission rate (%)",
            min_value=0.0,
            max_value=100.0,
            step=0.5,
            key=COMMISSION_RATE_PERCENT_KEY,
            on_change=_on_commission_rate_change,
        )


def render_plan_comparison_section(session_state: Mapping[str, Any]) -> None:
    application_result = session_state.get("analysis_result")
    if not application_result:
        return

    st.markdown('<p class="section-title">Recommendation Versus Manager Proposal</p>', unsafe_allow_html=True)
    comparison_frame = build_plan_comparison_frame(
        application_result["recommended_plan"],
        application_result["manager_proposal"],
    )
    st.dataframe(comparison_frame, use_container_width=True, hide_index=True)

    comparison = application_result["recommendation_manager_comparison"]
    diff_frame = pd.DataFrame(
        [
            {
                "difference_direction": "manager value - recommendation value",
                "staffing_agents": int(comparison["staffing_difference"]),
                "coverage_probability": float(comparison["coverage_difference"]),
                "overflow_probability": float(comparison["overflow_probability_difference"]),
                "regular_labor_cost": float(comparison["labor_cost_difference"]),
                "expected_overflow_workload_hours": float(
                    comparison["overflow_workload_difference"]
                ),
                "expected_overflow_commission": float(
                    comparison["overflow_commission_difference"]
                ),
                "expected_spare_capacity_hours": float(
                    comparison["spare_capacity_difference"]
                ),
                "expected_total_weekly_operating_cost": float(
                    comparison["total_cost_difference"]
                ),
            }
        ]
    )
    st.dataframe(diff_frame, use_container_width=True, hide_index=True)


def _render_outlook_card(
    outlook: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    *,
    emphasize: bool,
) -> None:
    percentile_label = str(outlook["percentile_label"])
    target_workload = float(
        diagnostics["target_total_workload_hours_by_percentile_label"][percentile_label]
    )
    selected_workload = float(
        diagnostics["selected_total_workload_hours_by_percentile_label"][percentile_label]
    )
    card_class = "outlook-card central" if emphasize else "outlook-card"
    st.markdown(
        f"""
        <div class="{card_class}">
            <div class="outlook-title">{outlook["outlook_name"]} - {percentile_label}</div>
            <div class="outlook-caption">
                {"Median simulated workload outlook." if percentile_label == "P50" else
                 "Relatively lower-demand simulated week." if percentile_label == "P25" else
                 "Higher-demand planning condition; about 90% of simulated total-workload outcomes are at or below the P90 threshold."}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2, gap="small")
    col1.metric("Total bookings", f"{float(outlook['total_bookings']):.1f}")
    col2.metric("Total workload", f"{float(outlook['total_workload_hours']):.1f} hrs")
    col1, col2 = st.columns(2, gap="small")
    col1.metric("Raw FTE", f"{float(outlook['raw_required_fte']):.2f}")
    col2.metric("Whole-agent need", f"{int(outlook['unconstrained_required_agents'])}")
    col1, col2 = st.columns(2, gap="small")
    col1.metric(
        "Constrained staffing",
        f"{int(outlook['recommended_inhouse_agents_for_outlook'])} agents",
    )
    if float(outlook["overflow_workload_hours"]) > 0.0:
        col2.metric("Representative overflow", f"{float(outlook['overflow_workload_hours']):.1f} hrs")
    else:
        col2.metric("Representative spare capacity", f"{float(outlook['spare_capacity_hours']):.1f} hrs")
    col1, col2, col3 = st.columns(3, gap="small")
    col1.metric("Labor cost", _format_currency(outlook["regular_labor_cost"]))
    col2.metric("Overflow commission", _format_currency(outlook["overflow_commission"]))
    col3.metric("Operating cost", _format_currency(outlook["total_weekly_operating_cost"]))
    st.caption(
        f"Percentile target workload: {target_workload:.1f} hrs. Selected representative row workload: {selected_workload:.1f} hrs. Simulation row id: {int(outlook['simulation_row_id'])}."
    )


def render_probabilistic_outlooks(session_state: Mapping[str, Any]) -> None:
    application_result = session_state.get("analysis_result")
    if not application_result:
        return

    st.markdown('<p class="section-title">Probabilistic Demand Outlooks</p>', unsafe_allow_html=True)
    st.caption(
        "All three outlooks are shown together from coherent representative simulation rows ordered by total workload."
    )
    outlooks = [
        application_result["lower_demand_outlook"],
        application_result["central_demand_outlook"],
        application_result["higher_demand_outlook"],
    ]
    cols = st.columns(3, gap="medium")
    for idx, outlook in enumerate(outlooks):
        with cols[idx]:
            _render_outlook_card(
                outlook,
                application_result["outlook_diagnostics"],
                emphasize=(outlook["percentile_label"] == "P50"),
            )


def render_staffing_risk_cost_section(session_state: Mapping[str, Any]) -> None:
    application_result = session_state.get("analysis_result")
    if not application_result:
        return

    st.markdown('<p class="section-title">Staffing Risk-Cost Table</p>', unsafe_allow_html=True)
    st.caption(
        "Lower-priority detail showing one row per evaluated staffing level, including relevant out-of-range manager and previous-week context."
    )
    risk_cost_frame = build_staffing_risk_cost_frame(
        application_result["staffing_risk_cost_records"]
    )
    st.dataframe(risk_cost_frame, use_container_width=True, hide_index=True)


def render_analysis_details_expander(session_state: Mapping[str, Any]) -> None:
    application_result = session_state.get("analysis_result")
    if not application_result:
        return

    history = _load_history()
    deterministic = application_result["deterministic_staffing_result"]
    effective_forecast = application_result["effective_forecast"]
    financial_recommendation = application_result["financial_recommendation"]
    applied = session_state.get("applied_inputs", {}) or {}

    with st.expander("Analysis Details", expanded=False):
        st.markdown("### Historical Demand")
        st.dataframe(
            build_history_display_frame_with_labels(history),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### Forecast Breakdown")
        st.dataframe(
            build_forecast_breakdown_frame(
                application_result["automatic_forecast"],
                effective_forecast,
                {
                    cat: float(item["value"])
                    for cat, item in applied.get("manual_overrides", {}).items()
                    if item.get("enabled")
                }
                if "manual_overrides" in applied
                else None,
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### Workload Breakdown")
        st.dataframe(
            build_workload_breakdown_frame(
                effective_forecast,
                deterministic,
                applied.get("category_assumptions", defaults_for_category_labels()),
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### Staffing and Capacity")
        st.dataframe(
            build_staffing_capacity_frame(
                deterministic,
                applied.get("workforce_assumptions", {}),
            ),
            use_container_width=True,
            hide_index=True,
        )

        if float(deterministic["overflow_workload_hours"]) > 0.0:
            st.markdown("### Overflow Detail")
            st.dataframe(
                build_overflow_detail_frame(deterministic),
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("### Financial Breakdown")
        st.dataframe(
            build_financial_breakdown_frame(
                financial_recommendation,
                deterministic,
                applied.get("category_assumptions", defaults_for_category_labels()),
                applied.get(
                    "strategic_assumptions",
                    {"third_party_commission_rate": 0.125},
                ),
            ),
            use_container_width=True,
            hide_index=True,
        )


def defaults_for_category_labels() -> list[dict[str, Any]]:
    defaults = _load_defaults()
    return [item.to_dict() for item in defaults["category_assumptions"]]


def render_methodology_expander() -> None:
    defaults = _load_defaults()
    sim = defaults["simulation_configuration"]
    with st.expander("Methodology", expanded=False):
        for point in build_methodology_points():
            st.markdown(f"- {point}")
        st.markdown(
            f"- Simulation iterations: `{sim.iterations}` with seed `{sim.random_seed}` and distribution `{sim.distribution_name}`."
        )
        st.markdown(
            "- In-House Coverage Probability means the probability that the selected staffing level can process simulated weekly demand entirely in-house without requiring third-party overflow."
        )
        st.markdown(
            "- Total weekly operating cost equals regular labor cost plus expected third-party overflow commission."
        )


def render_main_dashboard() -> None:
    _inject_dashboard_css()
    render_header()

    history = _load_history()
    defaults = _load_defaults()
    initialize_session_state(
        st.session_state,
        history=history,
        defaults=defaults,
    )
    _sync_display_percent_keys()

    render_action_row(st.session_state)
    render_hero_card(st.session_state)
    render_kpi_grid(st.session_state)
    render_narrative(st.session_state)
    render_plan_comparison_section(st.session_state)
    render_probabilistic_outlooks(st.session_state)
    render_business_decisions_section()
    render_business_assumptions_expander()
    render_staffing_risk_cost_section(st.session_state)
    render_analysis_details_expander(st.session_state)
    render_methodology_expander()
