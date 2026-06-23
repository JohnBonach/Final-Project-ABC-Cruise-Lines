"""Named staffing plan and candidate-selection helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from src.constants import CONFIDENCE_TARGET_FIELDS, NAMED_PLAN_COLUMNS
from src.models import validate_confidence_target_name
from src.validation import FieldValidationError, validate_non_negative_integer, validate_percentage

DEFAULT_CANDIDATE_LOW_PERCENTILE = 0.05
DEFAULT_CANDIDATE_HIGH_PERCENTILE = 0.95

PLAN_NAME_BY_TARGET = {
    "lean": "Lean",
    "balanced": "Balanced",
    "conservative": "Conservative",
}


def _validate_required_agents(required_agents: Sequence[int | float]) -> np.ndarray:
    """Validate and normalize a required-agent distribution."""

    if not isinstance(required_agents, Sequence) or isinstance(required_agents, (str, bytes)):
        raise FieldValidationError("required_agents must be a sequence of whole-agent values")

    normalized = np.asarray(required_agents, dtype=float)
    if normalized.size == 0:
        raise FieldValidationError("required_agents must contain at least one value")
    if not np.isfinite(normalized).all():
        raise FieldValidationError("required_agents must contain only finite values")
    if (normalized < 0).any():
        raise FieldValidationError("required_agents must be non-negative")
    if not np.allclose(normalized, np.round(normalized)):
        raise FieldValidationError("required_agents must contain whole-agent values")

    return normalized.astype(int, copy=False)


def _validate_candidate_percentile_bounds(
    candidate_low_percentile: float,
    candidate_high_percentile: float,
) -> tuple[float, float]:
    """Validate the explicit candidate-range percentile bounds."""

    normalized_low = validate_percentage(
        "candidate_low_percentile",
        candidate_low_percentile,
    )
    normalized_high = validate_percentage(
        "candidate_high_percentile",
        candidate_high_percentile,
    )
    if normalized_low > normalized_high:
        raise FieldValidationError(
            "candidate_low_percentile must be less than or equal to candidate_high_percentile"
        )
    return normalized_low, normalized_high


def _validate_confidence_targets(
    confidence_targets: Mapping[str, Any],
) -> dict[str, float]:
    """Validate confidence-target mapping and preserve canonical order."""

    if not isinstance(confidence_targets, Mapping):
        raise FieldValidationError("confidence_targets must be a mapping")

    actual_keys = tuple(confidence_targets.keys())
    if actual_keys != CONFIDENCE_TARGET_FIELDS:
        missing_keys = [key for key in CONFIDENCE_TARGET_FIELDS if key not in confidence_targets]
        unexpected_keys = [key for key in confidence_targets if key not in CONFIDENCE_TARGET_FIELDS]
        problems: list[str] = []
        if missing_keys:
            problems.append(f"missing keys: {missing_keys}")
        if unexpected_keys:
            problems.append(f"unexpected keys: {unexpected_keys}")
        raise FieldValidationError(
            "confidence_targets must include lean, balanced, and conservative in canonical order "
            f"({', '.join(problems)})"
        )

    normalized = {
        key: validate_percentage(f"confidence_targets[{key!r}]", confidence_targets[key])
        for key in CONFIDENCE_TARGET_FIELDS
    }
    if not (normalized["lean"] <= normalized["balanced"] <= normalized["conservative"]):
        raise FieldValidationError(
            "confidence_targets must be ordered lean <= balanced <= conservative"
        )
    return normalized


def _higher_quantile(required_agents: np.ndarray, percentile: float) -> int:
    """Return the upward-rounded percentile staffing for a whole-agent distribution."""

    ordered = np.sort(required_agents.astype(float, copy=False))
    index = max(math.ceil(percentile * ordered.size) - 1, 0)
    index = min(index, ordered.size - 1)
    return int(ordered[index])


def build_candidate_staffing_list(
    required_agents: Sequence[int | float],
    *,
    previous_week_staffing: int | None = None,
    manager_planned_staffing: int | None = None,
    candidate_low_percentile: float = DEFAULT_CANDIDATE_LOW_PERCENTILE,
    candidate_high_percentile: float = DEFAULT_CANDIDATE_HIGH_PERCENTILE,
) -> list[int]:
    """Build the sorted unique candidate staffing list from a required-agent distribution.

    The WBS calls for low/high candidate-range percentile bounds to come from configuration.
    Because the current repo does not yet centralize those bounds in config, this helper uses
    explicit parameters with documented defaults.
    """

    normalized_required_agents = _validate_required_agents(required_agents)
    normalized_low, normalized_high = _validate_candidate_percentile_bounds(
        candidate_low_percentile,
        candidate_high_percentile,
    )

    low_staffing = _higher_quantile(normalized_required_agents, normalized_low)
    high_staffing = _higher_quantile(normalized_required_agents, normalized_high)
    candidate_values = set(range(low_staffing, high_staffing + 1))

    if previous_week_staffing is not None:
        candidate_values.add(
            validate_non_negative_integer("previous_week_staffing", previous_week_staffing)
        )
    if manager_planned_staffing is not None:
        candidate_values.add(
            validate_non_negative_integer("manager_planned_staffing", manager_planned_staffing)
        )

    return sorted(candidate_values)


def select_named_plans(
    simulated_required_agents: Sequence[int | float],
    confidence_targets: Mapping[str, Any],
) -> dict[str, int]:
    """Select Lean, Balanced, and Conservative named staffing plans."""

    normalized_required_agents = _validate_required_agents(simulated_required_agents)
    normalized_targets = _validate_confidence_targets(confidence_targets)
    return {
        target_name: _higher_quantile(normalized_required_agents, normalized_targets[target_name])
        for target_name in CONFIDENCE_TARGET_FIELDS
    }


def build_named_plan_table(
    named_plans: Mapping[str, int],
    confidence_targets: Mapping[str, Any],
    *,
    staffing_evaluation_references: Mapping[int, str] | None = None,
) -> pd.DataFrame:
    """Build the canonical named-plan table from named staffing selections."""

    normalized_targets = _validate_confidence_targets(confidence_targets)
    if not isinstance(named_plans, Mapping):
        raise FieldValidationError("named_plans must be a mapping")

    if staffing_evaluation_references is None:
        staffing_evaluation_references = {}
    if not isinstance(staffing_evaluation_references, Mapping):
        raise FieldValidationError("staffing_evaluation_references must be a mapping")

    rows: list[dict[str, object]] = []
    for target_name in CONFIDENCE_TARGET_FIELDS:
        validate_confidence_target_name(target_name)
        if target_name not in named_plans:
            raise FieldValidationError(f"named_plans is missing {target_name!r}")
        staffing_agents = validate_non_negative_integer(
            f"named_plans[{target_name!r}]",
            named_plans[target_name],
        )
        rows.append(
            {
                "plan_name": PLAN_NAME_BY_TARGET[target_name],
                "confidence_target": normalized_targets[target_name],
                "staffing_agents": staffing_agents,
                "staffing_evaluation_reference": staffing_evaluation_references.get(
                    staffing_agents,
                    f"staffing_{staffing_agents}",
                ),
            }
        )

    return pd.DataFrame(rows, columns=NAMED_PLAN_COLUMNS)


__all__ = [
    "DEFAULT_CANDIDATE_HIGH_PERCENTILE",
    "DEFAULT_CANDIDATE_LOW_PERCENTILE",
    "build_candidate_staffing_list",
    "build_named_plan_table",
    "select_named_plans",
]
