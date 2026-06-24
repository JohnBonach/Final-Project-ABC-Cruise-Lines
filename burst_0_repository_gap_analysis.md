# Burst 0 Repository Verification and Gap Analysis

## 1. Repository State and Branch/Commit Inspected

- Branch inspected: `main`
- Commit inspected: `ad55b67c13fbd143e2991dea003d85c3a4848706`
- Working tree status: clean except one untracked file, `decision_interaction_refinenement_spec.md`
- Important note: `decision_interaction_refinenement_spec.md` currently exists in the workspace but is empty at `0` bytes, so the effective Burst 0 specification came from the user prompt rather than the on-disk markdown file.

## 2. Current Architecture Summary

The application entry point in [app.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/app.py:26) initializes Streamlit and delegates rendering to [src/ui/components.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/components.py:899). UI draft/applied/baseline state is normalized and persisted in [src/ui/state.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/state.py:149), then sent to [src/orchestration.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/orchestration.py:306), which composes forecasting, deterministic staffing, Monte Carlo demand simulation, staffing evaluation, recommendation selection, and narrative generation.

Forecast uncertainty is assembled in [src/forecasting/uncertainty.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/forecasting/uncertainty.py:75). Demand simulation is generated in [src/simulation/demand_sampler.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/simulation/demand_sampler.py:82), then translated into workload and staffing metrics in [src/simulation/monte_carlo.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/simulation/monte_carlo.py:166). Per-staffing financial evaluation is handled in [src/finance/staffing_evaluator.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/finance/staffing_evaluator.py:188), with recommendation ranking in [src/decision/optimizer.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/decision/optimizer.py:103) and named-plan support in [src/decision/plans.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/decision/plans.py:109).

The canonical reservation categories are preserved in [src/constants.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/constants.py:7):

```python
RESERVATION_CATEGORIES = (
    "day_cruise",
    "seven_night_cruise",
    "nine_night_cruise",
)
```

The active financial objective is still total weekly operating cost:

- regular labor cost
- expected third-party overflow commission

That objective is encoded through `expected_total_weekly_operating_cost` in [src/finance/staffing_evaluator.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/finance/staffing_evaluator.py:265) and used as the ranking objective in [src/decision/optimizer.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/decision/optimizer.py:134).

## 3. Specification-to-Code Gap Matrix

| Requested refinement | Current status | Notes |
|---|---|---|
| Configurable minimum in-house coverage target, default 85% | Absent | No coverage-feasibility field or rule exists yet. |
| Lowest-total-cost feasible recommendation meeting target | Absent | Current recommendation is pure lowest `expected_total_weekly_operating_cost` with tie-breaks. |
| Separately evaluated manager-proposed staffing level | Partial | Manager plan is included only if it survives candidate filtering; out-of-range values currently break the result. |
| Recommendation-versus-manager comparison | Partial | Comparison table and narrative deltas exist, but there is no dedicated recommendation-vs-manager evaluation model. |
| Lower/Central/Higher demand outlooks displayed together | Absent | Current UI supports a single interactive scenario selector only. |
| Probabilistic P25/P50/P90 demand outlooks | Absent/Feasible | Simulation data supports this, but no coherent percentile-row selector exists. |
| Lower-page staffing risk-cost table | Absent | No risk-cost summary table exists in UI or orchestration output. |
| Separation between Business Decisions and Business Assumptions | Partial | Current adjust-plan and assumptions sections exist, but boundaries are not aligned to requested refinement. |
| Removal of in-house capture target | Absent | Field is still present in config, model, state, UI, and tests. |
| Removal of interactive Low/Expected/High selector | Absent | Selector is active in UI and scenario names are enforced in validation/tests. |
| Repair manual forecast override interaction | Absent | Current form structure can leave manual value input disabled until submit/rerun. |

Already preserved correctly:

- Three-category cruise demand model
- Probabilistic staffing backend
- Floor/cap staffing logic
- Third-party overflow and commission cost logic
- Single-page Streamlit dashboard
- Editable business assumptions
- Draft/applied/result state model
- No reintroduction of abandonment, overtime, lost contribution, missed-sales cost, productive processing percentage, or in-house capture scaling of weekly demand in the active backend

## 4. Findings for All 15 Required Analysis Items

### 1. Exact current recommendation-selection rule

The current rule is:

1. Build simulated demand distribution.
2. Convert each simulation row into workload and clamped `recommended_inhouse_agents`.
3. Build candidate staffing levels from the integer range between the 5th and 95th percentiles of simulated required staffing, plus previous-week staffing and manager-planned staffing.
4. Filter candidates to the workforce floor/cap bounds.
5. Add named plan staffing levels selected at Lean/Balanced/Conservative confidence targets.
6. Evaluate each remaining staffing level financially.
7. Select the recommendation with minimum `expected_total_weekly_operating_cost`.
8. For rows tied within `selection_tolerance = 1e-9`, prefer:
   - higher `capacity_confidence`
   - lower `expected_overflow_workload_hours`
   - lower `staffing_agents`
   - then lower cost as final tuple position

References:

- [src/decision/plans.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/decision/plans.py:109)
- [src/orchestration.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/orchestration.py:401)
- [src/decision/optimizer.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/decision/optimizer.py:60)

### 2. Whether `capacity_confidence` already means probability that no overflow is required

Yes. It is computed as:

`mean(total_workload_hours <= inhouse_capacity_hours)`

That is the probability the staffing level can cover demand without overflow.

Reference:

- [src/simulation/monte_carlo.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/simulation/monte_carlo.py:277)

### 3. Whether `probability_overflow_required` is the complement

Yes in current behavior. It is computed as:

`mean(overflow_workload_hours > 0.0)`

That is effectively the complement of `capacity_confidence` under the current overflow definition.

References:

- [src/simulation/monte_carlo.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/simulation/monte_carlo.py:280)
- [tests/test_simulation.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/tests/test_simulation.py:174)

### 4. Which staffing levels are currently evaluated

Only the filtered candidate staffing set is evaluated.

Mechanically:

- start with simulated `recommended_inhouse_agents`
- derive low/high staffing range from the 5th and 95th percentiles
- include every integer in that range
- add previous week staffing
- add manager planned staffing
- filter all values to `minimum_schedulable_agents <= staffing <= maximum_inhouse_agents`
- add named plan selections
- deduplicate and sort

With the current default dataset/config, the evaluated levels are:

- `9`
- `10`
- `11`
- `12`

References:

- [src/decision/plans.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/decision/plans.py:109)
- [src/orchestration.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/orchestration.py:401)

### 5. Whether manager staffing below floor or above cap can currently be evaluated without clamping

No.

If manager staffing is outside the floor/cap range, it is added to the candidate list and then removed by the range filter. Later, the comparison-table builder requires the manager staffing row to exist in the staffing evaluation table and raises an error if it does not.

Verified directly:

- `manager_planned_staffing=1` returns `ok=False`
- `manager_planned_staffing=20` returns `ok=False`
- both fail with `Manager Plan staffing level must exist in the staffing evaluation table`

Reference:

- [src/orchestration.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/orchestration.py:234)

### 6. How the manager plan is currently passed through orchestration

The manager plan flow is:

1. UI stores `planned_staffing_agents` inside `workforce_assumptions`.
2. State layer passes that value as `manager_planned_staffing`.
3. Orchestration resolves it to `resolved_manager_staffing`.
4. Candidate staffing generation includes it.
5. Comparison table includes a `Manager Plan` row.
6. Narrative compares recommended staffing against manager staffing.

References:

- [src/ui/state.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/state.py:170)
- [src/orchestration.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/orchestration.py:395)
- [src/decision/narrative.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/decision/narrative.py:166)

### 7. Whether the UI currently uses backend financial records or reconstructs costs itself

It does both.

Uses backend records:

- analysis-detail financial breakdown
- staffing evaluation exports
- comparison table export

Reconstructs costs itself:

- `render_kpi_grid()` computes `labor_cost = recommended * paid_hours * hourly_wage`
- `render_narrative()` similarly computes total cost from labor only

That means the top-level UI ignores `expected_overflow_commission` and can disagree with the backend financial recommendation record.

References:

- [src/ui/components.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/components.py:350)
- [src/ui/components.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/components.py:413)
- [src/ui/charts.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/charts.py:339)

### 8. How manual overrides currently behave and why the field may remain disabled

Manual overrides are modeled correctly in state:

- each category has an enable toggle
- enabled categories contribute to `manual_overrides`
- manual overrides replace the scenario-adjusted automatic forecast

But the interaction bug is in the form behavior. In [src/ui/components.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/components.py:542), the toggle and number input are inside the same `st.form`, and the number input uses:

```python
disabled=not manual_enabled
```

Because forms do not rerun immediately on widget edits, turning on the toggle does not immediately enable the number input during that same render cycle. The field can appear stuck disabled until a submit/rerun occurs.

### 9. How Low/Expected/High demand scenarios are currently implemented

They are implemented in three places:

- configuration in [config/scenarios.json](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/config/scenarios.json:1)
- validation/enforced canonical naming in [src/validation.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/validation.py:352)
- duplicated hard-coded UI multipliers in [src/ui/components.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/components.py:84)

Orchestration resolves the selected scenario name and applies:

- `demand_multiplier` to automatic forecast
- `variability_multiplier` to simulation variability

References:

- [src/orchestration.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/orchestration.py:340)
- [src/ui/components.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/components.py:544)

### 10. Whether fixed scenario code is used by tests or exports

Yes.

Tests:

- end-to-end tests assert `Expected Demand` baseline and `High Demand` scenario behavior
- UI tests assert state handling for `High Demand`

Exports:

- forecast breakdown tables include scenario-based forecast-source labeling

References:

- [tests/test_end_to_end.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/tests/test_end_to_end.py:95)
- [tests/test_ui_bundle.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/tests/test_ui_bundle.py:315)
- [src/ui/charts.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/charts.py:392)

### 11. Whether Monte Carlo output supports selecting coherent representative P25, P50, and P90 demand/workload rows

Yes, with some new orchestration logic.

Current support already present:

- raw demand rows are preserved per simulation iteration
- completed workload/staffing rows remain coherent row-level records

Missing:

- there is no existing selector for representative percentile rows
- only staffing percentiles are summarized today

This means P25/P50/P90 coherent outlooks are feasible without changing the demand sampler format, but they are not yet implemented.

References:

- [src/simulation/demand_sampler.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/simulation/demand_sampler.py:122)
- [src/simulation/monte_carlo.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/simulation/monte_carlo.py:293)

### 12. Every active reference to `inhouse_capture_target`

Active code/test/config references:

- [config/defaults.json](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/config/defaults.json:49)
- [src/constants.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/constants.py:41)
- [src/models.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/models.py:152)
- [src/ui/state.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/state.py:241)
- [src/ui/state.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/state.py:325)
- [src/ui/components.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/components.py:701)
- [tests/test_finance.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/tests/test_finance.py:50)
- [tests/test_ui_bundle.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/tests/test_ui_bundle.py:187)
- [tests/test_ui_bundle.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/tests/test_ui_bundle.py:369)

No active backend financial logic currently uses the field beyond validation/model/state/UI presence.

### 13. Whether removing that field requires a config schema-version change

Not technically required by current runtime behavior.

Why:

- `schema_version` is loaded and preserved
- no code branches on schema version
- validation only checks exact keys for the active schema

So removal will require coordinated code/config/test edits, but not a version-gated migration unless we choose to introduce one. Semantically, it is a schema change and would justify a version bump for clarity.

Reference:

- [src/validation.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/validation.py:274)

### 14. Which requested features already exist, are partial, or are absent

Already exist:

- probabilistic staffing evaluation table
- manager plan input
- previous week vs manager vs named plan comparison table
- named plans via confidence targets
- narrative recommendation with manager delta

Partial:

- manager plan evaluation, because it only works if the manager staffing survives filtering
- separation of business decisions and assumptions, because the UI has separate areas but not the requested refined structure

Absent:

- configurable minimum in-house coverage target
- feasibility-constrained recommendation rule
- simultaneous Lower/Central/Higher probabilistic outlook panels
- P25/P50/P90 representative scenario outputs
- lower-page staffing risk-cost table
- removal of in-house capture target
- removal of interactive scenario selector
- repaired override interaction

### 15. Smallest dependency-ordered file groups for implementation

Recommended groups:

1. Contract/config group
   - [src/constants.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/constants.py:1)
   - [src/models.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/models.py:1)
   - [src/validation.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/validation.py:1)
   - [config/defaults.json](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/config/defaults.json:1)

2. Percentile outlook backend group
   - [src/simulation/monte_carlo.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/simulation/monte_carlo.py:1)
   - [src/orchestration.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/orchestration.py:1)
   - optionally [src/decision/plans.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/decision/plans.py:1)

3. Recommendation and manager-evaluation group
   - [src/finance/staffing_evaluator.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/finance/staffing_evaluator.py:1)
   - [src/decision/optimizer.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/decision/optimizer.py:1)
   - [src/decision/narrative.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/decision/narrative.py:1)
   - [src/orchestration.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/orchestration.py:1)

4. UI state/interaction group
   - [src/ui/state.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/state.py:1)
   - [src/ui/components.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/components.py:1)

5. UI presentation/export group
   - [src/ui/charts.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/charts.py:1)
   - [src/ui/components.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/src/ui/components.py:1)

6. Regression test group
   - [tests/test_decision.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/tests/test_decision.py:1)
   - [tests/test_end_to_end.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/tests/test_end_to_end.py:1)
   - [tests/test_ui_bundle.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/tests/test_ui_bundle.py:1)
   - [tests/test_simulation.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/tests/test_simulation.py:1)
   - [tests/test_forecasting.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/tests/test_forecasting.py:1)

## 5. Percentile-Outlook Feasibility Assessment

The requested Lower/Central/Higher probabilistic outlook design is feasible with the current simulation architecture.

Current strengths:

- Monte Carlo simulation already returns coherent per-iteration demand rows by category.
- Completed simulation tables preserve coherent row-level workload and staffing metrics.
- Per-staffing financial evaluation already exists and can be reused once representative percentile rows or percentile-defined outlook bundles are selected.

Current gap:

- There is no helper that picks coherent representative rows corresponding to P25, P50, and P90.
- Existing summary output only exposes percentile staffing counts, not percentile outlook bundles.

Practical implication:

Burst 1 can likely implement percentile outlooks without changing the core raw Monte Carlo data contract. Most of the work belongs in:

- `src/simulation/monte_carlo.py`
- `src/orchestration.py`
- downstream decision/UI formatting layers

## 6. Recommended Implementation File Groups

Implementation order should be:

1. Shared contract and config cleanup
2. Percentile outlook backend
3. Recommendation feasibility logic and manager-plan evaluation
4. UI state and interaction updates
5. UI presentation and export updates
6. Regression tests and cleanup of stale support scripts

Smallest workable groups:

- Group A: `src/constants.py`, `src/models.py`, `src/validation.py`, `config/defaults.json`
- Group B: `src/simulation/monte_carlo.py`, `src/orchestration.py`
- Group C: `src/finance/staffing_evaluator.py`, `src/decision/optimizer.py`, `src/decision/narrative.py`, `src/orchestration.py`
- Group D: `src/ui/state.py`, `src/ui/components.py`
- Group E: `src/ui/charts.py`, `src/ui/components.py`
- Group F: targeted tests plus stale script alignment

## 7. Current Test and Smoke-Test Results

### Commands run

```powershell
python -m unittest tests.test_decision tests.test_end_to_end tests.test_ui_bundle tests.test_simulation tests.test_forecasting
python -m unittest discover -s tests
python -m streamlit run app.py --server.headless true --server.port 8501
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8501/_stcore/health' -TimeoutSec 10
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8501/' -TimeoutSec 10
```

### Test results

- Focused suite: `49/49` tests passed
- Full suite: `59/59` tests passed
- Failures: none

### Existing warnings

During test execution, Streamlit emitted:

- `WARNING streamlit.runtime.caching.cache_data_api: No runtime found, using MemoryCacheStorageManager`

This appeared during test execution only and did not cause failures.

### Streamlit application launch

The application launched successfully.

Verified:

- local health endpoint returned HTTP `200` with content `ok`
- root page returned HTTP `200`

## 8. Risks or Specification Conflicts

### Empty authoritative spec file

The repo-local file named as the authoritative refinement spec is empty. That is the biggest documentation risk for Burst 1, because the saved repository artifact does not yet preserve the intended refinement details.

### UI/backend financial mismatch

Top-level UI cards and narrative still reconstruct labor-only cost in some places rather than using the backend financial recommendation record. That creates a risk of presenting inconsistent results once recommendation logic becomes more sophisticated.

### Manager-plan failure outside floor/cap

The requested separate manager-plan evaluation is currently blocked by orchestration behavior: manager staffing outside the floor/cap candidate filter produces an error instead of a valid evaluated comparison.

### Duplicated scenario logic

Scenario handling is duplicated across:

- config
- validation
- orchestration
- UI display constants
- tests

That makes scenario removal/replacement higher risk than a single-surface change.

### Stale support script references to removed legacy economics

[scripts/run_case_study.py](/C:/Users/jgall/Documents/Binghamton/SSIE%20510/Final%20Project%20ABC%20Cruise%20Lines/scripts/run_case_study.py:299) still references removed legacy fields such as:

- `expected_total_economic_cost`
- `expected_overtime_hours`
- `expected_abandoned_total`

This script is not reflected in the passing test suite and is out of sync with the preserved objective.

## 9. Proposed Burst 1 Exact Scope

Recommended Burst 1 scope:

1. Remove `inhouse_capture_target` from shared contracts, config, UI state, UI controls, and tests.
2. Add the new configurable minimum in-house coverage target with default `0.85`.
3. Add explicit separate evaluation for:
   - recommendation candidate
   - manager-proposed staffing
4. Change recommendation selection from pure minimum cost to minimum cost among staffing levels that satisfy the coverage target.
5. Add backend support for coherent Lower/Central/Higher probabilistic outlooks based preferably on P25/P50/P90 simulation outcomes.
6. Repair manual override interaction so enabling an override reliably enables input editing without awkward form behavior.

Suggested Burst 1 should begin with backend contracts and orchestration before any major UI rendering changes.

## 10. Mini-Agents Used, If Any

No mini-agents were used during Burst 0.

