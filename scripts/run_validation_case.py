"""Run the manual deterministic validation case for WBS Task 7.2."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.constants import RESERVATION_CATEGORIES
from src.finance.staffing_evaluator import evaluate_staffing_level
from src.forecasting.uncertainty import build_forecast_result
from src.models import CategoryAssumptions, WorkforceAssumptions
from src.orchestration import calculate_deterministic_staffing
from src.validation import FieldValidationError

DEFAULT_CASE_FILE = Path(__file__).resolve().parents[1] / "data" / "case_study_input.json"
DEFAULT_TOLERANCE = 1e-9


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


def load_validation_case(path: str | Path = DEFAULT_CASE_FILE) -> dict[str, Any]:
    """Load the manual validation case from JSON."""

    case_path = Path(path)
    with case_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise FieldValidationError("validation case file must contain a top-level JSON object")

    _require_keys(
        "validation case",
        payload,
        (
            "artifact_role",
            "case_name",
            "description",
            "validation_tolerance",
            "forecast_weights",
            "forecast_variability_multiplier",
            "validation_staffing_agents",
            "history",
            "category_assumptions",
            "workforce_assumptions",
            "expected",
        ),
    )
    return payload


def _load_history(payload: dict[str, Any]) -> pd.DataFrame:
    """Build the canonical history DataFrame from the case payload."""

    history = payload["history"]
    if not isinstance(history, list):
        raise FieldValidationError("history must be a list of weekly records")
    frame = pd.DataFrame(history)
    expected_columns = ("week_id", "week_start", *RESERVATION_CATEGORIES, "staffing_agents")
    if tuple(frame.columns) != expected_columns:
        raise FieldValidationError(
            "history must contain the canonical weekly columns in the shared order"
        )
    return frame


def _load_category_assumptions(payload: dict[str, Any]) -> tuple[CategoryAssumptions, ...]:
    """Build the canonical category assumptions tuple from the case payload."""

    category_assumptions = payload["category_assumptions"]
    if not isinstance(category_assumptions, list):
        raise FieldValidationError("category_assumptions must be a list")
    normalized = tuple(CategoryAssumptions.from_dict(dict(item)) for item in category_assumptions)
    if tuple(item.category for item in normalized) != RESERVATION_CATEGORIES:
        raise FieldValidationError("category_assumptions must follow the canonical category order")
    return normalized


def _load_workforce_assumptions(payload: dict[str, Any]) -> WorkforceAssumptions:
    """Build the shared workforce assumptions model from the case payload."""

    workforce_assumptions = payload["workforce_assumptions"]
    if not isinstance(workforce_assumptions, dict):
        raise FieldValidationError("workforce_assumptions must be an object")
    return WorkforceAssumptions.from_dict(dict(workforce_assumptions))


def _extract_category_map(
    frame: pd.DataFrame,
    column: str,
    *,
    cast_type: type[Any] = float,
) -> dict[str, Any]:
    """Extract a canonical category map from a one-row or multi-row forecast table."""

    indexed = frame.set_index("category")
    return {
        category: cast_type(indexed.loc[category, column])
        for category in RESERVATION_CATEGORIES
    }


def _build_comparison(
    actual: Any,
    expected: Any,
    *,
    tolerance: float,
) -> dict[str, Any]:
    """Return a numeric comparison record for a scalar or category map."""

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise FieldValidationError("comparison actual value must be a mapping")
        return {
            key: _build_comparison(actual[key], value, tolerance=tolerance)
            for key, value in expected.items()
        }

    if isinstance(expected, str):
        if actual != expected:
            return {
                "actual": actual,
                "expected": expected,
                "matches": False,
            }
        return {
            "actual": actual,
            "expected": expected,
            "matches": True,
        }

    actual_value = float(actual)
    expected_value = float(expected)
    delta = actual_value - expected_value
    return {
        "actual": actual_value,
        "expected": expected_value,
        "delta": delta,
        "matches": math.isclose(actual_value, expected_value, abs_tol=tolerance),
    }


def _all_leaf_matches(segment: Any) -> list[bool]:
    """Collect comparison outcomes from a nested comparison tree."""

    if isinstance(segment, dict):
        if "matches" in segment:
            return [bool(segment["matches"])]
        matches: list[bool] = []
        for value in segment.values():
            matches.extend(_all_leaf_matches(value))
        return matches
    return []


def build_validation_case_report(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the deterministic path and compare the results to the hand-worked expectations."""

    tolerance = float(payload.get("validation_tolerance", DEFAULT_TOLERANCE))
    history = _load_history(payload)
    category_assumptions = _load_category_assumptions(payload)
    workforce_assumptions = _load_workforce_assumptions(payload)
    weights = list(payload["forecast_weights"])
    variability_multiplier = float(payload["forecast_variability_multiplier"])

    forecast_result = build_forecast_result(
        history,
        weights,
        variability_multiplier,
        manual_overrides=None,
    )
    forecast_point = _extract_category_map(forecast_result, "point_forecast")
    deterministic_staffing_result = calculate_deterministic_staffing(
        forecast_point,
        category_assumptions,
        workforce_assumptions,
    )
    simulated_demand = pd.DataFrame(
        [
            {
                "simulation_id": 1,
                **forecast_point,
            }
        ]
    )
    staffing_evaluation = evaluate_staffing_level(
        simulated_demand,
        int(payload["validation_staffing_agents"]),
        category_assumptions,
        workforce_assumptions,
    )

    actual = {
        "forecast": {
            "point_forecast": forecast_point,
            "historical_mean": _extract_category_map(forecast_result, "historical_mean"),
            "historical_std": _extract_category_map(forecast_result, "historical_std"),
            "adjusted_std": _extract_category_map(forecast_result, "adjusted_std"),
            "forecast_source": _extract_category_map(
                forecast_result,
                "forecast_source",
                cast_type=str,
            ),
        },
        "deterministic_staffing": deterministic_staffing_result,
        "staffing_evaluation": staffing_evaluation,
    }
    expected = payload["expected"]

    comparison = {
        "forecast": {
            key: _build_comparison(actual["forecast"][key], expected["forecast"][key], tolerance=tolerance)
            for key in expected["forecast"]
        },
        "deterministic_staffing": {
            key: _build_comparison(
                actual["deterministic_staffing"][key],
                expected["deterministic_staffing"][key],
                tolerance=tolerance,
            )
            for key in expected["deterministic_staffing"]
        },
        "staffing_evaluation": {
            key: _build_comparison(
                actual["staffing_evaluation"][key],
                expected["staffing_evaluation"][key],
                tolerance=tolerance,
            )
            for key in expected["staffing_evaluation"]
        },
    }
    passed = all(_all_leaf_matches(comparison))

    return {
        "case_name": payload["case_name"],
        "description": payload["description"],
        "validation_tolerance": tolerance,
        "passed": passed,
        "actual": actual,
        "expected": expected,
        "comparison": comparison,
    }


def format_validation_case_report(report: dict[str, Any]) -> str:
    """Render a compact human-readable validation summary."""

    lines = [
        f"Validation case: {report['case_name']}",
        report["description"],
        f"Tolerance: {report['validation_tolerance']}",
        f"Overall result: {'PASS' if report['passed'] else 'FAIL'}",
        "",
    ]

    for section_name in ("forecast", "deterministic_staffing", "staffing_evaluation"):
        lines.append(section_name.replace("_", " ").title())
        for field_name, field_result in report["comparison"][section_name].items():
            if "matches" in field_result:
                status = "OK" if field_result["matches"] else "MISMATCH"
                delta = field_result.get("delta")
                delta_text = "" if delta is None else f", delta={delta}"
                lines.append(
                    f"  {field_name}: actual={field_result['actual']}, expected={field_result['expected']}{delta_text} [{status}]"
                )
            else:
                lines.append(f"  {field_name}:")
                for subfield_name, subfield_result in field_result.items():
                    status = "OK" if subfield_result["matches"] else "MISMATCH"
                    delta = subfield_result.get("delta")
                    delta_text = "" if delta is None else f", delta={delta}"
                    lines.append(
                        f"    {subfield_name}: actual={subfield_result['actual']}, expected={subfield_result['expected']}{delta_text} [{status}]"
                    )
        lines.append("")

    return "\n".join(lines).rstrip()


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line interface for the validation case runner."""

    parser = argparse.ArgumentParser(
        description="Run the manual deterministic validation case for Task 7.2."
    )
    parser.add_argument(
        "--case-file",
        type=Path,
        default=DEFAULT_CASE_FILE,
        help="Path to the validation-case JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the full validation report as JSON.",
    )
    return parser


def main() -> int:
    """Execute the validation case and print the comparison summary."""

    parser = build_argument_parser()
    args = parser.parse_args()

    report = build_validation_case_report(load_validation_case(args.case_file))
    print(format_validation_case_report(report))

    if args.output is not None:
        output_path = args.output.resolve()
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=True)
        print(f"\nSaved validation report to {output_path}")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
