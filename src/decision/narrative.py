"""Manager-facing recommendation narrative helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from src.validation import FieldValidationError
from src.validation import validate_non_negative
from src.validation import validate_non_negative_integer
from src.validation import validate_percentage

REQUIRED_COMPARISON_COLUMNS = (
    "plan_name",
    "staffing_agents",
    "capacity_confidence",
    "expected_overtime_hours",
    "expected_abandoned_total",
    "expected_total_economic_cost",
)

COMPARISON_PLAN_NAMES = (
    "Previous Week",
    "Manager Plan",
    "Lean",
    "Balanced",
    "Conservative",
    "Financial Recommendation",
)


def _validate_recommendation_payload(recommendation: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the optimizer recommendation payload required by the narrative."""

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
        "expected_overtime_hours",
        "expected_abandoned_total",
        "expected_total_economic_cost",
    )
    missing_fields = [field for field in required_fields if field not in recommended_record]
    if missing_fields:
        raise FieldValidationError(
            f"recommended_staffing_record is missing required fields: {missing_fields}"
        )

    return dict(recommendation)


def _validate_comparison_table(comparison_table: pd.DataFrame) -> pd.DataFrame:
    """Validate the plan comparison table used for narrative generation."""

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
    """Format staffing deltas with explicit sign for narrative text."""

    if delta > 0:
        return f"+{delta}"
    return str(delta)


def _find_plan_record(comparison_table: pd.DataFrame, plan_name: str) -> dict[str, Any] | None:
    """Return the first comparison row for a given plan name when present."""

    matches = comparison_table.loc[comparison_table["plan_name"] == plan_name]
    if matches.empty:
        return None
    return dict(matches.iloc[0].to_dict())


def _normalize_recommended_record(recommended_record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the fields used by the narrative and return normalized values."""

    normalized = dict(recommended_record)
    normalized["staffing_agents"] = validate_non_negative_integer(
        "recommended_staffing_record['staffing_agents']",
        normalized["staffing_agents"],
    )
    normalized["capacity_confidence"] = validate_percentage(
        "recommended_staffing_record['capacity_confidence']",
        normalized["capacity_confidence"],
    )
    normalized["expected_overtime_hours"] = validate_non_negative(
        "recommended_staffing_record['expected_overtime_hours']",
        normalized["expected_overtime_hours"],
    )
    normalized["expected_abandoned_total"] = validate_non_negative(
        "recommended_staffing_record['expected_abandoned_total']",
        normalized["expected_abandoned_total"],
    )
    normalized["expected_total_economic_cost"] = validate_non_negative(
        "recommended_staffing_record['expected_total_economic_cost']",
        normalized["expected_total_economic_cost"],
    )
    return normalized


def _normalize_staffing_agents(record: Mapping[str, Any], field_name: str) -> int:
    """Validate a staffing-agents value extracted from a comparison-table row."""

    return validate_non_negative_integer(field_name, record["staffing_agents"])


def _select_tradeoff_record(
    comparison_table: pd.DataFrame,
    recommended_staffing_agents: int,
) -> dict[str, Any] | None:
    """Choose an alternative named plan for the recommendation tradeoff sentence."""

    for plan_name in ("Balanced", "Lean", "Conservative"):
        record = _find_plan_record(comparison_table, plan_name)
        if record is not None and _normalize_staffing_agents(
            record,
            f"comparison_table[{plan_name!r}]['staffing_agents']",
        ) != recommended_staffing_agents:
            return record
    for plan_name in ("Balanced", "Lean", "Conservative"):
        record = _find_plan_record(comparison_table, plan_name)
        if record is not None:
            return record
    return None


def build_recommendation_warnings(
    recommendation: Mapping[str, Any],
    comparison_table: pd.DataFrame,
) -> list[str]:
    """Build optional warning messages from the recommendation context."""

    normalized_recommendation = _validate_recommendation_payload(recommendation)
    normalized_table = _validate_comparison_table(comparison_table)
    recommended_record = _normalize_recommended_record(
        normalized_recommendation["recommended_staffing_record"]
    )

    warnings: list[str] = []
    recommended_staffing_agents = recommended_record["staffing_agents"]
    named_plan_rows = normalized_table.loc[
        normalized_table["plan_name"].isin(("Lean", "Balanced", "Conservative"))
    ]
    duplicate_named_plans = named_plan_rows.loc[
        named_plan_rows["staffing_agents"] == recommended_staffing_agents
    ]
    if len(duplicate_named_plans) > 1:
        warnings.append(
            "Multiple named plans map to the same staffing level under the current confidence targets."
        )

    if recommended_record["expected_abandoned_total"] > 0.0:
        warnings.append(
            "Expected abandonment remains above zero, so the recommendation still reflects some service-risk tradeoff."
        )

    return warnings


def build_recommendation_text(
    recommendation: Mapping[str, Any],
    comparison_table: pd.DataFrame,
) -> str:
    """Build a short manager-facing recommendation paragraph from structured values."""

    normalized_recommendation = _validate_recommendation_payload(recommendation)
    normalized_table = _validate_comparison_table(comparison_table)
    recommended_record = _normalize_recommended_record(
        normalized_recommendation["recommended_staffing_record"]
    )

    recommended_staffing_agents = recommended_record["staffing_agents"]
    capacity_confidence_pct = recommended_record["capacity_confidence"] * 100.0
    expected_overtime_hours = recommended_record["expected_overtime_hours"]
    expected_abandoned_total = recommended_record["expected_abandoned_total"]
    expected_total_economic_cost = recommended_record["expected_total_economic_cost"]

    previous_week_record = _find_plan_record(normalized_table, "Previous Week")
    manager_plan_record = _find_plan_record(normalized_table, "Manager Plan")
    tradeoff_record = _select_tradeoff_record(normalized_table, recommended_staffing_agents)

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

    tradeoff_sentence = ""
    if tradeoff_record is not None:
        tradeoff_staffing_agents = _normalize_staffing_agents(
            tradeoff_record,
            f"comparison_table[{tradeoff_record['plan_name']!r}]['staffing_agents']",
        )
        tradeoff_sentence = (
            f" Compared with the {tradeoff_record['plan_name']} plan at "
            f"{tradeoff_staffing_agents} agents, this recommendation changes "
            f"expected economic cost to ${expected_total_economic_cost:.2f} while balancing "
            f"capacity confidence and abandonment risk."
        )

    return (
        f"Schedule {recommended_staffing_agents} reservation agents for the upcoming week. "
        f"This recommendation provides an estimated {capacity_confidence_pct:.1f}% capacity confidence, "
        f"with expected overtime of {expected_overtime_hours:.1f} hours, expected abandonment of "
        f"{expected_abandoned_total:.1f} reservations, and an expected total economic cost of "
        f"${expected_total_economic_cost:.2f}. Compared with previous-week staffing, the recommended "
        f"change is {previous_week_delta_text} agents, and compared with the manager plan, the change is "
        f"{manager_plan_delta_text} agents.{tradeoff_sentence}"
    )


__all__ = [
    "build_recommendation_text",
    "build_recommendation_warnings",
]
