"""Staffing-evaluation helpers for one whole-agent staffing level."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np
import pandas as pd

from src.constants import CATEGORY_ASSUMPTIONS_COLUMNS
from src.constants import RESERVATION_CATEGORIES
from src.constants import SIMULATION_OUTPUT_COLUMNS
from src.finance.economics import calculate_category_financials
from src.models import CategoryAssumptions
from src.models import WorkforceAssumptions
from src.operations.capacity import calculate_productive_hours_per_agent
from src.simulation.monte_carlo import calculate_simulation_summary
from src.simulation.monte_carlo import SIMULATED_WORKLOAD_OUTPUT_COLUMNS
from src.simulation.shortage import calculate_abandonment_and_overtime
from src.simulation.shortage import calculate_shortage_allocation_by_category
from src.simulation.monte_carlo import calculate_simulated_workload_and_staffing
from src.validation import FieldValidationError
from src.validation import validate_non_negative
from src.validation import validate_non_negative_integer
from src.validation import validate_positive


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


def calculate_regular_labor_cost(
    staffing_agents: int,
    paid_hours_per_agent: float,
    regular_hourly_wage: float,
) -> float:
    """Calculate weekly regular labor cost for a staffing level."""

    validated_staffing_agents = validate_non_negative_integer(
        "staffing_agents",
        staffing_agents,
    )
    validated_paid_hours_per_agent = validate_positive(
        "paid_hours_per_agent",
        paid_hours_per_agent,
    )
    validated_regular_hourly_wage = validate_non_negative(
        "regular_hourly_wage",
        regular_hourly_wage,
    )
    return (
        validated_staffing_agents
        * validated_paid_hours_per_agent
        * validated_regular_hourly_wage
    )


def calculate_overtime_cost(
    overtime_hours: float,
    regular_hourly_wage: float,
    overtime_multiplier: float,
) -> float:
    """Calculate overtime labor cost using the shared wage and multiplier rule."""

    validated_overtime_hours = validate_non_negative(
        "overtime_hours",
        overtime_hours,
    )
    validated_regular_hourly_wage = validate_non_negative(
        "regular_hourly_wage",
        regular_hourly_wage,
    )
    validated_overtime_multiplier = validate_non_negative(
        "overtime_multiplier",
        overtime_multiplier,
    )
    if validated_overtime_multiplier < 1.0:
        raise ValueError("overtime_multiplier must be at least 1.0")

    return (
        validated_overtime_hours
        * validated_regular_hourly_wage
        * validated_overtime_multiplier
    )


def calculate_regular_labor_cost_from_workforce(
    staffing_agents: int,
    workforce_assumptions: WorkforceAssumptions | Mapping[str, Any],
) -> float:
    """Calculate regular labor cost using shared workforce assumptions."""

    validated_workforce_assumptions = _normalize_workforce_assumptions(
        workforce_assumptions
    )
    return calculate_regular_labor_cost(
        staffing_agents=staffing_agents,
        paid_hours_per_agent=validated_workforce_assumptions.paid_hours_per_agent,
        regular_hourly_wage=validated_workforce_assumptions.regular_hourly_wage,
    )


def calculate_overtime_cost_from_workforce(
    overtime_hours: float,
    workforce_assumptions: WorkforceAssumptions | Mapping[str, Any],
) -> float:
    """Calculate overtime cost using shared workforce assumptions."""

    validated_workforce_assumptions = _normalize_workforce_assumptions(
        workforce_assumptions
    )
    return calculate_overtime_cost(
        overtime_hours=overtime_hours,
        regular_hourly_wage=validated_workforce_assumptions.regular_hourly_wage,
        overtime_multiplier=validated_workforce_assumptions.overtime_multiplier,
    )


def _normalize_category_assumptions(
    category_assumptions: pd.DataFrame | Iterable[CategoryAssumptions | Mapping[str, Any]],
) -> tuple[CategoryAssumptions, ...]:
    """Normalize category assumptions into canonical shared-model order."""

    if isinstance(category_assumptions, pd.DataFrame):
        actual_columns = tuple(category_assumptions.columns)
        if actual_columns != CATEGORY_ASSUMPTIONS_COLUMNS:
            missing_columns = [
                column
                for column in CATEGORY_ASSUMPTIONS_COLUMNS
                if column not in category_assumptions.columns
            ]
            unexpected_columns = [
                column
                for column in category_assumptions.columns
                if column not in CATEGORY_ASSUMPTIONS_COLUMNS
            ]
            problems: list[str] = []
            if missing_columns:
                problems.append(f"missing columns: {missing_columns}")
            if unexpected_columns:
                problems.append(f"unexpected columns: {unexpected_columns}")
            raise FieldValidationError(
                "category_assumptions must match the shared contract exactly "
                f"({', '.join(problems)})"
            )
        source_items: Iterable[CategoryAssumptions | Mapping[str, Any]] = (
            record for record in category_assumptions.to_dict(orient="records")
        )
    else:
        source_items = category_assumptions

    normalized = tuple(
        item if isinstance(item, CategoryAssumptions) else CategoryAssumptions.from_dict(dict(item))
        for item in source_items
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


def _to_category_financial_inputs(
    category_assumptions: tuple[CategoryAssumptions, ...],
) -> tuple[dict[str, float], dict[str, float], list[CategoryAssumptions]]:
    """Extract canonical handling-time and financial lookup maps from the shared models."""

    handling_times_minutes = {
        item.category: item.handling_time_minutes for item in category_assumptions
    }
    category_records = list(category_assumptions)
    return (
        handling_times_minutes,
        {
            item.category: item.average_revenue
            for item in category_assumptions
        },
        category_records,
    )


def _ensure_completed_simulation(
    simulated_demand: pd.DataFrame,
    handling_times_minutes: Mapping[str, float],
    productive_hours_per_agent: float,
) -> pd.DataFrame:
    """Return a completed simulation table regardless of the caller's input stage."""

    actual_columns = tuple(simulated_demand.columns)
    if actual_columns == SIMULATED_WORKLOAD_OUTPUT_COLUMNS:
        return simulated_demand
    if actual_columns == SIMULATION_OUTPUT_COLUMNS:
        return calculate_simulated_workload_and_staffing(
            simulated_demand,
            handling_times_minutes,
            productive_hours_per_agent,
        )

    raise FieldValidationError(
        "simulated_demand must match either the raw simulation contract or the "
        "completed workload contract"
    )


def _calculate_expected_financials(
    completed_simulation: pd.DataFrame,
    category_assumptions: tuple[CategoryAssumptions, ...],
    staffing_agents: int,
    handling_times_minutes: Mapping[str, float],
    productive_hours_per_agent: float,
    abandonment_rate: float,
) -> dict[str, float]:
    """Aggregate per-simulation financial outputs using the shared economics primitives."""

    retained_revenue_values: list[float] = []
    retained_contribution_values: list[float] = []
    lost_revenue_values: list[float] = []
    lost_contribution_values: list[float] = []

    for demand_row in completed_simulation.loc[:, RESERVATION_CATEGORIES].itertuples(
        index=False,
        name=None,
    ):
        demand_by_category = {
            category: float(demand_row[index])
            for index, category in enumerate(RESERVATION_CATEGORIES)
        }
        shortage = calculate_shortage_allocation_by_category(
            demand_by_category,
            handling_times_minutes,
            staffing_agents,
            productive_hours_per_agent,
        )
        overtime = calculate_abandonment_and_overtime(
            shortage["excess_reservations_by_category"],
            handling_times_minutes,
            abandonment_rate,
        )
        abandoned_reservations = overtime["abandoned_reservations_by_category"]
        completed_reservations = {
            category: demand_by_category[category] - abandoned_reservations[category]
            for category in RESERVATION_CATEGORIES
        }
        financials = calculate_category_financials(
            completed_reservations,
            abandoned_reservations,
            category_assumptions,
        )

        retained_revenue_values.append(float(financials["total_retained_revenue"]))
        retained_contribution_values.append(float(financials["total_retained_contribution"]))
        lost_revenue_values.append(float(financials["total_lost_revenue"]))
        lost_contribution_values.append(float(financials["total_lost_contribution"]))

    return {
        "expected_retained_revenue": float(np.mean(retained_revenue_values)),
        "expected_retained_contribution": float(np.mean(retained_contribution_values)),
        "expected_lost_revenue": float(np.mean(lost_revenue_values)),
        "expected_lost_contribution": float(np.mean(lost_contribution_values)),
    }


def evaluate_staffing_level(
    simulated_demand: pd.DataFrame,
    staffing_agents: int,
    category_assumptions: pd.DataFrame | Iterable[CategoryAssumptions | Mapping[str, Any]],
    workforce_assumptions: WorkforceAssumptions | Mapping[str, Any],
) -> dict[str, float | int]:
    """Evaluate one staffing level and return the Section 6.6 staffing-evaluation row."""

    if not isinstance(simulated_demand, pd.DataFrame):
        raise FieldValidationError("simulated_demand must be a pandas DataFrame")

    normalized_staffing_agents = validate_non_negative_integer(
        "staffing_agents",
        staffing_agents,
    )
    normalized_category_assumptions = _normalize_category_assumptions(category_assumptions)
    normalized_workforce_assumptions = _normalize_workforce_assumptions(
        workforce_assumptions
    )
    handling_times_minutes, _, _ = _to_category_financial_inputs(
        normalized_category_assumptions
    )
    productive_hours_per_agent = calculate_productive_hours_per_agent(
        normalized_workforce_assumptions.paid_hours_per_agent,
        normalized_workforce_assumptions.productive_processing_pct,
    )
    abandonment_rate = validate_non_negative(
        "abandonment_rate",
        normalized_workforce_assumptions.abandonment_rate,
    )

    completed_simulation = _ensure_completed_simulation(
        simulated_demand,
        handling_times_minutes,
        productive_hours_per_agent,
    )
    simulation_summary = calculate_simulation_summary(
        completed_simulation,
        normalized_staffing_agents,
        handling_times_minutes,
        productive_hours_per_agent,
        abandonment_rate,
    )

    financials = _calculate_expected_financials(
        completed_simulation,
        normalized_category_assumptions,
        normalized_staffing_agents,
        handling_times_minutes,
        productive_hours_per_agent,
        abandonment_rate,
    )

    regular_labor_cost = float(
        calculate_regular_labor_cost_from_workforce(
            normalized_staffing_agents,
            normalized_workforce_assumptions,
        )
    )
    expected_overtime_cost = float(
        calculate_overtime_cost_from_workforce(
            simulation_summary["expected_overtime_hours"],
            normalized_workforce_assumptions,
        )
    )
    expected_total_economic_cost = float(
        regular_labor_cost
        + expected_overtime_cost
        + financials["expected_lost_contribution"]
    )
    expected_net_contribution = float(
        financials["expected_retained_contribution"] - expected_total_economic_cost
    )

    result = {
        "staffing_agents": normalized_staffing_agents,
        "capacity_confidence": float(simulation_summary["capacity_confidence"]),
        "probability_overtime_required": float(
            simulation_summary["probability_overtime_required"]
        ),
        "expected_overtime_hours": float(simulation_summary["expected_overtime_hours"]),
        "expected_abandoned_total": float(simulation_summary["expected_abandoned_total"]),
        "expected_abandoned_simple": float(simulation_summary["expected_abandoned_simple"]),
        "expected_abandoned_standard": float(simulation_summary["expected_abandoned_standard"]),
        "expected_abandoned_complex_group": float(
            simulation_summary["expected_abandoned_complex_group"]
        ),
        "expected_abandoned_change_cancellation": float(
            simulation_summary["expected_abandoned_change_cancellation"]
        ),
        "regular_labor_cost": regular_labor_cost,
        "expected_overtime_cost": expected_overtime_cost,
        "expected_lost_revenue": financials["expected_lost_revenue"],
        "expected_lost_contribution": financials["expected_lost_contribution"],
        "expected_total_economic_cost": expected_total_economic_cost,
        "expected_retained_revenue": financials["expected_retained_revenue"],
        "expected_retained_contribution": financials["expected_retained_contribution"],
        "expected_net_contribution": expected_net_contribution,
        "expected_unused_regular_hours": float(
            simulation_summary["expected_unused_regular_hours"]
        ),
    }
    return result


__all__ = [
    "calculate_overtime_cost",
    "calculate_overtime_cost_from_workforce",
    "calculate_regular_labor_cost",
    "calculate_regular_labor_cost_from_workforce",
    "evaluate_staffing_level",
]
