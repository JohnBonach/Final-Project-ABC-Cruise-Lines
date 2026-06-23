"""Orchestration helpers that compose existing DSS calculation primitives."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
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
from src.forecasting.uncertainty import build_forecast_result
from src.forecasting.weighted_moving_average import calculate_weighted_moving_average
from src.finance.staffing_evaluator import evaluate_staffing_level
from src.models import (
    CategoryAssumptions,
    ConfidenceTargets,
    ForecastConfiguration,
    SimulationConfiguration,
    WorkforceAssumptions,
)
from src.operations.capacity import (
    calculate_productive_hours_per_agent,
    calculate_required_agents,
    calculate_required_fte,
)
from src.operations.workload import (
    calculate_workload_hours,
    calculate_workload_hours_by_category,
)
from src.simulation.demand_sampler import simulate_weekly_demand
from src.simulation.monte_carlo import calculate_simulated_workload_and_staffing
from src.validation import FieldValidationError, validate_non_negative

CategoryValueMap = dict[str, float]
DeterministicStaffingResult = dict[str, CategoryValueMap | float | int]
ApplicationResult = dict[str, Any]


def _normalize_demand_by_category(
    demand_by_category: Mapping[str, Any],
) -> CategoryValueMap:
    """Validate forecast demand using the shared category contract and validation path."""

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
    """Return validated category assumptions from shared models or plain mappings."""

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
    """Return validated workforce assumptions from a shared model or plain mapping."""

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
    """Return validated forecast configuration from a shared model or plain mapping."""

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
    """Return validated simulation configuration from a shared model or plain mapping."""

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
    """Return validated confidence targets from a shared model or plain mapping."""

    if isinstance(confidence_targets, ConfidenceTargets):
        return confidence_targets
    if not isinstance(confidence_targets, Mapping):
        raise TypeError(
            "confidence_targets must be a ConfidenceTargets instance or mapping"
        )
    return ConfidenceTargets.from_dict(dict(confidence_targets))


def calculate_deterministic_staffing(
    demand_by_category: Mapping[str, Any],
    category_assumptions: Iterable[CategoryAssumptions | Mapping[str, Any]],
    workforce_assumptions: WorkforceAssumptions | Mapping[str, Any],
) -> DeterministicStaffingResult:
    """Assemble deterministic workload and baseline staffing outputs from shared primitives."""

    normalized_demand = _normalize_demand_by_category(demand_by_category)
    normalized_category_assumptions = _normalize_category_assumptions(category_assumptions)
    normalized_workforce_assumptions = _normalize_workforce_assumptions(
        workforce_assumptions
    )

    handling_times_minutes = {
        item.category: item.handling_time_minutes
        for item in normalized_category_assumptions
    }
    workload_hours_by_category = calculate_workload_hours_by_category(
        normalized_demand,
        handling_times_minutes,
    )
    total_workload_hours = calculate_workload_hours(
        normalized_demand,
        handling_times_minutes,
    )
    productive_hours_per_agent = calculate_productive_hours_per_agent(
        normalized_workforce_assumptions.paid_hours_per_agent,
        normalized_workforce_assumptions.productive_processing_pct,
    )
    required_fte = calculate_required_fte(
        total_workload_hours,
        productive_hours_per_agent,
    )
    required_agents = calculate_required_agents(required_fte)

    return {
        "workload_hours_by_category": workload_hours_by_category,
        "total_workload_hours": total_workload_hours,
        "productive_hours_per_agent": productive_hours_per_agent,
        "required_fte": required_fte,
        "required_agents": required_agents,
    }


def _lookup_staffing_row(
    staffing_evaluation_rows: Mapping[int, dict[str, Any]],
    staffing_agents: int,
    *,
    field_name: str,
) -> dict[str, Any]:
    """Return a staffed evaluation row for a given whole-agent staffing level."""

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
    """Build the comparison table used by the narrative and dashboard preview."""

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
                "expected_overtime_hours": float(row["expected_overtime_hours"]),
                "expected_abandoned_total": float(row["expected_abandoned_total"]),
                "expected_total_economic_cost": float(row["expected_total_economic_cost"]),
            }
        )

    return pd.DataFrame(
        rows,
        columns=(
            "plan_name",
            "staffing_agents",
            "capacity_confidence",
            "expected_overtime_hours",
            "expected_abandoned_total",
            "expected_total_economic_cost",
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
    previous_week_staffing: int | None = None,
    manager_planned_staffing: int | None = None,
    manual_overrides: Mapping[str, float] | None = None,
) -> ApplicationResult:
    """Build the structured application result for the end-to-end dashboard flow."""

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

        if (
            normalized_forecast_configuration.variability_multiplier
            != normalized_simulation_configuration.variability_multiplier
        ):
            raise FieldValidationError(
                "forecast_configuration.variability_multiplier must match "
                "simulation_configuration.variability_multiplier"
            )

        manual_overrides_payload = dict(manual_overrides or {})
        automatic_forecast = calculate_weighted_moving_average(
            history,
            list(normalized_forecast_configuration.weights),
        )
        forecast_result = build_forecast_result(
            history,
            list(normalized_forecast_configuration.weights),
            float(normalized_forecast_configuration.variability_multiplier),
            manual_overrides=manual_overrides_payload or None,
        )

        deterministic_staffing_result = calculate_deterministic_staffing(
            {
                category: float(
                    forecast_result.loc[
                        forecast_result["category"] == category,
                        "point_forecast",
                    ].iloc[0]
                )
                for category in RESERVATION_CATEGORIES
            },
            normalized_category_assumptions,
            normalized_workforce_assumptions,
        )

        simulation_distribution = simulate_weekly_demand(
            forecast_result,
            iterations=normalized_simulation_configuration.iterations,
            seed=normalized_simulation_configuration.random_seed,
            distribution_name=normalized_simulation_configuration.distribution_name,
        )
        handling_times_minutes = {
            item.category: item.handling_time_minutes
            for item in normalized_category_assumptions
        }
        productive_hours_per_agent = calculate_productive_hours_per_agent(
            normalized_workforce_assumptions.paid_hours_per_agent,
            normalized_workforce_assumptions.productive_processing_pct,
        )
        completed_simulation = calculate_simulated_workload_and_staffing(
            simulation_distribution,
            handling_times_minutes,
            productive_hours_per_agent,
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

        candidate_staffing_levels = build_candidate_staffing_list(
            completed_simulation["required_agents"].tolist(),
            previous_week_staffing=resolved_previous_week_staffing,
            manager_planned_staffing=resolved_manager_staffing,
        )

        named_plan_selections = select_named_plans(
            completed_simulation["required_agents"].tolist(),
            normalized_confidence_targets.to_dict(),
        )
        candidate_staffing_levels = sorted(
            set(candidate_staffing_levels) | set(named_plan_selections.values())
        )

        staffing_evaluation_rows = [
            evaluate_staffing_level(
                completed_simulation,
                staffing_agents,
                normalized_category_assumptions,
                normalized_workforce_assumptions,
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
            "automatic_forecast": automatic_forecast,
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
