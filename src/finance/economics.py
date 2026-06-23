"""Category-level financial primitives for retained and lost reservation value."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from src.constants import RESERVATION_CATEGORIES
from src.models import CategoryAssumptions
from src.validation import FieldValidationError, validate_non_negative

CategoryValueMap = dict[str, float]
CategoryFinancialResult = dict[str, CategoryValueMap | float]


def _validate_category_metric_map(
    values: Mapping[str, Any],
    *,
    field_name: str,
) -> CategoryValueMap:
    """Validate a category-keyed numeric mapping and normalize it to floats."""

    if not isinstance(values, Mapping):
        raise FieldValidationError(f"{field_name} must be a mapping keyed by category")

    actual_categories = tuple(values.keys())
    if actual_categories != RESERVATION_CATEGORIES:
        raise FieldValidationError(
            f"{field_name} must include each canonical category exactly once "
            f"and in the shared order {RESERVATION_CATEGORIES}"
        )

    return {
        category: validate_non_negative(f"{field_name}.{category}", values[category])
        for category in RESERVATION_CATEGORIES
    }


def _normalize_category_assumptions(
    category_assumptions: Iterable[CategoryAssumptions | Mapping[str, Any]],
) -> tuple[CategoryAssumptions, ...]:
    """Validate category assumption records using the shared model contract."""

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


def extract_average_revenue_by_category(
    category_assumptions: Iterable[CategoryAssumptions | Mapping[str, Any]],
) -> CategoryValueMap:
    """Build the canonical average-revenue lookup from shared category assumptions."""

    normalized = _normalize_category_assumptions(category_assumptions)
    return {item.category: item.average_revenue for item in normalized}


def extract_contribution_by_category(
    category_assumptions: Iterable[CategoryAssumptions | Mapping[str, Any]],
) -> CategoryValueMap:
    """Build the canonical contribution-value lookup from shared category assumptions."""

    normalized = _normalize_category_assumptions(category_assumptions)
    return {item.category: item.contribution_per_reservation for item in normalized}


def _calculate_category_values(
    reservation_counts: Mapping[str, Any],
    value_by_category: Mapping[str, Any],
    *,
    count_field_name: str,
    value_field_name: str,
) -> CategoryValueMap:
    """Multiply validated category counts by validated category financial values."""

    normalized_counts = _validate_category_metric_map(
        reservation_counts,
        field_name=count_field_name,
    )
    normalized_values = _validate_category_metric_map(
        value_by_category,
        field_name=value_field_name,
    )
    return {
        category: normalized_counts[category] * normalized_values[category]
        for category in RESERVATION_CATEGORIES
    }


def calculate_retained_revenue(
    completed_reservations_by_category: Mapping[str, Any],
    average_revenue_by_category: Mapping[str, Any],
) -> CategoryValueMap:
    """Calculate retained revenue by category from completed reservations."""

    return _calculate_category_values(
        completed_reservations_by_category,
        average_revenue_by_category,
        count_field_name="completed_reservations_by_category",
        value_field_name="average_revenue_by_category",
    )


def calculate_retained_contribution(
    completed_reservations_by_category: Mapping[str, Any],
    contribution_by_category: Mapping[str, Any],
) -> CategoryValueMap:
    """Calculate retained contribution by category from completed reservations."""

    return _calculate_category_values(
        completed_reservations_by_category,
        contribution_by_category,
        count_field_name="completed_reservations_by_category",
        value_field_name="contribution_by_category",
    )


def calculate_lost_revenue(
    abandoned_reservations_by_category: Mapping[str, Any],
    average_revenue_by_category: Mapping[str, Any],
) -> CategoryValueMap:
    """Calculate lost revenue by category from abandoned reservations."""

    return _calculate_category_values(
        abandoned_reservations_by_category,
        average_revenue_by_category,
        count_field_name="abandoned_reservations_by_category",
        value_field_name="average_revenue_by_category",
    )


def calculate_lost_contribution(
    abandoned_reservations_by_category: Mapping[str, Any],
    contribution_by_category: Mapping[str, Any],
) -> CategoryValueMap:
    """Calculate lost contribution by category from abandoned reservations."""

    return _calculate_category_values(
        abandoned_reservations_by_category,
        contribution_by_category,
        count_field_name="abandoned_reservations_by_category",
        value_field_name="contribution_by_category",
    )


def calculate_category_financials(
    completed_reservations_by_category: Mapping[str, Any],
    abandoned_reservations_by_category: Mapping[str, Any],
    category_assumptions: Iterable[CategoryAssumptions | Mapping[str, Any]],
) -> CategoryFinancialResult:
    """Return category-preserving retained and lost revenue and contribution outputs."""

    average_revenue_by_category = extract_average_revenue_by_category(category_assumptions)
    contribution_by_category = extract_contribution_by_category(category_assumptions)

    retained_revenue = calculate_retained_revenue(
        completed_reservations_by_category,
        average_revenue_by_category,
    )
    retained_contribution = calculate_retained_contribution(
        completed_reservations_by_category,
        contribution_by_category,
    )
    lost_revenue = calculate_lost_revenue(
        abandoned_reservations_by_category,
        average_revenue_by_category,
    )
    lost_contribution = calculate_lost_contribution(
        abandoned_reservations_by_category,
        contribution_by_category,
    )

    return {
        "retained_revenue_by_category": retained_revenue,
        "retained_contribution_by_category": retained_contribution,
        "lost_revenue_by_category": lost_revenue,
        "lost_contribution_by_category": lost_contribution,
        "total_retained_revenue": sum(retained_revenue.values()),
        "total_retained_contribution": sum(retained_contribution.values()),
        "total_lost_revenue": sum(lost_revenue.values()),
        "total_lost_contribution": sum(lost_contribution.values()),
    }


__all__ = [
    "calculate_category_financials",
    "calculate_lost_contribution",
    "calculate_lost_revenue",
    "calculate_retained_contribution",
    "calculate_retained_revenue",
    "extract_average_revenue_by_category",
    "extract_contribution_by_category",
]
