"""Financial staffing recommendation helpers."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.constants import STAFFING_EVALUATION_COLUMNS
from src.validation import FieldValidationError
from src.validation import validate_non_negative
from src.validation import validate_percentage

DEFAULT_SELECTION_TOLERANCE = 0.01


def _validate_staffing_evaluations(staffing_evaluations: pd.DataFrame) -> pd.DataFrame:
    """Validate the staffing-evaluation contract and return a defensive copy."""

    if not isinstance(staffing_evaluations, pd.DataFrame):
        raise FieldValidationError("staffing_evaluations must be a pandas DataFrame")

    actual_columns = tuple(staffing_evaluations.columns)
    if actual_columns != STAFFING_EVALUATION_COLUMNS:
        missing_columns = [
            column
            for column in STAFFING_EVALUATION_COLUMNS
            if column not in staffing_evaluations.columns
        ]
        unexpected_columns = [
            column
            for column in staffing_evaluations.columns
            if column not in STAFFING_EVALUATION_COLUMNS
        ]
        problems: list[str] = []
        if missing_columns:
            problems.append(f"missing columns: {missing_columns}")
        if unexpected_columns:
            problems.append(f"unexpected columns: {unexpected_columns}")
        raise FieldValidationError(
            "staffing_evaluations must match the shared contract exactly "
            f"({', '.join(problems)})"
        )

    if staffing_evaluations.empty:
        raise FieldValidationError("staffing_evaluations must contain at least one row")

    return staffing_evaluations.copy(deep=True)


def _validate_selection_tolerance(selection_tolerance: float) -> float:
    """Validate the tolerance used to decide when two options are effectively tied."""

    tolerance = validate_non_negative(
        "selection_tolerance",
        selection_tolerance,
    )
    return tolerance


def _validate_minimum_inhouse_coverage_target(
    minimum_inhouse_coverage_target: float,
) -> float:
    """Validate the recommendation coverage target."""

    return validate_percentage(
        "minimum_inhouse_coverage_target",
        minimum_inhouse_coverage_target,
    )


def _monetary_tie_group(
    records: list[dict[str, Any]],
    *,
    selection_tolerance: float,
) -> list[dict[str, Any]]:
    """Return the candidate records that are within the monetary tie tolerance."""

    minimum_cost = min(
        float(record["expected_total_weekly_operating_cost"]) for record in records
    )
    tolerance_with_epsilon = selection_tolerance + 1e-12
    return [
        record
        for record in records
        if abs(float(record["expected_total_weekly_operating_cost"]) - minimum_cost)
        <= tolerance_with_epsilon
    ]


def _tie_break_key(record: dict[str, Any]) -> tuple[float, float, int]:
    """Return the deterministic tie-break key shared by normal and fallback selection."""

    return (
        -float(record["capacity_confidence"]),
        float(record["expected_overflow_workload_hours"]),
        int(record["staffing_agents"]),
    )


def _build_ranked_rows(
    staffing_evaluations: pd.DataFrame,
    *,
    minimum_inhouse_coverage_target: float,
    selection_tolerance: float,
) -> list[dict[str, Any]]:
    """Return row dictionaries ordered by the financial selection rule."""

    records = staffing_evaluations.to_dict(orient="records")
    if not records:
        return []

    annotated_records: list[dict[str, Any]] = []
    for record in records:
        annotated = dict(record)
        coverage = float(record["capacity_confidence"])
        total_cost = float(record["expected_total_weekly_operating_cost"])
        annotated["meets_coverage_target"] = (
            coverage >= minimum_inhouse_coverage_target
        )
        annotated["coverage_gap"] = max(
            minimum_inhouse_coverage_target - coverage,
            0.0,
        )
        annotated["total_cost_rounded_cents"] = round(total_cost, 2)
        annotated_records.append(annotated)

    eligible_records = [
        record for record in annotated_records if bool(record["meets_coverage_target"])
    ]
    if eligible_records:
        tied_eligible_records = _monetary_tie_group(
            eligible_records,
            selection_tolerance=selection_tolerance,
        )
        selected_staffing_agents = int(
            min(tied_eligible_records, key=_tie_break_key)["staffing_agents"]
        )

        def ranking_key(record: dict[str, Any]) -> tuple[float, float, float, int, int]:
            return (
                0.0 if bool(record["meets_coverage_target"]) else 1.0,
                float(record["expected_total_weekly_operating_cost"])
                if bool(record["meets_coverage_target"])
                else float("inf"),
                -float(record["capacity_confidence"]),
                float(record["expected_overflow_workload_hours"]),
                int(record["staffing_agents"]),
            )

        ranked = sorted(annotated_records, key=ranking_key)
    else:
        selected_staffing_agents = max(
            int(record["staffing_agents"]) for record in annotated_records
        )

        def ranking_key(record: dict[str, Any]) -> tuple[float, float, float, int]:
            return (
                -float(record["capacity_confidence"]),
                float(record["expected_overflow_workload_hours"]),
                -int(record["staffing_agents"]),
                float(record["expected_total_weekly_operating_cost"]),
            )

        ranked = sorted(annotated_records, key=ranking_key)

    selected_index = next(
        index
        for index, record in enumerate(ranked)
        if int(record["staffing_agents"]) == selected_staffing_agents
    )
    if selected_index != 0:
        ranked.insert(0, ranked.pop(selected_index))
    return ranked


def select_financial_recommendation(
    staffing_evaluations: pd.DataFrame,
    *,
    minimum_inhouse_coverage_target: float,
    selection_tolerance: float = DEFAULT_SELECTION_TOLERANCE,
) -> dict[str, Any]:
    """Select the financially recommended staffing option and rank all candidates."""

    normalized_staffing_evaluations = _validate_staffing_evaluations(staffing_evaluations)
    normalized_coverage_target = _validate_minimum_inhouse_coverage_target(
        minimum_inhouse_coverage_target
    )
    normalized_tolerance = _validate_selection_tolerance(selection_tolerance)

    ranked_records = _build_ranked_rows(
        normalized_staffing_evaluations,
        minimum_inhouse_coverage_target=normalized_coverage_target,
        selection_tolerance=normalized_tolerance,
    )
    ranked_columns = (
        *STAFFING_EVALUATION_COLUMNS,
        "meets_coverage_target",
        "coverage_gap",
        "total_cost_rounded_cents",
    )
    ranked_table = pd.DataFrame(ranked_records, columns=ranked_columns)
    ranked_table.insert(0, "financial_rank", range(1, len(ranked_table) + 1))

    recommended_record = dict(ranked_records[0])
    recommended_staffing_agents = int(recommended_record["staffing_agents"])
    recommended_coverage = float(recommended_record["capacity_confidence"])
    coverage_target_met = bool(recommended_record["meets_coverage_target"])
    if recommended_staffing_agents not in set(
        int(value) for value in normalized_staffing_evaluations["staffing_agents"].tolist()
    ):
        raise FieldValidationError(
            "selected recommendation must exist in the candidate table"
        )

    warning: str | None = None
    maximum_achievable_coverage = float(
        normalized_staffing_evaluations["capacity_confidence"].max()
    )
    if not coverage_target_met:
        warning = (
            "The configured in-house coverage target cannot be achieved within the "
            "current feasible staffing range. The recommendation uses the maximum "
            "available in-house staffing instead."
        )

    return {
        "recommended_staffing_record": recommended_record,
        "recommended_staffing_agents": recommended_staffing_agents,
        "selected_minimum_inhouse_coverage_target": normalized_coverage_target,
        "recommended_coverage": recommended_coverage,
        "coverage_target_met": coverage_target_met,
        "expected_total_weekly_operating_cost": float(
            recommended_record["expected_total_weekly_operating_cost"]
        ),
        "maximum_achievable_coverage": maximum_achievable_coverage,
        "warning": warning,
        "candidate_ranking": ranked_table,
        "selection_tolerance": normalized_tolerance,
        "objective_column": "expected_total_weekly_operating_cost",
    }


__all__ = [
    "DEFAULT_SELECTION_TOLERANCE",
    "select_financial_recommendation",
]
