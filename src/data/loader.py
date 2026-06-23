"""Historical-demand CSV loading and validation for ABC Cruise Lines."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from src.constants import HISTORICAL_DEMAND_COLUMNS, RESERVATION_CATEGORIES
from src.validation import (
    FieldValidationError,
    validate_non_negative,
    validate_non_negative_integer,
    validate_required_history_weeks,
)

MINIMUM_FORECAST_HISTORY_WEEKS = 4


def _ensure_required_columns(history: pd.DataFrame) -> None:
    """Require the canonical historical-demand columns."""

    missing_columns = [
        column for column in HISTORICAL_DEMAND_COLUMNS if column not in history.columns
    ]
    if missing_columns:
        raise FieldValidationError(
            "historical data is missing required columns: "
            f"{', '.join(missing_columns)}"
        )


def _parse_iso_week_start(week_id: str) -> date:
    """Convert a canonical week identifier into its Monday week-start date."""

    if not isinstance(week_id, str):
        raise FieldValidationError("week_id must contain non-empty strings")

    normalized_week_id = week_id.strip()
    if len(normalized_week_id) != 8 or normalized_week_id[4:6] != "-W":
        raise FieldValidationError(
            "week_id must use the canonical ISO format YYYY-Www"
        )

    year_text = normalized_week_id[:4]
    week_text = normalized_week_id[6:]
    if not year_text.isdigit() or not week_text.isdigit():
        raise FieldValidationError(
            "week_id must use the canonical ISO format YYYY-Www"
        )

    try:
        return date.fromisocalendar(int(year_text), int(week_text), 1)
    except ValueError as exc:
        raise FieldValidationError(
            f"week_id contains an invalid ISO week: {normalized_week_id!r}"
        ) from exc


def _normalize_weeks(history: pd.DataFrame) -> pd.DataFrame:
    """Parse and validate week identifiers and chronological sequencing."""

    normalized = history.copy()
    normalized["week_id"] = normalized["week_id"].astype("string").str.strip()
    if normalized["week_id"].isna().any() or (normalized["week_id"] == "").any():
        raise FieldValidationError("week_id must not contain blank values")

    try:
        normalized["week_start"] = pd.to_datetime(
            normalized["week_start"],
            errors="raise",
        ).dt.normalize()
    except (TypeError, ValueError) as exc:
        raise FieldValidationError("week_start must contain parseable dates") from exc

    expected_week_starts = normalized["week_id"].map(_parse_iso_week_start)
    actual_week_starts = normalized["week_start"].dt.date
    if not actual_week_starts.equals(expected_week_starts):
        raise FieldValidationError(
            "week_id and week_start must describe the same Monday week"
        )

    if normalized["week_id"].duplicated().any():
        duplicates = normalized.loc[
            normalized["week_id"].duplicated(),
            "week_id",
        ].unique()
        raise FieldValidationError(
            f"historical data contains duplicate week_id values: {duplicates.tolist()}"
        )

    if normalized["week_start"].duplicated().any():
        duplicates = normalized.loc[
            normalized["week_start"].duplicated(),
            "week_start",
        ].dt.strftime("%Y-%m-%d").unique()
        raise FieldValidationError(
            "historical data contains duplicate week_start values: "
            f"{duplicates.tolist()}"
        )

    normalized = normalized.sort_values(
        by=["week_start", "week_id"],
        kind="stable",
    ).reset_index(drop=True)
    week_gaps = normalized["week_start"].diff().dropna()
    if not week_gaps.empty and not week_gaps.eq(pd.Timedelta(days=7)).all():
        raise FieldValidationError(
            "historical data must contain contiguous weekly observations with no gaps"
        )

    validate_required_history_weeks(
        normalized["week_id"].nunique(),
        MINIMUM_FORECAST_HISTORY_WEEKS,
        field_name="history",
    )
    return normalized


def _coerce_integer_series(series: pd.Series, field_name: str) -> pd.Series:
    """Require numeric integer-compatible values and return an int64 series."""

    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().any():
        raise FieldValidationError(f"{field_name} must contain numeric values")

    if not numeric.mod(1).eq(0).all():
        raise FieldValidationError(f"{field_name} must contain integer-compatible values")

    integers = numeric.astype("int64")
    for index, value in integers.items():
        validate_non_negative_integer(f"{field_name}[{index}]", value)
    return integers


def _normalize_demands_and_staffing(history: pd.DataFrame) -> pd.DataFrame:
    """Validate category demand and staffing columns against shared rules."""

    normalized = history.copy()
    for category in RESERVATION_CATEGORIES:
        normalized[category] = _coerce_integer_series(normalized[category], category)

    staffing = pd.to_numeric(normalized["staffing_agents"], errors="coerce")
    if staffing.isna().any():
        raise FieldValidationError("staffing_agents must contain numeric values")
    if not staffing.mod(1).eq(0).all():
        raise FieldValidationError(
            "staffing_agents must contain integer-compatible values"
        )

    normalized["staffing_agents"] = staffing.astype("int64")
    for index, value in normalized["staffing_agents"].items():
        validate_non_negative("staffing_agents", value)
        validate_non_negative_integer(f"staffing_agents[{index}]", value)

    return normalized


def _summarize_numeric_history_column(series: pd.Series) -> dict[str, float | int]:
    """Return common descriptive statistics for a validated numeric column."""

    return {
        "total": int(series.sum()),
        "mean": float(series.mean()),
        "std": float(series.std()),
        "min": int(series.min()),
        "max": int(series.max()),
    }


def _history_quality_checks(history: pd.DataFrame) -> dict[str, bool]:
    """Return lightweight readiness checks for validated weekly history."""

    week_starts = pd.to_datetime(history["week_start"], errors="raise").dt.normalize()
    parsed_week_starts = history["week_id"].map(_parse_iso_week_start)
    demand_and_staffing_columns = list(RESERVATION_CATEGORIES) + ["staffing_agents"]

    return {
        "canonical_columns": tuple(history.columns) == HISTORICAL_DEMAND_COLUMNS,
        "week_ids_unique": bool(history["week_id"].is_unique),
        "week_starts_unique": bool(history["week_start"].is_unique),
        "week_id_matches_week_start": bool(
            week_starts.dt.date.equals(parsed_week_starts)
        ),
        "week_starts_are_mondays": bool((week_starts.dt.dayofweek == 0).all()),
        "weeks_are_contiguous": bool(
            week_starts.sort_values().diff().dropna().eq(pd.Timedelta(days=7)).all()
        ),
        "meets_minimum_history_weeks": bool(
            len(history) >= MINIMUM_FORECAST_HISTORY_WEEKS
        ),
        "no_missing_values": bool(
            not history[list(HISTORICAL_DEMAND_COLUMNS)].isna().any().any()
        ),
        "all_values_non_negative": bool(
            (history[demand_and_staffing_columns] >= 0).all().all()
        ),
    }


def _recent_four_week_extract(history: pd.DataFrame) -> list[dict[str, Any]]:
    """Return the most recent four validated weeks as serialized records."""

    recent_history = history.tail(4).copy()
    recent_history["week_start"] = pd.to_datetime(
        recent_history["week_start"], errors="raise"
    ).dt.date.astype("string")
    return recent_history.loc[:, HISTORICAL_DEMAND_COLUMNS].to_dict(orient="records")


def build_history_diagnostics(history: pd.DataFrame) -> dict[str, Any]:
    """Build descriptive summary and readiness checks for validated history.

    The input is expected to already satisfy the shared historical contract,
    typically via :func:`load_and_validate_history`. This helper keeps the
    summary layer separate from loader validation and only reports diagnostics.
    """

    if tuple(history.columns) != HISTORICAL_DEMAND_COLUMNS:
        raise FieldValidationError(
            "history must use the canonical historical-demand columns"
        )

    week_starts = pd.to_datetime(history["week_start"], errors="raise").dt.normalize()
    category_summary = {
        category: _summarize_numeric_history_column(history[category])
        for category in RESERVATION_CATEGORIES
    }

    return {
        "week_count": int(len(history)),
        "date_range": {
            "start": week_starts.min().date().isoformat(),
            "end": week_starts.max().date().isoformat(),
        },
        "category_summary": category_summary,
        "staffing_summary": _summarize_numeric_history_column(
            history["staffing_agents"]
        ),
        "recent_four_week_extract": _recent_four_week_extract(history),
        "quality_checks": _history_quality_checks(history),
    }


def load_and_validate_history(path: str | Path) -> pd.DataFrame:
    """Load a historical-demand CSV and return a validated DataFrame."""

    csv_path = Path(path)
    try:
        history = pd.read_csv(csv_path)
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise ValueError(f"unable to read historical data from {csv_path}") from exc

    _ensure_required_columns(history)
    normalized = _normalize_weeks(history)
    normalized = _normalize_demands_and_staffing(normalized)
    return normalized


__all__ = [
    "MINIMUM_FORECAST_HISTORY_WEEKS",
    "build_history_diagnostics",
    "load_and_validate_history",
]
