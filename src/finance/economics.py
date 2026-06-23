"""Category-level financial helpers for in-house handling and overflow commission."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from src.constants import RESERVATION_CATEGORIES
from src.models import CategoryAssumptions
from src.validation import (
    FieldValidationError,
    validate_non_negative,
    validate_percentage,
)

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
    """Validate category-assumption records using the shared contract."""

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


def extract_average_booking_value_by_category(
    category_assumptions: Iterable[CategoryAssumptions | Mapping[str, Any]],
) -> CategoryValueMap:
    """Build the canonical average-booking-value lookup."""

    normalized = _normalize_category_assumptions(category_assumptions)
    return {item.category: item.average_booking_value for item in normalized}


def calculate_booking_value_by_category(
    booking_counts_by_category: Mapping[str, Any],
    average_booking_value_by_category: Mapping[str, Any],
) -> CategoryValueMap:
    """Calculate category-level booking value from counts and average values."""

    normalized_counts = _validate_category_metric_map(
        booking_counts_by_category,
        field_name="booking_counts_by_category",
    )
    normalized_values = _validate_category_metric_map(
        average_booking_value_by_category,
        field_name="average_booking_value_by_category",
    )
    return {
        category: normalized_counts[category] * normalized_values[category]
        for category in RESERVATION_CATEGORIES
    }


def calculate_overflow_commission_by_category(
    overflow_bookings_by_category: Mapping[str, Any],
    average_booking_value_by_category: Mapping[str, Any],
    third_party_commission_rate: float,
) -> CategoryValueMap:
    """Calculate overflow commission costs by category."""

    normalized_commission_rate = validate_percentage(
        "third_party_commission_rate",
        third_party_commission_rate,
    )
    overflow_booking_value = calculate_booking_value_by_category(
        overflow_bookings_by_category,
        average_booking_value_by_category,
    )
    return {
        category: overflow_booking_value[category] * normalized_commission_rate
        for category in RESERVATION_CATEGORIES
    }


def calculate_weekly_operating_financials(
    inhouse_bookings_by_category: Mapping[str, Any],
    overflow_bookings_by_category: Mapping[str, Any],
    category_assumptions: Iterable[CategoryAssumptions | Mapping[str, Any]],
    third_party_commission_rate: float,
) -> CategoryFinancialResult:
    """Return the booking-value and overflow-commission outputs for one workload outcome."""

    average_booking_value_by_category = extract_average_booking_value_by_category(
        category_assumptions
    )
    inhouse_booking_value_by_category = calculate_booking_value_by_category(
        inhouse_bookings_by_category,
        average_booking_value_by_category,
    )
    overflow_booking_value_by_category = calculate_booking_value_by_category(
        overflow_bookings_by_category,
        average_booking_value_by_category,
    )
    overflow_commission_by_category = calculate_overflow_commission_by_category(
        overflow_bookings_by_category,
        average_booking_value_by_category,
        third_party_commission_rate,
    )

    return {
        "inhouse_booking_value_by_category": inhouse_booking_value_by_category,
        "overflow_booking_value_by_category": overflow_booking_value_by_category,
        "overflow_commission_by_category": overflow_commission_by_category,
        "total_inhouse_booking_value": sum(inhouse_booking_value_by_category.values()),
        "total_overflow_booking_value": sum(overflow_booking_value_by_category.values()),
        "total_overflow_commission": sum(overflow_commission_by_category.values()),
        "total_commission_avoided": sum(
            inhouse_booking_value_by_category[category] * third_party_commission_rate
            for category in RESERVATION_CATEGORIES
        ),
    }


__all__ = [
    "calculate_booking_value_by_category",
    "calculate_overflow_commission_by_category",
    "calculate_weekly_operating_financials",
    "extract_average_booking_value_by_category",
]
