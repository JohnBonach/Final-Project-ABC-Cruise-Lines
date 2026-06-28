# ABC Cruise Lines Voyage Command DSS

Voyage Command is a Python and Streamlit decision support system for ABC Cruise Lines. It forecasts reservation demand, evaluates weekly staffing choices under uncertainty, models the annual direct-booking business case, and recommends a transparent weekly commercial action.

The project is a fictional class prototype. Historical demand and commercial assumptions are synthetic and are labeled as scenario estimates in the interface.

The published build number appears in the top-left masthead. Update `APP_VERSION` in `src/constants.py` manually before publishing a new version.

For a plain-language walkthrough of every tab, control, output, guardrail, and formula, see [`VOYAGE_COMMAND_USER_GUIDE.md`](VOYAGE_COMMAND_USER_GUIDE.md).

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
- The direct-channel baseline uses $80M annual commissionable revenue, a 12.5% blended commission, 0% current direct capture, a 50% target, and $1M annual DSS operating cost. These editable assumptions reproduce the case brief's $4M net annual benefit.
- The weekly commercial recommender compares Protect Yield (+10%), Hold (0%), and Promote (-8%) scenario actions with a synthetic price-elasticity assumption and explicit operational guardrails.

## Decision Modules

- `Command Deck`: week-ahead recommendation, demand signals, risk, and manager brief.
- `Workforce Planner`: coverage policy, manager staffing proposal, forecast overrides, and detailed assumptions.
- `Commercial Strategy`: annual direct-channel economics plus weekly pricing/promotion action.
- `Scenarios & Evidence`: P25/P50/P90 demand outlooks, risk-cost evidence, calculations, methodology, and exports.

## Known Limitations

- The prototype does not do hourly scheduling or shift rostering.
- It does not model customer waiting-time behavior directly.
- It does not integrate with a real reservation system or live operational data.
- It does not optimize recruitment, training, or part-time staffing.
- Commercial outputs are deterministic planning scenarios, not causal demand forecasts or production revenue-management instructions.
- It is designed for weekly tactical decision support, not full workforce, fleet, or revenue management.

## Troubleshooting

- If `streamlit` is not found, reactivate the virtual environment and reinstall dependencies.
- If the app cannot find `data/synthetic_history.csv`, rerun the synthetic data command above.
- If a script or test fails because a file was edited locally, rerun the relevant generator or validation script to refresh the derived artifacts.
- If `python -m unittest ...` fails after dependency changes, reinstall from `requirements.txt` in a clean virtual environment.

## Useful Scripts

- `python scripts/run_validation_case.py` runs the deterministic validation case used for hand-checkable math.
- `python scripts/run_case_study.py` runs the probabilistic case study using the current coverage-target recommendation policy and writes a JSON report.
