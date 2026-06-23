# ABC Cruise Lines DSS Project Checklist

This document is the working checklist for the project tool.  
It focuses on the Decision Support System prototype first, before the report or presentation materials.

## 1. Project Scope

- [ ] Confirm the tool is a reservation staffing DSS for ABC Cruise Lines.
- [ ] Keep the scope centered on weekly workload, staffing needs, and labor cost.
- [ ] Define what the tool will not do so the build stays manageable.
- [ ] Lock the scope before development expands too far.

## 2. Core Inputs

- [ ] Weekly forecasted reservation volume.
- [ ] Reservation type or complexity levels.
- [ ] Processing time per reservation type.
- [ ] Worker productivity or throughput.
- [ ] Downtime or inefficiency factor.
- [ ] Labor cost per hour or per worker.
- [ ] Current staffing level.
- [ ] Target service level.

## 3. Workload Calculation Engine

- [ ] Convert demand into total workload hours.
- [ ] Apply complexity weights if needed.
- [ ] Include downtime or special handling assumptions.
- [ ] Produce a weekly workload total.
- [ ] Keep the formula transparent and explainable.

## 4. Staffing Calculation

- [ ] Convert workload hours into required FTE.
- [ ] Round staffing recommendations in a sensible way.
- [ ] Compare required staff to current staff.
- [ ] Calculate staffing gap or surplus.
- [ ] Flag whether the department is understaffed, adequate, or overstaffed.

## 5. Scenario Analysis

- [ ] Build at least three scenarios:
  - [ ] Low demand
  - [ ] Normal demand
  - [ ] Peak demand
- [ ] Show how staffing needs change by scenario.
- [ ] Let the user switch scenarios easily.
- [ ] Display scenario results clearly and side by side if possible.

## 6. Sensitivity Analysis

- [ ] Test how changes in assumptions affect the result.
- [ ] Vary key drivers such as:
  - [ ] Processing time
  - [ ] Productivity
  - [ ] Demand
  - [ ] Downtime
- [ ] Show which assumption has the biggest impact.
- [ ] Present the sensitivity results in a simple table or chart.

## 7. Visual Staffing Recommendation

- [ ] Create a clear recommendation panel for managers.
- [ ] Add a simple status indicator:
  - [ ] Green = sufficient staff
  - [ ] Yellow = borderline
  - [ ] Red = understaffed
- [ ] Show the recommended number of staff.
- [ ] Show the staffing gap clearly.
- [ ] Include a short recommendation sentence.

## 8. Dashboard Visuals

- [ ] Build KPI cards for:
  - [ ] Workload hours
  - [ ] Required FTE
  - [ ] Current staff
  - [ ] Staffing gap
  - [ ] Estimated labor cost
- [ ] Add a chart for scenario comparison.
- [ ] Add a chart or table for sensitivity analysis.
- [ ] Include a short summary section with the final recommendation.

## 9. Case Study

- [ ] Build one realistic sample week.
- [ ] Fill in sample reservation demand and assumptions.
- [ ] Run the DSS on that case.
- [ ] Capture the output clearly.
- [ ] Keep the case study ready for the presentation later.

## 10. Validation

- [ ] Check the calculations with at least one manual test case.
- [ ] Verify that outputs change correctly when inputs change.
- [ ] Confirm the scenario and sensitivity results make sense.
- [ ] Make sure the recommendation matches the math.
- [ ] Remove any confusing or inconsistent logic.

## 11. User Experience

- [ ] Keep the interface simple and clean.
- [ ] Use labels that managers can understand.
- [ ] Avoid clutter.
- [ ] Make key outputs visually obvious.
- [ ] Make the tool easy to demo live.

## 12. Presentation Prep Later

- [ ] Save screenshots of the tool.
- [ ] Save the case study output.
- [ ] Record the assumptions used.
- [ ] Save the scenario and sensitivity results.
- [ ] Keep the final recommendation and takeaway easy to reuse later.

## Recommended Build Order

1. Inputs
2. Core workload math
3. Staffing recommendation
4. Scenario analysis
5. Sensitivity analysis
6. Visual dashboard
7. Case study
8. Validation and polish

## Success Criteria

- [ ] The tool clearly answers how many reservation workers are needed for the week.
- [ ] The tool shows why the answer changes under different conditions.
- [ ] The tool gives managers a visual, easy-to-understand recommendation.
- [ ] The tool feels like a real DSS rather than just a calculator.
