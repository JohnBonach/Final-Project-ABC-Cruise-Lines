"""Manager-facing recommendation narrative helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from src.validation import (
    FieldValidationError,
    validate_non_negative,
    validate_non_negative_integer,
    validate_percentage,
)

REQUIRED_COMPARISON_COLUMNS = (
    "plan_name",
    "staffing_agents",
    "capacity_confidence",
    "expected_spare_capacity_hours",
    "expected_overflow_workload_hours",
    "expected_total_weekly_operating_cost",
)


def _validate_recommendation_payload(recommendation: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(recommendation, Mapping):
        raise FieldValidationError("recommendation must be a mapping")
    if "recommended_staffing_record" not in recommendation:
        raise FieldValidationError("recommendation must include recommended_staffing_record")

    recommended_record = recommendation["recommended_staffing_record"]
    if not isinstance(recommended_record, Mapping):
        raise FieldValidationError("recommended_staffing_record must be a mapping")

    required_fields = (
        "staffing_agents",
        "capacity_confidence",
        "expected_spare_capacity_hours",
        "expected_overflow_workload_hours",
        "expected_total_weekly_operating_cost",
    )
    missing_fields = [field for field in required_fields if field not in recommended_record]
    if missing_fields:
        raise FieldValidationError(
            f"recommended_staffing_record is missing required fields: {missing_fields}"
        )

    return dict(recommendation)


def _validate_comparison_table(comparison_table: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(comparison_table, pd.DataFrame):
        raise FieldValidationError("comparison_table must be a pandas DataFrame")

    missing_columns = [
        column for column in REQUIRED_COMPARISON_COLUMNS if column not in comparison_table.columns
    ]
    if missing_columns:
        raise FieldValidationError(
            f"comparison_table is missing required columns: {missing_columns}"
        )

    return comparison_table.copy(deep=True)


def _format_staffing_delta(delta: int) -> str:
    if delta > 0:
        return f"+{delta}"
    return str(delta)


def _find_plan_record(comparison_table: pd.DataFrame, plan_name: str) -> dict[str, Any] | None:
    matches = comparison_table.loc[comparison_table["plan_name"] == plan_name]
    if matches.empty:
        return None
    return dict(matches.iloc[0].to_dict())


def _normalize_recommended_record(recommended_record: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(recommended_record)
    normalized["staffing_agents"] = validate_non_negative_integer(
        "recommended_staffing_record['staffing_agents']",
        normalized["staffing_agents"],
    )
    normalized["capacity_confidence"] = validate_percentage(
        "recommended_staffing_record['capacity_confidence']",
        normalized["capacity_confidence"],
    )
    normalized["expected_spare_capacity_hours"] = validate_non_negative(
        "recommended_staffing_record['expected_spare_capacity_hours']",
        normalized["expected_spare_capacity_hours"],
    )
    normalized["expected_overflow_workload_hours"] = validate_non_negative(
        "recommended_staffing_record['expected_overflow_workload_hours']",
        normalized["expected_overflow_workload_hours"],
    )
    normalized["expected_total_weekly_operating_cost"] = validate_non_negative(
        "recommended_staffing_record['expected_total_weekly_operating_cost']",
        normalized["expected_total_weekly_operating_cost"],
    )
    return normalized


def _normalize_staffing_agents(record: Mapping[str, Any], field_name: str) -> int:
    return validate_non_negative_integer(field_name, record["staffing_agents"])


def build_recommendation_warnings(
    recommendation: Mapping[str, Any],
    comparison_table: pd.DataFrame,
) -> list[str]:
    normalized_recommendation = _validate_recommendation_payload(recommendation)
    normalized_table = _validate_comparison_table(comparison_table)
    recommended_record = _normalize_recommended_record(
        normalized_recommendation["recommended_staffing_record"]
    )

    warnings: list[str] = []
    named_plan_rows = normalized_table.loc[
        normalized_table["plan_name"].isin(("Lean", "Balanced", "Conservative"))
    ]
    duplicate_named_plans = named_plan_rows.loc[
        named_plan_rows["staffing_agents"] == recommended_record["staffing_agents"]
    ]
    if len(duplicate_named_plans) > 1:
        warnings.append(
            "Multiple named plans map to the same staffing level under the current confidence targets."
        )
    if recommended_record["expected_overflow_workload_hours"] > 0.0:
        warnings.append(
            "Overflow remains above zero, so third-party routing is still expected at the recommended staffing level."
        )

    return warnings


def build_recommendation_text(
    recommendation: Mapping[str, Any],
    comparison_table: pd.DataFrame,
) -> str:
    normalized_recommendation = _validate_recommendation_payload(recommendation)
    normalized_table = _validate_comparison_table(comparison_table)
    recommended_record = _normalize_recommended_record(
        normalized_recommendation["recommended_staffing_record"]
    )

    recommended_staffing_agents = recommended_record["staffing_agents"]
    capacity_confidence_pct = recommended_record["capacity_confidence"] * 100.0
    expected_spare_capacity_hours = recommended_record["expected_spare_capacity_hours"]
    expected_overflow_workload_hours = recommended_record["expected_overflow_workload_hours"]
    expected_total_weekly_operating_cost = recommended_record["expected_total_weekly_operating_cost"]

    previous_week_record = _find_plan_record(normalized_table, "Previous Week")
    manager_plan_record = _find_plan_record(normalized_table, "Manager Plan")

    previous_week_delta_text = "N/A"
    if previous_week_record is not None:
        previous_week_delta = recommended_staffing_agents - _normalize_staffing_agents(
            previous_week_record,
            "comparison_table['Previous Week']['staffing_agents']",
        )
        previous_week_delta_text = _format_staffing_delta(previous_week_delta)

    manager_plan_delta_text = "N/A"
    if manager_plan_record is not None:
        manager_plan_delta = recommended_staffing_agents - _normalize_staffing_agents(
            manager_plan_record,
            "comparison_table['Manager Plan']['staffing_agents']",
        )
        manager_plan_delta_text = _format_staffing_delta(manager_plan_delta)

    if expected_overflow_workload_hours > 0.0:
        capacity_sentence = (
            f"Expected overflow is {expected_overflow_workload_hours:.1f} workload hours."
        )
    else:
        capacity_sentence = (
            f"Expected spare capacity is {expected_spare_capacity_hours:.1f} workload hours."
        )

    return (
        f"Schedule {recommended_staffing_agents} reservation agents for the upcoming week. "
        f"This plan provides an estimated {capacity_confidence_pct:.1f}% capacity confidence. "
        f"{capacity_sentence} "
        f"Expected weekly operating cost is ${expected_total_weekly_operating_cost:.2f}. "
        f"Compared with previous-week staffing, the recommended change is {previous_week_delta_text} agents, "
        f"and compared with the manager plan, the change is {manager_plan_delta_text} agents."
    )


__all__ = [
    "build_recommendation_text",
    "build_recommendation_warnings",
]
