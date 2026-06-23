"""Weighted moving-average forecasting by canonical reservation category."""

from __future__ import annotations

import pandas as pd

from src.constants import HISTORICAL_DEMAND_COLUMNS, RESERVATION_CATEGORIES
from src.validation import (
    FieldValidationError,
    InsufficientHistoryError,
    validate_required_history_weeks,
    validate_weights,
)


def _ensure_required_columns(history: pd.DataFrame) -> None:
    """Require the approved historical-demand contract columns."""

    missing_columns = [
        column for column in HISTORICAL_DEMAND_COLUMNS if column not in history.columns
    ]
    if missing_columns:
        raise FieldValidationError(
            "historical data is missing required columns: "
            f"{', '.join(missing_columns)}"
        )


def _sort_history(history: pd.DataFrame) -> pd.DataFrame:
    """Return history ordered from oldest to most recent week."""

    return history.sort_values(
        by=["week_start", "week_id"],
        kind="stable",
    ).reset_index(drop=True)


def calculate_weighted_moving_average(
    history: pd.DataFrame,
    weights: list[float],
) -> dict[str, float]:
    """Calculate a four-week weighted moving-average point forecast per category."""

    _ensure_required_columns(history)
    normalized_weights = validate_weights(weights, expected_count=4)

    ordered_history = _sort_history(history)
    validate_required_history_weeks(
        len(ordered_history),
        len(normalized_weights),
        field_name="history",
    )

    recent_history = ordered_history.tail(len(normalized_weights))
    forecast_by_category: dict[str, float] = {}
    for category in RESERVATION_CATEGORIES:
        recent_values = recent_history[category].astype(float).tolist()
        forecast_by_category[category] = float(
            sum(
                value * weight
                for value, weight in zip(reversed(recent_values), normalized_weights)
            )
        )

    return forecast_by_category


__all__ = ["calculate_weighted_moving_average"]
