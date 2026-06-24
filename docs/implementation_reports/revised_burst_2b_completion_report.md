# Revised Burst 2B Completion Report

Generation date: 2026-06-24

## 1. Starting Branch, Commit, and Working-Tree State

- Branch at burst start: `main`
- Commit at burst start: `ad55b67c13fbd143e2991dea003d85c3a4848706`
- Working tree at burst start: not clean
- Starting dirty state matched the expected post-Burst-1 and post-Revised-Burst-2A uncommitted source/test/report changes plus generated `__pycache__` artifacts

## 2. Revised Burst 2A Verification Result

Revised Burst 2A was revalidated from the repository before editing.

Verified in code and/or tests:

- exact manager-proposed staffing evaluation remained active
- below-floor and above-cap evaluations remained unclamped
- previous-week staffing context remained active
- recommendation independence remained intact
- feasibility statuses remained:
  - `below_operating_floor`
  - `within_operating_range`
  - `above_inhouse_capacity`
- feasibility warnings remained active
- `recommendation_manager_comparison` remained present
- comparison difference direction remained `manager value - recommendation value`
- adaptive comparison narrative remained present
- staffing risk-cost records remained present
- Revised Burst 2A tests remained present
- the application still launched

Pre-edit full-suite rerun:

- Command: `python -m unittest discover -s tests`
- Result: `80/80` passed
- Match to Revised Burst 2A report: yes

## 3. Intervening Changes, If Any

No material repository inconsistency was found between the persisted Revised Burst 2A report and the actual repository.

Intervening uncommitted state before Revised Burst 2B remained the expected carried-forward work:

- retained Burst 1 source/config/test/report/spec changes
- retained Revised Burst 2A source/test/report changes
- generated `__pycache__` updates from prior verification runs

## 4. Files Modified

Direct Revised Burst 2B code/report edits:

- `src/models.py`
- `src/orchestration.py`
- `src/simulation/monte_carlo.py`
- `src/ui/charts.py`
- `src/ui/components.py`
- `tests/test_end_to_end.py`
- `tests/test_simulation.py`
- `tests/test_ui_bundle.py`
- `docs/implementation_reports/revised_burst_2b_completion_report.md`

Generated artifacts updated during verification:

- `__pycache__/...`
- `src/**/__pycache__/...`
- `tests/**/__pycache__/...`

## 5. Quantile Convention Used

Representative workload targets use the explicit `linear` quantile convention.

Implementation detail:

- function: `pandas.Series.quantile(percentile, interpolation="linear")`
- recorded constant: `OUTLOOK_QUANTILE_CONVENTION = "linear"`

## 6. Representative-Row Selection Algorithm

Representative outlook rows now use this deterministic procedure:

1. Complete the Monte Carlo simulation into the canonical workload table.
2. Order rows stably by:
   - `total_workload_hours`
   - `simulation_id`
3. For each requested outlook percentile:
   - calculate the target workload using the shared `linear` quantile convention
   - rank candidate completed rows by absolute distance to that target
   - prefer an unused row before any reused row
   - break equal-distance ties with lower `simulation_id`
   - preserve nondecreasing selected workloads across ascending percentiles
4. Reuse a row only if no distinct candidate remains under that deterministic ordering rule.
5. Return diagnostics with target workloads, selected workloads, selected row IDs, reuse information, and ordering-invariant status.

No synthetic category combinations are created.

Only actual completed Monte Carlo rows are used.

## 7. Stable Row-Identity Method

Stable representative-row identity uses the existing simulation contract field:

- row identity field: `simulation_id`

That field is preserved from sampled demand rows through the completed workload table and returned as:

- outlook field: `simulation_row_id`
- diagnostics field: `row_identity_field = "simulation_id"`

## 8. P25 Baseline Output

Baseline `Lower Demand — P25` outlook:

```python
{
    "outlook_name": "Lower Demand",
    "percentile": 0.25,
    "percentile_label": "P25",
    "simulation_row_id": 1859,
    "representative_row_reused": False,
    "demand_by_category": {
        "day_cruise": 213.0,
        "seven_night_cruise": 142.0,
        "nine_night_cruise": 80.0,
    },
    "total_bookings": 435.0,
    "workload_hours_by_category": {
        "day_cruise": 28.4,
        "seven_night_cruise": 52.06666666666667,
        "nine_night_cruise": 37.333333333333336,
    },
    "total_workload_hours": 117.80000000000001,
    "raw_required_fte": 9.424000000000001,
    "unconstrained_required_agents": 10,
    "recommended_inhouse_agents_for_outlook": 10,
    "spare_capacity_hours": 7.199999999999989,
    "overflow_workload_hours": 0.0,
    "overflow_bookings_by_category": {
        "day_cruise": 0.0,
        "seven_night_cruise": 0.0,
        "nine_night_cruise": 0.0,
    },
    "regular_labor_cost": 8800.0,
    "overflow_commission": 0.0,
    "total_weekly_operating_cost": 8800.0,
}
```

## 9. P50 Baseline Output

Baseline `Central Demand — P50` outlook:

```python
{
    "outlook_name": "Central Demand",
    "percentile": 0.5,
    "percentile_label": "P50",
    "simulation_row_id": 248,
    "representative_row_reused": False,
    "demand_by_category": {
        "day_cruise": 221.0,
        "seven_night_cruise": 157.0,
        "nine_night_cruise": 92.0,
    },
    "total_bookings": 470.0,
    "workload_hours_by_category": {
        "day_cruise": 29.466666666666665,
        "seven_night_cruise": 57.56666666666667,
        "nine_night_cruise": 42.93333333333333,
    },
    "total_workload_hours": 129.96666666666667,
    "raw_required_fte": 10.397333333333334,
    "unconstrained_required_agents": 11,
    "recommended_inhouse_agents_for_outlook": 11,
    "spare_capacity_hours": 7.533333333333331,
    "overflow_workload_hours": 0.0,
    "overflow_bookings_by_category": {
        "day_cruise": 0.0,
        "seven_night_cruise": 0.0,
        "nine_night_cruise": 0.0,
    },
    "regular_labor_cost": 9680.0,
    "overflow_commission": 0.0,
    "total_weekly_operating_cost": 9680.0,
}
```

## 10. P90 Baseline Output

Baseline `Higher Demand — P90` outlook:

```python
{
    "outlook_name": "Higher Demand",
    "percentile": 0.9,
    "percentile_label": "P90",
    "simulation_row_id": 2998,
    "representative_row_reused": False,
    "demand_by_category": {
        "day_cruise": 223.0,
        "seven_night_cruise": 156.0,
        "nine_night_cruise": 139.0,
    },
    "total_bookings": 518.0,
    "workload_hours_by_category": {
        "day_cruise": 29.733333333333334,
        "seven_night_cruise": 57.2,
        "nine_night_cruise": 64.86666666666666,
    },
    "total_workload_hours": 151.8,
    "raw_required_fte": 12.144,
    "unconstrained_required_agents": 13,
    "recommended_inhouse_agents_for_outlook": 12,
    "spare_capacity_hours": 0.0,
    "overflow_workload_hours": 1.8000000000000114,
    "overflow_bookings_by_category": {
        "day_cruise": 2.644268774703574,
        "seven_night_cruise": 1.8498023715415137,
        "nine_night_cruise": 1.648221343873528,
    },
    "regular_labor_cost": 10560.0,
    "overflow_commission": 1250.8399209486245,
    "total_weekly_operating_cost": 11810.839920948625,
}
```

## 11. Selected Row IDs

Baseline selected representative row IDs:

```python
{
    "P25": 1859,
    "P50": 248,
    "P90": 2998,
}
```

## 12. Target Percentile Workloads

Baseline target percentile workloads:

```python
{
    "P25": 117.8,
    "P50": 129.96666666666667,
    "P90": 151.8,
}
```

## 13. Selected Representative-Row Workloads

Baseline selected representative-row workloads:

```python
{
    "P25": 117.8,
    "P50": 129.96666666666667,
    "P90": 151.8,
}
```

## 14. Reuse Diagnostics

Baseline reuse diagnostics:

```python
{
    "row_reuse_detected": False,
    "reused_simulation_rows": [],
    "reuse_reason": None,
}
```

Broader diagnostics now also return:

- `quantile_convention`
- `ordering_measure`
- `row_identity_field`
- `selected_row_ids_by_percentile_label`
- `target_total_workload_hours_by_percentile_label`
- `selected_total_workload_hours_by_percentile_label`
- `ordering_invariant_satisfied`

## 15. Ordering-Invariant Result

Required invariant:

```text
P25 total workload <= P50 total workload <= P90 total workload
```

Baseline result:

- `117.8 <= 129.96666666666667 <= 151.8`
- diagnostics flag: `ordering_invariant_satisfied = True`

## 16. Manual-Override Backend Verification

Verified backend behavior:

- enabled manual overrides replace the corresponding central automatic forecast before simulation
- disabled manual overrides do not affect the central forecast
- applied manual overrides change the simulation distribution and representative outlooks
- obsolete scenario selection does not multiply manual override values

Concrete checks:

- baseline day-cruise central forecast: `235.0`
- overridden day-cruise central forecast: `300.0`
- baseline P50 day-cruise representative demand: `221.0`
- overridden P50 day-cruise representative demand: `286.0`
- with `scenario_name="High Demand"` and `manual_overrides={"nine_night_cruise": 120.0}`:
  - `scenario_adjusted_forecast` remained equal to `automatic_forecast`
  - `effective_forecast["nine_night_cruise"]` remained exactly `120.0`
  - all three outlook objects matched the equivalent `Expected Demand` run
  - the main recommendation also matched the equivalent `Expected Demand` run

## 17. Application-Result Contract Summary

Revised Burst 2B preserved Revised Burst 2A authoritative contracts and added these new authoritative percentile-outlook objects:

- `lower_demand_outlook`
- `central_demand_outlook`
- `higher_demand_outlook`
- `outlook_diagnostics`

Each outlook now returns exactly:

- `outlook_name`
- `percentile`
- `percentile_label`
- `simulation_row_id`
- `representative_row_reused`
- `demand_by_category`
- `total_bookings`
- `workload_hours_by_category`
- `total_workload_hours`
- `raw_required_fte`
- `unconstrained_required_agents`
- `recommended_inhouse_agents_for_outlook`
- `spare_capacity_hours`
- `overflow_workload_hours`
- `overflow_bookings_by_category`
- `regular_labor_cost`
- `overflow_commission`
- `total_weekly_operating_cost`

Additional compatibility/output updates:

- new typed model: `RepresentativeDemandOutlook`
- new top-level `scenario_compatibility` adapter metadata
- `build_results_export_frames(...)` now includes `probabilistic_outlooks`

## 18. Temporary Scenario Compatibility Adapters

Temporary scenario compatibility remains intentionally isolated until Revised Burst 3:

- `scenario_name` is still accepted by state/UI/backend
- the resolved `scenario` object is still returned
- `scenario_adjusted_forecast` is still returned for compatibility but now mirrors the central automatic forecast
- new `scenario_compatibility` metadata explicitly records that fixed scenarios are not used to alter:
  - the applied central forecast
  - the simulation distribution
  - the representative outlooks
  - the main probabilistic recommendation

Adapter payload now returns:

- `adapter_active`
- `selected_scenario_name`
- `scenario_adjusted_forecast_used_for_backend`
- `effective_demand_multiplier`
- `effective_variability_multiplier`

## 19. Recommendation-Independence Result

Verified:

- adding representative outlook selection does not change the feasible recommendation candidate set
- adding representative outlook selection does not change the selected coverage target
- adding representative outlook selection does not change the Burst 1 optimizer behavior
- adding representative outlook selection does not change the main recommendation
- adding representative outlook selection does not change manager-proposal evaluation
- adding representative outlook selection does not change recommendation-versus-manager comparison
- adding representative outlook selection does not change staffing risk-cost records
- temporary fixed-scenario compatibility does not alter percentile outputs

Concrete regression check:

- `Expected Demand`, `Low Demand`, and `High Demand` all preserved identical:
  - `recommendation_policy`
  - `recommended_plan`
  - `manager_proposal`
  - `recommendation_manager_comparison`
  - `staffing_risk_cost_records`

## 20. Focused Test Commands and Results

Syntax check:

- Command: `python -m py_compile src/models.py src/simulation/monte_carlo.py src/orchestration.py src/ui/charts.py src/ui/components.py tests/test_simulation.py tests/test_end_to_end.py tests/test_ui_bundle.py`
- Result: passed

Focused tests:

- Command: `python -m unittest tests.test_simulation tests.test_end_to_end tests.test_ui_bundle tests.test_finance tests.test_decision`
- Result: `77/77` passed

Observed warnings:

- `No runtime found, using MemoryCacheStorageManager`

## 21. Full-Suite Command and Result

- Command: `python -m unittest discover -s tests`
- Result: `89/89` passed

Observed warnings:

- `No runtime found, using MemoryCacheStorageManager`

## 22. Streamlit Smoke-Test Command and Result

Commands run:

```text
python -m streamlit run app.py --server.headless true --server.port 8501
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8501/_stcore/health' -TimeoutSec 10
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8501/' -TimeoutSec 10
```

Result:

- Streamlit launched successfully
- health endpoint returned HTTP `200` with `ok`
- root page returned HTTP `200`
- no startup exception appeared in server output

## 23. Deviations or Unresolved Issues

No functional deviation from the approved Revised Burst 2B scope was required.

Known deferred items:

- final outlook-card presentation is still not implemented
- final visible staffing risk-cost table UI is still not implemented
- final Business Decisions vs Business Assumptions redesign is still not implemented
- final scenario-selector removal is still deferred
- major manual-override UI repair is still deferred
- legacy comparison/export adapters remain intentionally present for final UI migration
- the working tree remains intentionally not clean because Burst 1 and Revised Burst 2A outputs were never committed

## 24. GPT-5.4 Mini Subagents Used and Their Exact Bounded Scopes

None.

## 25. Burst 3 Preparation

Revised Burst 3 should start from the repository, this report, the persisted Revised Burst 2A report, and the authoritative refinement spec file.

Immediate repository facts:

- Branch: `main`
- Commit: `ad55b67c13fbd143e2991dea003d85c3a4848706`
- Working tree clean: no

Expected non-clean state:

- retained Burst 1 source/config/test/report/spec outputs
- retained Revised Burst 2A source/test/report outputs
- Revised Burst 2B source/test/report outputs in:
  - `src/models.py`
  - `src/orchestration.py`
  - `src/simulation/monte_carlo.py`
  - `src/ui/charts.py`
  - `src/ui/components.py`
  - `tests/test_end_to_end.py`
  - `tests/test_simulation.py`
  - `tests/test_ui_bundle.py`
  - `docs/implementation_reports/revised_burst_2b_completion_report.md`
- generated `__pycache__` updates from verification runs

Most important new backend contracts:

- typed `RepresentativeDemandOutlook`
- top-level `lower_demand_outlook`
- top-level `central_demand_outlook`
- top-level `higher_demand_outlook`
- top-level `outlook_diagnostics`
- top-level `scenario_compatibility`

Selection rules that must remain stable unless explicitly superseded:

- quantile convention: `linear`
- ordering measure: `total_workload_hours`
- stable row identity: `simulation_id`
- tie break: lower `simulation_id`
- prefer unused rows before reused rows
- preserve nondecreasing selected workloads across ascending percentiles
- reuse only when a distinct choice is unavailable

Manual forecast behavior that must remain stable:

- manual overrides replace the corresponding central forecast before simulation
- disabled overrides do not affect the central forecast
- fixed-scenario compatibility must not multiply manual override values
- fixed-scenario compatibility must not alter percentile outlook results

Revised Burst 2A contracts that must remain unchanged:

- `recommendation_policy`
- `recommended_plan`
- `manager_proposal`
- `previous_week_staffing_context`
- `recommendation_manager_comparison`
- `adaptive_comparison_narrative`
- `staffing_risk_cost_records`
- comparison difference direction `manager value - recommendation value`

Suggested primary files for Revised Burst 3:

- `src/ui/components.py`
- `src/ui/charts.py`
- `src/orchestration.py`
- possibly `src/ui/state.py`
- related tests

Files Revised Burst 3 should avoid changing unless a verified defect requires it:

- `src/decision/optimizer.py`
- `src/decision/plans.py`
- Revised Burst 2A comparison semantics
- percentile-row selection logic in `src/simulation/monte_carlo.py`
- forecasting and sampling core modules

## COMPACTION HANDOFF FOR REVISED BURST 3

Current branch: `main`

Current commit: `ad55b67c13fbd143e2991dea003d85c3a4848706`

Working tree clean: no

Expected working-tree outputs of Burst 1, Revised Burst 2A, and Revised Burst 2B:

- retained Burst 1 outputs
- retained Revised Burst 2A outputs
- Revised Burst 2B direct edits:
  - `src/models.py`
  - `src/orchestration.py`
  - `src/simulation/monte_carlo.py`
  - `src/ui/charts.py`
  - `src/ui/components.py`
  - `tests/test_end_to_end.py`
  - `tests/test_simulation.py`
  - `tests/test_ui_bundle.py`
  - `docs/implementation_reports/revised_burst_2b_completion_report.md`
- generated `__pycache__` updates from compile/test/smoke commands

Authoritative contracts created or changed:

- typed `RepresentativeDemandOutlook`
- top-level `lower_demand_outlook`
- top-level `central_demand_outlook`
- top-level `higher_demand_outlook`
- top-level `outlook_diagnostics`
- top-level `scenario_compatibility`
- `build_results_export_frames(...)` now includes `probabilistic_outlooks`

Exact public outlook fields added:

- `outlook_name`
- `percentile`
- `percentile_label`
- `simulation_row_id`
- `representative_row_reused`
- `demand_by_category`
- `total_bookings`
- `workload_hours_by_category`
- `total_workload_hours`
- `raw_required_fte`
- `unconstrained_required_agents`
- `recommended_inhouse_agents_for_outlook`
- `spare_capacity_hours`
- `overflow_workload_hours`
- `overflow_bookings_by_category`
- `regular_labor_cost`
- `overflow_commission`
- `total_weekly_operating_cost`

Quantile convention:

- `linear`

Representative-row selection rules:

- sort completed simulation rows by `total_workload_hours`, then `simulation_id`
- compute target workloads with `linear` quantiles
- select actual completed rows nearest to the target workload
- prefer unused rows before reused rows
- break equal-distance ties with lower `simulation_id`
- preserve nondecreasing selected workloads across ascending percentile requests
- use only actual completed rows, never synthetic category combinations

Row-reuse behavior:

- rows are reused only when a distinct candidate is unavailable
- each outlook carries `representative_row_reused`
- diagnostics expose:
  - `row_reuse_detected`
  - `reused_simulation_rows`
  - `reuse_reason`

Manual forecast backend behavior:

- manual overrides replace the corresponding central forecast before simulation
- disabled overrides leave the central forecast unchanged
- manual values are not multiplied by obsolete scenario factors
- scenario compatibility does not alter percentile outlooks or the main recommendation

Temporary scenario adapters still present:

- input `scenario_name`
- returned `scenario`
- returned `scenario_adjusted_forecast` compatibility mirror of `automatic_forecast`
- returned `scenario_compatibility` metadata
- UI scenario selector still present temporarily

Recommendation and manager contracts that must remain unchanged:

- Burst 1 coverage-target recommendation policy
- Revised Burst 2A manager what-if behavior
- Revised Burst 2A difference direction `manager value - recommendation value`
- Revised Burst 2A staffing risk-cost record structure

Tests protecting these contracts:

- percentile-row selection and reuse diagnostics in `tests/test_simulation.py`
- outlook-content and recommendation-independence checks in `tests/test_end_to_end.py`
- export helper coverage in `tests/test_ui_bundle.py`
- existing Revised Burst 2A regression tests in `tests/test_end_to_end.py` and `tests/test_decision.py`

Known unresolved issues:

- final outlook-card UI not implemented
- final visible staffing risk-cost table UI not implemented
- final decision/assumption page redesign not implemented
- final scenario-selector removal not implemented
- major manual-override UI repair not implemented

Files Revised Burst 3 is expected to modify:

- `src/ui/components.py`
- `src/ui/charts.py`
- `src/orchestration.py`
- possibly `src/ui/state.py`
- related tests

Files Revised Burst 3 should avoid changing:

- `src/decision/optimizer.py`
- `src/decision/plans.py`
- `src/simulation/monte_carlo.py` unless a verified defect is found
- comparison semantics created in Revised Burst 2A

Deviations from the Revised Burst 2B prompt:

- none functional

Path to this completion report:

```text
docs/implementation_reports/revised_burst_2b_completion_report.md
```
