# ABC Cruise Lines Reservation Staffing Decision Support System

## Detailed System Design and Project Description

### 1. Project title

**ABC Cruise Lines Reservation Staffing Decision Support System**

### 2. Project overview

ABC Cruise Lines plans to develop an internal reservation operation that will allow the company to receive and process customer bookings directly instead of relying entirely on third-party travel agents.

Bringing the reservation function in-house creates a new operational planning problem. Managers must estimate the number and types of reservations expected during an upcoming week, determine the amount of work those reservations will generate, and decide how many reservation agents should be scheduled.

Demand is uncertain. If too few agents are scheduled, some customers may abandon their reservations and the remaining excess workload may require overtime. If too many agents are scheduled, ABC Cruise Lines will pay for capacity that is not required.

The project will develop a working Decision Support System using Python and Streamlit. The DSS will forecast weekly reservation demand, represent demand uncertainty probabilistically, translate forecasted reservations into workload hours, compare multiple staffing strategies, estimate their operational and financial consequences, and recommend a weekly staffing level.

The DSS is not intended to replace managerial judgment. It will give managers structured, explainable, and interactive information that helps them compare the consequences of different staffing choices.

---

## 3. Business problem

ABC Cruise Lines must determine how many reservation agents should be available during an upcoming week.

The staffing decision is difficult because:

* Weekly reservation demand changes over time.
* Different reservation categories require different amounts of processing time.
* The demand forecast will never be completely accurate.
* Insufficient staffing can create customer abandonment and overtime.
* Excess staffing increases regular labor cost.
* Different staffing strategies provide different levels of protection against demand uncertainty.
* Managers may value lower cost, greater capacity confidence, or lower customer-loss risk differently.

A simple staffing calculator would produce only one number based on one forecast. That would not adequately represent the uncertainty or tradeoffs involved in the decision.

The proposed DSS will instead estimate a distribution of possible weekly demand outcomes and evaluate how different staffing levels perform across those outcomes.

---

## 4. Project objective

The primary objective is to develop a realistic weekly staffing DSS that helps ABC Cruise Lines operational managers answer the following question:

> How many reservation agents should ABC Cruise Lines schedule for the upcoming week, considering expected demand, forecast uncertainty, reservation complexity, labor cost, overtime, customer abandonment, and the financial value of completed reservations?

The system will provide:

1. An automatic weekly demand forecast.
2. Forecast uncertainty estimates.
3. A weekly workload estimate.
4. Required full-time-equivalent staffing.
5. Whole-agent staffing recommendations.
6. Lean, Balanced, and Conservative staffing alternatives.
7. Expected regular labor cost.
8. Expected overtime requirements and cost.
9. Expected abandoned reservations.
10. Estimated lost revenue and lost contribution.
11. A financially recommended staffing plan.
12. A comparison with previous-week and manager-planned staffing.

---

## 5. Primary system user

The primary user is the **ABC Cruise Lines Reservation Manager** or another operational manager responsible for weekly workforce planning.

The manager is expected to understand reservation operations but should not need to understand Python, simulation, or the internal mathematical implementation.

The interface must therefore:

* Use plain operational terminology.
* Display units beside every input.
* Provide understandable default values.
* Explain major assumptions.
* Present recommendations visually.
* Allow assumptions to be modified interactively.
* Show why a recommendation was produced.

---

## 6. Decision supported by the DSS

The DSS supports a weekly tactical staffing decision.

The manager must decide how many reservation agents to schedule for the upcoming week.

The system will distinguish among:

* **Previous-week staffing:** the number of agents used during the most recently completed week.
* **Manager-planned staffing:** the number of agents the manager is currently considering for the upcoming week.
* **Recommended staffing:** the staffing level calculated by the DSS.
* **Alternative staffing plans:** Lean, Balanced, and Conservative plans based on different capacity-confidence targets.

The DSS will evaluate staffing in whole agents. It will also calculate decimal FTE requirements as an analytical measure.

---

## 7. Planning horizon

The primary planning horizon is **one week**.

The system will not initially perform:

* Hourly staffing.
* Shift scheduling.
* Queueing analysis.
* Intraday arrival modeling.
* Daily workforce allocation.
* Individual employee scheduling.

A daily breakdown may be considered in a future version, but it is not required for the initial prototype.

The weekly scope keeps the model consistent with the submitted project outline and prevents unnecessary expansion into a full workforce-management system.

---

## 8. Technology and system platform

The DSS will be developed using:

* Python
* Streamlit
* pandas
* NumPy
* Appropriate Python visualization libraries
* CSV or similar local files for prototype data storage

Streamlit will provide the user interface, input controls, charts, tables, recommendation panels, and scenario outputs.

The prototype should run locally using a documented command such as:

```bash
streamlit run app.py
```

The final submission should include:

* Source code.
* Required data files.
* Dependency file.
* README with setup and execution instructions.
* Sample data.
* Validation examples.
* Screenshots or other report evidence.

---

## 9. Reservation workload categories

Weekly demand will be forecast and modeled separately for four reservation workload categories.

### 9.1 Simple reservation

A relatively straightforward reservation for a half-day or one-day cruise with limited selections or special requirements.

Examples may include:

* Cruise selection.
* Departure date.
* Basic passenger information.
* Standard payment processing.

### 9.2 Standard reservation

A typical reservation for a seven-night or nine-night cruise.

It may include:

* Cruise and departure selection.
* Cabin selection.
* Transportation selection.
* Meal-plan selection.
* Onboard-credit options.
* Port excursions.
* Payment processing.

### 9.3 Complex or group reservation

A reservation requiring additional coordination or processing.

Examples may include:

* Corporate groups.
* Multiple passengers or cabins.
* Special transportation arrangements.
* Special customer requirements.
* Multiple excursions or package components.
* Additional communication and documentation.

### 9.4 Reservation change or cancellation

Work related to an existing reservation rather than a new booking.

Examples may include:

* Date changes.
* Cabin changes.
* Passenger changes.
* Transportation changes.
* Excursion changes.
* Rebooking.
* Cancellation processing.

Each category will have its own:

* Historical weekly demand.
* Forecasted weekly demand.
* Demand variability.
* Average handling time.
* Average revenue value.
* Contribution value or margin assumption.

---

## 10. Historical and synthetic data

Because ABC Cruise Lines is fictional and does not provide an actual internal reservation database, the prototype will use synthetic weekly historical data.

The synthetic dataset should initially contain approximately 8 to 12 weeks of observations.

Each row should represent one week and include fields such as:

* Week identifier.
* Simple reservation volume.
* Standard reservation volume.
* Complex or group reservation volume.
* Change or cancellation volume.
* Previous-week staffing.
* Regular hourly labor cost.
* Relevant seasonal or demand indicator, if included.
* Any other assumptions needed by the prototype.

The synthetic data should be realistic enough to demonstrate:

* Week-to-week demand variation.
* Differences among reservation categories.
* Occasional higher-demand weeks.
* A reasonable staffing requirement near the case-study expectation.
* Meaningful forecast uncertainty.

A separate script should eventually generate or regenerate the synthetic dataset using controlled assumptions and a reproducible random seed.

---

## 11. Automatic demand forecasting

The system will automatically forecast the upcoming week’s demand separately for each reservation category.

The initial forecasting method will be a four-week weighted moving average.

The default weights will be:

* Most recent week: 40 percent.
* Second most recent week: 30 percent.
* Third most recent week: 20 percent.
* Fourth most recent week: 10 percent.

For reservation category (c):

[
Forecast_c =
0.40D_{c,t-1}

* 0.30D_{c,t-2}
* 0.20D_{c,t-3}
* 0.10D_{c,t-4}
  ]

Where:

* (D_{c,t-1}) is the most recent observed demand.
* (D_{c,t-2}) is demand two weeks before the forecast.
* (D_{c,t-3}) is demand three weeks before the forecast.
* (D_{c,t-4}) is demand four weeks before the forecast.

The automatic forecast will serve as the default input.

The manager will also be able to override the forecast for one or more categories when operational information suggests that the historical forecast is not appropriate.

Examples may include:

* A promotional campaign.
* A holiday week.
* A new cruise offering.
* A large corporate-group inquiry.
* A temporary reduction in cruise availability.

The interface must clearly identify whether the current analysis uses:

* Automatic forecast values.
* Manager-adjusted forecast values.

---

## 12. Forecast uncertainty

The forecast will not be treated as a guaranteed outcome.

Historical variability will be estimated separately for each reservation category using the standard deviation of historical weekly demand.

The manager will be able to adjust a demand-variability multiplier.

Examples:

* 0.5: demand is assumed to be more stable than the historical pattern.
* 1.0: use historical variability.
* 1.5: demand is assumed to be more uncertain than the historical pattern.
* 2.0: high uncertainty or disruption scenario.

For category (c):

[
Adjusted\ Standard\ Deviation_c
===============================

Historical\ Standard\ Deviation_c
\times
Variability\ Multiplier
]

The prototype will use an appropriate probability distribution for weekly demand. The initial implementation may use a normal distribution with safeguards that:

* Prevent demand from becoming negative.
* Round demand to whole reservations.
* Preserve separate demand values for each category.

A truncated normal or zero-clipped normal distribution may be used for the initial prototype.

---

## 13. Monte Carlo simulation

The DSS will use Monte Carlo simulation to represent many possible upcoming-week demand outcomes.

A simulation run may contain approximately 5,000 to 10,000 iterations.

During each iteration, the system will:

1. Generate simulated demand for each reservation category.
2. Apply the category-specific handling time.
3. Calculate total simulated workload.
4. Determine how much work can be completed with a selected staffing level.
5. Calculate excess workload.
6. Estimate customer abandonment.
7. Assign the remaining excess workload to overtime.
8. Calculate labor cost.
9. Calculate lost revenue and lost contribution.
10. Record the operational and financial outcome.

The simulation results will form distributions rather than single deterministic outputs.

This allows the DSS to estimate:

* Probability that regular capacity is sufficient.
* Probability that overtime will be needed.
* Expected overtime hours.
* Expected abandoned reservations.
* Expected lost revenue.
* Expected lost contribution.
* Expected total economic cost.
* Expected net contribution.

---

## 14. Handling-time assumptions

Each reservation category will have an editable average handling time measured in minutes per reservation.

Illustrative fields include:

* Simple reservation handling time.
* Standard reservation handling time.
* Complex or group reservation handling time.
* Change or cancellation handling time.

The manager will be able to modify these values through the Streamlit interface.

This provides a simple process-improvement analysis.

For example, the manager may test:

* What happens if simple reservations become faster?
* What happens if a new reservation system reduces standard handling time?
* What happens if complex bookings require more coordination than originally assumed?
* How much staffing can be avoided through process improvements?

A separate efficiency multiplier is not required in the first version because editable handling times already represent productivity changes.

---

## 15. Weekly workload calculation

For each reservation category (c):

[
Workload\ Minutes_c
===================

Demand_c
\times
Average\ Handling\ Time_c
]

Total weekly workload minutes:

[
Total\ Workload\ Minutes
========================

\sum_c Workload\ Minutes_c
]

Total weekly workload hours:

[
Total\ Workload\ Hours
======================

\frac{Total\ Workload\ Minutes}{60}
]

The same calculation will be performed during each Monte Carlo iteration using the simulated demand values.

---

## 16. Agent capacity

Each full-time agent will be assumed to have:

* 40 paid hours per week by default.
* An editable productive-processing percentage.

The recommended official term is:

**Productive processing percentage**

This represents the percentage of paid time available for reservation-related processing after accounting for:

* Breaks.
* Meetings.
* Training.
* Administrative duties.
* Normal interruptions.
* Other non-processing time.

Default example:

* Paid hours per agent: 40.
* Productive processing percentage: 85 percent.

Effective productive hours per agent:

[
Productive\ Hours\ per\ Agent
=============================

Paid\ Weekly\ Hours
\times
Productive\ Processing\ Percentage
]

Example:

[
40 \times 0.85 = 34\ productive\ hours
]

This combined measure avoids separately modeling shrinkage and occupancy in the first version.

---

## 17. Required FTE calculation

For a deterministic forecast:

[
Required\ FTE
=============

\frac{Forecasted\ Workload\ Hours}
{Productive\ Hours\ per\ Agent}
]

The DSS will show:

* Decimal required FTE.
* Whole-agent requirement using upward rounding.
* Difference from previous-week staffing.
* Difference from manager-planned staffing.

Example:

* Calculated requirement: 8.4 FTE.
* Whole-agent staffing requirement: 9 agents.

During simulation, required staffing will be calculated for every simulated week. This creates a probability distribution of weekly staffing requirements.

---

## 18. Previous-week and planned staffing

The DSS will display three staffing values.

### 18.1 Previous-week staffing

This is obtained from the historical dataset and is read-only.

It provides the default baseline for comparison.

### 18.2 Manager-planned staffing

This is an editable value representing the number of agents the manager is currently considering for the upcoming week.

It allows the system to evaluate the manager’s current plan.

### 18.3 DSS-recommended staffing

This is calculated by the system after considering uncertainty, cost, overtime, and abandonment.

Example:

* Previous-week staffing: 9.
* Manager-planned staffing: 8.
* DSS recommendation: 10.
* Recommended change from previous week: +1.
* Recommended change from current plan: +2.

---

## 19. Staffing alternatives

The DSS will produce three primary staffing alternatives based on the simulated distribution of required staffing.

### 19.1 Lean plan

Default confidence target: 50th percentile.

Purpose:

* Lowest regular staffing among the three main plans.
* Covers approximately the median simulated workload.
* Greater probability of overtime.
* Greater probability of customer abandonment.
* Appropriate when the manager prioritizes lower scheduled labor cost.

### 19.2 Balanced plan

Default confidence target: approximately 80 to 85 percent.

Purpose:

* Covers most simulated demand outcomes.
* Balances regular labor cost and shortage risk.
* Expected to be the most practical option in many cases.

### 19.3 Conservative plan

Default confidence target: approximately 95 percent.

Purpose:

* Covers nearly all simulated demand outcomes.
* Lowest overtime and abandonment risk.
* Highest regular labor cost.
* Appropriate when service protection is more important than minimizing scheduled staffing.

The manager will be able to modify the three confidence targets.

The labels Lean, Balanced, and Conservative are preferred over optimistic and pessimistic because they describe management strategy more clearly.

---

## 20. Insufficient-capacity logic

When regular staffing capacity is lower than simulated workload, the model will calculate excess workload.

The prototype will assume the following sequence:

1. Regular staff complete work up to their productive capacity.
2. Some customers associated with the excess workload abandon the reservation process.
3. The remaining excess workload is completed through overtime.

Example:

* Simulated demand: 100 reservations.
* Regular capacity: 90 reservations.
* Excess demand: 10 reservations.
* Abandonment rate: 10 percent.
* Abandoned reservations: 1.
* Reservations completed through overtime: 9.

Formula:

[
Abandoned\ Reservations
=======================

Excess\ Reservations
\times
Abandonment\ Rate
]

[
Overtime\ Reservations
======================

## Excess\ Reservations

Abandoned\ Reservations
]

The initial version will use one global, editable abandonment rate.

Even though one rate is used, abandoned reservations will retain their category identity so that financial consequences can reflect different reservation values.

For the first version, shortages may be distributed proportionally across reservation categories according to their share of excess workload. Priority-based allocation may be considered in a later version.

---

## 21. Overtime calculation

Overtime is used only after regular productive capacity has been exhausted.

The initial overtime model will include:

* Regular hourly wage.
* Overtime wage multiplier.
* Overtime workload hours.
* Expected overtime cost.

Default overtime multiplier:

[
1.5 \times Regular\ Hourly\ Wage
]

Overtime cost:

[
Overtime\ Cost
==============

Overtime\ Hours
\times
Regular\ Hourly\ Wage
\times
Overtime\ Multiplier
]

The initial prototype may assume that sufficient overtime is available to complete all non-abandoned excess workload.

A future enhancement could introduce:

* Maximum overtime hours per agent.
* Maximum total overtime.
* Temporary or part-time labor.
* Unprocessed backlog when overtime is insufficient.

---

## 22. Financial value by reservation category

Each reservation category will have separate editable financial assumptions.

These should include:

* Average gross revenue per completed reservation.
* Average contribution amount or contribution-margin percentage.
* Lost revenue per abandoned reservation.
* Lost contribution per abandoned reservation.

Gross revenue and contribution must be distinguished.

### Gross revenue

The total revenue associated with a completed reservation.

### Contribution

The amount remaining after relevant variable costs. This is more appropriate for staffing optimization because it represents the economic value lost when a reservation is abandoned.

For category (c):

[
Lost\ Revenue_c
===============

Abandoned\ Reservations_c
\times
Average\ Revenue_c
]

[
Lost\ Contribution_c
====================

Abandoned\ Reservations_c
\times
Contribution\ Value_c
]

The system will report both lost revenue and lost contribution.

The primary optimization should use lost contribution rather than gross revenue.

For changes and cancellations, the financial value may be:

* Zero direct new revenue.
* A smaller retention value.
* An editable service-value assumption.

The prototype should allow this category to have a lower value than a new reservation.

---

## 23. Regular labor cost

Regular labor cost for staffing level (N):

[
Regular\ Labor\ Cost
====================

N
\times
Paid\ Weekly\ Hours
\times
Regular\ Hourly\ Wage
]

Unused productive capacity will be displayed as an operational metric but will not receive an additional financial penalty.

The cost of excess staffing is already represented through regular wages paid for agents whose capacity is not fully used.

This avoids double-counting.

---

## 24. Expected total economic cost

For each staffing alternative, the system will estimate:

[
Expected\ Total\ Economic\ Cost
===============================

Regular\ Labor\ Cost
+
Expected\ Overtime\ Cost
+
Expected\ Lost\ Contribution
]

This combines:

* Actual scheduled labor cost.
* Expected overtime cost.
* Opportunity cost from abandoned reservations.

The system may also calculate:

[
Expected\ Net\ Contribution
===========================

## Expected\ Retained\ Contribution

## Regular\ Labor\ Cost

Expected\ Overtime\ Cost
]

Both measures should be displayed.

The staffing rankings produced by these measures should generally be consistent because potential demand is shared across the evaluated staffing options.

---

## 25. Financial recommendation

The DSS will provide one primary financial recommendation.

The recommended staffing level will be the feasible whole-agent staffing option with the lowest expected total economic cost.

The recommendation will consider:

* Regular labor cost.
* Expected overtime cost.
* Expected abandoned reservations.
* Expected lost contribution.
* Probability of sufficient regular capacity.

The system should not recommend the lowest regular labor cost without considering shortage consequences.

It should also not automatically recommend the highest-confidence plan without considering unnecessary labor cost.

Example recommendation:

> Schedule 9 reservation agents. This option provides an estimated 86 percent probability that regular capacity will be sufficient and produces the lowest expected total economic cost. Compared with scheduling 8 agents, it increases regular labor cost but reduces expected overtime and abandonment losses. Scheduling 10 agents provides greater capacity protection but has a slightly higher expected total cost.

---

## 26. Internal staffing evaluation

The user interface will emphasize the Lean, Balanced, and Conservative plans.

Internally, the model may evaluate all relevant whole-agent staffing levels within a simulation-derived range.

The range should be derived from the staffing distribution rather than chosen arbitrarily.

For example:

* Lower evaluation bound: a low percentile of simulated required staffing.
* Upper evaluation bound: a high percentile of simulated required staffing.

The purpose is to ensure that the financial optimum is not missed simply because it does not exactly match one of the three named confidence plans.

The interface may display:

* The three named plans.
* The financially optimal plan.
* The manager’s planned staffing result.
* The previous-week staffing result.

Duplicate plans should be handled clearly. For example, if the 50th and 85th percentiles both produce nine whole agents, the interface should explain that both confidence targets lead to the same staffing requirement.

---

## 27. Manager-adjustable inputs

The Streamlit application should allow the manager to modify the following assumptions.

### Demand inputs

* Use automatic forecast or manual forecast.
* Forecasted simple reservations.
* Forecasted standard reservations.
* Forecasted complex or group reservations.
* Forecasted changes and cancellations.
* Demand-variability multiplier.

### Processing assumptions

* Simple handling time.
* Standard handling time.
* Complex handling time.
* Change or cancellation handling time.
* Paid hours per agent.
* Productive processing percentage.

### Staffing assumptions

* Manager-planned staffing.
* Regular hourly wage.
* Overtime multiplier.
* Global abandonment rate.

### Financial assumptions

For each category:

* Average revenue per completed reservation.
* Contribution value or margin.
* Retention or service value where applicable.

### Confidence-plan assumptions

* Lean confidence target.
* Balanced confidence target.
* Conservative confidence target.

### Simulation assumptions

* Number of Monte Carlo iterations.
* Optional random seed for reproducibility.

---

## 28. Core outputs

The DSS should produce the following outputs.

### Forecast outputs

* Automatic forecast by category.
* Manual override values, when used.
* Historical mean by category.
* Historical standard deviation by category.
* Forecast-variability multiplier.
* Forecast distribution visualization.

### Workload outputs

* Workload hours by category.
* Total expected workload hours.
* Productive hours per agent.
* Decimal FTE requirement.
* Whole-agent deterministic requirement.

### Staffing outputs

* Previous-week staffing.
* Manager-planned staffing.
* Lean staffing.
* Balanced staffing.
* Conservative staffing.
* Financially recommended staffing.
* Staffing difference from previous week.
* Staffing difference from manager plan.

### Risk outputs

* Probability regular capacity is sufficient.
* Probability overtime is required.
* Expected overtime hours.
* Expected abandoned reservations.
* Expected shortage workload.
* Expected unused regular capacity.

### Financial outputs

* Regular labor cost.
* Expected overtime cost.
* Expected lost revenue.
* Expected lost contribution.
* Expected total economic cost.
* Expected retained revenue.
* Expected retained contribution.
* Expected net contribution.

---

## 29. Dashboard and Streamlit interface

The application should be designed as a clean manager-facing DSS.

A practical interface may include the following sections or tabs.

### 29.1 Executive recommendation

This section should immediately show:

* Recommended agents.
* Capacity confidence.
* Expected total economic cost.
* Expected overtime.
* Expected abandonment.
* Difference from previous-week staffing.
* Difference from manager-planned staffing.
* Short written recommendation.

### 29.2 Forecast and historical demand

This section should show:

* Historical weekly demand.
* Weighted moving-average forecast.
* Demand by category.
* Forecast uncertainty.
* Manager override controls.

### 29.3 Operational assumptions

This section should contain:

* Handling times.
* Productive processing percentage.
* Paid hours.
* Planned staffing.
* Abandonment rate.
* Overtime assumptions.

### 29.4 Staffing-plan comparison

A table should compare:

* Previous-week plan.
* Manager-planned staffing.
* Lean plan.
* Balanced plan.
* Conservative plan.
* Financially recommended plan.

### 29.5 Simulation and risk results

This section should show:

* Distribution of required staffing.
* Probability of sufficient capacity.
* Overtime distribution.
* Abandonment distribution.
* Confidence-level markers.

### 29.6 Financial analysis

This section should show:

* Regular labor cost.
* Overtime cost.
* Lost revenue.
* Lost contribution.
* Expected total economic cost.
* Expected net contribution.

### 29.7 Methodology and assumptions

This section should explain:

* Forecasting method.
* Simulation method.
* Workload formulas.
* Staffing formulas.
* Financial formulas.
* Limitations.

---

## 30. Recommended visualizations

The initial prototype should use a limited number of meaningful visualizations.

Recommended visuals include:

1. Historical demand and forecast by category.
2. Distribution of simulated weekly workload.
3. Distribution of required agents.
4. Staffing-plan comparison table.
5. Expected economic cost by staffing option.
6. Probability of sufficient capacity by staffing option.
7. Cost composition by staffing option.
8. Previous-week, planned, and recommended staffing comparison.
9. Workload contribution by reservation category.

The dashboard should avoid displaying large raw spreadsheets as the primary output.

---

## 31. Recommendation language

The system should produce an automatically generated management summary.

Example:

> Based on the current weighted moving-average forecast and historical demand variability, the DSS recommends scheduling 9 reservation agents for the upcoming week. This staffing level provides an estimated 86 percent probability of meeting demand using regular capacity. The expected overtime requirement is 7.4 hours, and expected abandonment is 1.2 reservations. This option has a lower expected total economic cost than the Lean and Conservative alternatives.

The recommendation text must change when assumptions or forecast values change.

---

## 32. Scenario and sensitivity analysis

The interactive interface already provides basic sensitivity analysis because managers can modify assumptions and immediately observe the results.

The DSS should support testing changes in:

* Demand forecast.
* Demand variability.
* Handling time.
* Productive processing percentage.
* Abandonment rate.
* Hourly wage.
* Overtime multiplier.
* Reservation financial value.
* Confidence targets.

The project may also define three named demand scenarios:

* Low-demand scenario.
* Expected-demand scenario.
* High-demand scenario.

However, these scenarios should not replace the Monte Carlo simulation. They should serve as simpler illustrations of the probabilistic results.

---

## 33. Case study

The project report must include at least one detailed case study.

The case study should:

1. Select one synthetic forecast week.
2. Show the preceding historical demand.
3. Calculate the weighted moving-average forecast.
4. Estimate uncertainty.
5. Run the simulation.
6. Calculate workload.
7. Compare previous-week and planned staffing.
8. Present Lean, Balanced, and Conservative plans.
9. Present the financially recommended plan.
10. Explain the operational and financial tradeoffs.
11. Show how the recommendation changes when one major assumption is modified.

A useful secondary comparison could show the effect of:

* Lower handling time.
* Higher abandonment.
* Higher demand variability.
* Higher overtime cost.

---

## 34. Validation requirements

The prototype must be validated mathematically and functionally.

### Mathematical validation

* Manually calculate at least one deterministic workload example.
* Manually calculate required FTE.
* Manually calculate productive capacity.
* Manually calculate abandonment and overtime for a shortage case.
* Manually calculate regular labor and overtime cost.
* Compare manual results with program outputs.

### Simulation validation

* Confirm that higher forecast demand increases required staffing.
* Confirm that higher variability increases high-confidence staffing.
* Confirm that longer handling times increase workload.
* Confirm that higher productive processing percentage reduces staffing requirements.
* Confirm that higher abandonment reduces overtime but increases lost contribution.
* Confirm that higher overtime cost can shift the recommendation toward more regular staff.
* Confirm that higher contribution value can shift the recommendation toward more regular staff.
* Confirm that a fixed random seed reproduces results.

### Interface validation

* Reject negative demand.
* Reject negative handling times.
* Reject invalid percentages.
* Prevent confidence levels outside valid limits.
* Prevent division by zero.
* Display units.
* Provide clear error messages.
* Ensure the app does not crash under extreme but valid inputs.
* Provide reset-to-default functionality.

---

## 35. Robustness requirements

The final prototype should be considered robust if it:

* Runs from documented instructions.
* Includes all required dependencies.
* Handles missing or malformed data.
* Prevents invalid user inputs.
* Produces stable results.
* Uses reproducible synthetic data.
* Uses reproducible simulation when a seed is selected.
* Separates calculation logic from interface code where practical.
* Includes comments and clear function names.
* Includes default assumptions.
* Shows meaningful error messages.
* Can be demonstrated without manually editing source code.
* Can be tested on a computer other than the developer’s primary machine.

---

## 36. Key assumptions

The initial prototype will assume:

1. Weekly historical demand is sufficiently representative for creating a synthetic forecast example.
2. The four reservation categories capture the major differences in workload.
3. Average handling time is a suitable approximation within each category.
4. All full-time agents have similar productive capacity.
5. The productive processing percentage combines non-processing time into one assumption.
6. Customer abandonment applies only to workload exceeding regular capacity.
7. One global abandonment rate is sufficient for the first version.
8. Non-abandoned excess demand can be processed through overtime.
9. Overtime is available when required in the first version.
10. Reservation financial values can be represented using category averages.
11. Lost contribution is more appropriate than gross revenue for optimization.
12. Staffing decisions are made in whole agents.
13. The model supports weekly tactical planning rather than individual shift scheduling.
14. The synthetic data does not represent an actual cruise company.
15. The manager may override forecast and operating assumptions when better information is available.

---

## 37. Limitations

The initial prototype will have several limitations.

* It uses synthetic rather than actual company data.
* It does not model hourly arrival patterns.
* It does not model customer waiting-time behavior directly.
* It uses a simplified global abandonment rate.
* It does not schedule individual employees or shifts.
* It assumes average handling times within each category.
* It does not model differences in agent skill.
* It does not initially limit overtime availability.
* It does not model recruitment lead time.
* It does not model training requirements.
* It does not model part-time or temporary-worker scheduling in the first version.
* It does not integrate with a real reservation system.
* It does not forecast cruise prices.
* It does not optimize cabin inventory.
* It does not perform revenue management.
* It does not transfer bookings to shipboard systems.
* It does not make customer-facing reservations.

These limitations should be stated clearly and presented as opportunities for future improvement rather than hidden.

---

## 38. Out-of-scope functions

The following functions are intentionally outside the initial project scope:

* Building the customer reservation system.
* Taking customer payments.
* Managing cabins.
* Pricing cruises.
* Revenue-management integration.
* Shipboard-system integration.
* Marketing campaign optimization.
* Travel-agent commission management.
* Individual employee rostering.
* Hourly call-center queueing.
* Daily shift scheduling.
* Hiring and recruitment workflow.
* Employee training optimization.
* Customer relationship management.

The DSS uses reservation demand as an input to support staffing decisions. It does not execute the reservation process itself.

---

## 39. Future enhancements

Possible future enhancements include:

* Daily workload allocation.
* Hourly demand forecasting.
* Queueing and waiting-time analysis.
* Maximum overtime constraints.
* Part-time staffing.
* Temporary staffing.
* Employee skill levels.
* Category-specific abandonment rates.
* Priority processing for high-value reservations.
* Customer patience and waiting-time modeling.
* Backlog across weeks.
* Seasonal forecasting.
* Promotional-event variables.
* Cruise departure schedules.
* Machine-learning forecasts.
* Integration with an actual reservation database.
* Real-time dashboard updates.
* Comparison between internal booking cost and travel-agent commissions.
* Optimization across staffing, overtime, and temporary labor simultaneously.

---

## 40. Project success criteria

The DSS will be considered successful if:

1. It runs as a working Streamlit application.
2. It uses historical synthetic data to forecast weekly demand.
3. It models four reservation categories.
4. It represents demand uncertainty probabilistically.
5. It calculates workload and required FTE correctly.
6. It compares multiple confidence-based staffing plans.
7. It models regular capacity, abandonment, and overtime.
8. It estimates regular cost, overtime cost, lost revenue, and lost contribution.
9. It recommends a financially justified staffing level.
10. It explains the recommendation in understandable language.
11. It allows managers to change assumptions interactively.
12. It includes at least one documented case study.
13. Its calculations are manually validated.
14. It handles invalid inputs without crashing.
15. A manager can understand the results without knowing the underlying code.

---

## 41. End-to-end system flow

The complete DSS process will be:

```text
Synthetic historical weekly reservation demand
                    ↓
Demand separated into four reservation categories
                    ↓
Four-week weighted moving-average forecast
                    ↓
Historical standard deviation by category
                    ↓
Manager forecast overrides and variability settings
                    ↓
Monte Carlo simulation of weekly demand
                    ↓
Category demand multiplied by category handling time
                    ↓
Simulated weekly workload distribution
                    ↓
Productive hours per agent
                    ↓
Distribution of required weekly staffing
                    ↓
Lean, Balanced, and Conservative staffing plans
                    ↓
Evaluation of regular capacity
                    ↓
Excess workload, abandonment, and overtime
                    ↓
Regular labor cost, overtime cost, lost revenue,
lost contribution, and net contribution
                    ↓
Comparison with previous-week and manager-planned staffing
                    ↓
Financially recommended staffing level
                    ↓
Manager-facing dashboard and recommendation
```

---

## 42. Final system concept

The final product will be an interactive weekly reservation staffing DSS, not merely a staffing calculator.

Its value comes from combining:

* Historical demand.
* Forecasting.
* Demand uncertainty.
* Reservation complexity.
* Workload calculations.
* Staffing capacity.
* Customer abandonment.
* Overtime.
* Revenue exposure.
* Contribution loss.
* Confidence-based alternatives.
* Financial optimization.
* Explainable recommendations.

The manager will be able to see not only how many agents are recommended, but also why that number is recommended, what risks accompany lower staffing, what cost accompanies higher staffing, and how the decision changes when operational assumptions change.
