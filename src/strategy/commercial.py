"""Pure commercial decision helpers for direct-channel and weekly pricing strategy."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from src.constants import CATEGORY_ASSUMPTIONS_COLUMNS, RESERVATION_CATEGORIES
from src.models import CategoryAssumptions
from src.validation import FieldValidationError, validate_non_negative, validate_percentage

DEFAULT_COMMISSION_RATE = 0.125
ACTION_SCENARIOS: tuple[tuple[str, float], ...] = (
    ("Protect Yield", 0.10),
    ("Hold", 0.0),
    ("Promote", -0.08),
)


def _require_mapping(name: str, value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FieldValidationError(f"{name} must be a mapping")
    return value


def _normalize_currency(field_name: str, value: Any) -> float:
    return validate_non_negative(field_name, value)


def _normalize_rate(field_name: str, value: Any) -> float:
    return validate_percentage(field_name, value)


def _normalize_category_assumptions(
    category_assumptions: Iterable[CategoryAssumptions | Mapping[str, Any]] | pd.DataFrame,
) -> tuple[CategoryAssumptions, ...]:
    if isinstance(category_assumptions, pd.DataFrame):
        actual_columns = tuple(category_assumptions.columns)
        if actual_columns != CATEGORY_ASSUMPTIONS_COLUMNS:
            missing = [column for column in CATEGORY_ASSUMPTIONS_COLUMNS if column not in category_assumptions.columns]
            unexpected = [column for column in category_assumptions.columns if column not in CATEGORY_ASSUMPTIONS_COLUMNS]
            problems: list[str] = []
            if missing:
                problems.append(f"missing columns: {missing}")
            if unexpected:
                problems.append(f"unexpected columns: {unexpected}")
            raise FieldValidationError(
                "category_assumptions must match the shared contract exactly "
                f"({', '.join(problems)})"
            )
        source_items: Iterable[CategoryAssumptions | Mapping[str, Any]] = category_assumptions.to_dict(
            orient="records"
        )
    else:
        source_items = category_assumptions

    normalized_items: list[CategoryAssumptions] = []
    for item in source_items:
        if isinstance(item, CategoryAssumptions):
            normalized_items.append(item)
            continue
        try:
            normalized_items.append(CategoryAssumptions.from_dict(dict(item)))
        except (TypeError, ValueError, KeyError) as exc:
            raise FieldValidationError(
                "category_assumptions entries must match the shared category schema exactly"
            ) from exc
    normalized = tuple(normalized_items)
    if len(normalized) != len(RESERVATION_CATEGORIES):
        raise FieldValidationError(
            "category_assumptions must contain exactly one entry for each canonical category"
        )

    categories = tuple(item.category for item in normalized)
    if categories != RESERVATION_CATEGORIES:
        raise FieldValidationError(
            "category_assumptions must include each canonical category exactly once and in the shared order"
        )
    return normalized


def _normalize_category_value_map(
    field_name: str,
    values: Mapping[str, Any],
) -> dict[str, float]:
    normalized_mapping = _require_mapping(field_name, values)
    actual_categories = tuple(normalized_mapping.keys())
    if actual_categories != RESERVATION_CATEGORIES:
        raise FieldValidationError(
            f"{field_name} must include each canonical category exactly once and in the shared order {RESERVATION_CATEGORIES}"
        )
    return {
        category: _normalize_currency(f"{field_name}.{category}", normalized_mapping[category])
        for category in RESERVATION_CATEGORIES
    }


def _extract_application_mapping(application_result: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(application_result, Mapping):
        raise FieldValidationError("application_result must be a mapping")
    if field_name not in application_result:
        raise FieldValidationError(f"application_result must include {field_name!r}")
    return _require_mapping(field_name, application_result[field_name])


def _extract_commission_rate_from_application(application_result: Mapping[str, Any]) -> float | None:
    strategic_assumptions = application_result.get("strategic_assumptions")
    if strategic_assumptions is None:
        return None
    if isinstance(strategic_assumptions, Mapping):
        if "third_party_commission_rate" not in strategic_assumptions:
            return None
        return validate_percentage(
            "application_result.strategic_assumptions.third_party_commission_rate",
            strategic_assumptions["third_party_commission_rate"],
        )
    if hasattr(strategic_assumptions, "third_party_commission_rate"):
        return validate_percentage(
            "application_result.strategic_assumptions.third_party_commission_rate",
            getattr(strategic_assumptions, "third_party_commission_rate"),
        )
    return None


def _resolve_commission_rate(
    application_result: Mapping[str, Any],
    commission_rate: float | None,
) -> float:
    if commission_rate is not None:
        return _normalize_rate("commission_rate", commission_rate)

    application_rate = _extract_commission_rate_from_application(application_result)
    if application_rate is not None:
        return application_rate
    return DEFAULT_COMMISSION_RATE


def _resolve_effective_forecast(application_result: Mapping[str, Any]) -> dict[str, float]:
    if "effective_forecast" in application_result:
        source = application_result["effective_forecast"]
    elif "forecast_result" in application_result and isinstance(application_result["forecast_result"], Mapping):
        forecast_result = application_result["forecast_result"]
        if "effective_forecast" not in forecast_result:
            raise FieldValidationError(
                "application_result.forecast_result must include effective_forecast when top-level effective_forecast is absent"
            )
        source = forecast_result["effective_forecast"]
    else:
        raise FieldValidationError("application_result must include effective_forecast")

    return _normalize_category_value_map("effective_forecast", _require_mapping("effective_forecast", source))


def _resolve_average_booking_value_by_category(
    category_assumptions: Iterable[CategoryAssumptions | Mapping[str, Any]] | pd.DataFrame,
) -> dict[str, float]:
    normalized = _normalize_category_assumptions(category_assumptions)
    return {
        item.category: _normalize_currency(
            f"category_assumptions[{item.category!r}].average_booking_value",
            item.average_booking_value,
        )
        for item in normalized
    }


def _resolve_deterministic_booking_processing_hours_per_agent(
    application_result: Mapping[str, Any],
) -> float:
    if "deterministic_staffing_result" in application_result:
        deterministic_staffing_result = _require_mapping(
            "application_result.deterministic_staffing_result",
            application_result["deterministic_staffing_result"],
        )
        if "booking_processing_hours_per_agent" in deterministic_staffing_result:
            return validate_non_negative(
                "application_result.deterministic_staffing_result.booking_processing_hours_per_agent",
                deterministic_staffing_result["booking_processing_hours_per_agent"],
            )

    if "booking_processing_hours_per_agent" in application_result:
        return validate_non_negative(
            "application_result.booking_processing_hours_per_agent",
            application_result["booking_processing_hours_per_agent"],
        )

    raise FieldValidationError(
        "application_result must include booking_processing_hours_per_agent"
    )


def _resolve_recommended_plan(application_result: Mapping[str, Any]) -> Mapping[str, Any]:
    if "recommended_plan" in application_result:
        return _require_mapping("application_result.recommended_plan", application_result["recommended_plan"])
    if "financial_recommendation" in application_result:
        financial_recommendation = _require_mapping(
            "application_result.financial_recommendation",
            application_result["financial_recommendation"],
        )
        if "recommended_staffing_record" in financial_recommendation:
            return _require_mapping(
                "application_result.financial_recommendation.recommended_staffing_record",
                financial_recommendation["recommended_staffing_record"],
            )
    raise FieldValidationError("application_result must include recommended_plan")


def _require_plan_value(plan: Mapping[str, Any], field_name: str) -> Any:
    if field_name not in plan:
        raise FieldValidationError(
            f"application_result.recommended_plan must include {field_name!r}"
        )
    return plan[field_name]


def _build_scenario(
    *,
    action: str,
    price_change: float,
    price_elasticity: float,
    forecast_by_category: Mapping[str, float],
    average_booking_value_by_category: Mapping[str, float],
    direct_capture_rate: float,
    commission_rate: float,
    promotion_cost: float,
    hold_net_revenue_after_channel_cost: float | None,
) -> dict[str, Any]:
    expected_bookings_by_category = {
        category: forecast_by_category[category] * (1.0 - (price_elasticity * price_change))
        for category in RESERVATION_CATEGORIES
    }
    gross_revenue_by_category = {
        category: expected_bookings_by_category[category]
        * average_booking_value_by_category[category]
        * (1.0 + price_change)
        for category in RESERVATION_CATEGORIES
    }
    expected_bookings = sum(expected_bookings_by_category.values())
    gross_revenue = sum(gross_revenue_by_category.values())
    commission_paid = gross_revenue * (1.0 - direct_capture_rate) * commission_rate
    commission_avoided = gross_revenue * direct_capture_rate * commission_rate
    campaign_cost = promotion_cost if action == "Promote" else 0.0
    net_revenue_after_channel_cost = gross_revenue - commission_paid - campaign_cost
    delta_vs_hold = (
        net_revenue_after_channel_cost - hold_net_revenue_after_channel_cost
        if hold_net_revenue_after_channel_cost is not None
        else 0.0
    )

    return {
        "action": action,
        "price_change": price_change,
        "expected_bookings": expected_bookings,
        "expected_bookings_by_category": expected_bookings_by_category,
        "gross_revenue": gross_revenue,
        "gross_revenue_by_category": gross_revenue_by_category,
        "commission_paid": commission_paid,
        "commission_avoided": commission_avoided,
        "campaign_cost": campaign_cost,
        "net_revenue_after_channel_cost": net_revenue_after_channel_cost,
        "delta_vs_hold": delta_vs_hold,
    }


def build_channel_strategy(
    *,
    annual_revenue: float = 80_000_000.0,
    commission_rate: float = 0.125,
    current_capture_rate: float = 0.0,
    target_capture_rate: float = 0.5,
    annual_operating_cost: float = 1_000_000.0,
) -> dict[str, Any]:
    """Build the annual direct-channel business case."""

    annual_revenue = _normalize_currency("annual_revenue", annual_revenue)
    commission_rate = _normalize_rate("commission_rate", commission_rate)
    current_capture_rate = _normalize_rate("current_capture_rate", current_capture_rate)
    target_capture_rate = _normalize_rate("target_capture_rate", target_capture_rate)
    annual_operating_cost = _normalize_currency(
        "annual_operating_cost",
        annual_operating_cost,
    )

    commission_if_all_agent = annual_revenue * commission_rate
    commission_paid_current = annual_revenue * (1.0 - current_capture_rate) * commission_rate
    commission_paid_target = annual_revenue * (1.0 - target_capture_rate) * commission_rate
    gross_commission_avoided = commission_if_all_agent - commission_paid_target
    incremental_commission_avoided = commission_paid_current - commission_paid_target
    net_annual_benefit = gross_commission_avoided - annual_operating_cost
    capture_gap_percentage_points = (target_capture_rate - current_capture_rate) * 100.0

    if target_capture_rate < current_capture_rate:
        status = "regressive"
        recommendation = (
            "Do not reduce direct-channel capture; set the target at or above the current rate."
        )
    elif target_capture_rate == current_capture_rate:
        status = "hold"
        recommendation = (
            "The target matches current direct-channel capture; increase it to create additional commission savings."
        )
    elif net_annual_benefit > 0.0:
        status = "favorable"
        recommendation = (
            "Proceed with the direct-channel capture target; the avoided commission exceeds the annual operating cost."
        )
    else:
        status = "unfavorable"
        recommendation = (
            "Revisit the direct-channel capture target; the annual operating cost exceeds the avoided commission."
        )

    return {
        "annual_revenue": annual_revenue,
        "commission_rate": commission_rate,
        "current_capture_rate": current_capture_rate,
        "target_capture_rate": target_capture_rate,
        "annual_operating_cost": annual_operating_cost,
        "commission_if_all_agent": commission_if_all_agent,
        "commission_paid_current": commission_paid_current,
        "commission_paid_target": commission_paid_target,
        "gross_commission_avoided": gross_commission_avoided,
        "incremental_commission_avoided": incremental_commission_avoided,
        "net_annual_benefit": net_annual_benefit,
        "capture_gap_percentage_points": capture_gap_percentage_points,
        "status": status,
        "recommendation": recommendation,
    }


def build_weekly_commercial_strategy(
    application_result: Mapping[str, Any],
    category_assumptions: Iterable[CategoryAssumptions | Mapping[str, Any]] | pd.DataFrame,
    *,
    direct_capture_rate: float = 0.5,
    price_elasticity: float = 0.8,
    promotion_cost: float = 2500.0,
    commission_rate: float | None = None,
) -> dict[str, Any]:
    """Build the weekly pricing and promotion recommendation."""

    if not isinstance(application_result, Mapping):
        raise FieldValidationError("application_result must be a mapping")

    direct_capture_rate = _normalize_rate("direct_capture_rate", direct_capture_rate)
    price_elasticity = _normalize_rate("price_elasticity", price_elasticity)
    promotion_cost = _normalize_currency("promotion_cost", promotion_cost)
    commission_rate = _resolve_commission_rate(application_result, commission_rate)

    effective_forecast = _resolve_effective_forecast(application_result)
    recommended_plan = _resolve_recommended_plan(application_result)
    average_booking_value_by_category = _resolve_average_booking_value_by_category(
        category_assumptions
    )
    booking_processing_hours_per_agent = _resolve_deterministic_booking_processing_hours_per_agent(
        application_result
    )

    probability_overflow_required = validate_percentage(
        "application_result.recommended_plan.probability_overflow_required",
        _require_plan_value(recommended_plan, "probability_overflow_required"),
    )
    expected_spare_capacity_hours = validate_non_negative(
        "application_result.recommended_plan.expected_spare_capacity_hours",
        _require_plan_value(recommended_plan, "expected_spare_capacity_hours"),
    )

    pressure_metrics = {
        "probability_overflow_required": probability_overflow_required,
        "expected_spare_capacity_hours": expected_spare_capacity_hours,
        "booking_processing_hours_per_agent": booking_processing_hours_per_agent,
        "overflow_guardrail_threshold": 0.20,
        "promote_guardrail_spare_capacity_threshold": booking_processing_hours_per_agent / 2.0,
    }

    hold_scenario = _build_scenario(
        action="Hold",
        price_change=0.0,
        price_elasticity=price_elasticity,
        forecast_by_category=effective_forecast,
        average_booking_value_by_category=average_booking_value_by_category,
        direct_capture_rate=direct_capture_rate,
        commission_rate=commission_rate,
        promotion_cost=promotion_cost,
        hold_net_revenue_after_channel_cost=None,
    )

    protect_scenario = _build_scenario(
        action=ACTION_SCENARIOS[0][0],
        price_change=ACTION_SCENARIOS[0][1],
        price_elasticity=price_elasticity,
        forecast_by_category=effective_forecast,
        average_booking_value_by_category=average_booking_value_by_category,
        direct_capture_rate=direct_capture_rate,
        commission_rate=commission_rate,
        promotion_cost=promotion_cost,
        hold_net_revenue_after_channel_cost=hold_scenario["net_revenue_after_channel_cost"],
    )
    promote_scenario = _build_scenario(
        action=ACTION_SCENARIOS[2][0],
        price_change=ACTION_SCENARIOS[2][1],
        price_elasticity=price_elasticity,
        forecast_by_category=effective_forecast,
        average_booking_value_by_category=average_booking_value_by_category,
        direct_capture_rate=direct_capture_rate,
        commission_rate=commission_rate,
        promotion_cost=promotion_cost,
        hold_net_revenue_after_channel_cost=hold_scenario["net_revenue_after_channel_cost"],
    )

    actions: list[dict[str, Any]] = [protect_scenario, hold_scenario, promote_scenario]

    if probability_overflow_required >= pressure_metrics["overflow_guardrail_threshold"]:
        recommended_action = "Protect Yield"
    elif (
        probability_overflow_required < 0.10
        and expected_spare_capacity_hours >= pressure_metrics["promote_guardrail_spare_capacity_threshold"]
    ):
        recommended_action = "Promote"
    else:
        recommended_action = "Hold"

    actions_by_name = {scenario["action"]: scenario for scenario in actions}
    hold_net_revenue_after_channel_cost = hold_scenario["net_revenue_after_channel_cost"]
    for scenario in actions:
        scenario["delta_vs_hold"] = (
            scenario["net_revenue_after_channel_cost"] - hold_net_revenue_after_channel_cost
        )
        scenario["is_recommended"] = scenario["action"] == recommended_action

    recommended_scenario = actions_by_name[recommended_action]
    rationale = (
        f"Protect Yield is recommended because overflow probability is {probability_overflow_required:.1%}, "
        f"which meets the 20% guardrail."
        if recommended_action == "Protect Yield"
        else (
            f"Promote is recommended because overflow probability is {probability_overflow_required:.1%} and spare capacity "
            f"({expected_spare_capacity_hours:.2f} hours) exceeds half of one agent's processing capacity "
            f"({pressure_metrics['promote_guardrail_spare_capacity_threshold']:.2f} hours)."
            if recommended_action == "Promote"
            else (
                f"Hold is recommended because overflow probability is {probability_overflow_required:.1%} and spare capacity "
                f"({expected_spare_capacity_hours:.2f} hours) does not justify a price move under the guardrails."
            )
        )
    )

    scenario_estimate_notice = (
        "All weekly commercial outputs are deterministic scenario estimates derived from the effective forecast, the "
        "elasticity assumption, and the stated commission rate; they are not a second-order demand forecast."
    )

    return {
        "effective_forecast": effective_forecast,
        "category_average_booking_value": average_booking_value_by_category,
        "commission_rate": commission_rate,
        "direct_capture_rate": direct_capture_rate,
        "price_elasticity": price_elasticity,
        "promotion_cost": promotion_cost,
        "pressure_metrics": pressure_metrics,
        "base_metrics": hold_scenario,
        "recommended_action": recommended_action,
        "recommended_price_change": recommended_scenario["price_change"],
        "rationale": rationale,
        "scenario_estimate_notice": scenario_estimate_notice,
        "actions": actions,
    }


__all__ = [
    "build_channel_strategy",
    "build_weekly_commercial_strategy",
]
