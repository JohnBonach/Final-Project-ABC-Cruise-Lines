# ABC Cruise Lines Reservation Staffing DSS

ABC Cruise Lines Reservation Staffing DSS is a Python and Streamlit decision support system for weekly reservation staffing. It forecasts category-level demand, estimates workload, evaluates staffing choices under uncertainty, and recommends a financially justified number of reservation agents.

## Setup

This project targets Python 3.10 or newer.

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Run The App

Start the Streamlit application with:

```powershell
streamlit run app.py
```

## Generate Synthetic Data

Rebuild the synthetic historical dataset with:

```powershell
python scripts/generate_synthetic_data.py --output data/synthetic_history.csv
```

Use `--seed` if you want to override the default reproducible seed from `config/defaults.json`.

## Test Suite

Run the documented regression suite with:

```powershell
python -m unittest tests.test_ui_bundle tests.test_end_to_end tests.test_decision tests.test_finance tests.test_simulation tests.test_forecasting tests.test_data tests.test_workload
```

## Repository Layout

- `app.py`: Streamlit entry point.
- `src/`: Core forecasting, simulation, finance, decision, operations, data, validation, and UI modules.
- `scripts/`: Command-line helpers for synthetic data generation, deterministic validation, and case-study runs.
- `config/`: Default assumptions and simulation configuration.
- `data/`: Synthetic history and saved validation/case-study artifacts.
- `tests/`: Unit, integration, and regression coverage.
- `requirements.txt`: Third-party Python dependencies.

## Main Assumptions

- The planning horizon is one week.
- Demand is modeled for three canonical reservation categories: `day_cruise`, `seven_night_cruise`, and `nine_night_cruise`.
- Historical data is synthetic and reproducible rather than pulled from a live reservation system.
- Staffing is evaluated in whole agents, with FTE shown as an analytical aid.
- The recommendation objective is total weekly operating cost:
  regular labor cost plus expected third-party overflow commission.
- Managers can set a minimum in-house coverage target, evaluate an exact manager staffing proposal, and optionally apply manual category forecast overrides before rerunning the analysis.

## Known Limitations

- The prototype does not do hourly scheduling or shift rostering.
- It does not model customer waiting-time behavior directly.
- It does not integrate with a real reservation system or live operational data.
- It does not optimize recruitment, training, or part-time staffing.
- It is designed for weekly tactical staffing, not full workforce management.

## Troubleshooting

- If `streamlit` is not found, reactivate the virtual environment and reinstall dependencies.
- If the app cannot find `data/synthetic_history.csv`, rerun the synthetic data command above.
- If a script or test fails because a file was edited locally, rerun the relevant generator or validation script to refresh the derived artifacts.
- If `python -m unittest ...` fails after dependency changes, reinstall from `requirements.txt` in a clean virtual environment.

## Useful Scripts

- `python scripts/run_validation_case.py` runs the deterministic validation case used for hand-checkable math.
- `python scripts/run_case_study.py` runs the probabilistic case study using the current coverage-target recommendation policy and writes a JSON report.
