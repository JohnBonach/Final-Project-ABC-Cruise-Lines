"""Synthetic reservation-history specification scaffold for Task 1.1.

This module intentionally does not generate data yet. It captures the agreed
rules and placeholders that Task 1.2 will translate into reproducible
generation logic for ``data/synthetic_history.csv``.

Authority note:
- This file is the authoritative Task 1.1 synthetic-history specification for
  Task 1.2 implementation.
- ``data/case_study_input.json`` is a companion artifact that may summarize or
  later extend case-study inputs, but it is not the source of truth for the
  Task 1.1 generator contract.
- Workflow status is tracked only in
  ``ABC_Cruise_DSS_Development_WBS.md`` to avoid artifact drift.

Shared contract alignment:
- History must contain the canonical category keys from ``src/constants.py``.
- History must include 8 to 12 weekly observations.
- Weekly demand must be nonnegative whole reservations.
- Default staffing should remain plausible relative to the case-study baseline
  of roughly 8 to 12 agents, with a typical prior week near 9 agents.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Final


RESERVATION_CATEGORIES: Final[tuple[str, str, str, str]] = (
    "simple",
    "standard",
    "complex_group",
    "change_cancellation",
)

HISTORICAL_DEMAND_COLUMNS: Final[tuple[str, ...]] = (
    "week_id",
    "week_start",
    *RESERVATION_CATEGORIES,
    "staffing_agents",
)

SYNTHETIC_HISTORY_SPEC: Final[dict[str, object]] = {
    "task_id": "1.1",
    "artifact_role": "authoritative_task_1_1_specification",
    "workflow_status_source": "ABC_Cruise_DSS_Development_WBS.md -> Task 1.1 / task tracker",
    "implementation_phase": "specification_only",
    "notes": [
        "Do not generate or write CSV rows in Task 1.1.",
        "Task 1.2 should treat this file as the authoritative Task 1.1 source of truth for synthetic-history generation rules.",
        "Task 1.2 should consume this structure and implement deterministic, seed-based generation.",
        "Task 1.3 should materialize the baseline CSV after Task 1.2 is complete.",
    ],
    "history_window": {
        "weeks_min": 8,
        "weeks_max": 12,
        "default_weeks": 10,
        "week_frequency": "W-MON",
        "week_id_format": "YYYY-Www",
        "week_start_day": "Monday",
        "date_rule": {
            "strategy": "fixed_baseline_for_initial_dataset",
            "default_start_week": "2026-04-06",
            "default_end_week": "2026-06-08",
            "included_week_ids": [
                "2026-W15",
                "2026-W16",
                "2026-W17",
                "2026-W18",
                "2026-W19",
                "2026-W20",
                "2026-W21",
                "2026-W22",
                "2026-W23",
                "2026-W24",
            ],
            "implementation_notes": [
                "Generate one row per Monday week_start in ascending order.",
                "If Task 1.2 later allows 8 to 12 weeks, it must still preserve contiguous weekly dates and ordered week_id values.",
                "The most recent historical week should represent a completed week, not a partial in-progress week.",
            ],
        },
    },
    "random_seed_contract": {
        "field_name": "random_seed",
        "default_value": 510,
        "default_source_of_truth": "config/defaults.json -> simulation_configuration.random_seed",
        "task_1_2_usage": [
            "Task 1.2 must accept a random_seed input for synthetic-history generation.",
            "If Task 1.2 exposes both a function argument and config input, the explicit function argument takes precedence; otherwise read the default from the source-of-truth config field.",
            "Task 1.2 must initialize exactly one deterministic random-number generator from the resolved random_seed and use that same generator for all stochastic history draws in week order.",
            "With identical inputs and the same resolved random_seed, Task 1.2 must produce the same history rows and staffing_agents values.",
        ],
    },
    "demand_model": {
        "distribution_placeholder": "normal_with_rounding_and_floor_at_zero",
        "integerization_rule": "Apply shared week factor first, then any high-demand uplift, then clamp to category min/max bounds, then round half up to a whole reservation, then floor at zero.",
        "order_of_operations": [
            "Start from the category baseline mean and add continuous stochastic variation for the week.",
            "Apply the shared weekly factor to that continuous pre-bounds demand before any high-demand uplift is considered.",
            "If the week is flagged as high demand, multiply the shared-factor-adjusted continuous demand by the category-specific uplift for that same week.",
            "Clamp the resulting continuous demand to the category's minimum_reservations and maximum_reservations bounds before integer conversion.",
            "Round the bounded continuous demand to the nearest whole reservation using round-half-up behavior, then apply max(0, rounded_value) as the final nonnegative integer demand.",
        ],
        "correlation_assumptions": {
            "use_shared_week_factor": True,
            "shared_factor_purpose": "Create moderate co-movement across categories without making them identical.",
            "target_direction": {
                "simple": "positive",
                "standard": "positive",
                "complex_group": "positive",
                "change_cancellation": "positive_but_weaker",
            },
            "implementation_notes": [
                "A single weekly demand factor should influence all categories.",
                "Simple, standard, and complex_group should move together more strongly than change_cancellation.",
                "Independent residual noise should remain category-specific so standard deviation differs by category.",
            ],
        },
        "high_demand_week": {
            "enabled": True,
            "approx_probability_per_week": 0.15,
            "max_expected_occurrences_in_10_weeks": 2,
            "uplift_ranges": {
                "simple": [1.12, 1.25],
                "standard": [1.10, 1.22],
                "complex_group": [1.15, 1.30],
                "change_cancellation": [1.05, 1.15],
            },
            "business_rationale": "Promotions, itinerary releases, or seasonal booking spikes should occasionally increase demand across multiple categories.",
        },
        "category_rules": [
            {
                "category": "simple",
                "baseline_mean_reservations": 360,
                "week_to_week_std_reservations": 36,
                "minimum_reservations": 240,
                "maximum_reservations": 470,
                "shape_notes": "Highest-volume and lowest-handling-time category; should usually be the largest count.",
            },
            {
                "category": "standard",
                "baseline_mean_reservations": 190,
                "week_to_week_std_reservations": 24,
                "minimum_reservations": 120,
                "maximum_reservations": 260,
                "shape_notes": "Moderate volume with materially longer handling time than simple reservations.",
            },
            {
                "category": "complex_group",
                "baseline_mean_reservations": 36,
                "week_to_week_std_reservations": 6,
                "minimum_reservations": 18,
                "maximum_reservations": 55,
                "shape_notes": "Lowest-volume but highest-handling-time category; should contribute meaningful workload despite small counts.",
            },
            {
                "category": "change_cancellation",
                "baseline_mean_reservations": 130,
                "week_to_week_std_reservations": 18,
                "minimum_reservations": 70,
                "maximum_reservations": 185,
                "shape_notes": "Operationally meaningful support volume with weaker correlation to new-booking surges.",
            },
        ],
    },
    "staffing_history_rule": {
        "target_previous_week_staffing_range": [8, 12],
        "typical_center": 9,
        "source_inputs": [
            "generated category demand for the same week",
            "default handling_time_minutes from case-study assumptions",
            "paid_hours_per_agent = 40.0",
            "productive_processing_pct = 0.85",
        ],
        "whole_agent_rounding_rule": "Round implied FTE to the nearest whole agent using round-half-up behavior before applying the prior-week lag rule.",
        "deterministic_algorithm": [
            "For each week, convert generated category demand to workload hours using the case-study handling times and divide by 34.0 productive hours per agent to obtain implied_fte.",
            "Compute rounded_target_agents as the round-half-up whole-agent value of implied_fte.",
            "For the first historical week only, set staffing_agents to clamp(rounded_target_agents, 8, 12).",
            "For each later week, begin from the prior week's finalized staffing_agents value.",
            "If rounded_target_agents is greater than prior_week_staffing + 1, set current staffing_agents to prior_week_staffing + 1.",
            "If rounded_target_agents is less than prior_week_staffing - 1, set current staffing_agents to prior_week_staffing - 1.",
            "Otherwise set current staffing_agents to rounded_target_agents.",
            "After the one-agent lag rule is applied, clamp current staffing_agents to the inclusive operating band [8, 12].",
        ],
        "tie_breaking": [
            "Any implied_fte ending in exactly 0.5 agents rounds upward before the lag rule is applied.",
            "The prior-week lag rule is directional only: when the rounded target differs from prior-week staffing by more than one agent, move exactly one whole agent toward the rounded target.",
        ],
        "behavior_notes": [
            "Staffing history represents what was scheduled in that completed week, not an optimized recommendation.",
            "The allowed prior-week effect is exactly one whole agent per week in either direction relative to the prior finalized staffing value.",
            "The default dataset should usually end with staffing_agents near 9 to align with the case-study example.",
        ],
    },
    "reasonableness_targets": {
        "expected_average_total_workload_hours": [270.0, 310.0],
        "expected_implied_average_fte": [7.95, 9.15],
        "default_last_week_staffing_agents": 9,
        "purpose": "Keep the historical sample realistic for downstream forecasting, workload, and staffing modules.",
    },
}


def get_synthetic_history_spec() -> dict[str, object]:
    """Return the Task 1.1 generation specification for Task 1.2 to implement."""

    return SYNTHETIC_HISTORY_SPEC


def build_argument_parser() -> argparse.ArgumentParser:
    """Create a small CLI around the authoritative Task 1.1 specification."""

    parser = argparse.ArgumentParser(
        description=(
            "Generate seeded ABC Cruise Lines synthetic reservation history "
            "from the authoritative Task 1.1 specification."
        )
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help=(
            "Optional explicit random seed. If omitted, the script uses "
            "config/defaults.json -> simulation_configuration.random_seed."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional CSV path to write the generated history. If omitted, "
            "the script prints the generated table to stdout."
        ),
    )
    return parser


def main() -> int:
    """Execute synthetic-history generation while keeping this file as the spec anchor."""

    parser = build_argument_parser()
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.data.generator import generate_synthetic_history

    history = generate_synthetic_history(seed=args.seed)
    if args.output is not None:
        output_path = args.output.resolve()
        history.to_csv(output_path, index=False)
        print(f"Wrote {len(history)} synthetic history rows to {output_path}")
        return 0

    print(history.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
