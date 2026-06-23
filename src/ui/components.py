"""Reusable Streamlit components for the single-page manager dashboard."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.constants import CATEGORY_DISPLAY_LABELS, RESERVATION_CATEGORIES
from src.data.loader import build_history_diagnostics, load_and_validate_history
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
    build_results_export_frames,
    build_secondary_kpi_frame,
    build_staffing_capacity_frame,
    build_workload_breakdown_frame,
)
from src.ui.state import (
    category_assumption_key,
    decimal_to_percent,
    initialize_session_state,
    manual_override_enabled_key,
    manual_override_value_key,
    percent_to_decimal,
    reset_session_state,
    run_analysis_for_current_draft,
    simulation_control_key,
    strategic_control_key,
    update_draft_inputs_from_widgets,
    workforce_control_key,
)
from src.validation import EXPECTED_SCENARIO_NAMES, load_defaults_config

BASE_PATH = Path(__file__).resolve().parents[2]
HISTORY_PATH = BASE_PATH / "data" / "synthetic_history.csv"
DEFAULTS_PATH = BASE_PATH / "config" / "defaults.json"

SCENARIO_MULTIPLIERS: dict[str, dict[str, float]] = {
    "Low Demand": {"demand": 0.85, "variability": 0.75},
    "Expected Demand": {"demand": 1.00, "variability": 1.00},
    "High Demand": {"demand": 1.15, "variability": 1.25},
}


@st.cache_data(show_spinner=False)
def _load_history() -> pd.DataFrame:
    return load_and_validate_history(HISTORY_PATH)


@st.cache_data(show_spinner=False)
def _load_defaults() -> dict[str, Any]:
    return load_defaults_config(DEFAULTS_PATH)


# ---------------------------------------------------------------------------
# CSS injection
# ---------------------------------------------------------------------------

def _inject_dashboard_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #F5F7FA;
        }
        div[data-testid="stMetric"] {
            background: #FFFFFF;
            border-radius: 10px;
            padding: 14px 18px;
            border: 1px solid #E0E4E8;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.6rem !important;
            font-weight: 700 !important;
            color: #1B2838 !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.82rem !important;
            color: #5A6C7D !important;
        }
        h1, h2, h3 {
            color: #1B2838;
        }
        .hero-card {
            background: linear-gradient(135deg, #1B2838 0%, #0F3D5C 100%);
            border-radius: 14px;
            padding: 32px 36px;
            margin: 12px 0 24px 0;
            color: #FFFFFF;
        }
        .hero-card h2 {
            color: #FFFFFF;
            font-size: 1.1rem;
            font-weight: 400;
            opacity: 0.85;
            margin: 0 0 8px 0;
        }
        .hero-card .hero-number {
            font-size: 3.2rem;
            font-weight: 800;
            color: #FFFFFF;
            line-height: 1.1;
        }
        .hero-card .hero-label {
            font-size: 1.05rem;
            color: #8AB4D6;
            margin-top: 4px;
        }
        .hero-card .hero-message {
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid rgba(255,255,255,0.15);
            font-size: 0.95rem;
            line-height: 1.6;
            color: #C8DEEF;
        }
        .section-title {
            font-size: 1.2rem;
            font-weight: 700;
            color: #1B2838;
            margin: 32px 0 12px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid #006994;
        }
        button[kind="primary"] {
            background-color: #006994 !important;
            border-color: #006994 !important;
        }
        button[kind="primary"]:hover {
            background-color: #005577 !important;
        }
        .stButton button {
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def render_header() -> None:
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 4px;">
            <div style="font-size: 2rem;">&#x1F6A2;</div>
            <div>
                <h1 style="margin:0; font-size: 1.75rem;">ABC Cruise Lines</h1>
                <p style="margin:2px 0 0 0; color: #5A6C7D; font-size: 1rem;">
                    Weekly Reservation Staffing Decision Support System
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Forecast weekly reservation workload, compare in-house capacity, and plan third-party overflow."
    )
    st.divider()


# ---------------------------------------------------------------------------
# Hero recommendation card
# ---------------------------------------------------------------------------

def _build_hero_message(
    recommended: int,
    unconstrained: int,
    prev_week: int,
    manager_plan: int,
    spare_capacity: float,
    overflow_workload: float,
    overflow_bookings: dict[str, float],
    total_workload: float,
    booking_processing_hours: float,
    minimum_agents: int,
) -> str:
    total_overflow_bk = sum(overflow_bookings.values())

    delta_prev = recommended - prev_week
    delta_mgr = recommended - manager_plan

    lines: list[str] = []

    if recommended == unconstrained and recommended >= minimum_agents:
        change_word = "add" if delta_prev > 0 else "remove" if delta_prev < 0 else "no change in"
        amount = abs(delta_prev)
        agent_word = "agent" if amount == 1 else "agents"
        lines.append(
            f"{'Add' if delta_prev > 0 else 'Remove' if delta_prev < 0 else 'No change from'} "
            f"{abs(delta_prev)} {agent_word} compared with last week."
        )

        if delta_mgr != 0:
            direction = "above" if delta_mgr > 0 else "below"
            lines.append(
                f"The manager plan of {manager_plan} agents is {abs(delta_mgr)} agent{'s' if abs(delta_mgr) != 1 else ''} "
                f"{direction} the modeled requirement."
            )
        else:
            lines.append(f"The manager plan of {manager_plan} agents matches the modeled requirement.")
    elif recommended < unconstrained and overflow_workload > 0:
        lines.append(
            f"Workload requires {unconstrained} agents. "
            f"Schedule the maximum {recommended} in-house agents and route "
            f"approximately {round(total_overflow_bk)} bookings to third-party overflow."
        )
    else:
        spare = booking_processing_hours * minimum_agents - total_workload
        lines.append(
            f"Workload requires {unconstrained} agents. "
            f"ABC's assumed operating floor is {minimum_agents} agents, leaving approximately "
            f"{spare:.1f} booking-processing hours available."
        )

    if overflow_workload <= 0.0 and recommended >= unconstrained:
        lines.append("No third-party overflow is expected under the current forecast.")

    return " ".join(lines)


def render_hero_card(session_state: Mapping[str, Any]) -> None:
    application_result = session_state.get("analysis_result")
    if not application_result:
        return

    deterministic = application_result["deterministic_staffing_result"]
    effective_forecast = application_result["effective_forecast"]
    recommended = int(deterministic["recommended_inhouse_agents"])
    unconstrained = int(deterministic["unconstrained_required_agents"])
    prev_week = int(_load_history().iloc[-1]["staffing_agents"])
    applied = session_state.get("applied_inputs", {})
    manager_plan = int(
        applied.get("workforce_assumptions", {}).get("planned_staffing_agents", 10)
    ) if applied else 10
    minimum_agents = int(
        applied.get("workforce_assumptions", {}).get("minimum_schedulable_agents", 8)
    ) if applied else 8

    overflow_workload = float(deterministic["spare_capacity_hours"]) > 0 and float(deterministic["overflow_workload_hours"]) == 0

    spare = float(deterministic["spare_capacity_hours"])
    overflow = float(deterministic["overflow_workload_hours"])
    overflow_bookings = deterministic.get("overflow_bookings_by_category", {})
    total_workload = float(deterministic["total_workload_hours"])
    booking_processing = float(deterministic["booking_processing_hours_per_agent"])

    message = _build_hero_message(
        recommended=recommended,
        unconstrained=unconstrained,
        prev_week=prev_week,
        manager_plan=manager_plan,
        spare_capacity=spare,
        overflow_workload=overflow,
        overflow_bookings=overflow_bookings,
        total_workload=total_workload,
        booking_processing_hours=booking_processing,
        minimum_agents=minimum_agents,
    )

    st.markdown(
        f"""
        <div class="hero-card">
            <h2>Recommended In-House Staffing</h2>
            <div class="hero-number">{recommended} agents</div>
            <div class="hero-label">for the upcoming week</div>
            <div class="hero-message">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# KPI grid
# ---------------------------------------------------------------------------

def render_kpi_grid(session_state: Mapping[str, Any]) -> None:
    application_result = session_state.get("analysis_result")
    if not application_result:
        return

    deterministic = application_result["deterministic_staffing_result"]
    effective_forecast = application_result["effective_forecast"]
    applied = session_state.get("applied_inputs", {}) or {}
    workforce = applied.get("workforce_assumptions", {})

    total_bookings = sum(effective_forecast.values())
    workload_hours = float(deterministic["total_workload_hours"])
    raw_fte = float(deterministic["raw_required_fte"])
    unconstrained = int(deterministic["unconstrained_required_agents"])
    recommended = int(deterministic["recommended_inhouse_agents"])

    prev_week = int(_load_history().iloc[-1]["staffing_agents"])
    manager_plan = int(workforce.get("planned_staffing_agents", 10)) if workforce else 10
    spare = float(deterministic["spare_capacity_hours"])
    overflow = float(deterministic["overflow_workload_hours"])

    paid_hours = float(workforce.get("paid_hours_per_agent", 40)) if workforce else 40
    hourly_wage = float(workforce.get("regular_hourly_wage", 22)) if workforce else 22
    labor_cost = recommended * paid_hours * hourly_wage
    total_cost = labor_cost  # overflow commissions are 0 when no overflow from deterministic

    delta_prev = recommended - prev_week

    st.markdown('<p class="section-title">Management KPIs</p>', unsafe_allow_html=True)

    # Primary KPI row
    col1, col2, col3, col4, col5 = st.columns(5, gap="small")
    col1.metric("Forecasted Bookings", f"{total_bookings:.1f}", "reservations / week")
    col2.metric("Forecasted Workload", f"{workload_hours:.1f}", "hours / week")
    col3.metric("Raw Staffing Need", f"{raw_fte:.2f}", "FTE")
    col4.metric("Whole-Agent Need", f"{unconstrained}", "agents")
    col5.metric("Recommended Staffing", f"{recommended}", "agents")

    # Secondary KPI row
    col1, col2, col3, col4, col5 = st.columns(5, gap="small")
    col1.metric("Previous-Week Staffing", f"{prev_week}", "agents")
    col2.metric("Manager-Planned Staffing", f"{manager_plan}", "agents")

    delta_color = "off" if overflow > 0 else "normal"
    col3.metric(
        "Change from Prev. Week",
        f"{delta_prev:+d}",
        delta=f"{delta_prev:+d} agents",
    )

    if overflow > 0:
        col4.metric("Third-Party Overflow", f"{overflow:.1f}", "hours / week")
    else:
        col4.metric("Spare Capacity", f"{spare:.1f}", "hours / week")

    col5.metric(
        "Weekly Operating Cost",
        f"${total_cost:,.0f}",
        "USD / week",
    )


# ---------------------------------------------------------------------------
# Narrative
# ---------------------------------------------------------------------------

def render_narrative(session_state: Mapping[str, Any]) -> None:
    application_result = session_state.get("analysis_result")
    if not application_result:
        return

    deterministic = application_result["deterministic_staffing_result"]
    effective_forecast = application_result["effective_forecast"]
    recommended = int(deterministic["recommended_inhouse_agents"])
    total_bookings = round(sum(effective_forecast.values()), 1)
    workload = round(float(deterministic["total_workload_hours"]), 1)
    raw_fte = round(float(deterministic["raw_required_fte"]), 2)
    prev_week = int(_load_history().iloc[-1]["staffing_agents"])
    spare = float(deterministic["spare_capacity_hours"])
    overflow = float(deterministic["overflow_workload_hours"])

    applied = session_state.get("applied_inputs", {}) or {}
    workforce = applied.get("workforce_assumptions", {})
    manager_plan = int(workforce.get("planned_staffing_agents", 10)) if workforce else 10
    paid_hours = float(workforce.get("paid_hours_per_agent", 40)) if workforce else 40
    hourly_wage = float(workforce.get("regular_hourly_wage", 22)) if workforce else 22
    total_cost = recommended * paid_hours * hourly_wage

    delta_prev = recommended - prev_week
    delta_mgr = recommended - manager_plan

    parts = [
        f"Schedule **{recommended}** in-house reservation agents for the upcoming week.",
        f"Forecasted demand is approximately **{total_bookings}** bookings, "
        f"representing **{workload}** booking-processing hours and **{raw_fte}** FTE.",
    ]

    if delta_prev > 0:
        parts.append(
            f"This recommendation adds **{delta_prev} agent{'s' if delta_prev != 1 else ''}** "
            f"compared with the previous week"
        )
    elif delta_prev < 0:
        parts.append(
            f"This recommendation removes **{abs(delta_prev)} agent{'s' if abs(delta_prev) != 1 else ''}** "
            f"compared with the previous week"
        )
    else:
        parts.append("This matches the previous week's staffing level")

    if delta_mgr > 0:
        parts.append(
            f"and **{delta_mgr} agent{'s' if delta_mgr != 1 else ''}** "
            f"above the manager's current plan."
        )
    elif delta_mgr < 0:
        parts.append(
            f"and **{abs(delta_mgr)} agent{'s' if abs(delta_mgr) != 1 else ''}** "
            f"below the manager's current plan."
        )
    else:
        parts.append("and matches the manager's current plan.")

    if overflow > 0:
        parts.append(
            "Demand exceeds the 12-agent in-house cap, so third-party overflow is expected."
        )
    else:
        parts.append(
            "Demand remains within the in-house cap, so no third-party overflow is expected."
        )

    parts.append(f"The estimated total weekly operating cost is **${total_cost:,.0f}**.")

    st.markdown("#### Recommendation Rationale")
    st.markdown(". ".join(parts) + ".")


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def render_action_row(session_state: Mapping[str, Any]) -> None:
    history = _load_history()
    defaults = _load_defaults()

    col1, col2, col3, col4 = st.columns([1.2, 1.0, 1.0, 5.0], gap="small")

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
        application_result = session_state.get("analysis_result")
        if application_result:
            export_frames = build_results_export_frames(
                application_result,
                pd.DataFrame(),
                pd.DataFrame(),
            )
            csv_data = export_frames.get("comparison_table", pd.DataFrame()).to_csv(index=False)
            st.download_button(
                "Export Summary",
                data=csv_data,
                file_name="abc_cruise_staffing_summary.csv",
                mime="text/csv",
                use_container_width=True,
            )

    _render_stale_notice(session_state)
    _render_analysis_error(session_state)


def _render_stale_notice(session_state: Mapping[str, Any]) -> None:
    if session_state.get("results_stale", False):
        st.warning("Inputs have changed. Run the analysis to update the recommendation.")


def _render_analysis_error(session_state: Mapping[str, Any]) -> None:
    analysis_error = session_state.get("analysis_error")
    if analysis_error:
        st.error(str(analysis_error["message"]))


# ---------------------------------------------------------------------------
# Adjust Plan expander
# ---------------------------------------------------------------------------

def render_adjust_plan_expander(session_state: Mapping[str, Any]) -> None:
    defaults = _load_defaults()
    history = _load_history()
    application_result = session_state.get("analysis_result")

    with st.expander("Adjust Next Week's Plan", expanded=False):
        st.markdown(
            "Adjust demand scenarios, staffing plans, and override forecasts. "
            "Changes are saved as a draft until you run the analysis."
        )

        with st.form("adjust_plan_form"):
            st.markdown("#### Scenario")
            scenario_label = st.selectbox(
                "Demand scenario",
                options=EXPECTED_SCENARIO_NAMES,
                key="scenario_label",
                help="Low, Expected, or High demand scenario adjusts the automatic forecast.",
            )

            st.markdown("#### Manager Plan")
            manager_staffing = st.number_input(
                "Manager-planned staffing",
                min_value=0,
                max_value=30,
                step=1,
                value=int(
                    session_state.get(
                        workforce_control_key("planned_staffing_agents"),
                        defaults["workforce_assumptions"].planned_staffing_agents,
                    )
                ),
                key=workforce_control_key("planned_staffing_agents"),
                help="Number of agents the manager intends to schedule.",
            )

            st.markdown("#### Manual Forecast Overrides")
            if application_result:
                auto_forecast = application_result["automatic_forecast"]
                scenario_mult = SCENARIO_MULTIPLIERS[scenario_label]["demand"]
            else:
                auto_forecast = {cat: 0.0 for cat in RESERVATION_CATEGORIES}
                scenario_mult = 1.0

            override_cols = st.columns(len(RESERVATION_CATEGORIES), gap="small")
            for idx, category in enumerate(RESERVATION_CATEGORIES):
                with override_cols[idx]:
                    scenario_adj = auto_forecast.get(category, 0.0) * scenario_mult
                    st.caption(CATEGORY_DISPLAY_LABELS[category])
                    st.metric(
                        "Auto forecast",
                        f"{scenario_adj:.1f}",
                    )
                    manual_enabled = st.toggle(
                        "Override",
                        key=manual_override_enabled_key(category),
                    )
                    st.number_input(
                        "Manual value",
                        min_value=0.0,
                        step=1.0,
                        key=manual_override_value_key(category),
                        disabled=not manual_enabled,
                    )

            st.markdown("---")
            save_col, run_col, _ = st.columns([1, 1, 4], gap="small")
            with save_col:
                save_draft = st.form_submit_button("Save Draft")
            with run_col:
                run_analysis = st.form_submit_button("Run Analysis", type="primary")

            if save_draft:
                update_draft_inputs_from_widgets(st.session_state)
                st.rerun()
            elif run_analysis:
                run_analysis_for_current_draft(
                    st.session_state,
                    history=history,
                    defaults=defaults,
                )
                st.rerun()

        render_business_assumptions_expander(session_state, defaults)


def render_business_assumptions_expander(
    session_state: Mapping[str, Any],
    defaults: dict[str, Any],
) -> None:
    with st.expander("Business Assumptions", expanded=False):
        st.markdown("Adjust category handling times, workforce parameters, and strategic assumptions.")

        base_cat = defaults["category_assumptions"]
        base_wf = defaults["workforce_assumptions"]
        base_strat = defaults["strategic_assumptions"]

        st.markdown("##### Category Assumptions")
        cat_cols = st.columns(len(RESERVATION_CATEGORIES), gap="small")
        for idx, category in enumerate(RESERVATION_CATEGORIES):
            with cat_cols[idx]:
                base_item = next(
                    (i for i in base_cat if i.category == category),
                    None,
                )
                st.caption(CATEGORY_DISPLAY_LABELS[category])
                st.number_input(
                    "Handling time (min)",
                    min_value=0.1,
                    step=1.0,
                    key=category_assumption_key(category, "handling_time_minutes"),
                    help="Average minutes to process one reservation.",
                )
                st.number_input(
                    "Avg booking value ($)",
                    min_value=0.0,
                    step=25.0,
                    key=category_assumption_key(category, "average_booking_value"),
                    help="Average revenue per booking in this category.",
                )

        st.markdown("##### Workforce Assumptions")
        wf_col1, wf_col2, wf_col3 = st.columns(3, gap="small")
        wf_col1.number_input(
            "Paid hours per agent",
            min_value=1.0,
            step=1.0,
            key=workforce_control_key("paid_hours_per_agent"),
            help="Weekly paid hours per agent.",
        )
        wf_col2.number_input(
            "Booking-processing hrs/agent",
            min_value=0.1,
            step=0.5,
            key=workforce_control_key("weekly_booking_processing_hours_per_agent"),
            help="Direct booking-processing hours per agent per week.",
        )
        wf_col3.number_input(
            "Hourly labor rate ($)",
            min_value=0.0,
            step=1.0,
            key=workforce_control_key("regular_hourly_wage"),
            help="Regular hourly wage.",
        )
        wf_col1, wf_col2, _ = st.columns(3, gap="small")
        wf_col1.number_input(
            "Minimum agents",
            min_value=0,
            step=1,
            key=workforce_control_key("minimum_schedulable_agents"),
            help="Operating floor - minimum schedulable agents.",
        )
        wf_col2.number_input(
            "Maximum in-house agents",
            min_value=0,
            step=1,
            key=workforce_control_key("maximum_inhouse_agents"),
            help="In-house capacity cap.",
        )

        st.markdown("##### Strategic Assumptions")
        strat_col1, strat_col2 = st.columns(2, gap="small")
        strat_col1.number_input(
            "Third-party commission rate (%)",
            min_value=0.0,
            max_value=100.0,
            step=0.5,
            key=strategic_control_key("third_party_commission_rate"),
            help="Commission rate paid to third-party booking partners.",
        )
        strat_col2.number_input(
            "In-house capture target (%)",
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            key=strategic_control_key("inhouse_capture_target"),
            help="Target share of bookings captured in-house.",
        )


# ---------------------------------------------------------------------------
# Analysis Details expander
# ---------------------------------------------------------------------------

def render_analysis_details_expander(session_state: Mapping[str, Any]) -> None:
    application_result = session_state.get("analysis_result")
    if not application_result:
        return

    history = _load_history()
    deterministic = application_result["deterministic_staffing_result"]
    effective_forecast = application_result["effective_forecast"]
    financial_recommendation = application_result["financial_recommendation"]
    applied = session_state.get("applied_inputs", {}) or {}

    with st.expander("View Analysis Details", expanded=False):
        st.markdown("### Historical Demand")
        hist_display = build_history_display_frame_with_labels(history)
        st.dataframe(hist_display, use_container_width=True)

        st.markdown("### Historical Demand Chart")
        chart_data = history.copy()
        chart_data = chart_data.rename(
            columns={cat: CATEGORY_DISPLAY_LABELS[cat] for cat in RESERVATION_CATEGORIES}
        )
        chart_data["week_start"] = pd.to_datetime(chart_data["week_start"])
        chart_data = chart_data.set_index("week_start")
        chart_columns = [CATEGORY_DISPLAY_LABELS[cat] for cat in RESERVATION_CATEGORIES]
        st.bar_chart(chart_data[chart_columns])

        st.markdown("### Forecast Breakdown")
        forecast_breakdown = build_forecast_breakdown_frame(
            application_result["automatic_forecast"],
            application_result["scenario_adjusted_forecast"],
            effective_forecast,
            {
                cat: float(item["value"])
                for cat, item in applied.get("manual_overrides", {}).items()
                if item.get("enabled")
            }
            if "manual_overrides" in applied
            else None,
            application_result["scenario"]["scenario_name"],
        )
        st.dataframe(forecast_breakdown, use_container_width=True)

        st.markdown("### Workload Breakdown")
        workload_breakdown = build_workload_breakdown_frame(
            effective_forecast,
            deterministic,
            applied.get("category_assumptions", defaults_for_category_labels()),
        )
        st.dataframe(workload_breakdown, use_container_width=True)

        st.markdown("### Staffing and Capacity")
        staffing_frame = build_staffing_capacity_frame(
            deterministic,
            applied.get("workforce_assumptions", {}),
        )
        st.dataframe(staffing_frame, use_container_width=True)

        if float(deterministic["overflow_workload_hours"]) > 0:
            st.markdown("### Overflow Detail")
            overflow_frame = build_overflow_detail_frame(deterministic)
            st.dataframe(overflow_frame, use_container_width=True)

        st.markdown("### Financial Breakdown")
        financial_frame = build_financial_breakdown_frame(
            financial_recommendation,
            deterministic,
            applied.get("category_assumptions", defaults_for_category_labels()),
            applied.get("strategic_assumptions", {"third_party_commission_rate": 0.125}),
        )
        st.dataframe(financial_frame, use_container_width=True)

        st.markdown("### Export")
        export_csv = _build_export_csv(application_result)
        st.download_button(
            "Download Full Report (CSV)",
            data=export_csv,
            file_name="abc_cruise_full_report.csv",
            mime="text/csv",
        )


def defaults_for_category_labels() -> list[dict[str, Any]]:
    defaults = _load_defaults()
    return [item.to_dict() for item in defaults["category_assumptions"]]


def _build_export_csv(application_result: Mapping[str, Any]) -> str:
    """Build a concise manager-friendly CSV from the result."""
    deterministic = application_result["deterministic_staffing_result"]
    effective_forecast = application_result["effective_forecast"]
    fin_rec = application_result["financial_recommendation"]

    lines = ["metric,value,units"]
    total_bk = sum(effective_forecast.values())
    lines.append(f"forecasted_bookings,{total_bk:.1f},bookings/week")
    lines.append(f"forecasted_workload,{float(deterministic['total_workload_hours']):.1f},hours/week")
    lines.append(f"raw_fte,{float(deterministic['raw_required_fte']):.2f},FTE")
    lines.append(f"unconstrained_agents,{int(deterministic['unconstrained_required_agents'])},agents")
    lines.append(f"recommended_agents,{int(deterministic['recommended_inhouse_agents'])},agents")
    lines.append(f"spare_capacity,{float(deterministic['spare_capacity_hours']):.1f},hours/week")
    lines.append(f"overflow_workload,{float(deterministic['overflow_workload_hours']):.1f},hours/week")
    rec = fin_rec["recommended_staffing_record"]
    lines.append(f"labor_cost,{float(rec['regular_labor_cost']):.0f},USD/week")
    lines.append(f"overflow_commission,{float(rec['expected_overflow_commission']):.0f},USD/week")
    lines.append(f"total_operating_cost,{float(rec['expected_total_weekly_operating_cost']):.0f},USD/week")

    for cat in RESERVATION_CATEGORIES:
        lines.append(f"forecast_{cat},{effective_forecast[cat]:.1f},bookings/week")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Methodology expander
# ---------------------------------------------------------------------------

def render_methodology_expander() -> None:
    with st.expander("Methodology and Advanced Settings", expanded=False):
        st.markdown("### How the Recommendation Works")
        st.markdown(
            """
            The staffing recommendation follows a transparent analytical pipeline:
            """
        )
        for point in build_methodology_points():
            st.markdown(f"- {point}")

        defaults = _load_defaults()
        fc = defaults["forecast_configuration"]
        sim = defaults["simulation_configuration"]
        ct = defaults["confidence_targets"]

        st.markdown("### Forecasting")
        st.markdown(
            f"- **Method:** Four-week weighted moving average with weights "
            f"`[{fc.weights[0]}, {fc.weights[1]}, {fc.weights[2]}, {fc.weights[3]}]` (most recent first)."
        )
        st.markdown(
            f"- **Variability multiplier:** `{sim.variability_multiplier}` "
            f"(scaled by scenario factor for High/Low demand)."
        )
        st.markdown(f"- **Simulation iterations:** `{sim.iterations}`")
        st.markdown(f"- **Random seed:** `{sim.random_seed}`")
        st.markdown(f"- **Distribution:** `{sim.distribution_name}`")

        st.markdown("### Capacity")
        st.markdown(
            "- **Workload formula:** Forecast bookings × handling time (minutes) → convert to hours."
        )
        st.markdown(
            "- **Capacity formula:** Workload hours ÷ booking-processing hours per agent → FTE → ceil → whole agents."
        )
        st.markdown(
            "- **Operating floor:** Minimum schedulable agents applied as lower bound."
        )
        st.markdown(
            "- **In-house cap:** Maximum in-house agents applied as upper bound; excess routed to third-party overflow."
        )

        st.markdown("### Overflow Allocation")
        st.markdown(
            "- Workload above in-house capacity is allocated proportionally by category workload share."
        )
        st.markdown(
            f"- **Commission rate:** {decimal_to_percent(float(defaults['strategic_assumptions'].third_party_commission_rate)):.1f}% "
            f"of overflow booking value."
        )

        st.markdown("### Confidence Targets")
        target_data = {
            "Plan": ["Lean", "Balanced", "Conservative"],
            "Confidence": [
                f"{decimal_to_percent(ct.lean):.0f}%",
                f"{decimal_to_percent(ct.balanced):.0f}%",
                f"{decimal_to_percent(ct.conservative):.0f}%",
            ],
        }
        st.dataframe(pd.DataFrame(target_data), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Main dashboard orchestrator
# ---------------------------------------------------------------------------

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

    render_hero_card(st.session_state)
    render_kpi_grid(st.session_state)
    render_narrative(st.session_state)
    render_action_row(st.session_state)
    render_adjust_plan_expander(st.session_state)
    render_analysis_details_expander(st.session_state)
    render_methodology_expander()