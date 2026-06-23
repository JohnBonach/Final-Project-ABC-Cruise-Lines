"""Seeded synthetic historical-demand generation for ABC Cruise Lines."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.generate_synthetic_data import get_synthetic_history_spec
from src.constants import HISTORICAL_DEMAND_COLUMNS, RESERVATION_CATEGORIES
from src.models import CategoryAssumptions, SimulationConfiguration, WorkforceAssumptions
from src.operations.capacity import (
    calculate_productive_hours_per_agent,
    calculate_required_fte,
)
from src.operations.workload import calculate_workload_hours
from src.validation import (
    create_numpy_generator,
    load_defaults_config,
    validate_non_negative_integer,
    validate_positive_integer,
)

DEFAULTS_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "defaults.json"
DEFAULT_HISTORY_SEED = 510


def _round_half_up(value: float) -> int:
    """Round a finite value to the nearest integer with ties away from zero."""

    if value >= 0:
        return int(math.floor(value + 0.5))
    return int(math.ceil(value - 0.5))


def _coerce_defaults_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """Return validated defaults configuration from a supplied payload or disk."""

    if config is None:
        return load_defaults_config(DEFAULTS_CONFIG_PATH)
    if "simulation_configuration" not in config:
        raise ValueError(
            "config must be a validated defaults payload containing "
            "'simulation_configuration'"
        )
    return config


def _resolve_history_seed(
    config: dict[str, Any],
    seed: int | str | None,
    spec: dict[str, Any],
) -> int | None:
    """Resolve the synthetic-history seed using the Task 1.1 precedence rules."""

    if seed is not None:
        return seed

    simulation_configuration = config["simulation_configuration"]
    config_seed = (
        simulation_configuration.random_seed
        if isinstance(simulation_configuration, SimulationConfiguration)
        else simulation_configuration["random_seed"]
    )
    if config_seed is not None:
        return config_seed

    return int(spec["random_seed_contract"]["default_value"])


def _resolve_category_assumptions(
    config: dict[str, Any],
) -> dict[str, CategoryAssumptions]:
    """Return category assumptions keyed by canonical category."""

    payload = config["category_assumptions"]
    assumptions = (
        payload
        if payload and isinstance(payload[0], CategoryAssumptions)
        else tuple(CategoryAssumptions.from_dict(item) for item in payload)
    )
    return {
        assumption.category: assumption
        for assumption in assumptions
    }


def _resolve_workforce_assumptions(config: dict[str, Any]) -> WorkforceAssumptions:
    """Return workforce assumptions from a validated or raw defaults payload."""

    payload = config["workforce_assumptions"]
    if isinstance(payload, WorkforceAssumptions):
        return payload
    return WorkforceAssumptions.from_dict(payload)


def _resolve_week_starts(spec: dict[str, Any], weeks: int) -> list[pd.Timestamp]:
    """Build the contiguous Monday week-start series from the Task 1.1 spec."""

    history_window = spec["history_window"]
    date_rule = history_window["date_rule"]

    minimum_weeks = validate_positive_integer("weeks_min", history_window["weeks_min"])
    maximum_weeks = validate_positive_integer("weeks_max", history_window["weeks_max"])
    observed_weeks = validate_positive_integer("weeks", weeks)
    if observed_weeks < minimum_weeks or observed_weeks > maximum_weeks:
        raise ValueError(
            f"weeks must be between {minimum_weeks} and {maximum_weeks} inclusive"
        )

    default_start = pd.Timestamp(date_rule["default_start_week"])
    weekly_dates = pd.date_range(
        start=default_start,
        periods=observed_weeks,
        freq=history_window["week_frequency"],
    )
    return list(weekly_dates)


def _resolve_history_weeks(spec: dict[str, Any]) -> int:
    """Return the default number of historical weeks from the Task 1.1 spec."""

    return validate_positive_integer(
        "default_weeks",
        spec["history_window"]["default_weeks"],
    )


def _sample_category_demand(
    category_rule: dict[str, Any],
    shared_week_shock: float,
    high_demand_week: bool,
    generator: Any,
) -> int:
    """Generate one week's demand for a category using the Task 1.1 rule order."""

    mean = float(category_rule["baseline_mean_reservations"])
    std = float(category_rule["week_to_week_std_reservations"])
    minimum = float(category_rule["minimum_reservations"])
    maximum = float(category_rule["maximum_reservations"])

    pre_bounds_demand = mean + float(generator.normal(0.0, std))

    sensitivity_by_category = {
        "simple": 1.0,
        "standard": 0.9,
        "complex_group": 1.05,
        "change_cancellation": 0.45,
    }
    sensitivity = sensitivity_by_category[category_rule["category"]]
    adjusted_demand = pre_bounds_demand * (1.0 + (shared_week_shock * sensitivity))

    if high_demand_week:
        uplift_low, uplift_high = category_rule["uplift_range"]
        adjusted_demand *= float(generator.uniform(uplift_low, uplift_high))

    bounded_demand = min(max(adjusted_demand, minimum), maximum)
    rounded_demand = _round_half_up(bounded_demand)
    return max(0, rounded_demand)


def _build_category_rules(spec: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return category rules augmented with their high-demand uplift ranges."""

    demand_model = spec["demand_model"]
    uplift_ranges = demand_model["high_demand_week"]["uplift_ranges"]

    category_rules: list[dict[str, Any]] = []
    for rule in demand_model["category_rules"]:
        normalized_rule = dict(rule)
        normalized_rule["uplift_range"] = tuple(uplift_ranges[rule["category"]])
        category_rules.append(normalized_rule)
    return tuple(category_rules)


def _calculate_staffing_agents(
    demand_by_category: dict[str, int],
    category_assumptions: dict[str, CategoryAssumptions],
    workforce_assumptions: WorkforceAssumptions,
    prior_week_staffing: int | None,
    staffing_band: tuple[int, int],
) -> int:
    """Convert weekly demand into lagged whole-agent staffing history."""

    handling_times = {
        category: category_assumptions[category].handling_time_minutes
        for category in RESERVATION_CATEGORIES
    }
    workload_hours = calculate_workload_hours(demand_by_category, handling_times)
    productive_hours_per_agent = calculate_productive_hours_per_agent(
        workforce_assumptions.paid_hours_per_agent,
        workforce_assumptions.productive_processing_pct,
    )
    implied_fte = calculate_required_fte(workload_hours, productive_hours_per_agent)
    rounded_target_agents = _round_half_up(implied_fte)

    minimum_staffing, maximum_staffing = staffing_band
    if prior_week_staffing is None:
        return min(max(rounded_target_agents, minimum_staffing), maximum_staffing)

    if rounded_target_agents > prior_week_staffing + 1:
        current_staffing = prior_week_staffing + 1
    elif rounded_target_agents < prior_week_staffing - 1:
        current_staffing = prior_week_staffing - 1
    else:
        current_staffing = rounded_target_agents

    return min(max(current_staffing, minimum_staffing), maximum_staffing)


def _validate_output_frame(history: pd.DataFrame, expected_weeks: int) -> pd.DataFrame:
    """Validate the generated DataFrame against the shared historical contract."""

    if tuple(history.columns) != HISTORICAL_DEMAND_COLUMNS:
        raise ValueError(
            "generated history columns must match the shared contract exactly"
        )
    if len(history) != expected_weeks:
        raise ValueError("generated history row count does not match requested weeks")

    validate_non_negative_integer("generated_history_rows", len(history))

    for category in RESERVATION_CATEGORIES:
        if not pd.api.types.is_integer_dtype(history[category]):
            raise ValueError(f"{category} must contain integer weekly demand")
        if (history[category] < 0).any():
            raise ValueError(f"{category} must contain non-negative weekly demand")

    if not pd.api.types.is_integer_dtype(history["staffing_agents"]):
        raise ValueError("staffing_agents must contain integer values")
    if (history["staffing_agents"] < 0).any():
        raise ValueError("staffing_agents must contain non-negative values")

    return history


def generate_synthetic_history(
    config: dict[str, Any] | None = None,
    seed: int | str | None = None,
) -> pd.DataFrame:
    """Generate deterministic weekly historical demand from the Task 1.1 spec."""

    resolved_config = _coerce_defaults_config(config)
    spec = get_synthetic_history_spec()
    resolved_seed = _resolve_history_seed(resolved_config, seed, spec)
    generator = create_numpy_generator(resolved_seed)

    category_assumptions = _resolve_category_assumptions(resolved_config)
    workforce_assumptions = _resolve_workforce_assumptions(resolved_config)
    category_rules = _build_category_rules(spec)

    history_window = spec["history_window"]
    weeks = _resolve_history_weeks(spec)
    week_starts = _resolve_week_starts(spec, weeks)

    high_demand_probability = float(
        spec["demand_model"]["high_demand_week"]["approx_probability_per_week"]
    )
    minimum_staffing, maximum_staffing = (
        int(value)
        for value in spec["staffing_history_rule"][
            "target_previous_week_staffing_range"
        ]
    )

    rows: list[dict[str, object]] = []
    prior_week_staffing: int | None = None
    for week_start in week_starts:
        shared_week_shock = float(generator.normal(0.0, 0.07))
        high_demand_week = bool(generator.random() < high_demand_probability)

        demand_by_category = {
            rule["category"]: _sample_category_demand(
                rule,
                shared_week_shock,
                high_demand_week,
                generator,
            )
            for rule in category_rules
        }

        staffing_agents = _calculate_staffing_agents(
            demand_by_category,
            category_assumptions,
            workforce_assumptions,
            prior_week_staffing,
            (minimum_staffing, maximum_staffing),
        )
        prior_week_staffing = staffing_agents

        iso_year, iso_week, _ = week_start.isocalendar()
        row: dict[str, object] = {
            "week_id": f"{iso_year}-W{iso_week:02d}",
            "week_start": week_start.date().isoformat(),
            **demand_by_category,
            "staffing_agents": staffing_agents,
        }
        rows.append(row)

    history = pd.DataFrame(rows, columns=HISTORICAL_DEMAND_COLUMNS)
    integer_columns = list(RESERVATION_CATEGORIES) + ["staffing_agents"]
    history[integer_columns] = history[integer_columns].astype("int64")
    history["week_start"] = history["week_start"].astype("string")

    return _validate_output_frame(history, validate_positive_integer("weeks", weeks))


__all__ = [
    "DEFAULTS_CONFIG_PATH",
    "DEFAULT_HISTORY_SEED",
    "generate_synthetic_history",
]
