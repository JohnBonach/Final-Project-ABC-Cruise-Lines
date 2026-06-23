"""Staffing-evaluation helpers for one feasible in-house staffing level."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np
import pandas as pd

from src.constants import (
    CATEGORY_ASSUMPTIONS_COLUMNS,
    RESERVATION_CATEGORIES,
    SIMULATION_OUTPUT_COLUMNS,
)
from src.finance.economics import calculate_weekly_operating_financials
from src.models import CategoryAssumptions, StrategicAssumptions, WorkforceAssumptions
from src.operations.capacity import (
    calculate_booking_processing_hours_per_agent,
)
from src.simulation.monte_carlo import (
    SIMULATED_WORKLOAD_OUTPUT_COLUMNS,
    calculate_simulation_summary,
    calculate_simulated_workload_and_staffing,
)
from src.simulation.shortage import calculate_overflow_allocation_by_category
from src.validation import (
    FieldValidationError,
    validate_non_negative,
    validate_non_negative_integer,
    validate_positive,
)


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


def _to_category_inputs(
    category_assumptions: tuple[CategoryAssumptions, ...],
) -> dict[str, float]:
    return {
        item.category: item.handling_time_minutes
        for item in category_assumptions
    }


def _ensure_completed_simulation(
    simulated_demand: pd.DataFrame,
    handling_times_minutes: Mapping[str, float],
    booking_processing_hours_per_agent: float,
    minimum_schedulable_agents: int,
    maximum_inhouse_agents: int,
) -> pd.DataFrame:
    """Return a completed simulation table regardless of the caller's input stage."""

    actual_columns = tuple(simulated_demand.columns)
    if actual_columns == SIMULATED_WORKLOAD_OUTPUT_COLUMNS:
        return simulated_demand
    if actual_columns == SIMULATION_OUTPUT_COLUMNS:
        return calculate_simulated_workload_and_staffing(
            simulated_demand,
            handling_times_minutes,
            booking_processing_hours_per_agent,
            minimum_schedulable_agents=minimum_schedulable_agents,
            maximum_inhouse_agents=maximum_inhouse_agents,
        )

    raise FieldValidationError(
        "simulated_demand must match either the raw simulation contract or the "
        "completed workload contract"
    )


def evaluate_staffing_level(
    simulated_demand: pd.DataFrame,
    staffing_agents: int,
    category_assumptions: pd.DataFrame | Iterable[CategoryAssumptions | Mapping[str, Any]],
    workforce_assumptions: WorkforceAssumptions | Mapping[str, Any],
    strategic_assumptions: StrategicAssumptions | Mapping[str, Any],
) -> dict[str, float | int]:
    """Evaluate one staffing level using the floor/cap/overflow/commission baseline."""

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
    normalized_strategic_assumptions = _normalize_strategic_assumptions(
        strategic_assumptions
    )

    handling_times_minutes = _to_category_inputs(normalized_category_assumptions)
    booking_processing_hours_per_agent = calculate_booking_processing_hours_per_agent(
        normalized_workforce_assumptions.weekly_booking_processing_hours_per_agent
    )

    completed_simulation = _ensure_completed_simulation(
        simulated_demand,
        handling_times_minutes,
        booking_processing_hours_per_agent,
        normalized_workforce_assumptions.minimum_schedulable_agents,
        normalized_workforce_assumptions.maximum_inhouse_agents,
    )

    simulation_summary = calculate_simulation_summary(
        completed_simulation,
        normalized_staffing_agents,
        handling_times_minutes,
        booking_processing_hours_per_agent,
    )

    overflow_commission_values: list[float] = []
    inhouse_booking_value_values: list[float] = []
    overflow_booking_value_values: list[float] = []
    commission_avoided_values: list[float] = []

    for row in completed_simulation.to_dict(orient="records"):
        demand_by_category = {
            category: float(row[category])
            for category in RESERVATION_CATEGORIES
        }
        overflow_result = calculate_overflow_allocation_by_category(
            demand_by_category,
            handling_times_minutes,
            normalized_staffing_agents,
            booking_processing_hours_per_agent,
        )
        financials = calculate_weekly_operating_financials(
            overflow_result["inhouse_bookings_by_category"],
            overflow_result["overflow_bookings_by_category"],
            normalized_category_assumptions,
            normalized_strategic_assumptions.third_party_commission_rate,
        )
        overflow_commission_values.append(float(financials["total_overflow_commission"]))
        inhouse_booking_value_values.append(float(financials["total_inhouse_booking_value"]))
        overflow_booking_value_values.append(float(financials["total_overflow_booking_value"]))
        commission_avoided_values.append(float(financials["total_commission_avoided"]))

    regular_labor_cost = float(
        calculate_regular_labor_cost_from_workforce(
            normalized_staffing_agents,
            normalized_workforce_assumptions,
        )
    )
    expected_overflow_commission = float(np.mean(overflow_commission_values))
    expected_total_weekly_operating_cost = (
        regular_labor_cost + expected_overflow_commission
    )

    return {
        "staffing_agents": normalized_staffing_agents,
        "capacity_confidence": float(simulation_summary["capacity_confidence"]),
        "probability_overflow_required": float(
            simulation_summary["probability_overflow_required"]
        ),
        "expected_spare_capacity_hours": float(
            simulation_summary["expected_spare_capacity_hours"]
        ),
        "expected_overflow_workload_hours": float(
            simulation_summary["expected_overflow_workload_hours"]
        ),
        "expected_overflow_day_cruise": float(
            simulation_summary["expected_overflow_bookings_by_category"]["day_cruise"]
        ),
        "expected_overflow_seven_night_cruise": float(
            simulation_summary["expected_overflow_bookings_by_category"]["seven_night_cruise"]
        ),
        "expected_overflow_nine_night_cruise": float(
            simulation_summary["expected_overflow_bookings_by_category"]["nine_night_cruise"]
        ),
        "regular_labor_cost": regular_labor_cost,
        "expected_overflow_commission": expected_overflow_commission,
        "expected_total_weekly_operating_cost": float(
            expected_total_weekly_operating_cost
        ),
        "expected_inhouse_booking_value": float(np.mean(inhouse_booking_value_values)),
        "expected_overflow_booking_value": float(np.mean(overflow_booking_value_values)),
        "expected_commission_avoided": float(np.mean(commission_avoided_values)),
    }


__all__ = [
    "calculate_regular_labor_cost",
    "calculate_regular_labor_cost_from_workforce",
    "evaluate_staffing_level",
]
