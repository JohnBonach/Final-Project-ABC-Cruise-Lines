"""Monte Carlo demand sampling for weekly reservation forecasts."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.constants import (
    FORECAST_RESULT_COLUMNS,
    RESERVATION_CATEGORIES,
    SIMULATION_OUTPUT_COLUMNS,
    SIMULATION_SUPPORTED_DISTRIBUTIONS,
)
from src.validation import (
    FieldValidationError,
    create_numpy_generator,
    validate_positive_integer,
)

SUPPORTED_DISTRIBUTIONS = SIMULATION_SUPPORTED_DISTRIBUTIONS


def _validate_forecast_result(forecast_result: pd.DataFrame) -> pd.DataFrame:
    """Validate the canonical forecast-result table and return it in shared order."""

    if not isinstance(forecast_result, pd.DataFrame):
        raise FieldValidationError("forecast_result must be a pandas DataFrame")

    missing_columns = [column for column in FORECAST_RESULT_COLUMNS if column not in forecast_result.columns]
    unexpected_columns = [column for column in forecast_result.columns if column not in FORECAST_RESULT_COLUMNS]
    if missing_columns or unexpected_columns:
        problems: list[str] = []
        if missing_columns:
            problems.append(f"missing columns: {missing_columns}")
        if unexpected_columns:
            problems.append(f"unexpected columns: {unexpected_columns}")
        raise FieldValidationError(
            "forecast_result must match the shared forecast-result contract exactly "
            f"({', '.join(problems)})"
        )

    duplicate_categories = forecast_result["category"][forecast_result["category"].duplicated()].tolist()
    if duplicate_categories:
        raise FieldValidationError(
            "forecast_result must include each canonical category exactly once "
            f"; duplicates found: {duplicate_categories}"
        )

    ordered = forecast_result.set_index("category").reindex(RESERVATION_CATEGORIES)
    if ordered.isnull().any().any():
        missing_categories = [
            category
            for category in RESERVATION_CATEGORIES
            if category not in forecast_result["category"].tolist()
        ]
        raise FieldValidationError(
            "forecast_result must include each canonical category exactly once "
            f"and in the shared order {RESERVATION_CATEGORIES}; missing {missing_categories}"
        )

    return ordered.reset_index()


def _sample_normal_demand(
    means: np.ndarray,
    standard_deviations: np.ndarray,
    iterations: int,
    generator: np.random.Generator,
) -> np.ndarray:
    """Draw independent normal samples for each reservation category."""

    raw_samples = generator.normal(
        loc=means,
        scale=standard_deviations,
        size=(iterations, len(means)),
    )
    non_negative = np.clip(raw_samples, a_min=0.0, a_max=None)
    rounded = np.rint(non_negative)
    return rounded.astype(int)


def simulate_weekly_demand(
    forecast_result: pd.DataFrame,
    iterations: int,
    seed: int | str | None = None,
    distribution_name: str = "normal",
) -> pd.DataFrame:
    """Generate one weekly demand draw per iteration for each canonical category."""

    normalized_iterations = validate_positive_integer("iterations", iterations)

    if not isinstance(distribution_name, str) or not distribution_name:
        raise FieldValidationError("distribution_name must be a non-empty string")
    normalized_distribution = distribution_name.strip().lower()
    if normalized_distribution not in SUPPORTED_DISTRIBUTIONS:
        raise ValueError(
            f"distribution_name must be one of {SUPPORTED_DISTRIBUTIONS}"
        )

    ordered_forecast = _validate_forecast_result(forecast_result)
    means = ordered_forecast["point_forecast"].astype(float).to_numpy()
    standard_deviations = ordered_forecast["adjusted_std"].astype(float).to_numpy()

    if (standard_deviations < 0).any():
        raise FieldValidationError("adjusted_std must be non-negative for all categories")
    if not np.isfinite(means).all():
        raise FieldValidationError("point_forecast must contain only finite values")
    if not np.isfinite(standard_deviations).all():
        raise FieldValidationError("adjusted_std must contain only finite values")

    generator = create_numpy_generator(seed)
    if normalized_distribution == "normal":
        samples = _sample_normal_demand(
            means,
            standard_deviations,
            normalized_iterations,
            generator,
        )
    else:  # pragma: no cover - guarded by supported-distribution validation
        raise ValueError(f"unsupported distribution_name {distribution_name!r}")

    output = pd.DataFrame(samples, columns=RESERVATION_CATEGORIES)
    output.insert(0, "simulation_id", np.arange(1, normalized_iterations + 1, dtype=int))
    return output.loc[:, SIMULATION_OUTPUT_COLUMNS]


__all__ = [
    "SIMULATION_OUTPUT_COLUMNS",
    "SUPPORTED_DISTRIBUTIONS",
    "simulate_weekly_demand",
]
