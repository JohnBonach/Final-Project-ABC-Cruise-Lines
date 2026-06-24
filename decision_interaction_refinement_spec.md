# Decision Interaction Refinement Specification

## Status

Burst 0 findings are approved subject to the Burst 1 patch below.

This file replaces the empty misspelled placeholder `decision_interaction_refinenement_spec.md` and is the single authoritative repository specification artifact for this refinement track.

## Burst 1: Atomic Decision-Policy Contract and Optimizer Migration

### Scope boundary

Proceed with Burst 1 only.

Do not begin during this burst:

- percentile outlooks
- out-of-range manager evaluation
- scenario retirement
- manual override repair
- major UI redesign

### Objective

Atomically migrate the decision-policy contract by:

1. Removing `inhouse_capture_target`
2. Adding `minimum_inhouse_coverage_target`
3. Setting its default to `0.85`
4. Wiring it through model, config, validation, state, orchestration, reset, stale-result behavior, and tests
5. Replacing percentile-filtered recommendation candidates with every feasible integer staffing level
6. Selecting the lowest-total-cost feasible level meeting the coverage target
7. Implementing deterministic monetary tie handling
8. Implementing the no-eligible-level fallback
9. Keeping the current application runnable

### Preserve

Preserve:

- three canonical cruise categories
- existing forecasting
- existing Monte Carlo demand simulation
- deterministic workload and FTE calculations
- minimum and maximum staffing assumptions
- third-party overflow allocation
- regular labor cost
- expected overflow commission
- total weekly operating cost
- existing baseline/draft/applied/result/stale architecture
- existing single-page dashboard structure

Do not reintroduce:

- abandonment
- overtime
- lost contribution
- missed-sales cost
- in-house capture scaling
- old reservation categories

### Atomic contract migration

Remove every active reference to:

```text
inhouse_capture_target
```

Add:

```text
minimum_inhouse_coverage_target = 0.85
```

This is a Business Decision input.

It must participate in:

- baseline inputs
- draft inputs
- applied inputs
- stale-result comparison
- reset to baseline
- orchestration input
- reproducible exports or result metadata where appropriate

Behavioral requirements:

- changing the draft target marks results stale without erasing the currently applied result
- Run Analysis applies the new target
- Reset restores exactly `0.85`
- changing the target does not change manager-proposed staffing

Configuration requirement:

```text
schema_version = "2.0"
```

Do not add migration machinery.

### Recommendation evaluation set

For configured:

```text
minimum_schedulable_agents = m
maximum_inhouse_agents = M
```

Evaluate exactly:

```text
m, m+1, ..., M
```

for recommendation selection.

Do not derive recommendation candidates from the 5th–95th percentile simulated staffing range.

Do not add previous-week staffing or manager-proposed staffing to the feasible recommendation candidate set when they lie outside `[m, M]`.

Out-of-range manager proposal support belongs to Burst 2. During Burst 1, preserve current valid in-range behavior and fail clearly if an unsupported out-of-range value reaches a path not yet migrated.

### Coverage-constrained optimizer

Eligible levels satisfy:

```text
capacity_confidence >= minimum_inhouse_coverage_target
```

Among eligible levels, choose minimum:

```text
expected_total_weekly_operating_cost
```

Use monetary tie tolerance:

```text
absolute cost difference <= $0.01
```

Tie-breaking order:

1. Higher `capacity_confidence`
2. Lower `expected_overflow_workload_hours`
3. Lower `staffing_agents`

Return recommendation metadata including:

- selected target
- recommended staffing
- resulting coverage
- whether target was met
- expected total weekly operating cost
- warning, when applicable

### No eligible level

If no feasible level reaches the target:

- select maximum feasible staffing
- set `coverage_target_met = false`
- return the maximum achievable coverage
- return a warning explaining that the target cannot be achieved within current in-house capacity

Do not return an error or blank recommendation.

### Probabilistic metric verification

Confirm and preserve these trial-level definitions:

```python
expected_spare_capacity_hours = mean(
    max(capacity_hours - simulated_workload_hours, 0)
)

expected_overflow_workload_hours = mean(
    max(simulated_workload_hours - capacity_hours, 0)
)
```

Do not calculate them from mean workload.

Confirm and test complementary events:

```python
coverage_event = simulated_workload_hours <= capacity_hours
overflow_event = simulated_workload_hours > capacity_hours
```

Required invariant:

```text
capacity_confidence + probability_overflow_required ≈ 1.0
```

within numeric tolerance.

### Minimal UI compatibility

Make only the minimal UI edits required to:

- remove the capture-target control
- keep the application loading
- preserve existing state synchronization
- avoid broken references to the removed field

Do not yet add the final coverage-target control or redesign the visible decision section unless a small temporary control is necessary for end-to-end testing.

If a temporary control is added, keep it simple and clearly identify that final Business Decisions presentation belongs to a later burst.

### Expected files

Inspect and modify only as required:

- `decision_interaction_refinement_spec.md`
- `config/defaults.json`
- `src/constants.py`
- `src/models.py`
- `src/validation.py`
- `src/ui/state.py`
- `src/ui/components.py`
- `src/decision/plans.py`
- `src/decision/optimizer.py`
- `src/orchestration.py`
- related tests

Avoid changing simulation, percentile outlook, chart, or major presentation modules unless a verified dependency requires it.

### Acceptance tests

Add or update tests for:

#### Contract

- capture target absent
- coverage target present
- default exactly `0.85`
- valid range `0–1`
- schema version `2.0`
- weekly forecast demand unchanged

#### State

- baseline target `0.85`
- draft target stored
- applied target stored
- draft target change marks stale
- applied result remains visible
- Run Analysis applies target
- Reset restores `0.85`
- manager staffing remains unchanged

#### Recommendation candidate set

For minimum `8` and maximum `12`, evaluate exactly:

```text
8, 9, 10, 11, 12
```

#### Optimizer

- lowest-cost eligible plan selected
- every normal recommendation meets the target
- `70%`, `85%`, and `95%` targets produce deterministic reproducible outputs
- one-cent tie tolerance:
  - below `$0.01`
  - exactly `$0.01`
  - above `$0.01`
- tie order is coverage, overflow workload, staffing
- no-eligible fallback selects maximum staffing and returns warning

#### Probabilistic metrics

- coverage and overflow events use the same capacity boundary
- complementarity holds
- expected spare capacity is a mean of trial-level positive parts
- expected overflow is a mean of trial-level positive parts

#### Regression

- existing baseline deterministic calculations unchanged
- existing peak case unchanged
- existing low case unchanged
- current in-range manager plan still works
- full test suite passes

### Verification commands

Run focused tests first, then:

```text
python -m unittest discover -s tests
```

Launch:

```text
python -m streamlit run app.py --server.headless true --server.port 8501
```

Verify the health endpoint and root page return successfully.

### Completion report

Report:

1. repository commit/state used
2. files modified
3. contract changes
4. candidate levels evaluated
5. recommendation outputs at `70%`, `85%`, and `95%`
6. any target not achievable within the current range
7. tie-tolerance test results
8. coverage/overflow invariant result
9. focused tests
10. full suite result
11. Streamlit smoke-test result
12. any deviation from this scope
13. any GPT-5.4 mini subagents used and their exact bounded tasks

Stop after Burst 1.
