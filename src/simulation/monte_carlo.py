"""Simulation helpers for translating sampled demand into staffing and overflow needs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math

import numpy as np
import pandas as pd

from src.constants import RESERVATION_CATEGORIES
from src.operations.capacity import (
    calculate_booking_processing_hours_per_agent,
    calculate_capacity_hours,
    calculate_required_agents,
    calculate_required_fte,
    clamp_inhouse_staffing,
)
from src.operations.workload import MINUTES_PER_HOUR
from src.simulation.shortage import calculate_overflow_allocation_by_category
from src.validation import (
    FieldValidationError,
    validate_non_negative_integer,
    validate_percentage,
    validate_positive,
)

SIMULATED_WORKLOAD_OUTPUT_COLUMNS = (
    "simulation_id",
    *RESERVATION_CATEGORIES,
    "total_workload_hours",
    "raw_required_fte",
    "unconstrained_required_agents",
    "recommended_inhouse_agents",
    "spare_capacity_hours",
    "overflow_workload_hours",
)

OUTLOOK_QUANTILE_CONVENTION = "linear"


def _validate_simulated_demand(simulated_demand: pd.DataFrame) -> pd.DataFrame:
    """Validate the sampled-demand table and return it in canonical order."""

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

    actual_categories = tuple(handling_times_minutes.keys())
    if actual_categories != RESERVATION_CATEGORIES:
        raise FieldValidationError(
            "handling_times_minutes must include each canonical category exactly once "
            f"and in the shared order {RESERVATION_CATEGORIES}"
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
    """Validate the completed simulated-workload table and preserve canonical ordering."""

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
        raise FieldValidationError(
            "completed_simulation must match the shared simulation contract exactly "
            f"({', '.join(problems)})"
        )

    numeric_columns = list(RESERVATION_CATEGORIES) + [
        "total_workload_hours",
        "raw_required_fte",
        "unconstrained_required_agents",
        "recommended_inhouse_agents",
        "spare_capacity_hours",
        "overflow_workload_hours",
    ]
    numeric_values = completed_simulation.loc[:, numeric_columns].to_numpy(dtype=float, copy=False)
    if not np.isfinite(numeric_values).all():
        raise FieldValidationError("completed_simulation numeric columns must contain only finite values")
    if (numeric_values < 0).any():
        raise FieldValidationError("completed_simulation numeric columns must be non-negative")

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
        raise FieldValidationError("required-agent distribution must contain at least one value")

    ordered = np.sort(values.astype(float, copy=False))
    index = max(math.ceil(percentile * ordered.size) - 1, 0)
    index = min(index, ordered.size - 1)
    return int(ordered[index])


def _validate_outlook_requests(
    outlook_requests: Sequence[tuple[str, float, str]],
) -> tuple[tuple[str, float, str], ...]:
    if not isinstance(outlook_requests, Sequence) or isinstance(
        outlook_requests,
        (str, bytes),
    ):
        raise FieldValidationError(
            "outlook_requests must be a sequence of (outlook_name, percentile, percentile_label)"
        )

    normalized: list[tuple[str, float, str]] = []
    for index, item in enumerate(outlook_requests):
        if not isinstance(item, Sequence) or len(item) != 3:
            raise FieldValidationError(
                f"outlook_requests[{index}] must contain exactly three values"
            )
        outlook_name, percentile, percentile_label = item
        if not isinstance(outlook_name, str) or not outlook_name.strip():
            raise FieldValidationError(f"outlook_requests[{index}].outlook_name must be non-empty")
        if not isinstance(percentile_label, str) or not percentile_label.strip():
            raise FieldValidationError(
                f"outlook_requests[{index}].percentile_label must be non-empty"
            )
        normalized.append(
            (
                outlook_name.strip(),
                validate_percentage(
                    f"outlook_requests[{index}].percentile",
                    percentile,
                ),
                percentile_label.strip(),
            )
        )
    if not normalized:
        raise FieldValidationError("outlook_requests must contain at least one request")
    return tuple(normalized)


def _calculate_target_workload(
    sorted_total_workload_hours: pd.Series,
    percentile: float,
) -> float:
    return float(
        sorted_total_workload_hours.quantile(
            percentile,
            interpolation=OUTLOOK_QUANTILE_CONVENTION,
        )
    )


def _rank_representative_candidates(
    ordered_completed_simulation: pd.DataFrame,
    *,
    target_total_workload_hours: float,
    minimum_total_workload_hours: float,
    used_row_ids: set[int],
    allow_reuse: bool,
) -> pd.DataFrame:
    candidates = ordered_completed_simulation.loc[
        ordered_completed_simulation["total_workload_hours"] >= minimum_total_workload_hours
    ].copy()
    if not allow_reuse:
        candidates = candidates.loc[~candidates["simulation_id"].isin(used_row_ids)].copy()
    if candidates.empty:
        return candidates

    candidates["distance_to_target"] = (
        candidates["total_workload_hours"] - target_total_workload_hours
    ).abs()
    return candidates.sort_values(
        by=["distance_to_target", "simulation_id"],
        kind="stable",
    ).reset_index(drop=True)


def select_representative_simulation_rows(
    completed_simulation: pd.DataFrame,
    outlook_requests: Sequence[tuple[str, float, str]] = (
        ("Lower Demand", 0.25, "P25"),
        ("Central Demand", 0.5, "P50"),
        ("Higher Demand", 0.9, "P90"),
    ),
) -> dict[str, object]:
    """Select deterministic representative simulation rows for requested workload percentiles."""

    ordered_completed_simulation = _validate_completed_simulation(
        completed_simulation
    ).sort_values(
        by=["total_workload_hours", "simulation_id"],
        kind="stable",
    ).reset_index(drop=True)
    if ordered_completed_simulation.empty:
        raise FieldValidationError("completed_simulation must contain at least one simulation row")

    normalized_outlook_requests = _validate_outlook_requests(outlook_requests)
    sorted_total_workload_hours = ordered_completed_simulation["total_workload_hours"].astype(float)

    target_workload_by_label = {
        percentile_label: _calculate_target_workload(
            sorted_total_workload_hours,
            percentile,
        )
        for _, percentile, percentile_label in normalized_outlook_requests
    }

    selected_rows: list[dict[str, object]] = []
    used_row_ids: set[int] = set()
    minimum_total_workload_hours = float("-inf")

    for outlook_name, percentile, percentile_label in normalized_outlook_requests:
        target_total_workload_hours = target_workload_by_label[percentile_label]
        ranked_candidates = _rank_representative_candidates(
            ordered_completed_simulation,
            target_total_workload_hours=target_total_workload_hours,
            minimum_total_workload_hours=minimum_total_workload_hours,
            used_row_ids=used_row_ids,
            allow_reuse=False,
        )
        if ranked_candidates.empty:
            ranked_candidates = _rank_representative_candidates(
                ordered_completed_simulation,
                target_total_workload_hours=target_total_workload_hours,
                minimum_total_workload_hours=minimum_total_workload_hours,
                used_row_ids=used_row_ids,
                allow_reuse=True,
            )
        if ranked_candidates.empty:
            raise FieldValidationError(
                "unable to select a representative simulation row for the requested outlooks"
            )

        selected_row = ranked_candidates.iloc[0]
        simulation_row_id = int(selected_row["simulation_id"])
        total_workload_hours = float(selected_row["total_workload_hours"])
        used_row_ids.add(simulation_row_id)
        minimum_total_workload_hours = total_workload_hours
        selected_rows.append(
            {
                "outlook_name": outlook_name,
                "percentile": percentile,
                "percentile_label": percentile_label,
                "simulation_row_id": simulation_row_id,
                "target_total_workload_hours": target_total_workload_hours,
                "selected_total_workload_hours": total_workload_hours,
                "row": selected_row.loc[list(SIMULATED_WORKLOAD_OUTPUT_COLUMNS)].to_dict(),
            }
        )

    selected_row_ids_by_label = {
        item["percentile_label"]: int(item["simulation_row_id"])
        for item in selected_rows
    }
    selected_workloads_by_label = {
        item["percentile_label"]: float(item["selected_total_workload_hours"])
        for item in selected_rows
    }
    selected_row_counts: dict[int, int] = {}
    selected_outlooks_by_row_id: dict[int, list[str]] = {}
    for item in selected_rows:
        row_id = int(item["simulation_row_id"])
        selected_row_counts[row_id] = selected_row_counts.get(row_id, 0) + 1
        selected_outlooks_by_row_id.setdefault(row_id, []).append(str(item["outlook_name"]))

    for item in selected_rows:
        item["representative_row_reused"] = (
            selected_row_counts[int(item["simulation_row_id"])] > 1
        )

    reuse_details = [
        {
            "simulation_row_id": row_id,
            "outlooks": outlook_names,
        }
        for row_id, outlook_names in selected_outlooks_by_row_id.items()
        if len(outlook_names) > 1
    ]
    selected_workloads_in_request_order = [
        float(item["selected_total_workload_hours"])
        for item in selected_rows
    ]
    ordering_invariant_satisfied = all(
        earlier <= later
        for earlier, later in zip(
            selected_workloads_in_request_order,
            selected_workloads_in_request_order[1:],
        )
    )

    return {
        "selected_rows": selected_rows,
        "diagnostics": {
            "quantile_convention": OUTLOOK_QUANTILE_CONVENTION,
            "ordering_measure": "total_workload_hours",
            "row_identity_field": "simulation_id",
            "selected_row_ids_by_percentile_label": selected_row_ids_by_label,
            "target_total_workload_hours_by_percentile_label": target_workload_by_label,
            "selected_total_workload_hours_by_percentile_label": selected_workloads_by_label,
            "row_reuse_detected": bool(reuse_details),
            "reused_simulation_rows": reuse_details,
            "reuse_reason": (
                "Representative row reuse was required because too few completed simulation rows "
                "were available after distinct-row preference was applied."
                if reuse_details
                else None
            ),
            "ordering_invariant_satisfied": ordering_invariant_satisfied,
        },
    }


def calculate_simulated_workload_and_staffing(
    simulated_demand: pd.DataFrame,
    handling_times_minutes: Mapping[str, float],
    booking_processing_hours_per_agent: float,
    minimum_schedulable_agents: int = 8,
    maximum_inhouse_agents: int = 12,
) -> pd.DataFrame:
    """Extend a simulated-demand table with workload and approved staffing outputs."""

    ordered_demand = _validate_simulated_demand(simulated_demand)
    normalized_handling_times = _validate_handling_times(handling_times_minutes)
    normalized_processing_hours = calculate_booking_processing_hours_per_agent(
        booking_processing_hours_per_agent
    )

    demand_matrix = ordered_demand.loc[:, RESERVATION_CATEGORIES].to_numpy(dtype=float, copy=False)
    handling_vector = np.array(
        [normalized_handling_times[category] for category in RESERVATION_CATEGORIES],
        dtype=float,
    )
    total_workload_hours = demand_matrix @ handling_vector / MINUTES_PER_HOUR
    raw_required_fte = total_workload_hours / normalized_processing_hours
    unconstrained_required_agents = np.ceil(raw_required_fte).astype(int)
    recommended_inhouse_agents = np.array(
        [
            clamp_inhouse_staffing(
                int(required_agents),
                minimum_schedulable_agents,
                maximum_inhouse_agents,
            )
            for required_agents in unconstrained_required_agents
        ],
        dtype=int,
    )
    recommended_capacity_hours = recommended_inhouse_agents * normalized_processing_hours
    spare_capacity_hours = np.maximum(recommended_capacity_hours - total_workload_hours, 0.0)
    overflow_workload_hours = np.maximum(total_workload_hours - recommended_capacity_hours, 0.0)

    result = ordered_demand.copy()
    result["total_workload_hours"] = total_workload_hours
    result["raw_required_fte"] = raw_required_fte
    result["unconstrained_required_agents"] = unconstrained_required_agents
    result["recommended_inhouse_agents"] = recommended_inhouse_agents
    result["spare_capacity_hours"] = spare_capacity_hours
    result["overflow_workload_hours"] = overflow_workload_hours
    return result.loc[:, SIMULATED_WORKLOAD_OUTPUT_COLUMNS]


def calculate_simulation_summary(
    completed_simulation: pd.DataFrame,
    staffing_agents: int,
    handling_times_minutes: Mapping[str, float],
    booking_processing_hours_per_agent: float,
    percentiles: Sequence[float] = (0.5, 0.75, 0.9, 0.95),
) -> dict[str, object]:
    """Summarize simulation outcomes for one feasible in-house staffing level."""

    simulation_table = _validate_completed_simulation(completed_simulation)
    if simulation_table.empty:
        raise FieldValidationError("completed_simulation must contain at least one simulation row")

    normalized_staffing_agents = validate_non_negative_integer(
        "staffing_agents",
        staffing_agents,
    )
    normalized_handling_times = _validate_handling_times(handling_times_minutes)
    normalized_processing_hours = calculate_booking_processing_hours_per_agent(
        booking_processing_hours_per_agent
    )
    normalized_percentiles = _validate_percentiles(percentiles)

    total_workload_hours = simulation_table["total_workload_hours"].to_numpy(dtype=float, copy=False)
    unconstrained_required_agents = simulation_table["unconstrained_required_agents"].to_numpy(
        dtype=int,
        copy=False,
    )
    inhouse_capacity_hours = calculate_capacity_hours(
        normalized_staffing_agents,
        normalized_processing_hours,
    )

    overflow_hours_by_category: dict[str, list[float]] = {
        category: [] for category in RESERVATION_CATEGORIES
    }
    overflow_bookings_by_category: dict[str, list[float]] = {
        category: [] for category in RESERVATION_CATEGORIES
    }
    spare_capacity_hours: list[float] = []
    overflow_workload_hours: list[float] = []

    for row in simulation_table.to_dict(orient="records"):
        demand_by_category = {
            category: float(row[category])
            for category in RESERVATION_CATEGORIES
        }
        overflow_result = calculate_overflow_allocation_by_category(
            demand_by_category,
            normalized_handling_times,
            normalized_staffing_agents,
            normalized_processing_hours,
        )
        spare_capacity_hours.append(float(overflow_result["spare_capacity_hours"]))
        overflow_workload_hours.append(float(overflow_result["overflow_workload_hours"]))
        for category in RESERVATION_CATEGORIES:
            overflow_hours_by_category[category].append(
                float(overflow_result["overflow_hours_by_category"][category])
            )
            overflow_bookings_by_category[category].append(
                float(overflow_result["overflow_bookings_by_category"][category])
            )

    return {
        "staffing_agents": normalized_staffing_agents,
        "capacity_confidence": float(np.mean(total_workload_hours <= inhouse_capacity_hours)),
        "probability_overflow_required": float(
            np.mean(np.array(overflow_workload_hours, dtype=float) > 0.0)
        ),
        "expected_spare_capacity_hours": float(np.mean(spare_capacity_hours)),
        "expected_overflow_workload_hours": float(np.mean(overflow_workload_hours)),
        "expected_overflow_hours_by_category": {
            category: float(np.mean(values))
            for category, values in overflow_hours_by_category.items()
        },
        "expected_overflow_bookings_by_category": {
            category: float(np.mean(values))
            for category, values in overflow_bookings_by_category.items()
        },
        "required_agent_percentiles": {
            percentile: _higher_quantile(unconstrained_required_agents, percentile)
            for percentile in normalized_percentiles
        },
    }


__all__ = [
    "OUTLOOK_QUANTILE_CONVENTION",
    "SIMULATED_WORKLOAD_OUTPUT_COLUMNS",
    "calculate_simulation_summary",
    "calculate_simulated_workload_and_staffing",
    "select_representative_simulation_rows",
]
