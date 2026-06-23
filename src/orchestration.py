"""Orchestration helpers that compose the backend analytical pipeline."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from src.constants import RESERVATION_CATEGORIES, STAFFING_EVALUATION_COLUMNS
from src.decision.narrative import build_recommendation_text, build_recommendation_warnings
from src.decision.optimizer import select_financial_recommendation
from src.decision.plans import (
    build_candidate_staffing_list,
    build_named_plan_table,
    select_named_plans,
)
from src.finance.staffing_evaluator import evaluate_staffing_level
from src.forecasting.uncertainty import build_forecast_result
from src.forecasting.weighted_moving_average import calculate_weighted_moving_average
from src.models import (
    CategoryAssumptions,
    ConfidenceTargets,
    ForecastConfiguration,
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
from src.simulation.monte_carlo import calculate_simulated_workload_and_staffing
from src.simulation.shortage import calculate_overflow_allocation_by_category
from src.validation import (
    FieldValidationError,
    load_scenarios_config,
    validate_non_negative,
)

DEFAULT_SCENARIOS_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "scenarios.json"
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


def _resolve_scenario(scenario_name: str | None) -> dict[str, Any]:
    normalized_name = scenario_name or "Expected Demand"
    scenarios = load_scenarios_config(DEFAULT_SCENARIOS_CONFIG_PATH)["scenarios"]
    for scenario in scenarios:
        if scenario["scenario_name"] == normalized_name:
            return dict(scenario)
    raise FieldValidationError(f"unknown scenario_name {normalized_name!r}")


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


def _lookup_staffing_row(
    staffing_evaluation_rows: Mapping[int, dict[str, Any]],
    staffing_agents: int,
    *,
    field_name: str,
) -> dict[str, Any]:
    if staffing_agents not in staffing_evaluation_rows:
        raise FieldValidationError(f"{field_name} must exist in the staffing evaluation table")
    return dict(staffing_evaluation_rows[staffing_agents])


def _build_comparison_table(
    staffing_evaluation_table: pd.DataFrame,
    recommendation: Mapping[str, Any],
    named_plans: Mapping[str, int],
    *,
    previous_week_staffing: int,
    manager_planned_staffing: int,
) -> pd.DataFrame:
    evaluation_rows = {
        int(row["staffing_agents"]): row
        for row in staffing_evaluation_table.to_dict(orient="records")
    }
    recommended_record = dict(recommendation["recommended_staffing_record"])
    recommended_staffing_agents = int(recommendation["recommended_staffing_agents"])

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
            recommended_record
            if plan_name == "Financial Recommendation"
            else _lookup_staffing_row(
                evaluation_rows,
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
    previous_week_staffing: int | None = None,
    manager_planned_staffing: int | None = None,
    manual_overrides: Mapping[str, float] | None = None,
    scenario_name: str | None = None,
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
        normalized_strategic_assumptions = _normalize_strategic_assumptions(
            strategic_assumptions
        )
        scenario = _resolve_scenario(scenario_name)

        manual_overrides_payload = dict(manual_overrides or {})
        automatic_forecast = calculate_weighted_moving_average(
            history,
            list(normalized_forecast_configuration.weights),
        )
        scenario_adjusted_forecast = {
            category: automatic_forecast[category] * float(scenario["demand_multiplier"])
            for category in RESERVATION_CATEGORIES
        }
        effective_forecast = {
            category: float(
                manual_overrides_payload.get(
                    category,
                    scenario_adjusted_forecast[category],
                )
            )
            for category in RESERVATION_CATEGORIES
        }
        forecast_result = build_forecast_result(
            history,
            list(normalized_forecast_configuration.weights),
            float(normalized_simulation_configuration.variability_multiplier)
            * float(scenario["variability_multiplier"]),
            demand_multiplier=float(scenario["demand_multiplier"]),
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

        resolved_previous_week_staffing = (
            int(previous_week_staffing)
            if previous_week_staffing is not None
            else int(history.iloc[-1]["staffing_agents"])
        )
        resolved_manager_staffing = (
            int(manager_planned_staffing)
            if manager_planned_staffing is not None
            else int(normalized_workforce_assumptions.planned_staffing_agents)
        )

        feasible_required_agents = completed_simulation["recommended_inhouse_agents"].tolist()
        candidate_staffing_levels = build_candidate_staffing_list(
            feasible_required_agents,
            previous_week_staffing=resolved_previous_week_staffing,
            manager_planned_staffing=resolved_manager_staffing,
        )
        candidate_staffing_levels = [
            staffing
            for staffing in candidate_staffing_levels
            if normalized_workforce_assumptions.minimum_schedulable_agents
            <= staffing
            <= normalized_workforce_assumptions.maximum_inhouse_agents
        ]

        named_plan_selections = {
            name: clamp_inhouse_staffing(
                staffing,
                normalized_workforce_assumptions.minimum_schedulable_agents,
                normalized_workforce_assumptions.maximum_inhouse_agents,
            )
            for name, staffing in select_named_plans(
                feasible_required_agents,
                normalized_confidence_targets.to_dict(),
            ).items()
        }
        candidate_staffing_levels = sorted(
            set(candidate_staffing_levels) | set(named_plan_selections.values())
        )

        staffing_evaluation_rows = [
            evaluate_staffing_level(
                completed_simulation,
                staffing_agents,
                normalized_category_assumptions,
                normalized_workforce_assumptions,
                normalized_strategic_assumptions,
            )
            for staffing_agents in candidate_staffing_levels
        ]
        staffing_evaluation_table = pd.DataFrame(
            staffing_evaluation_rows,
            columns=STAFFING_EVALUATION_COLUMNS,
        )

        financial_recommendation = select_financial_recommendation(staffing_evaluation_table)
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
            staffing_evaluation_table,
            financial_recommendation,
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
            "scenario": scenario,
            "automatic_forecast": automatic_forecast,
            "scenario_adjusted_forecast": scenario_adjusted_forecast,
            "effective_forecast": effective_forecast,
            "forecast_result": forecast_result,
            "deterministic_staffing_result": deterministic_staffing_result,
            "simulation_distribution": simulation_distribution,
            "staffing_evaluation_table": staffing_evaluation_table,
            "named_plans": {
                "selected": named_plan_selections,
                "table": named_plan_table,
                "candidate_staffing_levels": candidate_staffing_levels,
                "staffing_evaluation_references": staffing_evaluation_references,
            },
            "financial_recommendation": financial_recommendation,
            "narrative": {
                "text": narrative_text,
                "warnings": narrative_warnings,
                "comparison_table": comparison_table,
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
