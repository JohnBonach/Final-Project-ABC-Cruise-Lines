"""Simulation helpers for translating sampled demand into staffing needs."""

from __future__ import annotations

from collections.abc import Sequence
from collections.abc import Mapping
import math

import numpy as np
import pandas as pd

from src.constants import RESERVATION_CATEGORIES
from src.operations.workload import MINUTES_PER_HOUR
from src.simulation.shortage import calculate_abandonment_and_overtime
from src.simulation.shortage import calculate_shortage_allocation_by_category
from src.validation import FieldValidationError, validate_positive
from src.validation import validate_non_negative_integer
from src.validation import validate_percentage

SIMULATED_WORKLOAD_OUTPUT_COLUMNS = (
    "simulation_id",
    *RESERVATION_CATEGORIES,
    "total_workload_hours",
    "required_fte",
    "required_agents",
)


def _validate_simulated_demand(simulated_demand: pd.DataFrame) -> pd.DataFrame:
    """Validate the sampled demand table and return it in canonical column order."""

    if not isinstance(simulated_demand, pd.DataFrame):
        raise FieldValidationError("simulated_demand must be a pandas DataFrame")

    expected_columns = ("simulation_id", *RESERVATION_CATEGORIES)
    actual_columns = tuple(simulated_demand.columns)
    if actual_columns != expected_columns:
        missing_columns = [column for column in expected_columns if column not in simulated_demand.columns]
        unexpected_columns = [column for column in simulated_demand.columns if column not in expected_columns]
        problems: list[str] = []
        if missing_columns:
            problems.append(f"missing columns: {missing_columns}")
        if unexpected_columns:
            problems.append(f"unexpected columns: {unexpected_columns}")
        if len(set(actual_columns)) != len(actual_columns):
            duplicated_columns = [
                column
                for column in expected_columns
                if simulated_demand.columns.tolist().count(column) > 1
            ]
            if duplicated_columns:
                problems.append(f"duplicate columns: {duplicated_columns}")
        raise FieldValidationError(
            "simulated_demand must match the shared simulation contract exactly "
            f"({', '.join(problems)})"
        )

    demand_values = simulated_demand.loc[:, RESERVATION_CATEGORIES].to_numpy(dtype=float, copy=False)
    if not np.isfinite(demand_values).all():
        raise FieldValidationError("simulated_demand category columns must contain only finite values")
    if (demand_values < 0).any():
        raise FieldValidationError("simulated_demand category columns must be non-negative")

    return simulated_demand.loc[:, expected_columns]


def _validate_handling_times(
    handling_times_minutes: Mapping[str, float],
) -> dict[str, float]:
    """Validate exact canonical category handling times and normalize their order."""

    if not isinstance(handling_times_minutes, Mapping):
        raise FieldValidationError("handling_times_minutes must be a mapping keyed by category")

    actual_categories = set(handling_times_minutes)
    expected_categories = set(RESERVATION_CATEGORIES)
    if actual_categories != expected_categories:
        missing = sorted(expected_categories - actual_categories)
        unexpected = sorted(actual_categories - expected_categories)
        problems: list[str] = []
        if missing:
            problems.append(f"missing categories: {missing}")
        if unexpected:
            problems.append(f"unexpected categories: {unexpected}")
        raise FieldValidationError(
            "handling_times_minutes must contain exactly the canonical reservation categories "
            f"({', '.join(problems)})"
        )

    return {
        category: validate_positive(
            f"handling_times_minutes[{category!r}]",
            handling_times_minutes[category],
        )
        for category in RESERVATION_CATEGORIES
        }


def _validate_completed_simulation(
    completed_simulation: pd.DataFrame,
) -> pd.DataFrame:
    """Validate the simulated workload table and preserve canonical ordering."""

    if not isinstance(completed_simulation, pd.DataFrame):
        raise FieldValidationError("completed_simulation must be a pandas DataFrame")

    actual_columns = tuple(completed_simulation.columns)
    if actual_columns != SIMULATED_WORKLOAD_OUTPUT_COLUMNS:
        missing_columns = [
            column for column in SIMULATED_WORKLOAD_OUTPUT_COLUMNS if column not in completed_simulation.columns
        ]
        unexpected_columns = [
            column for column in completed_simulation.columns if column not in SIMULATED_WORKLOAD_OUTPUT_COLUMNS
        ]
        problems: list[str] = []
        if missing_columns:
            problems.append(f"missing columns: {missing_columns}")
        if unexpected_columns:
            problems.append(f"unexpected columns: {unexpected_columns}")
        if len(set(actual_columns)) != len(actual_columns):
            duplicated_columns = [
                column
                for column in SIMULATED_WORKLOAD_OUTPUT_COLUMNS
                if completed_simulation.columns.tolist().count(column) > 1
            ]
            if duplicated_columns:
                problems.append(f"duplicate columns: {duplicated_columns}")
        raise FieldValidationError(
            "completed_simulation must match the shared simulation contract exactly "
            f"({', '.join(problems)})"
        )

    numeric_values = completed_simulation.loc[:, list(RESERVATION_CATEGORIES) + [
        "total_workload_hours",
        "required_fte",
        "required_agents",
    ]].to_numpy(dtype=float, copy=False)
    if not np.isfinite(numeric_values).all():
        raise FieldValidationError("completed_simulation numeric columns must contain only finite values")
    if (numeric_values < 0).any():
        raise FieldValidationError("completed_simulation numeric columns must be non-negative")

    required_agents = completed_simulation["required_agents"].to_numpy(dtype=float, copy=False)
    if not np.allclose(required_agents, np.round(required_agents)):
        raise FieldValidationError("completed_simulation required_agents must contain whole-agent values")

    return completed_simulation.loc[:, SIMULATED_WORKLOAD_OUTPUT_COLUMNS]


def _validate_percentiles(percentiles: Sequence[float]) -> tuple[float, ...]:
    """Validate percentile requests and preserve the caller's order."""

    if not isinstance(percentiles, Sequence) or isinstance(percentiles, (str, bytes)):
        raise FieldValidationError("percentiles must be a sequence of decimal fractions")

    normalized = tuple(
        validate_percentage(f"percentiles[{index}]", percentile)
        for index, percentile in enumerate(percentiles)
    )
    if not normalized:
        raise FieldValidationError("percentiles must contain at least one value")
    if len(set(normalized)) != len(normalized):
        raise FieldValidationError("percentiles must not contain duplicates")
    return normalized


def _higher_quantile(values: np.ndarray, percentile: float) -> int:
    """Return the upward-rounded percentile for a whole-agent distribution."""

    if values.size == 0:
        raise FieldValidationError("required_agent distribution must contain at least one value")

    ordered = np.sort(values.astype(float, copy=False))
    index = max(math.ceil(percentile * ordered.size) - 1, 0)
    index = min(index, ordered.size - 1)
    return int(ordered[index])


def calculate_simulation_summary(
    completed_simulation: pd.DataFrame,
    staffing_agents: int,
    handling_times_minutes: Mapping[str, float],
    productive_hours_per_agent: float,
    abandonment_rate: float,
    percentiles: Sequence[float] = (0.5, 0.75, 0.9, 0.95),
) -> dict[str, object]:
    """Summarize simulation outcomes for a single staffing level."""

    simulation_table = _validate_completed_simulation(completed_simulation)
    if simulation_table.empty:
        raise FieldValidationError("completed_simulation must contain at least one simulation row")
    normalized_staffing_agents = validate_non_negative_integer(
        "staffing_agents",
        staffing_agents,
    )
    normalized_handling_times = _validate_handling_times(handling_times_minutes)
    normalized_productive_hours = validate_positive(
        "productive_hours_per_agent",
        productive_hours_per_agent,
    )
    normalized_percentiles = _validate_percentiles(percentiles)
    normalized_abandonment_rate = validate_percentage(
        "abandonment_rate",
        abandonment_rate,
    )

    demand_rows = simulation_table.loc[:, RESERVATION_CATEGORIES].to_numpy(dtype=float, copy=False)
    total_workload_hours = simulation_table["total_workload_hours"].to_numpy(dtype=float, copy=False)
    required_agents = simulation_table["required_agents"].to_numpy(dtype=float, copy=False)

    capacity_hours = normalized_staffing_agents * normalized_productive_hours
    regular_capacity_meets_workload = total_workload_hours <= capacity_hours

    overtime_hours: list[float] = []
    unused_regular_hours: list[float] = []
    abandoned_by_category: dict[str, list[float]] = {category: [] for category in RESERVATION_CATEGORIES}

    for demand_vector in demand_rows:
        demand_by_category = {
            category: float(demand_vector[column_index])
            for column_index, category in enumerate(RESERVATION_CATEGORIES)
        }
        shortage_result = calculate_shortage_allocation_by_category(
            demand_by_category,
            normalized_handling_times,
            normalized_staffing_agents,
            normalized_productive_hours,
        )
        excess_reservations = shortage_result["excess_reservations_by_category"]
        overtime_result = calculate_abandonment_and_overtime(
            excess_reservations,
            normalized_handling_times,
            normalized_abandonment_rate,
        )
        overtime_hours.append(float(overtime_result["overtime_hours"]))
        unused_regular_hours.append(
            max(
                float(shortage_result["regular_capacity_hours"]) - float(shortage_result["total_workload_hours"]),
                0.0,
            )
        )
        abandoned_reservations = overtime_result["abandoned_reservations_by_category"]
        for category in RESERVATION_CATEGORIES:
            abandoned_by_category[category].append(float(abandoned_reservations[category]))

    abandoned_totals = [
        sum(abandoned_by_category[category][row_index] for category in RESERVATION_CATEGORIES)
        for row_index in range(len(simulation_table))
    ]
    expected_abandoned_by_category = {
        category: float(np.mean(values)) for category, values in abandoned_by_category.items()
    }
    expected_abandoned_total = float(np.mean(abandoned_totals))
    required_agent_percentiles = {
        percentile: _higher_quantile(required_agents, percentile)
        for percentile in normalized_percentiles
    }

    summary: dict[str, object] = {
        "staffing_agents": normalized_staffing_agents,
        "capacity_confidence": float(np.mean(regular_capacity_meets_workload)),
        "probability_overtime_required": float(
            np.mean(np.array(overtime_hours, dtype=float) > 0.0)
        ),
        "expected_overtime_hours": float(np.mean(overtime_hours)),
        "expected_abandoned_by_category": expected_abandoned_by_category,
        "expected_abandoned_total": expected_abandoned_total,
        "expected_unused_regular_hours": float(np.mean(unused_regular_hours)),
        "required_agent_percentiles": required_agent_percentiles,
    }

    for category in RESERVATION_CATEGORIES:
        summary[f"expected_abandoned_{category}"] = expected_abandoned_by_category[category]

    return summary


calculate_simulation_aggregation = calculate_simulation_summary
calculate_staffing_level_simulation_summary = calculate_simulation_summary


def calculate_simulated_workload_and_staffing(
    simulated_demand: pd.DataFrame,
    handling_times_minutes: Mapping[str, float],
    productive_hours_per_agent: float,
) -> pd.DataFrame:
    """Extend a simulated demand table with workload hours and staffing requirements."""

    ordered_demand = _validate_simulated_demand(simulated_demand)
    normalized_handling_times = _validate_handling_times(handling_times_minutes)
    normalized_productive_hours = validate_positive(
        "productive_hours_per_agent",
        productive_hours_per_agent,
    )

    demand_matrix = ordered_demand.loc[:, RESERVATION_CATEGORIES].to_numpy(dtype=float, copy=False)
    handling_vector = np.array(
        [normalized_handling_times[category] for category in RESERVATION_CATEGORIES],
        dtype=float,
    )

    total_workload_hours = demand_matrix @ handling_vector / MINUTES_PER_HOUR
    required_fte = total_workload_hours / normalized_productive_hours
    required_agents = np.ceil(required_fte).astype(int)

    result = ordered_demand.copy()
    result["total_workload_hours"] = total_workload_hours
    result["required_fte"] = required_fte
    result["required_agents"] = required_agents
    return result.loc[:, SIMULATED_WORKLOAD_OUTPUT_COLUMNS]


__all__ = [
    "SIMULATED_WORKLOAD_OUTPUT_COLUMNS",
    "calculate_simulation_aggregation",
    "calculate_simulation_summary",
    "calculate_simulated_workload_and_staffing",
    "calculate_staffing_level_simulation_summary",
]
