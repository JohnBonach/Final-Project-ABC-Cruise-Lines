"""Run the probabilistic case study for the current staffing refinement."""

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
from src.models import (
    CategoryAssumptions,
    ConfidenceTargets,
    DecisionPolicy,
    ForecastConfiguration,
    SimulationConfiguration,
    StrategicAssumptions,
    WorkforceAssumptions,
)
from src.orchestration import build_application_result
from src.validation import FieldValidationError

DEFAULT_CASE_FILE = PROJECT_ROOT / "data" / "probabilistic_case_study_input.json"
DEFAULT_OUTPUT_FILE = PROJECT_ROOT / "data" / "probabilistic_case_study_report.json"

BASELINE_FIELDS = (
    "history",
    "category_assumptions",
    "workforce_assumptions",
    "decision_policy",
    "forecast_configuration",
    "simulation_configuration",
    "confidence_targets",
    "strategic_assumptions",
)
SENSITIVITY_FIELDS = (
    "sensitivity_name",
    "description",
    "handling_time_multiplier",
)


def _require_keys(name: str, payload: dict[str, Any], expected_keys: tuple[str, ...]) -> None:
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
        raise FieldValidationError(
            f"{name} must match the expected schema exactly ({', '.join(problems)})"
        )


def load_case_study_input(path: str | Path = DEFAULT_CASE_FILE) -> dict[str, Any]:
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
            "manager_proposed_staffing",
            "baseline",
            "sensitivity",
        ),
    )
    if payload["artifact_role"] != "probabilistic_case_study_input":
        raise FieldValidationError("artifact_role must be probabilistic_case_study_input")

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
    category_assumptions = payload["baseline"]["category_assumptions"]
    if not isinstance(category_assumptions, list):
        raise FieldValidationError("baseline.category_assumptions must be a list")
    normalized = tuple(CategoryAssumptions.from_dict(dict(item)) for item in category_assumptions)
    if tuple(item.category for item in normalized) != RESERVATION_CATEGORIES:
        raise FieldValidationError("baseline.category_assumptions must follow the canonical category order")
    return normalized


def _load_workforce_assumptions(payload: dict[str, Any]) -> WorkforceAssumptions:
    return WorkforceAssumptions.from_dict(dict(payload["baseline"]["workforce_assumptions"]))


def _load_decision_policy(payload: dict[str, Any]) -> DecisionPolicy:
    return DecisionPolicy.from_dict(dict(payload["baseline"]["decision_policy"]))


def _load_forecast_configuration(payload: dict[str, Any]) -> ForecastConfiguration:
    return ForecastConfiguration.from_dict(dict(payload["baseline"]["forecast_configuration"]))


def _load_simulation_configuration(payload: dict[str, Any]) -> SimulationConfiguration:
    return SimulationConfiguration.from_dict(dict(payload["baseline"]["simulation_configuration"]))


def _load_confidence_targets(payload: dict[str, Any]) -> ConfidenceTargets:
    return ConfidenceTargets.from_dict(dict(payload["baseline"]["confidence_targets"]))


def _load_strategic_assumptions(payload: dict[str, Any]) -> StrategicAssumptions:
    return StrategicAssumptions.from_dict(dict(payload["baseline"]["strategic_assumptions"]))


def _frame_to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(frame.to_json(orient="records"))


def _serialize_application_result(result: dict[str, Any]) -> dict[str, Any]:
    financial_recommendation = dict(result["financial_recommendation"])
    if isinstance(financial_recommendation.get("candidate_ranking"), pd.DataFrame):
        financial_recommendation["candidate_ranking"] = _frame_to_records(
            financial_recommendation["candidate_ranking"]
        )

    return {
        "ok": bool(result["ok"]),
        "automatic_forecast": dict(result["automatic_forecast"]),
        "effective_forecast": dict(result["effective_forecast"]),
        "forecast_result": _frame_to_records(result["forecast_result"]),
        "recommended_plan": dict(result["recommended_plan"]),
        "manager_proposal": dict(result["manager_proposal"]),
        "previous_week_staffing_context": dict(result["previous_week_staffing_context"]),
        "recommendation_manager_comparison": dict(result["recommendation_manager_comparison"]),
        "staffing_risk_cost_records": result["staffing_risk_cost_records"],
        "lower_demand_outlook": dict(result["lower_demand_outlook"]),
        "central_demand_outlook": dict(result["central_demand_outlook"]),
        "higher_demand_outlook": dict(result["higher_demand_outlook"]),
        "outlook_diagnostics": dict(result["outlook_diagnostics"]),
        "financial_recommendation": financial_recommendation,
        "narrative": {
            "text": result["narrative"]["text"],
            "warnings": list(result["narrative"]["warnings"]),
            "comparison_table": _frame_to_records(result["narrative"]["comparison_table"]),
            "manager_comparison": dict(result["adaptive_comparison_narrative"]),
        },
    }


def _scale_category_assumptions(
    category_assumptions: tuple[CategoryAssumptions, ...],
    handling_time_multiplier: float,
) -> tuple[CategoryAssumptions, ...]:
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
    decision_policy: DecisionPolicy,
    forecast_configuration: ForecastConfiguration,
    simulation_configuration: SimulationConfiguration,
    confidence_targets: ConfidenceTargets,
    strategic_assumptions: StrategicAssumptions,
    previous_week_staffing: int,
    manager_proposed_staffing: int,
) -> dict[str, Any]:
    result = build_application_result(
        history=history,
        category_assumptions=category_assumptions,
        workforce_assumptions=workforce_assumptions,
        decision_policy=decision_policy,
        forecast_configuration=forecast_configuration,
        simulation_configuration=simulation_configuration,
        confidence_targets=confidence_targets,
        strategic_assumptions=strategic_assumptions,
        previous_week_staffing=previous_week_staffing,
        manager_planned_staffing=manager_proposed_staffing,
        manual_overrides=None,
    )
    if not result["ok"]:
        raise FieldValidationError(result["error"]["message"])
    return _serialize_application_result(result)


def build_case_study_report(payload: dict[str, Any]) -> dict[str, Any]:
    history = _load_history(payload)
    category_assumptions = _load_category_assumptions(payload)
    workforce_assumptions = _load_workforce_assumptions(payload)
    decision_policy = _load_decision_policy(payload)
    forecast_configuration = _load_forecast_configuration(payload)
    simulation_configuration = _load_simulation_configuration(payload)
    confidence_targets = _load_confidence_targets(payload)
    strategic_assumptions = _load_strategic_assumptions(payload)

    previous_week_staffing = int(payload["previous_week_staffing"])
    manager_proposed_staffing = int(payload["manager_proposed_staffing"])

    baseline_result = _build_case_result(
        history=history,
        category_assumptions=category_assumptions,
        workforce_assumptions=workforce_assumptions,
        decision_policy=decision_policy,
        forecast_configuration=forecast_configuration,
        simulation_configuration=simulation_configuration,
        confidence_targets=confidence_targets,
        strategic_assumptions=strategic_assumptions,
        previous_week_staffing=previous_week_staffing,
        manager_proposed_staffing=manager_proposed_staffing,
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
        decision_policy=decision_policy,
        forecast_configuration=forecast_configuration,
        simulation_configuration=simulation_configuration,
        confidence_targets=confidence_targets,
        strategic_assumptions=strategic_assumptions,
        previous_week_staffing=previous_week_staffing,
        manager_proposed_staffing=manager_proposed_staffing,
    )

    baseline_recommendation = int(baseline_result["recommended_plan"]["staffing_agents"])
    sensitivity_recommendation = int(sensitivity_result["recommended_plan"]["staffing_agents"])
    baseline_total_cost = float(
        baseline_result["recommended_plan"]["expected_total_weekly_operating_cost"]
    )
    sensitivity_total_cost = float(
        sensitivity_result["recommended_plan"]["expected_total_weekly_operating_cost"]
    )

    comparison = {
        "recommended_staffing_agents": {
            "baseline": baseline_recommendation,
            "sensitivity": sensitivity_recommendation,
            "delta": sensitivity_recommendation - baseline_recommendation,
        },
        "inhouse_coverage_probability": {
            "baseline": float(baseline_result["recommended_plan"]["capacity_confidence"]),
            "sensitivity": float(sensitivity_result["recommended_plan"]["capacity_confidence"]),
        },
        "expected_total_weekly_operating_cost": {
            "baseline": baseline_total_cost,
            "sensitivity": sensitivity_total_cost,
            "delta": sensitivity_total_cost - baseline_total_cost,
        },
    }

    passed = baseline_result["ok"] and sensitivity_result["ok"]

    return {
        "artifact_role": "probabilistic_case_study_report",
        "case_name": payload["case_name"],
        "description": payload["description"],
        "passed": passed,
        "source_case": payload,
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
    baseline = report["baseline"]["recommended_plan"]
    sensitivity = report["sensitivity"]["recommended_plan"]
    lines = [
        f"Case study: {report['case_name']}",
        report["description"],
        f"Overall result: {'PASS' if report['passed'] else 'FAIL'}",
        report["executive_summary"],
        "",
        "Baseline",
        f"  Recommendation: {baseline['staffing_agents']} agents",
        f"  In-house coverage probability: {baseline['capacity_confidence']:.4f}",
        f"  Expected overflow commission: {baseline['expected_overflow_commission']:.2f}",
        f"  Expected total weekly operating cost: {baseline['expected_total_weekly_operating_cost']:.2f}",
        "",
        "Sensitivity",
        f"  Recommendation: {sensitivity['staffing_agents']} agents",
        f"  In-house coverage probability: {sensitivity['capacity_confidence']:.4f}",
        f"  Expected overflow commission: {sensitivity['expected_overflow_commission']:.2f}",
        f"  Expected total weekly operating cost: {sensitivity['expected_total_weekly_operating_cost']:.2f}",
        "",
        "Shift",
        f"  Recommendation delta: {report['comparison']['recommended_staffing_agents']['delta']}",
        f"  Operating-cost delta: {report['comparison']['expected_total_weekly_operating_cost']['delta']:.2f}",
    ]
    return "\n".join(lines)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the probabilistic case study for the current staffing refinement."
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
