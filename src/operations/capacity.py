"""Deterministic in-house capacity and staffing calculations."""

from __future__ import annotations

import math

from src.validation import (
    validate_non_negative,
    validate_non_negative_integer,
    validate_positive,
)


def calculate_booking_processing_hours_per_agent(
    weekly_booking_processing_hours_per_agent: float,
) -> float:
    """Return validated direct booking-processing hours per agent."""

    return validate_positive(
        "weekly_booking_processing_hours_per_agent",
        weekly_booking_processing_hours_per_agent,
    )


def calculate_required_fte(
    workload_hours: float,
    booking_processing_hours_per_agent: float,
) -> float:
    """Return the decimal FTE required to cover a weekly workload."""

    normalized_workload_hours = validate_non_negative("workload_hours", workload_hours)
    normalized_capacity = validate_positive(
        "booking_processing_hours_per_agent",
        booking_processing_hours_per_agent,
    )
    return normalized_workload_hours / normalized_capacity


def calculate_required_agents(required_fte: float) -> int:
    """Return the unconstrained whole-agent requirement using upward rounding."""

    normalized_required_fte = validate_non_negative("required_fte", required_fte)
    return math.ceil(normalized_required_fte)


def clamp_inhouse_staffing(
    unconstrained_required_agents: int,
    minimum_schedulable_agents: int,
    maximum_inhouse_agents: int,
) -> int:
    """Apply the approved operating floor and in-house cap."""

    normalized_unconstrained = validate_non_negative_integer(
        "unconstrained_required_agents",
        unconstrained_required_agents,
    )
    minimum_staffing = validate_non_negative_integer(
        "minimum_schedulable_agents",
        minimum_schedulable_agents,
    )
    maximum_staffing = validate_non_negative_integer(
        "maximum_inhouse_agents",
        maximum_inhouse_agents,
    )
    if maximum_staffing < minimum_staffing:
        raise ValueError(
            "maximum_inhouse_agents must be greater than or equal to minimum_schedulable_agents"
        )
    return min(max(normalized_unconstrained, minimum_staffing), maximum_staffing)


def calculate_capacity_hours(
    staffing_agents: int,
    booking_processing_hours_per_agent: float,
) -> float:
    """Return total weekly booking-processing capacity hours for a staffing level."""

    normalized_staffing_agents = validate_non_negative_integer(
        "staffing_agents",
        staffing_agents,
    )
    normalized_capacity = calculate_booking_processing_hours_per_agent(
        booking_processing_hours_per_agent
    )
    return normalized_staffing_agents * normalized_capacity


__all__ = [
    "calculate_booking_processing_hours_per_agent",
    "calculate_capacity_hours",
    "calculate_required_agents",
    "calculate_required_fte",
    "clamp_inhouse_staffing",
]
