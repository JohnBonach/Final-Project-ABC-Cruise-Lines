"""Deterministic synthetic historical-demand generation for ABC Cruise Lines."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.constants import HISTORICAL_DEMAND_COLUMNS, RESERVATION_CATEGORIES
from src.validation import load_defaults_config

DEFAULTS_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "defaults.json"
DEFAULT_HISTORY_SEED = 510

APPROVED_SYNTHETIC_HISTORY_ROWS: tuple[dict[str, object], ...] = (
    {"week_id": "2026-W15", "week_start": "2026-04-06", "day_cruise": 150, "seven_night_cruise": 95, "nine_night_cruise": 45, "staffing_agents": 8},
    {"week_id": "2026-W16", "week_start": "2026-04-13", "day_cruise": 165, "seven_night_cruise": 100, "nine_night_cruise": 50, "staffing_agents": 8},
    {"week_id": "2026-W17", "week_start": "2026-04-20", "day_cruise": 175, "seven_night_cruise": 105, "nine_night_cruise": 50, "staffing_agents": 8},
    {"week_id": "2026-W18", "week_start": "2026-04-27", "day_cruise": 160, "seven_night_cruise": 92, "nine_night_cruise": 43, "staffing_agents": 8},
    {"week_id": "2026-W19", "week_start": "2026-05-04", "day_cruise": 180, "seven_night_cruise": 110, "nine_night_cruise": 55, "staffing_agents": 8},
    {"week_id": "2026-W20", "week_start": "2026-05-11", "day_cruise": 155, "seven_night_cruise": 98, "nine_night_cruise": 47, "staffing_agents": 8},
    {"week_id": "2026-W21", "week_start": "2026-05-18", "day_cruise": 145, "seven_night_cruise": 90, "nine_night_cruise": 45, "staffing_agents": 8},
    {"week_id": "2026-W22", "week_start": "2026-05-25", "day_cruise": 190, "seven_night_cruise": 120, "nine_night_cruise": 60, "staffing_agents": 8},
    {"week_id": "2026-W23", "week_start": "2026-06-01", "day_cruise": 210, "seven_night_cruise": 135, "nine_night_cruise": 70, "staffing_agents": 9},
    {"week_id": "2026-W24", "week_start": "2026-06-08", "day_cruise": 230, "seven_night_cruise": 150, "nine_night_cruise": 80, "staffing_agents": 10},
    {"week_id": "2026-W25", "week_start": "2026-06-15", "day_cruise": 300, "seven_night_cruise": 200, "nine_night_cruise": 130, "staffing_agents": 12},
    {"week_id": "2026-W26", "week_start": "2026-06-22", "day_cruise": 195, "seven_night_cruise": 125, "nine_night_cruise": 70, "staffing_agents": 9},
)


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


def generate_synthetic_history(
    config: dict[str, Any] | None = None,
    seed: int | str | None = None,
) -> pd.DataFrame:
    """Return the exact approved baseline history for the restored backend."""

    _coerce_defaults_config(config)
    if seed not in (None, DEFAULT_HISTORY_SEED, "510", 510):
        raise ValueError(
            "the approved synthetic history is fixed and only supports the baseline seed 510"
        )

    history = pd.DataFrame(APPROVED_SYNTHETIC_HISTORY_ROWS, columns=HISTORICAL_DEMAND_COLUMNS)
    integer_columns = list(RESERVATION_CATEGORIES) + ["staffing_agents"]
    history[integer_columns] = history[integer_columns].astype("int64")
    history["week_start"] = history["week_start"].astype("string")
    return history


__all__ = [
    "APPROVED_SYNTHETIC_HISTORY_ROWS",
    "DEFAULTS_CONFIG_PATH",
    "DEFAULT_HISTORY_SEED",
    "generate_synthetic_history",
]
