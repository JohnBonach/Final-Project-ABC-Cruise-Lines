"""Financial staffing recommendation helpers."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.constants import STAFFING_EVALUATION_COLUMNS
from src.validation import FieldValidationError
from src.validation import validate_non_negative

DEFAULT_SELECTION_TOLERANCE = 1e-9


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


def _build_ranked_rows(
    staffing_evaluations: pd.DataFrame,
    *,
    selection_tolerance: float,
) -> list[dict[str, Any]]:
    """Return row dictionaries ordered by the financial selection rule."""

    records = staffing_evaluations.to_dict(orient="records")
    if not records:
        return []

    minimum_cost = min(
        float(record["expected_total_weekly_operating_cost"]) for record in records
    )

    def ranking_key(record: dict[str, Any]) -> tuple[float, float, float, int, float]:
        total_weekly_operating_cost = float(record["expected_total_weekly_operating_cost"])
        within_tolerance = (
            total_weekly_operating_cost <= minimum_cost + selection_tolerance
        )
        capacity_confidence = float(record["capacity_confidence"])
        expected_overflow_workload_hours = float(record["expected_overflow_workload_hours"])
        staffing_agents = int(record["staffing_agents"])

        if within_tolerance:
            return (
                0.0,
                -capacity_confidence,
                expected_overflow_workload_hours,
                staffing_agents,
                total_weekly_operating_cost,
            )
        return (
            1.0,
            total_weekly_operating_cost,
            -capacity_confidence,
            expected_overflow_workload_hours,
            staffing_agents,
        )

    return sorted(records, key=ranking_key)


def select_financial_recommendation(
    staffing_evaluations: pd.DataFrame,
    *,
    selection_tolerance: float = DEFAULT_SELECTION_TOLERANCE,
) -> dict[str, Any]:
    """Select the financially recommended staffing option and rank all candidates."""

    normalized_staffing_evaluations = _validate_staffing_evaluations(staffing_evaluations)
    normalized_tolerance = _validate_selection_tolerance(selection_tolerance)

    ranked_records = _build_ranked_rows(
        normalized_staffing_evaluations,
        selection_tolerance=normalized_tolerance,
    )
    ranked_table = pd.DataFrame(ranked_records, columns=STAFFING_EVALUATION_COLUMNS)
    ranked_table.insert(0, "financial_rank", range(1, len(ranked_table) + 1))

    recommended_record = dict(ranked_records[0])
    recommended_staffing_agents = int(recommended_record["staffing_agents"])
    if recommended_staffing_agents not in set(
        int(value) for value in normalized_staffing_evaluations["staffing_agents"].tolist()
    ):
        raise FieldValidationError(
            "selected recommendation must exist in the candidate table"
        )

    return {
        "recommended_staffing_record": recommended_record,
        "recommended_staffing_agents": recommended_staffing_agents,
        "candidate_ranking": ranked_table,
        "selection_tolerance": normalized_tolerance,
        "objective_column": "expected_total_weekly_operating_cost",
    }


__all__ = [
    "DEFAULT_SELECTION_TOLERANCE",
    "select_financial_recommendation",
]
