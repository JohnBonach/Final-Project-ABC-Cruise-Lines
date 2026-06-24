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
- Deterministic forecast: retained as the earlier hand-check artifact for foundational math verification
- Deterministic workload: 40.0 hours total
- Booking-processing hours per agent: 30.0
- Required FTE: 1.3333333333333333
- Required agents: 2
- Staffing test point: 1 agent
- Total weekly operating cost: 1325.0

### Probabilistic case study
- Case name: `four_week_handling_time_sensitivity_case`
- Result: `PASS`
- Baseline recommendation: 12 agents
- Baseline in-house coverage probability: 0.8558
- Baseline expected overflow commission: 971.88
- Baseline expected total weekly operating cost: 11531.88
- Sensitivity recommendation: 11 agents
- Sensitivity in-house coverage probability: 0.9548
- Sensitivity expected overflow commission: 256.70
- Sensitivity expected total weekly operating cost: 9936.70
- Recommendation shift under 0.85x handling times: `-1` agent

## Assumptions Table

| Assumption | Value | Source |
|---|---:|---|
| Forecast weights | 0.4, 0.3, 0.2, 0.1 | `ABC_Cruise_Lines_Design_Document.md`, `data/case_study_input.json`, `data/probabilistic_case_study_input.json` |
| Planning horizon | 1 week | `ABC_Cruise_Lines_Design_Document.md` |
| Category set | `day_cruise`, `seven_night_cruise`, `nine_night_cruise` | `config/defaults.json`, `data/probabilistic_case_study_input.json` |
| Paid hours per agent | 40.0 hours/week | `data/case_study_input.json`, `data/probabilistic_case_study_input.json` |
| Weekly booking-processing hours per agent | 12.5 hours/week | `config/defaults.json`, `data/probabilistic_case_study_input.json` |
| Minimum coverage target | 0.85 | `config/defaults.json`, `data/probabilistic_case_study_input.json` |
| Third-party commission rate | 0.125 | `config/defaults.json`, `data/probabilistic_case_study_input.json` |
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
- Booking-processing hours per agent:
  - `Configured weekly booking-processing hours per agent`
- Required FTE:
  - `Workload hours / booking-processing hours per agent`
- Whole-agent staffing:
  - `ceil(required FTE)`
- Total weekly operating cost:
  - `regular labor cost + expected overflow commission`

## Process Flow

```text
Historical weekly demand
  -> 4-week weighted moving-average forecast
  -> optional manual central-forecast overrides
  -> uncertainty estimate by category
  -> Monte Carlo demand sampling
  -> workload minutes by category
  -> required FTE and whole-agent staffing
  -> evaluate feasible staffing range against minimum coverage target
  -> exact manager-proposal evaluation
  -> P25 / P50 / P90 representative outlook selection by total workload
  -> staffing risk-cost comparison and manager-facing narrative
```

## Validation Evidence

- Manual deterministic validation report: `PASS` with zero deltas on all expected values in `data/task_7_2_validation_report.json`.
- Probabilistic case-study report: `PASS` in `data/probabilistic_case_study_report.json`.
- Usability review: `data/task_7_5_usability_review.md` confirms the recommendation appears first, units are explicit, and comparison views are manager-facing.
- Release-state traceability: the evidence pack references the accepted task state in `ABC_Cruise_DSS_Development_WBS.md` and the documented run instructions in `README.md`.

## Key Recommendation

For the baseline probabilistic case, schedule **12 reservation agents** for the upcoming week. That release-state recommendation is recorded in `data/probabilistic_case_study_report.json`. Under the documented faster-booking sensitivity, the recommendation shifts to **11 agents**, which is useful as a planning example but does not replace the baseline recommendation policy.

## Limitations

- The dataset is synthetic rather than live operational data.
- The model is weekly tactical only and does not do hourly scheduling.
- The prototype does not model shift rostering, queueing, or waiting-time behavior directly.
- Screenshots were not saved in this environment; the report team should rely on the structured JSON and markdown outputs listed above.
