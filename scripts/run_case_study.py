"""Run the probabilistic case study for WBS Task 7.3."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.constants import RESERVATION_CATEGORIES
from src.models import CategoryAssumptions, ConfidenceTargets, ForecastConfiguration
from src.models import SimulationConfiguration, WorkforceAssumptions
from src.orchestration import build_application_result
from src.validation import FieldValidationError

DEFAULT_CASE_FILE = Path(__file__).resolve().parents[1] / "data" / "probabilistic_case_study_input.json"
DEFAULT_OUTPUT_FILE = Path(__file__).resolve().parents[1] / "data" / "probabilistic_case_study_report.json"

BASELINE_FIELDS = (
    "history",
    "category_assumptions",
    "workforce_assumptions",
    "forecast_configuration",
    "simulation_configuration",
    "confidence_targets",
)
SENSITIVITY_FIELDS = (
    "scenario_name",
    "description",
    "handling_time_multiplier",
)


def _require_keys(name: str, payload: dict[str, Any], expected_keys: tuple[str, ...]) -> None:
    """Require an exact set of keys for a case-file section."""

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
        raise FieldValidationError(f"{name} must match the expected schema exactly ({', '.join(problems)})")


def load_case_study_input(path: str | Path = DEFAULT_CASE_FILE) -> dict[str, Any]:
    """Load the probabilistic case-study input from JSON."""

    case_path = Path(path)
    with case_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise FieldValidationError("case study file must contain a top-level JSON object")

    _require_keys(
        "case study",
        payload,
        (
            "artifact_role",
            "case_name",
            "description",
            "previous_week_staffing",
            "manager_planned_staffing",
            "baseline",
            "sensitivity",
        ),
    )
    if payload["artifact_role"] != "probabilistic_case_study_input":
        raise FieldValidationError(
            "artifact_role must be probabilistic_case_study_input"
        )

    baseline = payload["baseline"]
    if not isinstance(baseline, dict):
        raise FieldValidationError("baseline must be an object")
    _require_keys("baseline", baseline, BASELINE_FIELDS)

    sensitivity = payload["sensitivity"]
    if not isinstance(sensitivity, dict):
        raise FieldValidationError("sensitivity must be an object")
    _require_keys("sensitivity", sensitivity, SENSITIVITY_FIELDS)

    return payload


def _load_history(payload: dict[str, Any]) -> pd.DataFrame:
    """Build the canonical history DataFrame from the case payload."""

    history = payload["baseline"]["history"]
    if not isinstance(history, list):
        raise FieldValidationError("baseline.history must be a list of weekly records")
    frame = pd.DataFrame(history)
    expected_columns = ("week_id", "week_start", *RESERVATION_CATEGORIES, "staffing_agents")
    if tuple(frame.columns) != expected_columns:
        raise FieldValidationError(
            "baseline.history must contain the canonical weekly columns in the shared order"
        )
    return frame


def _load_category_assumptions(payload: dict[str, Any]) -> tuple[CategoryAssumptions, ...]:
    """Build the canonical category assumptions tuple from the baseline payload."""

    category_assumptions = payload["baseline"]["category_assumptions"]
    if not isinstance(category_assumptions, list):
        raise FieldValidationError("baseline.category_assumptions must be a list")
    normalized = tuple(CategoryAssumptions.from_dict(dict(item)) for item in category_assumptions)
    if tuple(item.category for item in normalized) != RESERVATION_CATEGORIES:
        raise FieldValidationError("baseline.category_assumptions must follow the canonical category order")
    return normalized


def _load_workforce_assumptions(payload: dict[str, Any]) -> WorkforceAssumptions:
    """Build the shared workforce assumptions model from the baseline payload."""

    workforce_assumptions = payload["baseline"]["workforce_assumptions"]
    if not isinstance(workforce_assumptions, dict):
        raise FieldValidationError("baseline.workforce_assumptions must be an object")
    return WorkforceAssumptions.from_dict(dict(workforce_assumptions))


def _load_forecast_configuration(payload: dict[str, Any]) -> ForecastConfiguration:
    """Build the shared forecast configuration model from the baseline payload."""

    forecast_configuration = payload["baseline"]["forecast_configuration"]
    if not isinstance(forecast_configuration, dict):
        raise FieldValidationError("baseline.forecast_configuration must be an object")
    return ForecastConfiguration.from_dict(dict(forecast_configuration))


def _load_simulation_configuration(payload: dict[str, Any]) -> SimulationConfiguration:
    """Build the shared simulation configuration model from the baseline payload."""

    simulation_configuration = payload["baseline"]["simulation_configuration"]
    if not isinstance(simulation_configuration, dict):
        raise FieldValidationError("baseline.simulation_configuration must be an object")
    return SimulationConfiguration.from_dict(dict(simulation_configuration))


def _load_confidence_targets(payload: dict[str, Any]) -> ConfidenceTargets:
    """Build the shared confidence-target model from the baseline payload."""

    confidence_targets = payload["baseline"]["confidence_targets"]
    if not isinstance(confidence_targets, dict):
        raise FieldValidationError("baseline.confidence_targets must be an object")
    return ConfidenceTargets.from_dict(dict(confidence_targets))


def _frame_to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to JSON-native row records."""

    return json.loads(frame.to_json(orient="records"))


def _serialize_application_result(result: dict[str, Any]) -> dict[str, Any]:
    """Convert the orchestration result into JSON-serializable evidence."""

    financial_recommendation = dict(result["financial_recommendation"])
    if isinstance(financial_recommendation.get("candidate_ranking"), pd.DataFrame):
        financial_recommendation["candidate_ranking"] = _frame_to_records(
            financial_recommendation["candidate_ranking"]
        )

    return {
        "ok": bool(result["ok"]),
        "automatic_forecast": dict(result["automatic_forecast"]),
        "forecast_result": _frame_to_records(result["forecast_result"]),
        "deterministic_staffing_result": dict(result["deterministic_staffing_result"]),
        "simulation_distribution": _frame_to_records(result["simulation_distribution"]),
        "staffing_evaluation_table": _frame_to_records(result["staffing_evaluation_table"]),
        "named_plans": {
            "selected": dict(result["named_plans"]["selected"]),
            "table": _frame_to_records(result["named_plans"]["table"]),
            "candidate_staffing_levels": list(result["named_plans"]["candidate_staffing_levels"]),
            "staffing_evaluation_references": dict(
                result["named_plans"]["staffing_evaluation_references"]
            ),
        },
        "financial_recommendation": financial_recommendation,
        "narrative": {
            "text": result["narrative"]["text"],
            "warnings": list(result["narrative"]["warnings"]),
            "comparison_table": _frame_to_records(result["narrative"]["comparison_table"]),
        },
    }


def _scale_category_assumptions(
    category_assumptions: tuple[CategoryAssumptions, ...],
    handling_time_multiplier: float,
) -> tuple[CategoryAssumptions, ...]:
    """Create a sensitivity case by scaling handling times across all categories."""

    return tuple(
        CategoryAssumptions.from_dict(
            {
                **item.to_dict(),
                "handling_time_minutes": item.handling_time_minutes * handling_time_multiplier,
            }
        )
        for item in category_assumptions
    )


def _build_case_result(
    *,
    history: pd.DataFrame,
    category_assumptions: tuple[CategoryAssumptions, ...],
    workforce_assumptions: WorkforceAssumptions,
    forecast_configuration: ForecastConfiguration,
    simulation_configuration: SimulationConfiguration,
    confidence_targets: ConfidenceTargets,
    previous_week_staffing: int,
    manager_planned_staffing: int,
) -> dict[str, Any]:
    """Execute the full orchestration path for one staffing case."""

    result = build_application_result(
        history=history,
        category_assumptions=category_assumptions,
        workforce_assumptions=workforce_assumptions,
        forecast_configuration=forecast_configuration,
        simulation_configuration=simulation_configuration,
        confidence_targets=confidence_targets,
        previous_week_staffing=previous_week_staffing,
        manager_planned_staffing=manager_planned_staffing,
        manual_overrides=None,
    )
    if not result["ok"]:
        raise FieldValidationError(result["error"]["message"])
    return _serialize_application_result(result)


def build_case_study_report(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the baseline and sensitivity case-study scenarios."""

    history = _load_history(payload)
    category_assumptions = _load_category_assumptions(payload)
    workforce_assumptions = _load_workforce_assumptions(payload)
    forecast_configuration = _load_forecast_configuration(payload)
    simulation_configuration = _load_simulation_configuration(payload)
    confidence_targets = _load_confidence_targets(payload)

    previous_week_staffing = int(payload["previous_week_staffing"])
    manager_planned_staffing = int(payload["manager_planned_staffing"])

    baseline_result = _build_case_result(
        history=history,
        category_assumptions=category_assumptions,
        workforce_assumptions=workforce_assumptions,
        forecast_configuration=forecast_configuration,
        simulation_configuration=simulation_configuration,
        confidence_targets=confidence_targets,
        previous_week_staffing=previous_week_staffing,
        manager_planned_staffing=manager_planned_staffing,
    )

    sensitivity_payload = payload["sensitivity"]
    handling_time_multiplier = float(sensitivity_payload["handling_time_multiplier"])
    sensitivity_result = _build_case_result(
        history=history,
        category_assumptions=_scale_category_assumptions(
            category_assumptions,
            handling_time_multiplier,
        ),
        workforce_assumptions=workforce_assumptions,
        forecast_configuration=forecast_configuration,
        simulation_configuration=simulation_configuration,
        confidence_targets=confidence_targets,
        previous_week_staffing=previous_week_staffing,
        manager_planned_staffing=manager_planned_staffing,
    )

    baseline_recommendation = int(
        baseline_result["financial_recommendation"]["recommended_staffing_agents"]
    )
    sensitivity_recommendation = int(
        sensitivity_result["financial_recommendation"]["recommended_staffing_agents"]
    )

    comparison = {
        "recommended_staffing_agents": {
            "baseline": baseline_recommendation,
            "sensitivity": sensitivity_recommendation,
            "delta": sensitivity_recommendation - baseline_recommendation,
        },
        "expected_total_economic_cost": {
            "baseline": float(
                baseline_result["financial_recommendation"]["recommended_staffing_record"][
                    "expected_total_economic_cost"
                ]
            ),
            "sensitivity": float(
                sensitivity_result["financial_recommendation"]["recommended_staffing_record"][
                    "expected_total_economic_cost"
                ]
            ),
        },
        "expected_overtime_hours": {
            "baseline": float(
                baseline_result["financial_recommendation"]["recommended_staffing_record"][
                    "expected_overtime_hours"
                ]
            ),
            "sensitivity": float(
                sensitivity_result["financial_recommendation"]["recommended_staffing_record"][
                    "expected_overtime_hours"
                ]
            ),
        },
        "expected_abandoned_total": {
            "baseline": float(
                baseline_result["financial_recommendation"]["recommended_staffing_record"][
                    "expected_abandoned_total"
                ]
            ),
            "sensitivity": float(
                sensitivity_result["financial_recommendation"]["recommended_staffing_record"][
                    "expected_abandoned_total"
                ]
            ),
        },
    }

    passed = (
        baseline_result["ok"]
        and sensitivity_result["ok"]
        and baseline_recommendation != sensitivity_recommendation
    )

    return {
        "artifact_role": "probabilistic_case_study_report",
        "case_name": payload["case_name"],
        "description": payload["description"],
        "passed": passed,
        "source_case": {
            "previous_week_staffing": previous_week_staffing,
            "manager_planned_staffing": manager_planned_staffing,
            "baseline": payload["baseline"],
            "sensitivity": payload["sensitivity"],
        },
        "baseline": baseline_result,
        "sensitivity": sensitivity_result,
        "comparison": comparison,
        "executive_summary": (
            f"Baseline recommendation: {baseline_recommendation} agents. "
            f"Sensitivity recommendation: {sensitivity_recommendation} agents after applying "
            f"{handling_time_multiplier:.2f}x handling times."
        ),
    }


def format_case_study_report(report: dict[str, Any]) -> str:
    """Render a compact human-readable summary for the console."""

    baseline = report["baseline"]["financial_recommendation"]
    sensitivity = report["sensitivity"]["financial_recommendation"]
    lines = [
        f"Case study: {report['case_name']}",
        report["description"],
        f"Overall result: {'PASS' if report['passed'] else 'FAIL'}",
        report["executive_summary"],
        "",
        "Baseline",
        f"  Recommendation: {baseline['recommended_staffing_agents']} agents",
        f"  Named plans: {report['baseline']['named_plans']['selected']}",
        f"  Expected total economic cost: {baseline['recommended_staffing_record']['expected_total_economic_cost']}",
        f"  Expected overtime hours: {baseline['recommended_staffing_record']['expected_overtime_hours']}",
        f"  Expected abandoned total: {baseline['recommended_staffing_record']['expected_abandoned_total']}",
        "",
        "Sensitivity",
        f"  Recommendation: {sensitivity['recommended_staffing_agents']} agents",
        f"  Named plans: {report['sensitivity']['named_plans']['selected']}",
        f"  Expected total economic cost: {sensitivity['recommended_staffing_record']['expected_total_economic_cost']}",
        f"  Expected overtime hours: {sensitivity['recommended_staffing_record']['expected_overtime_hours']}",
        f"  Expected abandoned total: {sensitivity['recommended_staffing_record']['expected_abandoned_total']}",
        "",
        "Shift",
        f"  Recommendation delta: {report['comparison']['recommended_staffing_agents']['delta']}",
    ]
    return "\n".join(lines)


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line interface for the case-study runner."""

    parser = argparse.ArgumentParser(
        description="Run the probabilistic case study for Task 7.3."
    )
    parser.add_argument(
        "--case-file",
        type=Path,
        default=DEFAULT_CASE_FILE,
        help="Path to the probabilistic case-study JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="Optional path to write the full case-study report as JSON.",
    )
    return parser


def main() -> int:
    """Execute the case study and print the comparison summary."""

    parser = build_argument_parser()
    args = parser.parse_args()

    report = build_case_study_report(load_case_study_input(args.case_file))
    print(format_case_study_report(report))

    if args.output is not None:
        output_path = args.output.resolve()
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=True)
        print(f"\nSaved case-study report to {output_path}")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
