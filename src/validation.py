"""Reusable validation and reproducibility utilities for shared modules."""

from __future__ import annotations

import json
from numbers import Integral, Real
from pathlib import Path
from typing import Any
from typing import TypeAlias

import numpy as np

from src.constants import RESERVATION_CATEGORIES
from src.models import (
    CategoryAssumptions,
    ConfidenceTargets,
    DecisionPolicy,
    ForecastConfiguration,
    SimulationConfiguration,
    StrategicAssumptions,
    WorkforceAssumptions,
)

NumberLike: TypeAlias = int | float

DEFAULT_WEIGHT_SUM_TOLERANCE = 1e-9
MAX_NUMPY_SEED = 2**32 - 1
DEFAULTS_TOP_LEVEL_FIELDS = (
    "schema_version",
    "category_assumptions",
    "workforce_assumptions",
    "decision_policy",
    "forecast_configuration",
    "simulation_configuration",
    "confidence_targets",
    "strategic_assumptions",
)

class ValidationError(ValueError):
    """Base class for deterministic validation failures."""


class FieldValidationError(ValidationError):
    """Raised when a named field violates a shared input rule."""


class InsufficientHistoryError(ValidationError):
    """Raised when historical data does not contain enough weekly observations."""


class RandomSeedValidationError(ValidationError):
    """Raised when a random-seed value cannot be normalized safely."""


def _require_real_number(field_name: str, value: NumberLike) -> float:
    """Return a finite float after validating that the value is numeric."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise FieldValidationError(f"{field_name} must be a real number")

    normalized = float(value)
    if not np.isfinite(normalized):
        raise FieldValidationError(f"{field_name} must be finite")
    return normalized


def validate_percentage(
    field_name: str,
    value: NumberLike,
    *,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    """Validate that a percentage-like value is represented as an internal decimal."""

    normalized = _require_real_number(field_name, value)
    if normalized < minimum or normalized > maximum:
        raise FieldValidationError(
            f"{field_name} must be between {minimum} and {maximum} inclusive"
        )
    return normalized


def validate_non_negative(
    field_name: str,
    value: NumberLike,
) -> float:
    """Validate that a numeric field is finite and non-negative."""

    normalized = _require_real_number(field_name, value)
    if normalized < 0.0:
        raise FieldValidationError(f"{field_name} must be non-negative")
    return normalized


def validate_positive(
    field_name: str,
    value: NumberLike,
) -> float:
    """Validate that a numeric field is finite and strictly positive."""

    normalized = _require_real_number(field_name, value)
    if normalized <= 0.0:
        raise FieldValidationError(f"{field_name} must be greater than 0")
    return normalized


def validate_non_negative_integer(
    field_name: str,
    value: int,
) -> int:
    """Validate that an integer field is not negative."""

    if isinstance(value, bool) or not isinstance(value, Integral):
        raise FieldValidationError(f"{field_name} must be an integer")

    normalized = int(value)
    if normalized < 0:
        raise FieldValidationError(f"{field_name} must be non-negative")
    return normalized


def validate_positive_integer(
    field_name: str,
    value: int,
) -> int:
    """Validate that an integer field is greater than zero."""

    if isinstance(value, bool) or not isinstance(value, Integral):
        raise FieldValidationError(f"{field_name} must be an integer")

    normalized = int(value)
    if normalized <= 0:
        raise FieldValidationError(f"{field_name} must be greater than 0")
    return normalized


def validate_weights(
    weights: list[NumberLike] | tuple[NumberLike, ...],
    *,
    expected_count: int | None = None,
    tolerance: float = DEFAULT_WEIGHT_SUM_TOLERANCE,
    field_name: str = "weights",
) -> tuple[float, ...]:
    """Validate weighted-average inputs and return a normalized immutable tuple."""

    if expected_count is not None and expected_count <= 0:
        raise FieldValidationError("expected_count must be greater than 0")
    if tolerance < 0.0:
        raise FieldValidationError("tolerance must be non-negative")

    normalized = tuple(validate_percentage(field_name, weight) for weight in weights)
    if not normalized:
        raise FieldValidationError(f"{field_name} must contain at least one value")
    if expected_count is not None and len(normalized) != expected_count:
        raise FieldValidationError(
            f"{field_name} must contain exactly {expected_count} values"
        )

    if abs(sum(normalized) - 1.0) > tolerance:
        raise FieldValidationError(
            f"{field_name} must sum to 1.0 within tolerance {tolerance}"
        )
    return normalized


def validate_required_history_weeks(
    observed_weeks: int,
    required_weeks: int,
    *,
    field_name: str = "history",
) -> int:
    """Validate that enough historical weekly observations are available."""

    observed = validate_non_negative_integer("observed_weeks", observed_weeks)
    required = validate_positive_integer("required_weeks", required_weeks)

    if observed < required:
        raise InsufficientHistoryError(
            f"{field_name} must contain at least {required} historical weeks; "
            f"received {observed}"
        )
    return observed


def normalize_random_seed(seed: int | str | None) -> int | None:
    """Normalize an optional random seed into the NumPy-compatible unsigned range."""

    if seed is None:
        return None
    if isinstance(seed, bool):
        raise RandomSeedValidationError("random_seed must be an integer or None")

    candidate = seed
    if isinstance(seed, str):
        candidate = seed.strip()
        if not candidate:
            return None
        try:
            candidate = int(candidate)
        except ValueError as exc:
            raise RandomSeedValidationError(
                "random_seed must be an integer string, integer, or None"
            ) from exc

    if not isinstance(candidate, Integral):
        raise RandomSeedValidationError("random_seed must be an integer or None")

    normalized = int(candidate)
    if normalized < 0 or normalized > MAX_NUMPY_SEED:
        raise RandomSeedValidationError(
            f"random_seed must be between 0 and {MAX_NUMPY_SEED} inclusive"
        )
    return normalized


def create_numpy_generator(seed: int | str | None) -> np.random.Generator:
    """Create a reproducible NumPy random generator using normalized seed rules."""

    return np.random.default_rng(normalize_random_seed(seed))


def _load_json_file(path: str | Path) -> dict[str, Any]:
    """Load a configuration JSON file and require an object at the top level."""

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)

    if not isinstance(payload, dict):
        raise FieldValidationError(
            f"configuration at {config_path} must contain a top-level JSON object"
        )
    return payload


def _require_exact_keys(
    name: str,
    payload: dict[str, Any],
    expected_keys: tuple[str, ...],
) -> None:
    """Validate that a configuration object contains exactly the expected keys."""

    actual_keys = set(payload)
    expected_key_set = set(expected_keys)
    if actual_keys != expected_key_set:
        missing = sorted(expected_key_set - actual_keys)
        unexpected = sorted(actual_keys - expected_key_set)
        problems: list[str] = []
        if missing:
            problems.append(f"missing keys: {missing}")
        if unexpected:
            problems.append(f"unexpected keys: {unexpected}")
        details = ", ".join(problems)
        raise FieldValidationError(
            f"{name} must match the expected configuration schema exactly ({details})"
        )


def validate_defaults_config(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize the default business and simulation configuration."""

    _require_exact_keys("defaults configuration", payload, DEFAULTS_TOP_LEVEL_FIELDS)

    category_payload = payload["category_assumptions"]
    if not isinstance(category_payload, list):
        raise FieldValidationError("category_assumptions must be a list")

    category_assumptions = tuple(
        CategoryAssumptions.from_dict(item) for item in category_payload
    )
    if len(category_assumptions) != len(RESERVATION_CATEGORIES):
        raise FieldValidationError(
            "category_assumptions must contain exactly one entry for each canonical category"
        )

    categories = tuple(item.category for item in category_assumptions)
    if categories != RESERVATION_CATEGORIES:
        raise FieldValidationError(
            "category_assumptions must include each canonical category exactly once "
            "and in the shared order"
        )

    workforce_assumptions = WorkforceAssumptions.from_dict(
        payload["workforce_assumptions"]
    )
    decision_policy = DecisionPolicy.from_dict(payload["decision_policy"])
    forecast_configuration = ForecastConfiguration.from_dict(
        payload["forecast_configuration"]
    )
    simulation_payload = dict(payload["simulation_configuration"])
    try:
        simulation_payload["random_seed"] = normalize_random_seed(
            simulation_payload["random_seed"]
        )
    except RandomSeedValidationError as exc:
        raise FieldValidationError(f"simulation_configuration.{exc}") from exc
    simulation_configuration = SimulationConfiguration.from_dict(simulation_payload)
    confidence_targets = ConfidenceTargets.from_dict(payload["confidence_targets"])
    strategic_assumptions = StrategicAssumptions.from_dict(
        payload["strategic_assumptions"]
    )

    if (
        simulation_configuration.variability_multiplier
        != forecast_configuration.variability_multiplier
    ):
        raise FieldValidationError(
            "simulation_configuration.variability_multiplier must match "
            "forecast_configuration.variability_multiplier"
        )

    if not (
        confidence_targets.lean
        <= confidence_targets.balanced
        <= confidence_targets.conservative
    ):
        raise FieldValidationError(
            "confidence_targets must be ordered lean <= balanced <= conservative"
        )

    return {
        "schema_version": payload["schema_version"],
        "category_assumptions": category_assumptions,
        "workforce_assumptions": workforce_assumptions,
        "decision_policy": decision_policy,
        "forecast_configuration": forecast_configuration,
        "simulation_configuration": simulation_configuration,
        "confidence_targets": confidence_targets,
        "strategic_assumptions": strategic_assumptions,
    }


def load_defaults_config(path: str | Path) -> dict[str, Any]:
    """Load, validate, and normalize the default configuration file."""

    return validate_defaults_config(_load_json_file(path))


__all__ = [
    "DEFAULT_WEIGHT_SUM_TOLERANCE",
    "MAX_NUMPY_SEED",
    "FieldValidationError",
    "InsufficientHistoryError",
    "RandomSeedValidationError",
    "ValidationError",
    "create_numpy_generator",
    "load_defaults_config",
    "normalize_random_seed",
    "validate_defaults_config",
    "validate_non_negative",
    "validate_non_negative_integer",
    "validate_percentage",
    "validate_positive",
    "validate_positive_integer",
    "validate_required_history_weeks",
    "validate_weights",
]
