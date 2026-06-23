"""Reusable Streamlit components for the application shell."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.constants import RESERVATION_CATEGORIES
from src.data.loader import build_history_diagnostics, load_and_validate_history
from src.models import CategoryAssumptions, ConfidenceTargets, SimulationConfiguration, WorkforceAssumptions
from src.ui.charts import (
    build_category_assumptions_frame,
    build_forecast_display_frame,
    build_history_display_frame,
    build_methodology_points,
    build_plan_comparison_frame,
    build_recommendation_summary_frame,
    build_results_export_frames,
    build_tradeoff_chart_frames,
)
from src.ui.state import (
    category_assumption_key,
    confidence_target_control_key,
    confidence_targets_are_ordered,
    decimal_to_percent,
    manual_override_enabled_key,
    manual_override_value_key,
    percent_to_decimal,
    refresh_draft_shell_preferences,
    reset_session_state,
    run_analysis_for_current_draft,
    section_options,
    simulation_control_key,
    update_draft_inputs_from_widgets,
    workforce_control_key,
)
from src.validation import EXPECTED_SCENARIO_NAMES, load_defaults_config

BASE_PATH = Path(__file__).resolve().parents[2]
HISTORY_PATH = BASE_PATH / "data" / "synthetic_history.csv"
DEFAULTS_PATH = BASE_PATH / "config" / "defaults.json"

FORECAST_MODE_LABELS: dict[str, str] = {
    "automatic": "Automatic",
    "manual_override": "Manual override",
}


def _percent_widget_key(base_key: str) -> str:
    """Return a widget key for a percent-valued control."""

    return f"{base_key}__percent"


@st.cache_data(show_spinner=False)
def _load_history() -> pd.DataFrame:
    """Load and validate the shared historical-demand file."""

    return load_and_validate_history(HISTORY_PATH)


@st.cache_data(show_spinner=False)
def _load_defaults() -> dict[str, Any]:
    """Load the validated default configuration file."""

    return load_defaults_config(DEFAULTS_PATH)


def _render_percent_input(
    label: str,
    *,
    base_key: str,
    default_decimal: float,
    help_text: str,
) -> float:
    """Render a percent-valued input and return its internal decimal value."""

    widget_key = _percent_widget_key(base_key)
    st.session_state.setdefault(widget_key, decimal_to_percent(default_decimal))
    percent_value = st.number_input(
        label,
        min_value=0.0,
        max_value=100.0,
        step=1.0,
        format="%.1f",
        key=widget_key,
        help=help_text,
    )
    return percent_to_decimal(float(percent_value))


def _build_category_assumptions_from_state(session_state: Mapping[str, Any]) -> tuple[CategoryAssumptions, ...]:
    """Build validated category assumption models from the current widget state."""

    assumptions: list[CategoryAssumptions] = []
    for category in RESERVATION_CATEGORIES:
        assumptions.append(
            CategoryAssumptions(
                category=category,
                handling_time_minutes=float(
                    session_state[category_assumption_key(category, "handling_time_minutes")]
                ),
                average_revenue=float(
                    session_state[category_assumption_key(category, "average_revenue")]
                ),
                contribution_per_reservation=float(
                    session_state[
                        category_assumption_key(category, "contribution_per_reservation")
                    ]
                ),
            )
        )
    return tuple(assumptions)


def _render_percent_value_from_state(
    session_state: Mapping[str, Any],
    *,
    base_key: str,
) -> float:
    """Read a percent-valued widget from session state and convert it to a decimal."""

    display_key = _percent_widget_key(base_key)
    raw_value = session_state[display_key]
    return percent_to_decimal(float(raw_value))


def _render_stale_notice(session_state: Mapping[str, Any]) -> None:
    """Show the stale-results warning when draft inputs differ from applied inputs."""

    if session_state.get("results_stale", False):
        st.warning("Inputs have changed. Run the analysis to update the recommendation.")


def _render_analysis_error(session_state: Mapping[str, Any]) -> None:
    """Show the last stored analysis error when present."""

    analysis_error = session_state.get("analysis_error")
    if analysis_error:
        st.error(str(analysis_error["message"]))


def render_sidebar(session_state: Mapping[str, Any]) -> None:
    """Render persistent shell controls in the sidebar."""

    history = _load_history()
    defaults = _load_defaults()
    with st.sidebar:
        st.header("Workspace")
        st.caption("All sections share one validated orchestration result.")
        st.radio(
            "Section",
            options=section_options(),
            key="active_section",
        )
        st.selectbox(
            "Reservation category",
            options=RESERVATION_CATEGORIES,
            key="selected_category",
        )
        st.radio(
            "Forecast mode",
            options=("automatic", "manual_override"),
            key="forecast_mode",
            format_func=lambda option: FORECAST_MODE_LABELS.get(option, option),
            horizontal=True,
        )
        st.selectbox(
            "Scenario",
            options=EXPECTED_SCENARIO_NAMES,
            key="scenario_label",
            help="Scenario label used in the comparison and export views.",
        )
        st.slider(
            "Weeks to display",
            min_value=4,
            max_value=26,
            key="weeks_to_display",
        )
        st.toggle(
            "Show contract snapshot",
            key="show_contract_snapshot",
        )
        st.text_area(
            "Working notes",
            key="manual_override_notes",
            height=120,
            placeholder="Capture assumptions or follow-up items here.",
        )
        st.caption("These controls stay in sync with the shared staffing workflow.")
        st.divider()
        st.button(
            "Reset workspace",
            type="secondary",
            help="Restore baseline inputs, return to the Overview section, and rerun the baseline analysis.",
            on_click=reset_session_state,
            kwargs={"session_state": st.session_state, "history": history, "defaults": defaults},
        )
    refresh_draft_shell_preferences(st.session_state)


def render_header() -> None:
    """Render the top-level page heading."""

    st.title("ABC Cruise Lines Reservation Staffing DSS")
    st.caption(
        "This weekly staffing workspace turns validated history, manager assumptions, and simulation results into one recommendation."
    )


def render_active_section(session_state: Mapping[str, Any]) -> None:
    """Render the active content section."""

    active_section = session_state["active_section"]
    if active_section == "Overview":
        render_overview(session_state)
    elif active_section == "Demand Inputs":
        render_demand_inputs(session_state)
    elif active_section == "Operations":
        render_operations(session_state)
    else:
        render_results(session_state)


def render_overview(session_state: Mapping[str, Any]) -> None:
    """Render the overview section."""

    left_col, right_col = st.columns((1.4, 1.0), gap="large")
    with left_col:
        st.subheader("Application overview")
        st.write(
            "This workspace helps a reservation manager review the forecast, operating assumptions, simulation risk, and final staffing recommendation in one place."
        )
        st.info(
            "All visible results come from the shared orchestration pipeline, so the dashboard stays internally consistent and every unit is shown explicitly."
        )
    with right_col:
        st.subheader("Current workspace state")
        st.metric("Active section", session_state["active_section"])
        st.metric(
            "Forecast mode",
            FORECAST_MODE_LABELS.get(session_state["forecast_mode"], session_state["forecast_mode"]),
        )
        st.metric("Focused category", session_state["selected_category"])

    if session_state["show_contract_snapshot"]:
        st.subheader("Shared contract snapshot")
        st.json(
            {
                "reservation_categories": list(RESERVATION_CATEGORIES),
                "scenario_label": session_state["scenario_label"],
                "weeks_to_display": session_state["weeks_to_display"],
            }
        )


def render_demand_inputs(session_state: Mapping[str, Any]) -> None:
    """Render validated historical demand and forecast controls."""

    history = _load_history()
    defaults = _load_defaults()
    forecast_config = defaults["forecast_configuration"]
    diagnostics = build_history_diagnostics(history)
    application_result = session_state.get("analysis_result")
    if not application_result:
        _render_analysis_error(session_state)
        return

    automatic_forecast = application_result["automatic_forecast"]

    st.subheader("Demand Inputs")
    st.write(
        "Validated historical demand feeds the automatic forecast. Manual overrides can be enabled independently by category when the manager has better current information."
    )
    st.caption(
        "Automatic forecast uses the validated history and the shared default weights; manual overrides only replace the enabled category and leave the other categories unchanged."
    )

    top_left, top_center, top_right = st.columns(3, gap="medium")
    top_left.metric("Historical weeks", diagnostics["week_count"])
    top_center.metric(
        "History range",
        f"{diagnostics['date_range']['start']} to {diagnostics['date_range']['end']}",
    )
    top_right.metric("Forecast mode", FORECAST_MODE_LABELS.get(session_state["forecast_mode"], session_state["forecast_mode"]))

    left_col, right_col = st.columns((1.05, 1.25), gap="large")
    with left_col:
        with st.container(border=True):
            st.markdown("**Validated history**")
            st.caption("The table below is loaded from `data/synthetic_history.csv` after validation.")
            history_display = build_history_display_frame(
                history,
                weeks_to_display=int(session_state["weeks_to_display"]),
            )
            st.dataframe(history_display, use_container_width=True)

        with st.expander("History diagnostics", expanded=False):
            st.json(diagnostics["quality_checks"])
            st.json(
                {
                    "category_summary": diagnostics["category_summary"],
                    "staffing_summary": diagnostics["staffing_summary"],
                }
            )

    with right_col:
        with st.container(border=True):
            st.markdown("**Forecast by category**")
            st.caption("Automatic, manual, and effective values are shown side by side for each reservation category.")
            with st.form("demand_inputs_form"):
                for category in RESERVATION_CATEGORIES:
                    with st.container(border=True):
                        st.markdown(f"**{category.replace('_', ' ').title()}**")
                        category_cols = st.columns((1.0, 1.0))
                        category_cols[0].metric(
                            "Automatic forecast",
                            f"{automatic_forecast[category]:.1f}",
                        )
                        manual_enabled = category_cols[1].toggle(
                            "Enable manual override",
                            key=manual_override_enabled_key(category),
                            help="When enabled, the manual forecast replaces only this category's automatic forecast.",
                        )
                        st.number_input(
                            "Manual forecast",
                            min_value=0.0,
                            step=1.0,
                            key=manual_override_value_key(category),
                            disabled=not manual_enabled,
                            help="Enter a non-negative weekly reservation forecast. The value is only used when manual override is enabled.",
                        )
                action_cols = st.columns(2, gap="medium")
                save_draft = action_cols[0].form_submit_button("Save Draft")
                run_analysis = action_cols[1].form_submit_button("Run Analysis", type="primary")

            if save_draft:
                update_draft_inputs_from_widgets(st.session_state)
            elif run_analysis:
                run_analysis_for_current_draft(
                    st.session_state,
                    history=history,
                    defaults=defaults,
                )
                application_result = st.session_state.get("analysis_result")

            _render_stale_notice(st.session_state)
            _render_analysis_error(st.session_state)
            applied_inputs = session_state.get("applied_inputs", {})
            applied_manual_overrides = {
                category: float(item["value"])
                for category, item in applied_inputs.get("manual_overrides", {}).items()
                if item["enabled"]
            }
            forecast_result = application_result["forecast_result"]
            forecast_display = build_forecast_display_frame(
                automatic_forecast,
                forecast_result,
                manual_overrides=applied_manual_overrides,
            )
            st.dataframe(forecast_display, use_container_width=True)
            st.bar_chart(
                forecast_display.set_index("category")[
                    ["automatic_forecast", "effective_forecast"]
                ]
            )
            st.caption("Forecast source is explicit in the table, and manual overrides remain independent from the automatic forecast.")

        with st.container(border=True):
            st.markdown("**Default forecast settings**")
            st.write(f"Weights: `{list(forecast_config.weights)}`")
            st.write(f"Variability multiplier: `{forecast_config.variability_multiplier}`")


def render_operations(session_state: Mapping[str, Any]) -> None:
    """Render the operational and financial control section."""

    defaults = _load_defaults()
    history = _load_history()

    st.subheader("Operations")
    st.write(
        "Validated assumption controls cover category economics, workforce capacity, confidence targets, and simulation setup in manager-friendly terms."
    )
    st.caption(
        "Percent-based values are displayed as UI-friendly percentages but converted back to decimals before validation and downstream use."
    )

    with st.form("operations_form"):
        category_tab, workforce_tab, simulation_tab = st.tabs(
            ["Category assumptions", "Workforce and finance", "Confidence and simulation"]
        )

        with category_tab:
            st.write("Category assumptions are editable one reservation type at a time.")
            category_rows: list[dict[str, Any]] = []
            for category in RESERVATION_CATEGORIES:
                with st.container(border=True):
                    st.markdown(f"**{category.replace('_', ' ').title()}**")
                    value_cols = st.columns(3, gap="small")
                    handling_time = value_cols[0].number_input(
                        "Handling time (minutes/reservation)",
                        min_value=0.1,
                        step=1.0,
                        key=category_assumption_key(category, "handling_time_minutes"),
                        help="Average staff time required to process one reservation in this category.",
                    )
                    average_revenue = value_cols[1].number_input(
                        "Average revenue ($/reservation)",
                        min_value=0.0,
                        step=25.0,
                        key=category_assumption_key(category, "average_revenue"),
                        help="Gross revenue expected from one reservation before contribution is applied.",
                    )
                    contribution = value_cols[2].number_input(
                        "Contribution ($/reservation)",
                        min_value=0.0,
                        step=10.0,
                        key=category_assumption_key(category, "contribution_per_reservation"),
                        help="Contribution dollars retained per reservation after direct category costs.",
                    )
                    category_rows.append(
                        {
                            "category": category,
                            "handling_time_minutes": float(handling_time),
                            "average_revenue": float(average_revenue),
                            "contribution_per_reservation": float(contribution),
                        }
                    )

            try:
                category_assumptions = _build_category_assumptions_from_state(st.session_state)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.dataframe(
                    build_category_assumptions_frame(category_rows),
                    use_container_width=True,
                )
                st.caption("The table reflects the current controls; the validated model preserves the canonical category order.")
                st.json([item.to_dict() for item in category_assumptions])

        with workforce_tab:
            st.write("Workforce controls combine capacity, compensation, and abandonment assumptions.")
            left_col, right_col = st.columns((1.2, 0.9), gap="large")
            with left_col:
                paid_hours_per_agent = st.number_input(
                    "Paid hours per agent (hours/week)",
                    min_value=1.0,
                    step=1.0,
                    key=workforce_control_key("paid_hours_per_agent"),
                    help="Weekly paid hours available per agent before productivity adjustments.",
                )
                productive_processing_pct = _render_percent_input(
                    "Productive processing (% of paid hours)",
                    base_key=workforce_control_key("productive_processing_pct"),
                    default_decimal=float(defaults["workforce_assumptions"].productive_processing_pct),
                    help_text="Share of paid hours that can be used for reservation processing.",
                )
                regular_hourly_wage = st.number_input(
                    "Regular hourly wage ($/hour)",
                    min_value=0.0,
                    step=1.0,
                    key=workforce_control_key("regular_hourly_wage"),
                    help="Base hourly wage for regular labor hours.",
                )
                overtime_multiplier = st.number_input(
                    "Overtime multiplier (x)",
                    min_value=1.0,
                    step=0.1,
                    key=workforce_control_key("overtime_multiplier"),
                    help="Multiplier applied to regular wage when overtime is required.",
                )
                abandonment_rate = _render_percent_input(
                    "Abandonment rate (% of excess demand)",
                    base_key=workforce_control_key("abandonment_rate"),
                    default_decimal=float(defaults["workforce_assumptions"].abandonment_rate),
                    help_text="Share of excess demand assumed to abandon the queue rather than wait.",
                )
                planned_staffing_agents = st.number_input(
                    "Planned staffing (agents)",
                    min_value=0,
                    step=1,
                    key=workforce_control_key("planned_staffing_agents"),
                    help="Baseline agent count to plan against before the optimizer or staffing simulation runs.",
                )

            with right_col:
                try:
                    workforce_assumptions = WorkforceAssumptions(
                        paid_hours_per_agent=float(paid_hours_per_agent),
                        productive_processing_pct=productive_processing_pct,
                        regular_hourly_wage=float(regular_hourly_wage),
                        overtime_multiplier=float(overtime_multiplier),
                        abandonment_rate=abandonment_rate,
                        planned_staffing_agents=int(planned_staffing_agents),
                    )
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.markdown("**Current workforce snapshot**")
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "field": "Paid hours per agent",
                                    "value": workforce_assumptions.paid_hours_per_agent,
                                    "units": "hours/week",
                                },
                                {
                                    "field": "Productive processing",
                                    "value": decimal_to_percent(workforce_assumptions.productive_processing_pct),
                                    "units": "%",
                                },
                                {
                                    "field": "Regular hourly wage",
                                    "value": workforce_assumptions.regular_hourly_wage,
                                    "units": "$/hour",
                                },
                                {
                                    "field": "Overtime multiplier",
                                    "value": workforce_assumptions.overtime_multiplier,
                                    "units": "x",
                                },
                                {
                                    "field": "Abandonment rate",
                                    "value": decimal_to_percent(workforce_assumptions.abandonment_rate),
                                    "units": "%",
                                },
                                {
                                    "field": "Planned staffing",
                                    "value": workforce_assumptions.planned_staffing_agents,
                                    "units": "agents",
                                },
                            ]
                        ),
                        use_container_width=True,
                    )
                    st.caption("Percent fields are stored as decimals in the validated model.")

        with simulation_tab:
            st.write("Confidence targets and simulation controls are managed together so the target ordering stays visible.")
            left_col, right_col = st.columns((1.1, 0.9), gap="large")
            with left_col:
                lean_target = _render_percent_input(
                    "Lean confidence target (%)",
                    base_key=confidence_target_control_key("lean"),
                    default_decimal=float(defaults["confidence_targets"].lean),
                    help_text="Lower-confidence staffing target, shown as a percent in the UI but stored internally as a decimal.",
                )
                balanced_target = _render_percent_input(
                    "Balanced confidence target (%)",
                    base_key=confidence_target_control_key("balanced"),
                    default_decimal=float(defaults["confidence_targets"].balanced),
                    help_text="Middle confidence target for the balanced staffing plan.",
                )
                conservative_target = _render_percent_input(
                    "Conservative confidence target (%)",
                    base_key=confidence_target_control_key("conservative"),
                    default_decimal=float(defaults["confidence_targets"].conservative),
                    help_text="Highest confidence target for the conservative staffing plan.",
                )

                try:
                    confidence_targets = ConfidenceTargets(
                        lean=lean_target,
                        balanced=balanced_target,
                        conservative=conservative_target,
                    )
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    if confidence_targets_are_ordered(confidence_targets.to_dict()):
                        st.success("Confidence targets are ordered Lean <= Balanced <= Conservative.")
                    else:
                        st.warning(
                            "Confidence targets should increase from Lean to Balanced to Conservative; otherwise the named plans become difficult to interpret."
                        )
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "plan": "Lean",
                                    "confidence_target_pct": decimal_to_percent(confidence_targets.lean),
                                },
                                {
                                    "plan": "Balanced",
                                    "confidence_target_pct": decimal_to_percent(confidence_targets.balanced),
                                },
                                {
                                    "plan": "Conservative",
                                    "confidence_target_pct": decimal_to_percent(confidence_targets.conservative),
                                },
                            ]
                        ),
                        use_container_width=True,
                    )

            with right_col:
                iterations = st.number_input(
                    "Simulation iterations",
                    min_value=1,
                    step=100,
                    key=simulation_control_key("iterations"),
                    help="Number of Monte Carlo repetitions to run when the simulation layer is connected.",
                )
                random_seed = st.number_input(
                    "Random seed",
                    min_value=0,
                    step=1,
                    key=simulation_control_key("random_seed"),
                    help="Reproducible seed for simulation draws and downstream randomized checks.",
                )
                st.caption(
                    f"Defaults keep the simulation distribution at `{defaults['simulation_configuration'].distribution_name}` with a variability multiplier of `{defaults['simulation_configuration'].variability_multiplier}`."
                )
                simulation_configuration = SimulationConfiguration(
                    iterations=int(iterations),
                    random_seed=int(random_seed),
                    variability_multiplier=float(defaults["simulation_configuration"].variability_multiplier),
                    distribution_name=str(defaults["simulation_configuration"].distribution_name),
                )
                st.json(simulation_configuration.to_dict())

        action_cols = st.columns(2, gap="medium")
        save_draft = action_cols[0].form_submit_button("Save Draft")
        run_analysis = action_cols[1].form_submit_button("Run Analysis", type="primary")

    if save_draft:
        update_draft_inputs_from_widgets(st.session_state)
    elif run_analysis:
        run_analysis_for_current_draft(
            st.session_state,
            history=history,
            defaults=defaults,
        )
    _render_stale_notice(st.session_state)
    _render_analysis_error(st.session_state)


def render_results(session_state: Mapping[str, Any]) -> None:
    """Render the executive recommendation dashboard and comparison views."""

    st.subheader("Results")
    _render_stale_notice(session_state)
    _render_analysis_error(session_state)
    application_result = session_state.get("analysis_result")
    if not application_result:
        return

    financial_recommendation = application_result["financial_recommendation"]
    comparison_table = application_result["narrative"]["comparison_table"]
    recommendation_summary = build_recommendation_summary_frame(
        financial_recommendation,
        comparison_table,
    )
    comparison_frame = build_plan_comparison_frame(comparison_table)
    tradeoff_frames = build_tradeoff_chart_frames(comparison_table)

    recommended_staffing = int(financial_recommendation["recommended_staffing_agents"])
    recommended_record = financial_recommendation["recommended_staffing_record"]
    summary_values = recommendation_summary.set_index("metric")["value"].to_dict()

    applied_scenario_label = session_state.get("applied_inputs", {}).get("shell", {}).get(
        "scenario_label",
        session_state["scenario_label"],
    )
    st.write(
        f"Scenario `{applied_scenario_label}` is active. The dashboard below stays aligned with the orchestration result and updates whenever assumptions change."
    )
    with st.container(border=True):
        st.markdown("**Executive recommendation**")
        st.markdown(
            f"### Schedule {recommended_staffing} reservation agents"
        )
        st.caption(
            "Units are explicit: agents, %, hours per week, reservations per week, and USD per week."
        )

        top_row = st.columns(4, gap="medium")
        top_row[0].metric(
            "Recommended staffing",
            f"{recommended_staffing} agents",
            delta=f"{int(summary_values['Difference vs previous week']):+d} vs previous week",
        )
        top_row[1].metric(
            "Capacity confidence",
            f"{summary_values['Capacity confidence']:.1f}%",
        )
        top_row[2].metric(
            "Expected total economic cost",
            f"${summary_values['Expected total economic cost']:,.2f} / week",
        )
        top_row[3].metric(
            "Expected overtime",
            f"{summary_values['Expected overtime']:.1f} hours / week",
        )

        bottom_row = st.columns(4, gap="medium")
        bottom_row[0].metric(
            "Expected abandonment",
            f"{summary_values['Expected abandonment']:.1f} reservations / week",
        )
        bottom_row[1].metric(
            "Difference vs manager plan",
            f"{int(summary_values['Difference vs manager plan']):+d} agents",
        )
        bottom_row[2].metric(
            "Weekly overtime hours",
            f"{recommended_record['expected_overtime_hours']:.1f} hours",
        )
        bottom_row[3].metric(
            "Weekly abandonment",
            f"{recommended_record['expected_abandoned_total']:.1f} reservations",
        )

        st.info(application_result["narrative"]["text"])
        warnings = application_result["narrative"]["warnings"]
        if warnings:
            st.warning(" ".join(warnings))

    with st.expander("Methodology", expanded=False):
        st.write(
            "This recommendation stays manager-friendly by moving from the latest validated demand to a staffing choice in a few transparent steps."
        )
        for point in build_methodology_points():
            st.markdown(f"- {point}")
        st.caption(
            "Manual overrides affect only enabled categories, and the recommendation still compares the same named plans before choosing the lowest-cost option."
        )

    st.subheader("Plan comparison")
    st.caption(
        "Previous Week, Manager Plan, Lean, Balanced, Conservative, and Financial Recommendation all come from the same orchestration output."
    )
    st.dataframe(
        comparison_frame.reset_index(drop=True),
        use_container_width=True,
    )

    chart_cols = st.columns(3, gap="large")
    with chart_cols[0]:
        st.markdown("**Expected total economic cost (USD/week)**")
        st.bar_chart(tradeoff_frames["cost"].set_index("plan_name"))
    with chart_cols[1]:
        st.markdown("**Expected overtime (hours/week)**")
        st.bar_chart(tradeoff_frames["overtime"].set_index("plan_name"))
    with chart_cols[2]:
        st.markdown("**Expected abandonment (reservations/week)**")
        st.bar_chart(tradeoff_frames["abandonment"].set_index("plan_name"))

    with st.expander("Executive summary details", expanded=False):
        st.dataframe(
            recommendation_summary.reset_index(drop=True),
            use_container_width=True,
        )

    export_frames = build_results_export_frames(
        application_result,
        recommendation_summary,
        comparison_frame,
    )
    export_labels = {
        "forecast_result": "Forecast result",
        "staffing_evaluation_table": "Staffing evaluation",
        "named_plan_table": "Named plan table",
        "comparison_table": "Comparison table",
        "plan_comparison_display": "Plan comparison display",
        "recommendation_summary": "Executive summary",
    }
    with st.expander("Export", expanded=False):
        st.write("Download the structured outputs as CSV for reporting, audit, or downstream analysis.")
        export_cols = st.columns(2, gap="medium")
        for index, (name, frame) in enumerate(export_frames.items()):
            export_cols[index % 2].download_button(
                export_labels[name],
                data=frame.to_csv(index=False),
                file_name=f"{name}.csv",
                mime="text/csv",
                key=f"export_{name}",
            )
