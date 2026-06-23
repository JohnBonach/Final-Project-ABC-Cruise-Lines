"""Reusable Streamlit components for the application shell."""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.constants import RESERVATION_CATEGORIES
from src.data.loader import build_history_diagnostics, load_and_validate_history
from src.models import CategoryAssumptions, ConfidenceTargets, SimulationConfiguration, WorkforceAssumptions
from src.orchestration import build_application_result
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
    build_manual_overrides_from_state,
    category_assumption_key,
    confidence_target_control_key,
    confidence_targets_are_ordered,
    decimal_to_percent,
    manual_override_enabled_key,
    manual_override_value_key,
    percent_to_decimal,
    reset_session_state,
    section_options,
    simulation_control_key,
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


def _seed_demand_controls(
    session_state: MutableMapping[str, Any],
    automatic_forecast: Mapping[str, float],
) -> None:
    """Seed widget defaults for the demand-input section."""

    for category in RESERVATION_CATEGORIES:
        session_state.setdefault(manual_override_enabled_key(category), False)
        session_state.setdefault(
            manual_override_value_key(category),
            float(automatic_forecast[category]),
        )


def _seed_operations_controls(session_state: MutableMapping[str, Any], defaults: dict[str, Any]) -> None:
    """Seed widget defaults for the operational and financial controls."""

    for category_assumption in defaults["category_assumptions"]:
        session_state.setdefault(
            category_assumption_key(category_assumption.category, "handling_time_minutes"),
            float(category_assumption.handling_time_minutes),
        )
        session_state.setdefault(
            category_assumption_key(category_assumption.category, "average_revenue"),
            float(category_assumption.average_revenue),
        )
        session_state.setdefault(
            category_assumption_key(
                category_assumption.category,
                "contribution_per_reservation",
            ),
            float(category_assumption.contribution_per_reservation),
        )

    workforce = defaults["workforce_assumptions"]
    session_state.setdefault(workforce_control_key("paid_hours_per_agent"), float(workforce.paid_hours_per_agent))
    session_state.setdefault(
        _percent_widget_key(workforce_control_key("productive_processing_pct")),
        decimal_to_percent(float(workforce.productive_processing_pct)),
    )
    session_state.setdefault(workforce_control_key("regular_hourly_wage"), float(workforce.regular_hourly_wage))
    session_state.setdefault(workforce_control_key("overtime_multiplier"), float(workforce.overtime_multiplier))
    session_state.setdefault(
        _percent_widget_key(workforce_control_key("abandonment_rate")),
        decimal_to_percent(float(workforce.abandonment_rate)),
    )
    session_state.setdefault(workforce_control_key("planned_staffing_agents"), int(workforce.planned_staffing_agents))

    simulation = defaults["simulation_configuration"]
    session_state.setdefault(simulation_control_key("iterations"), int(simulation.iterations))
    session_state.setdefault(simulation_control_key("random_seed"), int(simulation.random_seed or 0))

    confidence_targets = defaults["confidence_targets"]
    session_state.setdefault(
        _percent_widget_key(confidence_target_control_key("lean")),
        decimal_to_percent(float(confidence_targets.lean)),
    )
    session_state.setdefault(
        _percent_widget_key(confidence_target_control_key("balanced")),
        decimal_to_percent(float(confidence_targets.balanced)),
    )
    session_state.setdefault(
        _percent_widget_key(confidence_target_control_key("conservative")),
        decimal_to_percent(float(confidence_targets.conservative)),
    )


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


def _build_confidence_targets_from_state(session_state: Mapping[str, Any]) -> ConfidenceTargets:
    """Build a validated confidence-target model from the current widget state."""

    return ConfidenceTargets(
        lean=_render_percent_value_from_state(
            session_state,
            base_key=confidence_target_control_key("lean"),
        ),
        balanced=_render_percent_value_from_state(
            session_state,
            base_key=confidence_target_control_key("balanced"),
        ),
        conservative=_render_percent_value_from_state(
            session_state,
            base_key=confidence_target_control_key("conservative"),
        ),
    )


def _build_simulation_configuration_from_state(
    session_state: Mapping[str, Any],
    defaults: dict[str, Any],
) -> SimulationConfiguration:
    """Build a validated simulation-configuration model from the current widget state."""

    simulation_defaults = defaults["simulation_configuration"]
    return SimulationConfiguration(
        iterations=int(session_state[simulation_control_key("iterations")]),
        random_seed=int(session_state[simulation_control_key("random_seed")]),
        variability_multiplier=float(simulation_defaults.variability_multiplier),
        distribution_name=str(simulation_defaults.distribution_name),
    )


def _build_workforce_assumptions_from_state(
    session_state: Mapping[str, Any],
) -> WorkforceAssumptions:
    """Build a validated workforce-assumption model from the current widget state."""

    return WorkforceAssumptions(
        paid_hours_per_agent=float(session_state[workforce_control_key("paid_hours_per_agent")]),
        productive_processing_pct=_render_percent_value_from_state(
            session_state,
            base_key=workforce_control_key("productive_processing_pct"),
        ),
        regular_hourly_wage=float(session_state[workforce_control_key("regular_hourly_wage")]),
        overtime_multiplier=float(session_state[workforce_control_key("overtime_multiplier")]),
        abandonment_rate=_render_percent_value_from_state(
            session_state,
            base_key=workforce_control_key("abandonment_rate"),
        ),
        planned_staffing_agents=int(
            session_state[workforce_control_key("planned_staffing_agents")]
        ),
    )


def _build_application_result_from_state(
    session_state: Mapping[str, Any],
    manual_overrides: Mapping[str, float] | None,
    *,
    history: pd.DataFrame | None = None,
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the full orchestration result from the current widget state."""

    history = history if history is not None else _load_history()
    defaults = defaults if defaults is not None else _load_defaults()
    return build_application_result(
        history=history,
        category_assumptions=_build_category_assumptions_from_state(session_state),
        workforce_assumptions=_build_workforce_assumptions_from_state(session_state),
        forecast_configuration=defaults["forecast_configuration"],
        simulation_configuration=_build_simulation_configuration_from_state(
            session_state,
            defaults,
        ),
        confidence_targets=_build_confidence_targets_from_state(session_state),
        previous_week_staffing=int(history.iloc[-1]["staffing_agents"]),
        manager_planned_staffing=int(
            session_state[workforce_control_key("planned_staffing_agents")]
        ),
        manual_overrides=manual_overrides,
    )


def _resolve_demand_application_result(
    session_state: MutableMapping[str, Any],
    preview_result: Mapping[str, Any],
    *,
    history: pd.DataFrame,
    defaults: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, float]]:
    """Reuse the preview result unless manual overrides require a recompute."""

    automatic_forecast = preview_result["automatic_forecast"]
    _seed_demand_controls(session_state, automatic_forecast)

    manual_overrides = build_manual_overrides_from_state(session_state)
    if not manual_overrides:
        return dict(preview_result), manual_overrides

    application_result = _build_application_result_from_state(
        session_state,
        manual_overrides,
        history=history,
        defaults=defaults,
    )
    return application_result, manual_overrides


def render_sidebar(session_state: Mapping[str, Any]) -> None:
    """Render persistent shell controls in the sidebar."""

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
            help="Restore the default workspace state, clear widget inputs, and return to the Overview section.",
            on_click=reset_session_state,
            args=(st.session_state,),
        )


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
    _seed_operations_controls(st.session_state, defaults)
    diagnostics = build_history_diagnostics(history)
    preview_result = _build_application_result_from_state(
        st.session_state,
        None,
        history=history,
        defaults=defaults,
    )
    if not preview_result.get("ok", False):
        st.error(preview_result["error"]["message"])
        return

    automatic_forecast = preview_result["automatic_forecast"]

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

            try:
                application_result, manual_overrides = _resolve_demand_application_result(
                    st.session_state,
                    preview_result,
                    history=history,
                    defaults=defaults,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                if not application_result.get("ok", False):
                    st.error(application_result["error"]["message"])
                    return
                forecast_result = application_result["forecast_result"]
                forecast_display = build_forecast_display_frame(
                    automatic_forecast,
                    forecast_result,
                    manual_overrides=manual_overrides,
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
    _seed_operations_controls(st.session_state, defaults)

    st.subheader("Operations")
    st.write(
        "Validated assumption controls cover category economics, workforce capacity, confidence targets, and simulation setup in manager-friendly terms."
    )
    st.caption(
        "Percent-based values are displayed as UI-friendly percentages but converted back to decimals before validation and downstream use."
    )

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
            st.number_input(
                "Simulation iterations",
                min_value=1,
                step=100,
                key=simulation_control_key("iterations"),
                help="Number of Monte Carlo repetitions to run when the simulation layer is connected.",
            )
            st.number_input(
                "Random seed",
                min_value=0,
                step=1,
                key=simulation_control_key("random_seed"),
                help="Reproducible seed for simulation draws and downstream randomized checks.",
            )
            st.caption(
                f"Defaults keep the simulation distribution at `{defaults['simulation_configuration'].distribution_name}` with a variability multiplier of `{defaults['simulation_configuration'].variability_multiplier}`."
            )
            try:
                simulation_configuration = _build_simulation_configuration_from_state(
                    st.session_state,
                    defaults,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.json(simulation_configuration.to_dict())


def render_results(session_state: Mapping[str, Any]) -> None:
    """Render the executive recommendation dashboard and comparison views."""

    st.subheader("Results")
    defaults = _load_defaults()
    _seed_operations_controls(st.session_state, defaults)
    try:
        manual_overrides = build_manual_overrides_from_state(st.session_state)
    except ValueError as exc:
        st.error(str(exc))
        return

    application_result = _build_application_result_from_state(
        session_state,
        manual_overrides or None,
    )
    if not application_result.get("ok", False):
        st.error(application_result["error"]["message"])
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

    st.write(
        f"Scenario `{session_state['scenario_label']}` is active. The dashboard below stays aligned with the orchestration result and updates whenever assumptions change."
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
