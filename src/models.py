"""Typed shared contracts for the ABC Cruise Lines DSS."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, ClassVar

from src.constants import (
    CONFIDENCE_TARGET_FIELDS,
    FORECAST_SOURCES,
    RESERVATION_CATEGORIES,
    SIMULATION_SUPPORTED_DISTRIBUTIONS,
)


def _require_exact_keys(model_name: str, data: dict[str, Any], expected_keys: tuple[str, ...]) -> None:
    actual_keys = set(data)
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
        raise ValueError(f"{model_name} fields must match the shared contract exactly ({details})")


def _validate_category(category: str) -> str:
    if category not in RESERVATION_CATEGORIES:
        raise ValueError(
            f"category must be one of {RESERVATION_CATEGORIES}; received {category!r}"
        )
    return category


def _validate_non_negative(name: str, value: float) -> float:
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _validate_positive(name: str, value: float) -> float:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return value


def _validate_decimal(name: str, value: float) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be represented internally as a decimal between 0.0 and 1.0")
    return value


def _dataclass_field_names(model_type: type[Any]) -> tuple[str, ...]:
    return tuple(field.name for field in fields(model_type))


@dataclass(frozen=True, slots=True)
class CategoryAssumptions:
    """Shared category-level operational and economic assumptions."""

    category: str
    handling_time_minutes: float
    average_revenue: float
    contribution_per_reservation: float

    _FIELD_NAMES: ClassVar[tuple[str, ...]]

    def __post_init__(self) -> None:
        _validate_category(self.category)
        _validate_positive("handling_time_minutes", self.handling_time_minutes)
        _validate_non_negative("average_revenue", self.average_revenue)
        _validate_non_negative(
            "contribution_per_reservation",
            self.contribution_per_reservation,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary using the canonical contract field names."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CategoryAssumptions":
        """Build the model from a dictionary with exact contract keys."""

        _require_exact_keys(cls.__name__, data, cls._FIELD_NAMES)
        return cls(**data)


CategoryAssumptions._FIELD_NAMES = _dataclass_field_names(CategoryAssumptions)


@dataclass(frozen=True, slots=True)
class WorkforceAssumptions:
    """Shared workforce planning assumptions."""

    paid_hours_per_agent: float
    productive_processing_pct: float
    regular_hourly_wage: float
    overtime_multiplier: float
    abandonment_rate: float
    planned_staffing_agents: int

    _FIELD_NAMES: ClassVar[tuple[str, ...]]

    def __post_init__(self) -> None:
        _validate_positive("paid_hours_per_agent", self.paid_hours_per_agent)
        _validate_decimal(
            "productive_processing_pct",
            self.productive_processing_pct,
        )
        _validate_non_negative("regular_hourly_wage", self.regular_hourly_wage)
        if self.overtime_multiplier < 1.0:
            raise ValueError("overtime_multiplier must be at least 1.0")
        _validate_decimal("abandonment_rate", self.abandonment_rate)
        if self.planned_staffing_agents < 0:
            raise ValueError("planned_staffing_agents must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary using the canonical contract field names."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkforceAssumptions":
        """Build the model from a dictionary with exact contract keys."""

        _require_exact_keys(cls.__name__, data, cls._FIELD_NAMES)
        return cls(**data)


WorkforceAssumptions._FIELD_NAMES = _dataclass_field_names(WorkforceAssumptions)


@dataclass(frozen=True, slots=True)
class ForecastConfiguration:
    """Shared forecasting configuration inputs."""

    weights: tuple[float, float, float, float]
    variability_multiplier: float
    manual_overrides: dict[str, float] | None = None

    _FIELD_NAMES: ClassVar[tuple[str, ...]]

    def __post_init__(self) -> None:
        if len(self.weights) != 4:
            raise ValueError("weights must contain exactly four values")
        for weight in self.weights:
            _validate_decimal("weights", weight)
        if abs(sum(self.weights) - 1.0) > 1e-9:
            raise ValueError("weights must sum to 1.0")
        _validate_non_negative("variability_multiplier", self.variability_multiplier)
        if self.manual_overrides is not None:
            for category, demand in self.manual_overrides.items():
                _validate_category(category)
                _validate_non_negative("manual_overrides values", demand)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary using the shared configuration field names."""

        payload = asdict(self)
        payload["weights"] = list(self.weights)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ForecastConfiguration":
        """Build the model from a dictionary with exact contract keys."""

        _require_exact_keys(cls.__name__, data, cls._FIELD_NAMES)
        normalized = dict(data)
        normalized["weights"] = tuple(normalized["weights"])
        return cls(**normalized)


ForecastConfiguration._FIELD_NAMES = _dataclass_field_names(ForecastConfiguration)


@dataclass(frozen=True, slots=True)
class SimulationConfiguration:
    """Shared Monte Carlo simulation configuration."""

    iterations: int
    random_seed: int | None
    variability_multiplier: float
    distribution_name: str

    _FIELD_NAMES: ClassVar[tuple[str, ...]]

    def __post_init__(self) -> None:
        if self.iterations <= 0:
            raise ValueError("iterations must be greater than 0")
        _validate_non_negative("variability_multiplier", self.variability_multiplier)
        if not isinstance(self.distribution_name, str) or not self.distribution_name.strip():
            raise ValueError("distribution_name must be a non-empty string")
        if self.distribution_name.strip().lower() not in SIMULATION_SUPPORTED_DISTRIBUTIONS:
            raise ValueError(
                f"distribution_name must be one of {SIMULATION_SUPPORTED_DISTRIBUTIONS}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary using the canonical contract field names."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimulationConfiguration":
        """Build the model from a dictionary with exact contract keys."""

        _require_exact_keys(cls.__name__, data, cls._FIELD_NAMES)
        return cls(**data)


SimulationConfiguration._FIELD_NAMES = _dataclass_field_names(SimulationConfiguration)


@dataclass(frozen=True, slots=True)
class ConfidenceTargets:
    """Shared confidence targets for named staffing plans."""

    lean: float
    balanced: float
    conservative: float

    _FIELD_NAMES: ClassVar[tuple[str, ...]]

    def __post_init__(self) -> None:
        _validate_decimal("lean", self.lean)
        _validate_decimal("balanced", self.balanced)
        _validate_decimal("conservative", self.conservative)

    def to_dict(self) -> dict[str, float]:
        """Return a mapping suitable for downstream plan-selection modules."""

        return {
            "lean": self.lean,
            "balanced": self.balanced,
            "conservative": self.conservative,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConfidenceTargets":
        """Build the model from a dictionary with exact contract keys."""

        _require_exact_keys(cls.__name__, data, cls._FIELD_NAMES)
        return cls(**data)


ConfidenceTargets._FIELD_NAMES = _dataclass_field_names(ConfidenceTargets)


def validate_forecast_source(forecast_source: str) -> str:
    """Validate the shared forecast-source contract."""

    if forecast_source not in FORECAST_SOURCES:
        raise ValueError(f"forecast_source must be one of {FORECAST_SOURCES}")
    return forecast_source


def validate_confidence_target_name(name: str) -> str:
    """Validate the shared confidence-target mapping keys."""

    if name not in CONFIDENCE_TARGET_FIELDS:
        raise ValueError(
            f"confidence target name must be one of {CONFIDENCE_TARGET_FIELDS}"
        )
    return name
