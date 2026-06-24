"""Typed shared contracts for the ABC Cruise Lines DSS."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, ClassVar

from src.constants import (
    CONFIDENCE_TARGET_FIELDS,
    DECISION_POLICY_FIELDS,
    FORECAST_SOURCES,
    RESERVATION_CATEGORIES,
    SIMULATION_SUPPORTED_DISTRIBUTIONS,
    STRATEGIC_ASSUMPTION_FIELDS,
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


def _validate_boolean(name: str, value: bool) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _validate_non_empty_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _dataclass_field_names(model_type: type[Any]) -> tuple[str, ...]:
    return tuple(field.name for field in fields(model_type))


def _validate_category_metric_map(
    name: str,
    values: dict[str, float],
) -> dict[str, float]:
    if not isinstance(values, dict):
        raise ValueError(f"{name} must be a dictionary keyed by category")
    if tuple(values.keys()) != RESERVATION_CATEGORIES:
        raise ValueError(
            f"{name} must include each canonical category exactly once and in the shared order "
            f"{RESERVATION_CATEGORIES}"
        )
    return {
        category: _validate_non_negative(f"{name}.{category}", values[category])
        for category in RESERVATION_CATEGORIES
    }


@dataclass(frozen=True, slots=True)
class CategoryAssumptions:
    """Shared category-level operational assumptions."""

    category: str
    handling_time_minutes: float
    average_booking_value: float

    _FIELD_NAMES: ClassVar[tuple[str, ...]]

    def __post_init__(self) -> None:
        _validate_category(self.category)
        _validate_positive("handling_time_minutes", self.handling_time_minutes)
        _validate_non_negative("average_booking_value", self.average_booking_value)

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
    weekly_booking_processing_hours_per_agent: float
    regular_hourly_wage: float
    minimum_schedulable_agents: int
    maximum_inhouse_agents: int
    planned_staffing_agents: int

    _FIELD_NAMES: ClassVar[tuple[str, ...]]

    def __post_init__(self) -> None:
        _validate_positive("paid_hours_per_agent", self.paid_hours_per_agent)
        _validate_positive(
            "weekly_booking_processing_hours_per_agent",
            self.weekly_booking_processing_hours_per_agent,
        )
        if self.weekly_booking_processing_hours_per_agent > self.paid_hours_per_agent:
            raise ValueError(
                "weekly_booking_processing_hours_per_agent must not exceed paid_hours_per_agent"
            )
        _validate_non_negative("regular_hourly_wage", self.regular_hourly_wage)
        if self.minimum_schedulable_agents < 0:
            raise ValueError("minimum_schedulable_agents must be non-negative")
        if self.maximum_inhouse_agents < self.minimum_schedulable_agents:
            raise ValueError(
                "maximum_inhouse_agents must be greater than or equal to minimum_schedulable_agents"
            )
        if self.planned_staffing_agents < 0:
            raise ValueError("planned_staffing_agents must be non-negative")

    @property
    def direct_booking_share(self) -> float:
        """Return the share of paid time available for direct booking processing."""

        return (
            self.weekly_booking_processing_hours_per_agent
            / self.paid_hours_per_agent
        )

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
class StrategicAssumptions:
    """Shared strategic business-case assumptions kept separate from weekly staffing."""

    third_party_commission_rate: float

    _FIELD_NAMES: ClassVar[tuple[str, ...]]

    def __post_init__(self) -> None:
        _validate_decimal("third_party_commission_rate", self.third_party_commission_rate)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary using the canonical contract field names."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StrategicAssumptions":
        """Build the model from a dictionary with exact contract keys."""

        _require_exact_keys(cls.__name__, data, STRATEGIC_ASSUMPTION_FIELDS)
        return cls(**data)


StrategicAssumptions._FIELD_NAMES = _dataclass_field_names(StrategicAssumptions)


@dataclass(frozen=True, slots=True)
class DecisionPolicy:
    """Shared decision-policy inputs for recommendation selection."""

    minimum_inhouse_coverage_target: float

    _FIELD_NAMES: ClassVar[tuple[str, ...]]

    def __post_init__(self) -> None:
        _validate_decimal(
            "minimum_inhouse_coverage_target",
            self.minimum_inhouse_coverage_target,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary using the canonical contract field names."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DecisionPolicy":
        """Build the model from a dictionary with exact contract keys."""

        _require_exact_keys(cls.__name__, data, DECISION_POLICY_FIELDS)
        return cls(**data)


DecisionPolicy._FIELD_NAMES = _dataclass_field_names(DecisionPolicy)


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


@dataclass(frozen=True, slots=True)
class RepresentativeDemandOutlook:
    """Structured representative Monte Carlo outlook for one planning percentile."""

    outlook_name: str
    percentile: float
    percentile_label: str
    simulation_row_id: int
    representative_row_reused: bool
    demand_by_category: dict[str, float]
    total_bookings: float
    workload_hours_by_category: dict[str, float]
    total_workload_hours: float
    raw_required_fte: float
    unconstrained_required_agents: int
    recommended_inhouse_agents_for_outlook: int
    spare_capacity_hours: float
    overflow_workload_hours: float
    overflow_bookings_by_category: dict[str, float]
    regular_labor_cost: float
    overflow_commission: float
    total_weekly_operating_cost: float

    def __post_init__(self) -> None:
        _validate_non_empty_text("outlook_name", self.outlook_name)
        _validate_decimal("percentile", self.percentile)
        _validate_non_empty_text("percentile_label", self.percentile_label)
        if self.simulation_row_id <= 0:
            raise ValueError("simulation_row_id must be greater than 0")
        _validate_boolean("representative_row_reused", self.representative_row_reused)
        _validate_category_metric_map("demand_by_category", self.demand_by_category)
        _validate_non_negative("total_bookings", self.total_bookings)
        _validate_category_metric_map(
            "workload_hours_by_category",
            self.workload_hours_by_category,
        )
        _validate_non_negative("total_workload_hours", self.total_workload_hours)
        _validate_non_negative("raw_required_fte", self.raw_required_fte)
        if self.unconstrained_required_agents < 0:
            raise ValueError("unconstrained_required_agents must be non-negative")
        if self.recommended_inhouse_agents_for_outlook < 0:
            raise ValueError("recommended_inhouse_agents_for_outlook must be non-negative")
        _validate_non_negative("spare_capacity_hours", self.spare_capacity_hours)
        _validate_non_negative("overflow_workload_hours", self.overflow_workload_hours)
        _validate_category_metric_map(
            "overflow_bookings_by_category",
            self.overflow_bookings_by_category,
        )
        _validate_non_negative("regular_labor_cost", self.regular_labor_cost)
        _validate_non_negative("overflow_commission", self.overflow_commission)
        _validate_non_negative(
            "total_weekly_operating_cost",
            self.total_weekly_operating_cost,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary using the shared outlook field names."""

        return asdict(self)


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
