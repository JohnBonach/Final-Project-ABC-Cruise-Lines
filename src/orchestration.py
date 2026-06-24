"""Orchestration helpers that compose the backend analytical pipeline."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from src.constants import RESERVATION_CATEGORIES, STAFFING_EVALUATION_COLUMNS
from src.decision.narrative import (
    build_manager_comparison_narrative,
    build_recommendation_text,
    build_recommendation_warnings,
)
from src.decision.optimizer import select_financial_recommendation
from src.decision.plans import (
    build_candidate_staffing_list,
    build_named_plan_table,
    select_named_plans,
)
from src.finance.staffing_evaluator import (
    build_staffing_feasibility_flags,
    build_structured_staffing_record,
    calculate_regular_labor_cost_from_workforce,
    classify_staffing_feasibility_status,
    evaluate_staffing_level,
)
from src.finance.economics import calculate_weekly_operating_financials
from src.forecasting.uncertainty import build_forecast_result
from src.forecasting.weighted_moving_average import calculate_weighted_moving_average
from src.models import (
    CategoryAssumptions,
    ConfidenceTargets,
    DecisionPolicy,
    ForecastConfiguration,
    RepresentativeDemandOutlook,
    SimulationConfiguration,
    StrategicAssumptions,
    WorkforceAssumptions,
)
from src.operations.capacity import (
    calculate_booking_processing_hours_per_agent,
    calculate_required_agents,
    calculate_required_fte,
    clamp_inhouse_staffing,
)
from src.operations.workload import calculate_workload_hours, calculate_workload_hours_by_category
from src.simulation.demand_sampler import simulate_weekly_demand
from src.simulation.monte_carlo import (
    calculate_simulated_workload_and_staffing,
    select_representative_simulation_rows,
)
from src.simulation.shortage import calculate_overflow_allocation_by_category
from src.validation import (
    FieldValidationError,
    validate_non_negative,
    validate_non_negative_integer,
)

CategoryValueMap = dict[str, float]
DeterministicStaffingResult = dict[str, CategoryValueMap | float | int]
ApplicationResult = dict[str, Any]


def _normalize_demand_by_category(
    demand_by_category: Mapping[str, Any],
) -> CategoryValueMap:
    if not isinstance(demand_by_category, Mapping):
        raise FieldValidationError("demand_by_category must be a mapping keyed by category")

    actual_categories = tuple(demand_by_category.keys())
    if actual_categories != RESERVATION_CATEGORIES:
        raise FieldValidationError(
            "demand_by_category must include each canonical category exactly once "
            f"and in the shared order {RESERVATION_CATEGORIES}"
        )

    return {
        category: validate_non_negative(
            f"demand_by_category.{category}",
            demand_by_category[category],
        )
        for category in RESERVATION_CATEGORIES
    }


def _normalize_category_assumptions(
    category_assumptions: Iterable[CategoryAssumptions | Mapping[str, Any]],
) -> tuple[CategoryAssumptions, ...]:
    normalized = tuple(
        item
        if isinstance(item, CategoryAssumptions)
        else CategoryAssumptions.from_dict(dict(item))
        for item in category_assumptions
    )
    if len(normalized) != len(RESERVATION_CATEGORIES):
        raise FieldValidationError(
            "category_assumptions must contain exactly one entry for each canonical category"
        )

    categories = tuple(item.category for item in normalized)
    if categories != RESERVATION_CATEGORIES:
        raise FieldValidationError(
            "category_assumptions must include each canonical category exactly once "
            "and in the shared order"
        )
    return normalized


def _normalize_workforce_assumptions(
    workforce_assumptions: WorkforceAssumptions | Mapping[str, Any],
) -> WorkforceAssumptions:
    if isinstance(workforce_assumptions, WorkforceAssumptions):
        return workforce_assumptions
    if not isinstance(workforce_assumptions, Mapping):
        raise TypeError(
            "workforce_assumptions must be a WorkforceAssumptions instance or mapping"
        )
    return WorkforceAssumptions.from_dict(dict(workforce_assumptions))


def _normalize_forecast_configuration(
    forecast_configuration: ForecastConfiguration | Mapping[str, Any],
) -> ForecastConfiguration:
    if isinstance(forecast_configuration, ForecastConfiguration):
        return forecast_configuration
    if not isinstance(forecast_configuration, Mapping):
        raise TypeError(
            "forecast_configuration must be a ForecastConfiguration instance or mapping"
        )
    return ForecastConfiguration.from_dict(dict(forecast_configuration))


def _normalize_simulation_configuration(
    simulation_configuration: SimulationConfiguration | Mapping[str, Any],
) -> SimulationConfiguration:
    if isinstance(simulation_configuration, SimulationConfiguration):
        return simulation_configuration
    if not isinstance(simulation_configuration, Mapping):
        raise TypeError(
            "simulation_configuration must be a SimulationConfiguration instance or mapping"
        )
    return SimulationConfiguration.from_dict(dict(simulation_configuration))


def _normalize_confidence_targets(
    confidence_targets: ConfidenceTargets | Mapping[str, Any],
) -> ConfidenceTargets:
    if isinstance(confidence_targets, ConfidenceTargets):
        return confidence_targets
    if not isinstance(confidence_targets, Mapping):
        raise TypeError(
            "confidence_targets must be a ConfidenceTargets instance or mapping"
        )
    return ConfidenceTargets.from_dict(dict(confidence_targets))


def _normalize_strategic_assumptions(
    strategic_assumptions: StrategicAssumptions | Mapping[str, Any],
) -> StrategicAssumptions:
    if isinstance(strategic_assumptions, StrategicAssumptions):
        return strategic_assumptions
    if not isinstance(strategic_assumptions, Mapping):
        raise TypeError(
            "strategic_assumptions must be a StrategicAssumptions instance or mapping"
        )
    return StrategicAssumptions.from_dict(dict(strategic_assumptions))


def _normalize_decision_policy(
    decision_policy: DecisionPolicy | Mapping[str, Any] | None,
) -> DecisionPolicy:
    if decision_policy is None:
        return DecisionPolicy(minimum_inhouse_coverage_target=0.85)
    if isinstance(decision_policy, DecisionPolicy):
        return decision_policy
    if not isinstance(decision_policy, Mapping):
        raise TypeError(
            "decision_policy must be a DecisionPolicy instance or mapping"
        )
    return DecisionPolicy.from_dict(dict(decision_policy))


def _extract_handling_times(
    category_assumptions: tuple[CategoryAssumptions, ...],
) -> dict[str, float]:
    return {
        item.category: item.handling_time_minutes
        for item in category_assumptions
    }


def calculate_deterministic_staffing(
    demand_by_category: Mapping[str, Any],
    category_assumptions: Iterable[CategoryAssumptions | Mapping[str, Any]],
    workforce_assumptions: WorkforceAssumptions | Mapping[str, Any],
) -> DeterministicStaffingResult:
    """Assemble deterministic workload, floor/cap, and overflow outputs."""

    normalized_demand = _normalize_demand_by_category(demand_by_category)
    normalized_category_assumptions = _normalize_category_assumptions(category_assumptions)
    normalized_workforce_assumptions = _normalize_workforce_assumptions(
        workforce_assumptions
    )

    handling_times_minutes = _extract_handling_times(normalized_category_assumptions)
    workload_hours_by_category = calculate_workload_hours_by_category(
        normalized_demand,
        handling_times_minutes,
    )
    total_workload_hours = calculate_workload_hours(
        normalized_demand,
        handling_times_minutes,
    )
    booking_processing_hours_per_agent = calculate_booking_processing_hours_per_agent(
        normalized_workforce_assumptions.weekly_booking_processing_hours_per_agent
    )
    raw_required_fte = calculate_required_fte(
        total_workload_hours,
        booking_processing_hours_per_agent,
    )
    unconstrained_required_agents = calculate_required_agents(raw_required_fte)
    recommended_inhouse_agents = clamp_inhouse_staffing(
        unconstrained_required_agents,
        normalized_workforce_assumptions.minimum_schedulable_agents,
        normalized_workforce_assumptions.maximum_inhouse_agents,
    )
    overflow_result = calculate_overflow_allocation_by_category(
        normalized_demand,
        handling_times_minutes,
        recommended_inhouse_agents,
        booking_processing_hours_per_agent,
    )

    return {
        "workload_hours_by_category": workload_hours_by_category,
        "total_workload_hours": total_workload_hours,
        "booking_processing_hours_per_agent": booking_processing_hours_per_agent,
        "raw_required_fte": raw_required_fte,
        "unconstrained_required_agents": unconstrained_required_agents,
        "recommended_inhouse_agents": recommended_inhouse_agents,
        "spare_capacity_hours": float(overflow_result["spare_capacity_hours"]),
        "overflow_workload_hours": float(overflow_result["overflow_workload_hours"]),
        "overflow_hours_by_category": dict(overflow_result["overflow_hours_by_category"]),
        "overflow_bookings_by_category": dict(overflow_result["overflow_bookings_by_category"]),
    }


def _lookup_staffing_record(
    staffing_records: Mapping[int, dict[str, Any]],
    staffing_agents: int,
    *,
    field_name: str,
) -> dict[str, Any]:
    if staffing_agents not in staffing_records:
        raise FieldValidationError(f"{field_name} must exist in the staffing evaluation table")
    return dict(staffing_records[staffing_agents])


def _build_recommendation_policy(
    decision_policy: DecisionPolicy,
    financial_recommendation: Mapping[str, Any],
    candidate_staffing_levels: list[int],
    *,
    minimum_staffing: int,
    maximum_staffing: int,
) -> dict[str, Any]:
    return {
        "minimum_inhouse_coverage_target": (
            decision_policy.minimum_inhouse_coverage_target
        ),
        "candidate_staffing_levels": list(candidate_staffing_levels),
        "minimum_schedulable_agents": int(minimum_staffing),
        "maximum_inhouse_agents": int(maximum_staffing),
        "selection_tolerance": float(financial_recommendation["selection_tolerance"]),
        "objective_column": str(financial_recommendation["objective_column"]),
        "difference_direction": "manager_value_minus_recommendation_value",
    }


def _build_recommended_plan(
    financial_recommendation: Mapping[str, Any],
    workforce_assumptions: WorkforceAssumptions,
) -> dict[str, Any]:
    recommended_plan = build_structured_staffing_record(
        financial_recommendation["recommended_staffing_record"],
        workforce_assumptions,
    )
    recommended_plan["selected_minimum_inhouse_coverage_target"] = float(
        financial_recommendation["selected_minimum_inhouse_coverage_target"]
    )
    recommended_plan["recommended_coverage"] = float(
        financial_recommendation["recommended_coverage"]
    )
    recommended_plan["coverage_target_met"] = bool(
        financial_recommendation["coverage_target_met"]
    )
    recommended_plan["maximum_achievable_coverage"] = float(
        financial_recommendation["maximum_achievable_coverage"]
    )
    recommended_plan["warning"] = financial_recommendation["warning"]
    return recommended_plan


def _build_previous_week_staffing_context(
    staffing_agents: int,
    workforce_assumptions: WorkforceAssumptions,
) -> dict[str, Any]:
    feasibility_status = classify_staffing_feasibility_status(
        staffing_agents,
        workforce_assumptions,
    )
    flags = build_staffing_feasibility_flags(
        staffing_agents,
        workforce_assumptions,
    )
    return {
        "staffing_agents": int(staffing_agents),
        "feasibility_status": feasibility_status,
        **flags,
    }


def _build_recommendation_manager_comparison(
    recommended_plan: Mapping[str, Any],
    manager_proposal: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "staffing_difference": (
            int(manager_proposal["staffing_agents"])
            - int(recommended_plan["staffing_agents"])
        ),
        "coverage_difference": (
            float(manager_proposal["capacity_confidence"])
            - float(recommended_plan["capacity_confidence"])
        ),
        "overflow_probability_difference": (
            float(manager_proposal["probability_overflow_required"])
            - float(recommended_plan["probability_overflow_required"])
        ),
        "labor_cost_difference": (
            float(manager_proposal["regular_labor_cost"])
            - float(recommended_plan["regular_labor_cost"])
        ),
        "overflow_commission_difference": (
            float(manager_proposal["expected_overflow_commission"])
            - float(recommended_plan["expected_overflow_commission"])
        ),
        "total_cost_difference": (
            float(manager_proposal["expected_total_weekly_operating_cost"])
            - float(recommended_plan["expected_total_weekly_operating_cost"])
        ),
        "spare_capacity_difference": (
            float(manager_proposal["expected_spare_capacity_hours"])
            - float(recommended_plan["expected_spare_capacity_hours"])
        ),
        "overflow_workload_difference": (
            float(manager_proposal["expected_overflow_workload_hours"])
            - float(recommended_plan["expected_overflow_workload_hours"])
        ),
        "manager_feasibility_status": str(manager_proposal["feasibility_status"]),
    }


def _build_staffing_risk_cost_records(
    staffing_levels: list[int],
    staffing_evaluation_rows: Mapping[int, dict[str, Any]],
    workforce_assumptions: WorkforceAssumptions,
    *,
    recommended_staffing_agents: int,
    manager_staffing_agents: int,
    previous_week_staffing_agents: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for staffing_agents in staffing_levels:
        structured_record = build_structured_staffing_record(
            _lookup_staffing_record(
                staffing_evaluation_rows,
                staffing_agents,
                field_name="staffing risk-cost level",
            ),
            workforce_assumptions,
        )
        structured_record["is_model_recommendation"] = (
            staffing_agents == recommended_staffing_agents
        )
        structured_record["is_manager_proposal"] = (
            staffing_agents == manager_staffing_agents
        )
        structured_record["is_previous_week"] = (
            staffing_agents == previous_week_staffing_agents
        )
        records.append(structured_record)
    return records


def _build_representative_outlook(
    *,
    selected_row: Mapping[str, Any],
    outlook_name: str,
    percentile: float,
    percentile_label: str,
    representative_row_reused: bool,
    category_assumptions: tuple[CategoryAssumptions, ...],
    workforce_assumptions: WorkforceAssumptions,
    strategic_assumptions: StrategicAssumptions,
) -> dict[str, Any]:
    demand_by_category = {
        category: float(selected_row[category])
        for category in RESERVATION_CATEGORIES
    }
    deterministic_result = calculate_deterministic_staffing(
        demand_by_category,
        category_assumptions,
        workforce_assumptions,
    )
    handling_times_minutes = _extract_handling_times(category_assumptions)
    overflow_result = calculate_overflow_allocation_by_category(
        demand_by_category,
        handling_times_minutes,
        int(deterministic_result["recommended_inhouse_agents"]),
        float(deterministic_result["booking_processing_hours_per_agent"]),
    )
    financials = calculate_weekly_operating_financials(
        overflow_result["inhouse_bookings_by_category"],
        overflow_result["overflow_bookings_by_category"],
        category_assumptions,
        strategic_assumptions.third_party_commission_rate,
    )
    regular_labor_cost = calculate_regular_labor_cost_from_workforce(
        int(deterministic_result["recommended_inhouse_agents"]),
        workforce_assumptions,
    )
    overflow_commission = float(financials["total_overflow_commission"])

    return RepresentativeDemandOutlook(
        outlook_name=outlook_name,
        percentile=percentile,
        percentile_label=percentile_label,
        simulation_row_id=int(selected_row["simulation_id"]),
        representative_row_reused=representative_row_reused,
        demand_by_category=demand_by_category,
        total_bookings=float(sum(demand_by_category.values())),
        workload_hours_by_category={
            category: float(deterministic_result["workload_hours_by_category"][category])
            for category in RESERVATION_CATEGORIES
        },
        total_workload_hours=float(deterministic_result["total_workload_hours"]),
        raw_required_fte=float(deterministic_result["raw_required_fte"]),
        unconstrained_required_agents=int(
            deterministic_result["unconstrained_required_agents"]
        ),
        recommended_inhouse_agents_for_outlook=int(
            deterministic_result["recommended_inhouse_agents"]
        ),
        spare_capacity_hours=float(deterministic_result["spare_capacity_hours"]),
        overflow_workload_hours=float(deterministic_result["overflow_workload_hours"]),
        overflow_bookings_by_category={
            category: float(deterministic_result["overflow_bookings_by_category"][category])
            for category in RESERVATION_CATEGORIES
        },
        regular_labor_cost=float(regular_labor_cost),
        overflow_commission=overflow_commission,
        total_weekly_operating_cost=float(regular_labor_cost + overflow_commission),
    ).to_dict()


def _build_probabilistic_outlooks(
    completed_simulation: pd.DataFrame,
    *,
    category_assumptions: tuple[CategoryAssumptions, ...],
    workforce_assumptions: WorkforceAssumptions,
    strategic_assumptions: StrategicAssumptions,
) -> dict[str, Any]:
    selection_result = select_representative_simulation_rows(completed_simulation)
    outlooks_by_label: dict[str, dict[str, Any]] = {}
    for selected_row in selection_result["selected_rows"]:
        outlooks_by_label[str(selected_row["percentile_label"])] = _build_representative_outlook(
            selected_row=selected_row["row"],
            outlook_name=str(selected_row["outlook_name"]),
            percentile=float(selected_row["percentile"]),
            percentile_label=str(selected_row["percentile_label"]),
            representative_row_reused=bool(selected_row["representative_row_reused"]),
            category_assumptions=category_assumptions,
            workforce_assumptions=workforce_assumptions,
            strategic_assumptions=strategic_assumptions,
        )

    return {
        "lower_demand_outlook": outlooks_by_label["P25"],
        "central_demand_outlook": outlooks_by_label["P50"],
        "higher_demand_outlook": outlooks_by_label["P90"],
        "outlook_diagnostics": dict(selection_result["diagnostics"]),
    }


def _build_comparison_table(
    staffing_records: Mapping[int, dict[str, Any]],
    recommended_plan: Mapping[str, Any],
    named_plans: Mapping[str, int],
    *,
    previous_week_staffing: int,
    manager_planned_staffing: int,
) -> pd.DataFrame:
    recommended_staffing_agents = int(recommended_plan["staffing_agents"])

    plan_order: list[tuple[str, int]] = [
        ("Previous Week", previous_week_staffing),
        ("Manager Plan", manager_planned_staffing),
        ("Lean", int(named_plans["lean"])),
        ("Balanced", int(named_plans["balanced"])),
        ("Conservative", int(named_plans["conservative"])),
        ("Financial Recommendation", recommended_staffing_agents),
    ]

    rows: list[dict[str, Any]] = []
    for plan_name, staffing_agents in plan_order:
        row = (
            dict(recommended_plan)
            if plan_name == "Financial Recommendation"
            else _lookup_staffing_record(
                staffing_records,
                staffing_agents,
                field_name=f"{plan_name} staffing level",
            )
        )
        rows.append(
            {
                "plan_name": plan_name,
                "staffing_agents": int(staffing_agents),
                "capacity_confidence": float(row["capacity_confidence"]),
                "expected_spare_capacity_hours": float(row["expected_spare_capacity_hours"]),
                "expected_overflow_workload_hours": float(row["expected_overflow_workload_hours"]),
                "expected_total_weekly_operating_cost": float(
                    row["expected_total_weekly_operating_cost"]
                ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=(
            "plan_name",
            "staffing_agents",
            "capacity_confidence",
            "expected_spare_capacity_hours",
            "expected_overflow_workload_hours",
            "expected_total_weekly_operating_cost",
        ),
    )


def build_application_result(
    *,
    history: pd.DataFrame,
    category_assumptions: Iterable[CategoryAssumptions | Mapping[str, Any]],
    workforce_assumptions: WorkforceAssumptions | Mapping[str, Any],
    forecast_configuration: ForecastConfiguration | Mapping[str, Any],
    simulation_configuration: SimulationConfiguration | Mapping[str, Any],
    confidence_targets: ConfidenceTargets | Mapping[str, Any],
    strategic_assumptions: StrategicAssumptions | Mapping[str, Any],
    decision_policy: DecisionPolicy | Mapping[str, Any] | None = None,
    previous_week_staffing: int | None = None,
    manager_planned_staffing: int | None = None,
    manual_overrides: Mapping[str, float] | None = None,
) -> ApplicationResult:
    """Build the structured backend result for the restored analytical pipeline."""

    try:
        if not isinstance(history, pd.DataFrame):
            raise FieldValidationError("history must be a pandas DataFrame")

        normalized_category_assumptions = _normalize_category_assumptions(category_assumptions)
        normalized_workforce_assumptions = _normalize_workforce_assumptions(
            workforce_assumptions
        )
        normalized_forecast_configuration = _normalize_forecast_configuration(
            forecast_configuration
        )
        normalized_simulation_configuration = _normalize_simulation_configuration(
            simulation_configuration
        )
        normalized_confidence_targets = _normalize_confidence_targets(confidence_targets)
        normalized_decision_policy = _normalize_decision_policy(decision_policy)
        normalized_strategic_assumptions = _normalize_strategic_assumptions(
            strategic_assumptions
        )

        manual_overrides_payload = dict(manual_overrides or {})
        automatic_forecast = calculate_weighted_moving_average(
            history,
            list(normalized_forecast_configuration.weights),
        )
        effective_forecast = {
            category: float(
                manual_overrides_payload.get(
                    category,
                    automatic_forecast[category],
                )
            )
            for category in RESERVATION_CATEGORIES
        }
        forecast_result = build_forecast_result(
            history,
            list(normalized_forecast_configuration.weights),
            float(normalized_simulation_configuration.variability_multiplier),
            demand_multiplier=1.0,
            manual_overrides=manual_overrides_payload or None,
        )

        deterministic_staffing_result = calculate_deterministic_staffing(
            effective_forecast,
            normalized_category_assumptions,
            normalized_workforce_assumptions,
        )

        simulation_distribution = simulate_weekly_demand(
            forecast_result,
            iterations=normalized_simulation_configuration.iterations,
            seed=normalized_simulation_configuration.random_seed,
            distribution_name=normalized_simulation_configuration.distribution_name,
        )
        handling_times_minutes = _extract_handling_times(normalized_category_assumptions)
        completed_simulation = calculate_simulated_workload_and_staffing(
            simulation_distribution,
            handling_times_minutes,
            normalized_workforce_assumptions.weekly_booking_processing_hours_per_agent,
            minimum_schedulable_agents=normalized_workforce_assumptions.minimum_schedulable_agents,
            maximum_inhouse_agents=normalized_workforce_assumptions.maximum_inhouse_agents,
        )
        probabilistic_outlooks = _build_probabilistic_outlooks(
            completed_simulation,
            category_assumptions=normalized_category_assumptions,
            workforce_assumptions=normalized_workforce_assumptions,
            strategic_assumptions=normalized_strategic_assumptions,
        )

        resolved_previous_week_staffing = (
            validate_non_negative_integer(
                "previous_week_staffing",
                previous_week_staffing,
            )
            if previous_week_staffing is not None
            else validate_non_negative_integer(
                "history.iloc[-1]['staffing_agents']",
                history.iloc[-1]["staffing_agents"],
            )
        )
        resolved_manager_staffing = (
            validate_non_negative_integer(
                "manager_planned_staffing",
                manager_planned_staffing,
            )
            if manager_planned_staffing is not None
            else validate_non_negative_integer(
                "workforce_assumptions.planned_staffing_agents",
                normalized_workforce_assumptions.planned_staffing_agents,
            )
        )
        minimum_staffing = normalized_workforce_assumptions.minimum_schedulable_agents
        maximum_staffing = normalized_workforce_assumptions.maximum_inhouse_agents

        feasible_required_agents = completed_simulation["recommended_inhouse_agents"].tolist()
        candidate_staffing_levels = build_candidate_staffing_list(
            minimum_staffing,
            maximum_staffing,
        )

        named_plan_selections = {
            name: clamp_inhouse_staffing(
                staffing,
                minimum_staffing,
                maximum_staffing,
            )
            for name, staffing in select_named_plans(
                feasible_required_agents,
                normalized_confidence_targets.to_dict(),
            ).items()
        }

        risk_cost_staffing_levels = sorted(
            {
                *candidate_staffing_levels,
                resolved_manager_staffing,
                resolved_previous_week_staffing,
            }
        )
        risk_cost_evaluation_rows = [
            evaluate_staffing_level(
                completed_simulation,
                staffing_agents,
                normalized_category_assumptions,
                normalized_workforce_assumptions,
                normalized_strategic_assumptions,
            )
            for staffing_agents in risk_cost_staffing_levels
        ]
        risk_cost_evaluation_row_map = {
            int(row["staffing_agents"]): dict(row)
            for row in risk_cost_evaluation_rows
        }
        staffing_evaluation_rows = [
            _lookup_staffing_record(
                risk_cost_evaluation_row_map,
                staffing_agents,
                field_name="recommendation candidate staffing level",
            )
            for staffing_agents in candidate_staffing_levels
        ]
        staffing_evaluation_table = pd.DataFrame(
            staffing_evaluation_rows,
            columns=STAFFING_EVALUATION_COLUMNS,
        )

        financial_recommendation = select_financial_recommendation(
            staffing_evaluation_table,
            minimum_inhouse_coverage_target=(
                normalized_decision_policy.minimum_inhouse_coverage_target
            ),
        )
        recommendation_policy = _build_recommendation_policy(
            normalized_decision_policy,
            financial_recommendation,
            candidate_staffing_levels,
            minimum_staffing=minimum_staffing,
            maximum_staffing=maximum_staffing,
        )
        recommended_plan = _build_recommended_plan(
            financial_recommendation,
            normalized_workforce_assumptions,
        )
        manager_proposal = build_structured_staffing_record(
            _lookup_staffing_record(
                risk_cost_evaluation_row_map,
                resolved_manager_staffing,
                field_name="manager_planned_staffing",
            ),
            normalized_workforce_assumptions,
            include_boundary_warnings=True,
        )
        previous_week_staffing_context = _build_previous_week_staffing_context(
            resolved_previous_week_staffing,
            normalized_workforce_assumptions,
        )
        recommendation_manager_comparison = _build_recommendation_manager_comparison(
            recommended_plan,
            manager_proposal,
        )
        staffing_risk_cost_records = _build_staffing_risk_cost_records(
            risk_cost_staffing_levels,
            risk_cost_evaluation_row_map,
            normalized_workforce_assumptions,
            recommended_staffing_agents=int(recommended_plan["staffing_agents"]),
            manager_staffing_agents=resolved_manager_staffing,
            previous_week_staffing_agents=resolved_previous_week_staffing,
        )
        adaptive_comparison_narrative = build_manager_comparison_narrative(
            recommendation_policy,
            recommended_plan,
            manager_proposal,
            recommendation_manager_comparison,
        )
        staffing_evaluation_references = {
            int(row["staffing_agents"]): f"staffing_{int(row['staffing_agents'])}"
            for row in staffing_evaluation_rows
        }
        named_plan_table = build_named_plan_table(
            named_plan_selections,
            normalized_confidence_targets.to_dict(),
            staffing_evaluation_references=staffing_evaluation_references,
        )
        comparison_table = _build_comparison_table(
            risk_cost_evaluation_row_map,
            recommended_plan,
            named_plan_selections,
            previous_week_staffing=resolved_previous_week_staffing,
            manager_planned_staffing=resolved_manager_staffing,
        )

        narrative_text = build_recommendation_text(
            financial_recommendation,
            comparison_table,
        )
        narrative_warnings = build_recommendation_warnings(
            financial_recommendation,
            comparison_table,
        )

        return {
            "ok": True,
            "automatic_forecast": automatic_forecast,
            "effective_forecast": effective_forecast,
            "forecast_result": forecast_result,
            "deterministic_staffing_result": deterministic_staffing_result,
            "simulation_distribution": simulation_distribution,
            "decision_policy": normalized_decision_policy.to_dict(),
            "recommendation_policy": recommendation_policy,
            "staffing_evaluation_table": staffing_evaluation_table,
            "named_plans": {
                "selected": named_plan_selections,
                "table": named_plan_table,
                "candidate_staffing_levels": candidate_staffing_levels,
                "staffing_evaluation_references": staffing_evaluation_references,
            },
            "financial_recommendation": financial_recommendation,
            "recommended_plan": recommended_plan,
            "manager_proposal": manager_proposal,
            "lower_demand_outlook": probabilistic_outlooks["lower_demand_outlook"],
            "central_demand_outlook": probabilistic_outlooks["central_demand_outlook"],
            "higher_demand_outlook": probabilistic_outlooks["higher_demand_outlook"],
            "outlook_diagnostics": probabilistic_outlooks["outlook_diagnostics"],
            "previous_week_staffing_context": previous_week_staffing_context,
            "recommendation_manager_comparison": recommendation_manager_comparison,
            "adaptive_comparison_narrative": adaptive_comparison_narrative,
            "staffing_risk_cost_records": staffing_risk_cost_records,
            "narrative": {
                "text": narrative_text,
                "warnings": narrative_warnings,
                "comparison_table": comparison_table,
                "manager_comparison": adaptive_comparison_narrative,
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
            },
        }


__all__ = ["build_application_result", "calculate_deterministic_staffing"]
