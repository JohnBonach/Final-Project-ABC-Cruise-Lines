"""Commercial strategy Streamlit renderer for ABC Cruise Lines."""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd
import streamlit as st

COMMERCIAL_KEY_PREFIX = "commercial_"
DEFAULT_ANNUAL_COMMISSIONABLE_REVENUE = 80_000_000.0
DEFAULT_CURRENT_DIRECT_CAPTURE_RATE = 0.0
DEFAULT_TARGET_DIRECT_CAPTURE_RATE = 0.5
DEFAULT_ANNUAL_DSS_OPERATING_COST = 1_000_000.0
DEFAULT_WEEKLY_DIRECT_CAPTURE_RATE = 0.5
DEFAULT_PRICE_ELASTICITY = 0.8
DEFAULT_PROMOTION_COST = 2_500.0

_CHANNEL_BUSINESS_CASE_KEYS = (
    "business_case",
    "direct_channel_business_case",
    "summary",
    "kpis",
    "metrics",
)
_CHANNEL_SCENARIO_KEYS = (
    "commission_scenarios",
    "scenario_table",
    "scenarios",
    "comparison_table",
    "table",
)
_WEEKLY_RESULT_KEYS = (
    "weekly_strategy",
    "weekly_recommendation",
    "weekly_action",
    "decision",
    "summary",
    "kpis",
    "metrics",
)
_WEEKLY_ACTION_TABLE_KEYS = (
    "action_comparison",
    "comparison_table",
    "alternatives",
    "scenario_table",
    "table",
)


def commercial_control_key(name: str) -> str:
    return f"{COMMERCIAL_KEY_PREFIX}{name}"


def _format_currency(value: Any) -> str:
    amount = float(value)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    if amount >= 1_000_000:
        return f"{sign}${amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"{sign}${amount:,.0f}"
    return f"{sign}${amount:,.2f}".rstrip("0").rstrip(".")


def _format_percent(value: Any, *, places: int = 0) -> str:
    return f"{float(value) * 100.0:.{places}f}%"


def _format_signed_percent(value: Any, *, places: int = 0) -> str:
    amount = float(value) * 100.0
    sign = "+" if amount > 0 else ""
    return f"{sign}{amount:.{places}f}%"


def _format_decimal(value: Any, *, places: int = 2) -> str:
    return f"{float(value):.{places}f}"


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_mapping_value(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _coerce_float(value: Any, fallback: float) -> float:
    try:
        if value is None:
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _resolve_section(payload: Mapping[str, Any], section_keys: Sequence[str]) -> Mapping[str, Any]:
    for key in section_keys:
        candidate = payload.get(key)
        if isinstance(candidate, Mapping):
            return candidate
    return payload


def _frame_from_source(source: Any) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        return source.copy(deep=True)
    if isinstance(source, Sequence) and not isinstance(source, (str, bytes, bytearray)):
        return pd.DataFrame(list(source))
    if isinstance(source, Mapping):
        if source and all(isinstance(value, Mapping) for value in source.values()):
            rows = []
            for label, row in source.items():
                row_payload = dict(row)
                row_payload.setdefault("scenario", label)
                rows.append(row_payload)
            return pd.DataFrame(rows)
        return pd.DataFrame([dict(source)])
    return pd.DataFrame()


def _extract_frame(payload: Mapping[str, Any], keys: Sequence[str]) -> pd.DataFrame:
    for key in keys:
        candidate = payload.get(key)
        if candidate is not None:
            frame = _frame_from_source(candidate)
            if not frame.empty or isinstance(candidate, pd.DataFrame):
                return frame
    return pd.DataFrame()


def _invoke_with_supported_kwargs(func: Any, /, *args: Any, **kwargs: Any) -> Any:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return func(*args, **kwargs)

    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        return func(*args, **kwargs)

    supported = {
        name: value
        for name, value in kwargs.items()
        if name in signature.parameters
        and signature.parameters[name].kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    return func(*args, **supported)


def _lookup_numeric(
    payload: Mapping[str, Any],
    aliases: Sequence[str],
    fallback: float,
) -> float:
    for alias in aliases:
        if alias in payload:
            return _coerce_float(payload[alias], fallback)
    return fallback


def _build_channel_business_case(
    application_result: Mapping[str, Any],
    strategy_result: Mapping[str, Any],
    annual_commissionable_revenue: float,
    current_direct_capture_rate: float,
    target_direct_capture_rate: float,
    annual_dss_operating_cost: float,
    commission_rate: float,
) -> dict[str, float]:
    section = _resolve_section(strategy_result, _CHANNEL_BUSINESS_CASE_KEYS)
    return {
        "annual_commissionable_revenue": _lookup_numeric(
            section,
            (
                "annual_commissionable_revenue",
                "annual_revenue",
                "commissionable_revenue",
                "revenue",
            ),
            annual_commissionable_revenue,
        ),
        "current_direct_capture_rate": _lookup_numeric(
            section,
            (
                "current_direct_capture_rate",
                "baseline_direct_capture_rate",
                "current_capture_rate",
                "direct_capture_rate_current",
            ),
            current_direct_capture_rate,
        ),
        "target_direct_capture_rate": _lookup_numeric(
            section,
            (
                "target_direct_capture_rate",
                "direct_capture_rate",
                "capture_target",
                "target_capture_rate",
            ),
            target_direct_capture_rate,
        ),
        "annual_dss_operating_cost": _lookup_numeric(
            section,
            (
                "annual_dss_operating_cost",
                "annual_operating_cost",
                "dss_operating_cost",
                "operating_cost",
            ),
            annual_dss_operating_cost,
        ),
        "commission_rate": _lookup_numeric(
            section,
            ("commission_rate", "third_party_commission_rate", "agent_commission_rate"),
            commission_rate,
        ),
        "current_commission_paid": _lookup_numeric(
            section,
            (
                "current_commission_paid",
                "commission_paid_current",
                "baseline_commission_paid",
            ),
            annual_commissionable_revenue * (1.0 - current_direct_capture_rate) * commission_rate,
        ),
        "target_commission_paid": _lookup_numeric(
            section,
            (
                "target_commission_paid",
                "commission_paid_target",
                "scenario_commission_paid",
            ),
            annual_commissionable_revenue * (1.0 - target_direct_capture_rate) * commission_rate,
        ),
        "gross_commission_avoided": _lookup_numeric(
            section,
            ("gross_commission_avoided", "commission_avoided", "commission_savings"),
            annual_commissionable_revenue
            * (target_direct_capture_rate - current_direct_capture_rate)
            * commission_rate,
        ),
        "net_annual_benefit": _lookup_numeric(
            section,
            ("net_annual_benefit", "net_benefit", "annual_net_benefit"),
            annual_commissionable_revenue
            * (target_direct_capture_rate - current_direct_capture_rate)
            * commission_rate
            - annual_dss_operating_cost,
        ),
    }


def _build_channel_scenario_frame(
    strategy_result: Mapping[str, Any],
    business_case: Mapping[str, float],
) -> pd.DataFrame:
    frame = _extract_frame(strategy_result, _CHANNEL_SCENARIO_KEYS)
    if not frame.empty:
        return frame

    target_capture = business_case["target_direct_capture_rate"]
    current_capture = business_case["current_direct_capture_rate"]
    revenue = business_case["annual_commissionable_revenue"]
    commission_rate = business_case["commission_rate"]
    annual_dss_operating_cost = business_case["annual_dss_operating_cost"]

    stretch_capture = min(1.0, max(target_capture, current_capture) + 0.10)
    rows = [
        {
            "scenario": "Current",
            "direct_capture_rate": current_capture,
            "commission_paid": revenue * (1.0 - current_capture) * commission_rate,
            "commission_avoided": 0.0,
            "net_annual_benefit": -annual_dss_operating_cost,
        },
        {
            "scenario": "Target",
            "direct_capture_rate": target_capture,
            "commission_paid": business_case["target_commission_paid"],
            "commission_avoided": business_case["gross_commission_avoided"],
            "net_annual_benefit": business_case["net_annual_benefit"],
        },
        {
            "scenario": "Stretch",
            "direct_capture_rate": stretch_capture,
            "commission_paid": revenue * (1.0 - stretch_capture) * commission_rate,
            "commission_avoided": revenue * (stretch_capture - current_capture) * commission_rate,
            "net_annual_benefit": revenue * (stretch_capture - current_capture) * commission_rate
            - annual_dss_operating_cost,
        },
    ]
    return pd.DataFrame(rows)


def _build_channel_metrics(business_case: Mapping[str, float]) -> list[dict[str, str]]:
    return [
        {
            "label": "Annual commissionable revenue",
            "value": _format_currency(business_case["annual_commissionable_revenue"]),
            "help": "Scenario estimate",
        },
        {
            "label": "Current commission paid",
            "value": _format_currency(business_case["current_commission_paid"]),
            "help": f"{_format_percent(business_case['current_direct_capture_rate'])} direct capture",
        },
        {
            "label": "Target commission paid",
            "value": _format_currency(business_case["target_commission_paid"]),
            "help": f"{_format_percent(business_case['target_direct_capture_rate'])} direct capture",
        },
        {
            "label": "Gross commission avoided",
            "value": _format_currency(business_case["gross_commission_avoided"]),
            "help": "Before DSS operating cost",
        },
        {
            "label": "Net annual benefit",
            "value": _format_currency(business_case["net_annual_benefit"]),
            "help": "After DSS operating cost",
        },
    ]


def _build_weekly_action_frame(
    strategy_result: Mapping[str, Any],
) -> pd.DataFrame:
    frame = _extract_frame(strategy_result, _WEEKLY_ACTION_TABLE_KEYS)
    if not frame.empty:
        return frame

    section = _resolve_section(strategy_result, _WEEKLY_RESULT_KEYS)
    actions = section.get("actions") if isinstance(section, Mapping) else None
    if isinstance(actions, Sequence) and not isinstance(actions, (str, bytes, bytearray)):
        return pd.DataFrame(list(actions))
    return pd.DataFrame()


def _normalize_action_name(action: Any) -> str:
    text = str(action or "").strip()
    if not text:
        return "Hold"
    normalized = text.lower().replace("_", " ").replace("-", " ")
    if normalized in {"protect", "protect yield", "raise price", "up"}:
        return "Protect Yield"
    if normalized in {"promote", "discount promote", "discount / promote", "down"}:
        return "Promote"
    if normalized in {"hold", "hold fares"}:
        return "Hold"
    return text


def _build_weekly_metrics(
    strategy_result: Mapping[str, Any],
    action_frame: pd.DataFrame,
    recommended_action: str,
) -> list[dict[str, str]]:
    section = _resolve_section(strategy_result, _WEEKLY_RESULT_KEYS)
    payload = section if isinstance(section, Mapping) else {}
    pressure_metrics = payload.get("pressure_metrics") if isinstance(payload, Mapping) else None
    recommended_price_change = payload.get("recommended_price_change") if isinstance(payload, Mapping) else None

    if isinstance(pressure_metrics, Mapping) and pressure_metrics:
        rows: list[dict[str, str]] = []
        if recommended_price_change is not None:
            rows.append(
                {
                    "label": "Recommended price change",
                    "value": _format_signed_percent(recommended_price_change),
                    "help": recommended_action,
                }
            )
        for key in (
            "probability_overflow_required",
            "expected_spare_capacity_hours",
            "booking_processing_hours_per_agent",
            "promote_guardrail_spare_capacity_threshold",
        ):
            if key not in pressure_metrics:
                continue
            value = pressure_metrics[key]
            if "probability" in key:
                display = _format_percent(value)
            else:
                display = _format_decimal(value)
            rows.append(
                {
                    "label": key.replace("_", " ").title(),
                    "value": display,
                    "help": recommended_action,
                }
            )
        if rows:
            return rows[:4]

    if isinstance(payload, Mapping) and payload.get("kpis") is not None:
        kpis = payload["kpis"]
    elif isinstance(payload, Mapping) and payload.get("metrics") is not None:
        kpis = payload["metrics"]
    else:
        kpis = None

    if isinstance(kpis, Mapping):
        rows: list[dict[str, str]] = []
        for key, value in kpis.items():
            label = str(key).replace("_", " ").strip().title()
            if isinstance(value, (int, float)) and "rate" in label.lower():
                display = _format_percent(value)
            elif isinstance(value, (int, float)) and abs(float(value)) >= 1000:
                display = _format_currency(value)
            elif isinstance(value, (int, float)):
                display = _format_decimal(value)
            else:
                display = str(value)
            rows.append({"label": label, "value": display, "help": recommended_action})
        return rows[:4]

    if action_frame.empty:
        return [{"label": "Recommended action", "value": recommended_action, "help": "Model output"}]

    selected_row = action_frame.copy()
    action_column = _select_action_column(selected_row)
    if action_column is not None:
        selected_row = selected_row.loc[
            selected_row[action_column].map(_normalize_action_name) == recommended_action
        ]
    if selected_row.empty:
        selected_row = action_frame.head(1)
    row = selected_row.iloc[0].to_dict()
    metrics: list[dict[str, str]] = []
    preferred_columns = (
        "recommended_price_change",
        "price_change",
        "expected_net_value",
        "net_value",
        "net_revenue_after_channel_cost",
        "score",
        "expected_revenue",
        "gross_revenue",
        "revenue",
        "promotion_cost",
        "campaign_cost",
        "expected_commission",
        "commission_paid",
        "commission_avoided",
        "demand_uplift_pct",
        "expected_bookings",
        "load_factor",
        "direct_capture_rate",
    )
    for column in preferred_columns:
        if column in row and row[column] is not None:
            value = row[column]
            label = column.replace("_", " ").title()
            if "rate" in column or "pct" in column or "percentage" in column or "load_factor" in column:
                display = _format_percent(value)
            elif "cost" in column or "value" in column or "revenue" in column or "commission" in column:
                display = _format_currency(value)
            else:
                display = _format_decimal(value)
            metrics.append({"label": label, "value": display, "help": recommended_action})
        if len(metrics) == 4:
            break
    if not metrics:
        metrics.append({"label": "Recommended action", "value": recommended_action, "help": "Model output"})
    return metrics


def _select_action_column(frame: pd.DataFrame) -> str | None:
    for column in frame.columns:
        if column.lower() in {"action", "scenario", "plan"}:
            return column
    return None


def _select_numeric_column(frame: pd.DataFrame) -> str | None:
    preferred = (
        "commission_paid",
        "gross_commission_avoided",
        "net_annual_benefit",
        "net_revenue_after_channel_cost",
        "expected_net_value",
        "net_value",
        "score",
        "expected_revenue",
        "gross_revenue",
        "revenue",
        "promotion_cost",
        "campaign_cost",
        "expected_commission",
        "commission_avoided",
        "recommended_price_change",
        "price_change",
    )
    for column in preferred:
        if column in frame.columns and pd.api.types.is_numeric_dtype(frame[column]):
            return column
    for column in frame.columns:
        if pd.api.types.is_numeric_dtype(frame[column]):
            return column
    return None


def _render_metric_row(metrics: Sequence[Mapping[str, str]]) -> None:
    if not metrics:
        return
    cols = st.columns(min(4, len(metrics)), gap="small")
    for index, metric in enumerate(metrics):
        with cols[index % len(cols)]:
            st.metric(metric["label"], metric["value"], help=metric.get("help"))


def _inject_commercial_css() -> None:
    st.markdown(
        """
        <style>
        .commercial-shell {
            background:
                radial-gradient(circle at top right, rgba(11, 110, 138, 0.10), transparent 26%),
                linear-gradient(180deg, #F7FBFC 0%, #EEF4F7 100%);
            border: 1px solid rgba(23, 50, 77, 0.08);
            border-radius: 22px;
            padding: 20px 22px 14px 22px;
            box-shadow: 0 10px 28px rgba(17, 43, 60, 0.06);
        }
        .commercial-eyebrow {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.76rem;
            color: #5B7185;
            margin-bottom: 6px;
        }
        .commercial-title {
            color: #17324D;
            font-size: 1.45rem;
            font-weight: 800;
            line-height: 1.15;
            margin: 0 0 8px 0;
        }
        .commercial-subtitle {
            color: #38556B;
            font-size: 0.98rem;
            line-height: 1.55;
            margin: 0 0 10px 0;
        }
        .scenario-banner {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 10px 14px;
            border-radius: 999px;
            background: #17324D;
            color: #FFFFFF;
            font-weight: 700;
            margin: 6px 0 12px 0;
        }
        .commercial-card {
            background: rgba(255,255,255,0.95);
            border: 1px solid #D8E3EA;
            border-radius: 18px;
            padding: 18px 18px 14px 18px;
            box-shadow: 0 8px 20px rgba(17, 43, 60, 0.05);
            min-height: 100%;
        }
        .commercial-card .card-label {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.11em;
            color: #5B7185;
            margin-bottom: 6px;
        }
        .commercial-card .card-title {
            color: #17324D;
            font-size: 1.25rem;
            font-weight: 800;
            margin-bottom: 6px;
        }
        .commercial-card .card-body {
            color: #38556B;
            font-size: 0.95rem;
            line-height: 1.55;
        }
        .commercial-card.protect {
            border-left: 5px solid #C9A14A;
        }
        .commercial-card.hold {
            border-left: 5px solid #0B6E8A;
        }
        .commercial-card.promote {
            border-left: 5px solid #6BBF9B;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_commercial_card(action: str, rationale: str, strategy_result: Mapping[str, Any]) -> None:
    slug = action.lower().replace(" ", "-")
    direction = {
        "protect yield": "protect",
        "hold": "hold",
        "promote": "promote",
    }.get(action.lower(), "hold")
    card_body = rationale or "The model returned no rationale, so the action is shown as a planning placeholder."
    st.markdown(
        f"""
        <div class="commercial-card {direction}">
            <div class="card-label">Recommended weekly action</div>
            <div class="card-title">{action}</div>
            <div class="card-body">{card_body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if isinstance(strategy_result, Mapping):
        signal = strategy_result.get("signal") or strategy_result.get("decision_signal")
        if signal is not None:
            st.caption(f"Decision signal: {signal}")


def _lookup_strategy_function(module: Any, name: str) -> Any:
    func = getattr(module, name, None)
    if func is None:
        raise AttributeError(f"{module.__name__} is missing required function {name}")
    return func


def render_commercial_strategy(
    application_result: Mapping[str, Any],
    category_assumptions: Sequence[Mapping[str, Any]],
    commission_rate: float,
) -> None:
    """Render the commercial strategy tab."""

    _inject_commercial_css()
    st.markdown(
        """
        <div class="commercial-shell">
            <div class="commercial-eyebrow">Commercial Strategy</div>
            <div class="commercial-title">Direct-channel economics and weekly pricing action</div>
            <div class="commercial-subtitle">
                Use the controls below to review the annual direct-booking business case and the
                next-week Protect Yield / Hold / Promote recommendation.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="scenario-banner">Scenario estimates</div>', unsafe_allow_html=True)
    st.caption("All values on this tab are scenario estimates, not observed operating results.")

    strategy_module = importlib.import_module("src.strategy.commercial")
    build_channel_strategy = _lookup_strategy_function(strategy_module, "build_channel_strategy")
    build_weekly_commercial_strategy = _lookup_strategy_function(
        strategy_module,
        "build_weekly_commercial_strategy",
    )

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("#### Direct-Channel Business Case")
        st.caption("Annual planning controls for in-house reservation capture.")
        revenue = st.number_input(
            "Annual commissionable revenue ($)",
            min_value=0.0,
            step=1_000_000.0,
            value=DEFAULT_ANNUAL_COMMISSIONABLE_REVENUE,
            key=commercial_control_key("annual_commissionable_revenue"),
        )
        capture_cols = st.columns(2, gap="small")
        with capture_cols[0]:
            current_capture = st.slider(
                "Current direct capture",
                min_value=0.0,
                max_value=100.0,
                value=DEFAULT_CURRENT_DIRECT_CAPTURE_RATE * 100.0,
                step=1.0,
                format="%.0f%%",
                key=commercial_control_key("current_direct_capture_percent"),
            ) / 100.0
        with capture_cols[1]:
            target_capture = st.slider(
                "Target direct capture",
                min_value=0.0,
                max_value=100.0,
                value=DEFAULT_TARGET_DIRECT_CAPTURE_RATE * 100.0,
                step=1.0,
                format="%.0f%%",
                key=commercial_control_key("target_direct_capture_percent"),
            ) / 100.0
        annual_dss_cost = st.number_input(
            "Annual DSS operating cost ($)",
            min_value=0.0,
            step=100_000.0,
            value=DEFAULT_ANNUAL_DSS_OPERATING_COST,
            key=commercial_control_key("annual_dss_operating_cost"),
        )

        channel_result = build_channel_strategy(
            annual_revenue=revenue,
            current_capture_rate=current_capture,
            target_capture_rate=target_capture,
            annual_operating_cost=annual_dss_cost,
            commission_rate=commission_rate,
        )
        if not isinstance(channel_result, Mapping):
            channel_result = {}

        business_case = _build_channel_business_case(
            application_result,
            channel_result,
            float(revenue),
            float(current_capture),
            float(target_capture),
            float(annual_dss_cost),
            float(commission_rate),
        )
        metrics = _build_channel_metrics(business_case)
        _render_metric_row(metrics[:3])
        _render_metric_row(metrics[3:])
        channel_status = str(channel_result.get("status", "")).strip().lower()
        channel_recommendation = str(channel_result.get("recommendation", "")).strip()
        if channel_recommendation:
            if channel_status == "favorable":
                st.success(channel_recommendation)
            elif channel_status in {"regressive", "unfavorable"}:
                st.warning(channel_recommendation)
            else:
                st.info(channel_recommendation)
        st.caption(
            "Baseline path at 0% current capture and 50% target capture produces about $5.0M of gross commission avoided and $4.0M net after the DSS cost."
        )

        scenario_frame = _build_channel_scenario_frame(channel_result, business_case)
        if not scenario_frame.empty:
            st.dataframe(scenario_frame, width="stretch", hide_index=True)
            chart_column = _first_mapping_value(
                {name: name for name in scenario_frame.columns},
                "commission_paid",
                "gross_commission_avoided",
                "net_annual_benefit",
            )
            if chart_column is not None:
                scenario_chart = scenario_frame.copy()
                action_column = _select_action_column(scenario_chart)
                if action_column is not None:
                    scenario_chart = scenario_chart.set_index(action_column)[[chart_column]]
                st.bar_chart(scenario_chart)

    with right:
        st.markdown("#### Weekly Commercial Action")
        st.caption("Weekly demand-shaping controls for the next sailing cycle.")
        weekly_capture = st.slider(
            "Weekly direct capture",
            min_value=0.0,
            max_value=100.0,
            value=DEFAULT_WEEKLY_DIRECT_CAPTURE_RATE * 100.0,
            step=1.0,
            format="%.0f%%",
            key=commercial_control_key("weekly_direct_capture_percent"),
        ) / 100.0
        weekly_elasticity = st.slider(
            "Price elasticity",
            min_value=0.0,
            max_value=1.0,
            value=DEFAULT_PRICE_ELASTICITY,
            step=0.05,
            format="%.2f",
            key=commercial_control_key("weekly_price_elasticity"),
        )
        weekly_promotion_cost = st.number_input(
            "Promotion cost ($)",
            min_value=0.0,
            step=250.0,
            value=DEFAULT_PROMOTION_COST,
            key=commercial_control_key("weekly_promotion_cost"),
        )

        weekly_result = build_weekly_commercial_strategy(
            application_result,
            category_assumptions,
            direct_capture_rate=weekly_capture,
            price_elasticity=weekly_elasticity,
            promotion_cost=weekly_promotion_cost,
            commission_rate=commission_rate,
        )
        if not isinstance(weekly_result, Mapping):
            weekly_result = {}

        weekly_section = _resolve_section(weekly_result, _WEEKLY_RESULT_KEYS)
        recommended_action = _normalize_action_name(
            _first_mapping_value(
                weekly_section,
                "recommended_action",
                "action_recommendation",
                "decision",
                "recommended_decision",
                "strategy_decision",
            )
        )
        rationale = str(
            _first_mapping_value(
                weekly_section,
                "rationale",
                "reason",
                "explanation",
                "summary",
                "narrative",
            )
            or ""
        )

        _render_commercial_card(recommended_action, rationale, weekly_result)
        weekly_action_frame = _build_weekly_action_frame(weekly_result)
        metrics = _build_weekly_metrics(weekly_result, weekly_action_frame, recommended_action)
        _render_metric_row(metrics)

        if not weekly_action_frame.empty:
            st.dataframe(weekly_action_frame, width="stretch", hide_index=True)
            action_column = _select_action_column(weekly_action_frame)
            chart_column = _select_numeric_column(weekly_action_frame)
            if action_column is not None and chart_column is not None:
                chart_frame = weekly_action_frame[[action_column, chart_column]].copy()
                chart_frame = chart_frame.set_index(action_column)
                st.bar_chart(chart_frame)
