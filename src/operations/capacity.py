"""Deterministic productive-capacity and FTE calculations."""

from __future__ import annotations

import math

from src.validation import validate_non_negative, validate_percentage, validate_positive


def calculate_productive_hours_per_agent(
    paid_hours: float,
    productive_processing_pct: float,
) -> float:
    """Return productive weekly hours available from one agent."""

    normalized_paid_hours = validate_positive("paid_hours", paid_hours)
    normalized_productive_pct = validate_percentage(
        "productive_processing_pct",
        productive_processing_pct,
    )

    productive_hours = normalized_paid_hours * normalized_productive_pct
    if productive_hours <= 0.0:
        raise ValueError(
            "productive hours per agent must be greater than 0; "
            "check paid_hours and productive_processing_pct"
        )
    return productive_hours


def calculate_required_fte(
    workload_hours: float,
    productive_hours_per_agent: float,
) -> float:
    """Return the decimal FTE required to cover a weekly workload."""

    normalized_workload_hours = validate_non_negative("workload_hours", workload_hours)
    normalized_productive_hours = validate_positive(
        "productive_hours_per_agent",
        productive_hours_per_agent,
    )
    return normalized_workload_hours / normalized_productive_hours


def calculate_required_agents(required_fte: float) -> int:
    """Return the whole-agent requirement using upward rounding."""

    normalized_required_fte = validate_non_negative("required_fte", required_fte)
    return math.ceil(normalized_required_fte)


__all__ = [
    "calculate_productive_hours_per_agent",
    "calculate_required_agents",
    "calculate_required_fte",
]
