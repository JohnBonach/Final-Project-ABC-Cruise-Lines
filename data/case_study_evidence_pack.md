# ABC Cruise Lines Case-Study Evidence Pack

Source artifacts:
- [data/case_study_input.json](case_study_input.json)
- [data/task_7_2_validation_report.json](task_7_2_validation_report.json)
- [data/probabilistic_case_study_input.json](probabilistic_case_study_input.json)
- [data/probabilistic_case_study_report.json](probabilistic_case_study_report.json)
- [data/task_7_5_usability_review.md](task_7_5_usability_review.md)
- [README.md](../README.md)
- [ABC_Cruise_DSS_Development_WBS.md](../ABC_Cruise_DSS_Development_WBS.md)

## Case-Study Outputs

### Manual validation case
- Case name: `uniform_four_week_hand_check`
- Result: `PASS`
- Deterministic forecast: simple 12, standard 8, complex_group 4, change_cancellation 6
- Deterministic workload: 40.0 hours total
- Productive hours per agent: 30.0
- Required FTE: 1.3333333333333333
- Required agents: 2
- Staffing test point: 1 agent
- Expected total economic cost: 1325.0

### Probabilistic case study
- Case name: `four_week_handling_time_sensitivity_case`
- Result: `PASS`
- Baseline recommendation: 9 agents
- Baseline capacity confidence: 0.3814
- Baseline expected overtime: 9.253155 hours
- Baseline expected abandoned reservations: 2.4915411284566726
- Baseline expected total economic cost: 8736.44373109719
- Sensitivity recommendation: 8 agents
- Sensitivity capacity confidence: 0.9404
- Sensitivity expected overtime: 0.30987599999999993 hours
- Sensitivity expected abandoned reservations: 0.10406040593956131
- Sensitivity expected total economic cost: 7071.583710601327
- Recommendation shift under 0.80x handling times: `-1` agent

## Assumptions Table

| Assumption | Value | Source |
|---|---:|---|
| Forecast weights | 0.4, 0.3, 0.2, 0.1 | `ABC_Cruise_Lines_Design_Document.md`, `data/case_study_input.json`, `data/probabilistic_case_study_input.json` |
| Planning horizon | 1 week | `ABC_Cruise_Lines_Design_Document.md` |
| Category set | `simple`, `standard`, `complex_group`, `change_cancellation` | `ABC_Cruise_Lines_Design_Document.md` |
| Paid hours per agent | 40.0 hours/week | `data/case_study_input.json`, `data/probabilistic_case_study_input.json` |
| Productive processing percentage | 0.75 in validation case, 0.85 in probabilistic case | `data/case_study_input.json`, `data/probabilistic_case_study_input.json` |
| Overtime multiplier | 1.5 | `data/case_study_input.json`, `data/probabilistic_case_study_input.json` |
| Abandonment rate | 0.5 in validation case, 0.1 in probabilistic case | `data/case_study_input.json`, `data/probabilistic_case_study_input.json` |
| Simulation iterations | 5000 | `data/probabilistic_case_study_input.json` |
| Random seed | 510 | `data/probabilistic_case_study_input.json` |
| Lean/Balanced/Conservative confidence targets | 0.50 / 0.85 / 0.95 | `data/probabilistic_case_study_input.json`, `ABC_Cruise_DSS_Development_WBS.md` |

## Formula Summary

- Weighted moving average forecast:
  - `Forecast = 0.40*D(t-1) + 0.30*D(t-2) + 0.20*D(t-3) + 0.10*D(t-4)`
- Category workload:
  - `Workload minutes = demand * handling time`
- Total workload:
  - `Total workload hours = sum(category workload minutes) / 60`
- Productive hours per agent:
  - `Paid hours * productive processing percentage`
- Required FTE:
  - `Workload hours / productive hours per agent`
- Whole-agent staffing:
  - `ceil(required FTE)`
- Economic cost:
  - `regular labor cost + overtime cost + lost contribution`

## Process Flow

```text
Historical weekly demand
  -> 4-week weighted moving-average forecast
  -> uncertainty estimate by category
  -> Monte Carlo demand sampling
  -> workload minutes by category
  -> productive hours per agent
  -> required FTE and whole-agent staffing
  -> Lean / Balanced / Conservative plans
  -> overtime, abandonment, and cost evaluation
  -> financially recommended staffing level
  -> manager-facing narrative and comparison table
```

## Validation Evidence

- Manual deterministic validation report: `PASS` with zero deltas on all expected values in `data/task_7_2_validation_report.json`.
- Probabilistic case-study report: `PASS` in `data/probabilistic_case_study_report.json`.
- Usability review: `data/task_7_5_usability_review.md` confirms the recommendation appears first, units are explicit, and comparison views are manager-facing.
- Release-state traceability: the evidence pack references the accepted task state in `ABC_Cruise_DSS_Development_WBS.md` and the documented run instructions in `README.md`.

## Key Recommendation

For the baseline probabilistic case, schedule **9 reservation agents** for the upcoming week. That baseline recommendation is the final release-state result captured in `data/probabilistic_case_study_report.json`. Under the documented handling-time improvement scenario, the recommendation shifts to **8 agents**, which is useful as a sensitivity example but does not replace the baseline recommendation.

## Limitations

- The dataset is synthetic rather than live operational data.
- The model is weekly tactical only and does not do hourly scheduling.
- The prototype does not model shift rostering, queueing, or waiting-time behavior directly.
- Abandonment uses a simplified global rate.
- Screenshots were not saved in this environment; the report team should rely on the structured JSON and markdown outputs listed above.

