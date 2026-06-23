"""Forecast uncertainty and canonical forecast assembly."""

from __future__ import annotations

import pandas as pd

from src.constants import FORECAST_RESULT_COLUMNS, RESERVATION_CATEGORIES
from src.forecasting.weighted_moving_average import calculate_weighted_moving_average
from src.validation import (
    FieldValidationError,
    validate_non_negative,
    validate_required_history_weeks,
)


def _ensure_required_columns(history: pd.DataFrame) -> None:
    """Require the canonical weekly history contract columns."""

    required_columns = ("week_id", "week_start", *RESERVATION_CATEGORIES, "staffing_agents")
    missing_columns = [column for column in required_columns if column not in history.columns]
    if missing_columns:
        raise FieldValidationError(
            "historical data is missing required columns: "
            f"{', '.join(missing_columns)}"
        )


def calculate_historical_uncertainty(
    history: pd.DataFrame,
    variability_multiplier: float,
) -> dict[str, dict[str, float]]:
    """Return historical mean, standard deviation, and adjusted standard deviation."""

    _ensure_required_columns(history)
    multiplier = validate_non_negative("variability_multiplier", variability_multiplier)
    validate_required_history_weeks(len(history), 4, field_name="history")

    ordered_history = history.sort_values(
        by=["week_start", "week_id"],
        kind="stable",
    ).reset_index(drop=True)

    records: dict[str, dict[str, float]] = {}
    for category in RESERVATION_CATEGORIES:
        category_series = ordered_history[category].astype(float)
        historical_std = float(category_series.std())
        records[category] = {
            "historical_mean": float(category_series.mean()),
            "historical_std": historical_std,
            "adjusted_std": float(historical_std * multiplier),
        }

    return records


def _normalize_manual_overrides(
    manual_overrides: dict[str, float] | None,
) -> dict[str, float]:
    """Validate and normalize optional manual forecast overrides."""

    if manual_overrides is None:
        return {}

    normalized: dict[str, float] = {}
    for category, value in manual_overrides.items():
        if category not in RESERVATION_CATEGORIES:
            raise ValueError(
                f"manual_overrides contains unknown category {category!r}; "
                f"expected one of {RESERVATION_CATEGORIES}"
            )
        normalized[category] = validate_non_negative(f"manual_overrides[{category}]", value)
    return normalized


def assemble_forecast_result(
    history: pd.DataFrame,
    weights: list[float],
    variability_multiplier: float,
    manual_overrides: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Assemble the canonical forecast-result table."""

    point_forecast = calculate_weighted_moving_average(history, weights)
    historical_stats = calculate_historical_uncertainty(history, variability_multiplier)
    overrides = _normalize_manual_overrides(manual_overrides)

    records: list[dict[str, object]] = []
    for category in RESERVATION_CATEGORIES:
        is_manual = category in overrides
        records.append(
            {
                "category": category,
                "point_forecast": float(overrides.get(category, point_forecast[category])),
                "historical_mean": float(historical_stats[category]["historical_mean"]),
                "historical_std": float(historical_stats[category]["historical_std"]),
                "adjusted_std": float(historical_stats[category]["adjusted_std"]),
                "forecast_source": "manual_override" if is_manual else "automatic",
            }
        )

    return pd.DataFrame(records, columns=FORECAST_RESULT_COLUMNS)


def build_forecast_result(
    history: pd.DataFrame,
    weights: list[float],
    variability_multiplier: float,
    manual_overrides: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Alias for assembling the canonical forecast-result table."""

    return assemble_forecast_result(
        history,
        weights,
        variability_multiplier,
        manual_overrides=manual_overrides,
    )


calculate_forecast_result = assemble_forecast_result


__all__ = [
    "assemble_forecast_result",
    "build_forecast_result",
    "calculate_forecast_result",
    "calculate_historical_uncertainty",
]
