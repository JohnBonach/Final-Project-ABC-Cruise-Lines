# Voyage Command User Guide

## What This Application Does

Voyage Command is a weekly decision-support prototype for ABC Cruise Lines. It converts recent reservation history and editable operating assumptions into two connected decisions:

1. How many in-house reservation agents should be planned for the coming week?
2. Should the commercial posture Protect Yield, Hold, or Promote, and what is the estimated channel economics of each choice?

The data is simulated. Results are planning estimates, not actual bookings, causal forecasts, or production pricing instructions.

## Command Deck

The Command Deck is the executive summary. The large recommendation is the model-selected number of agents. The chips beneath it show modeled in-house coverage, forecast bookings, and total weekly operating cost.

Decision Signals compare this week's recommendation with the same forecast evaluated at last week's staffing level. A positive delta is green and a negative delta is red. This is a like-for-like modeled comparison, not an accounting comparison with last week's actual results.

- **Recommended Agents:** whole agents selected by the model.
- **Coverage Probability:** share of simulated weeks handled completely in-house.
- **Overflow Risk:** probability that at least some work must be sent to a third party.
- **Central Demand:** median simulated booking outlook for this week.
- **Spare Capacity:** average unused in-house processing hours.
- **Overflow Commission:** expected commission paid for overflow bookings.
- **Weekly Operating Cost:** regular labor plus expected overflow commission.
- **Manager Plan:** the manager-entered staffing proposal, shown for comparison.

Run Analysis applies draft changes from the Workforce Planner. Until it is clicked, the existing result remains visible and a stale-result warning appears.

## Workforce Planner

This section controls the staffing recommendation.

- **Minimum in-house coverage target:** required probability of processing all weekly demand internally.
- **Manager proposed staffing:** exact staffing level to evaluate beside the recommendation; it does not force the recommendation.
- **Forecast overrides:** optional manager forecasts that replace the automatic forecast for selected cruise categories.
- **Paid hours per agent:** paid weekly hours used in labor cost.
- **Booking processing hours per agent:** productive weekly capacity available for reservation handling.
- **Hourly wage:** regular labor cost per paid hour.
- **Minimum and maximum agents:** feasible range searched by the recommendation model.
- **Commission rate:** percentage paid on bookings handled by third parties.

## Commercial Strategy

### Direct-Channel Business Case

This is an annual strategic scenario. It estimates the value of moving bookings from third-party agents to ABC's direct channel.

- **Annual commissionable revenue:** booking revenue to which agent commission could apply.
- **Current direct capture:** share already booked directly.
- **Target direct capture:** proposed future direct share.
- **Annual DSS operating cost:** assumed annual cost of the direct-channel organization and decision system.

Key calculations:

```text
Commission paid = annual revenue x (1 - direct capture) x commission rate
Gross commission avoided = annual revenue x target direct capture x commission rate
Net annual benefit = gross commission avoided - annual DSS operating cost
```

The Current, Target, and Stretch rows are scenarios. They update immediately when an annual control changes.

### Weekly Commercial Action

This section compares three fare actions. All controls update the live impact cards, comparison table, and chart immediately.

- **Weekly direct capture:** reduces third-party commission as more bookings are handled directly.
- **Price elasticity:** controls how strongly scenario bookings respond to fare changes. For example, elasticity 0.80 and an 8% discount imply a 6.4% booking increase in the Promote scenario.
- **Promotion cost:** campaign spend deducted only from Promote.

Actions:

- **Protect Yield:** raises fares 10% and estimates a booking reduction of `elasticity x 10%`.
- **Hold:** leaves fares and forecast demand unchanged.
- **Promote:** lowers fares 8% and estimates a booking increase of `elasticity x 8%`.

Weekly formulas:

```text
Scenario bookings = base forecast x (1 - elasticity x fare change)
Gross revenue = scenario bookings x average booking value x (1 + fare change)
Agent commission = gross revenue x (1 - direct capture) x commission rate
Net revenue after channel cost = gross revenue - agent commission - campaign cost
```

The headline action is deliberately controlled by operational guardrails rather than whichever scenario has the highest estimated revenue:

- Protect Yield when overflow risk is at least 20%.
- Promote when overflow risk is below 10% and spare capacity is at least half one agent's productive weekly capacity.
- Hold otherwise.

Therefore, changing a weekly commercial control can change all financial estimates without changing the headline action. To change the operational pressure behind the headline action, adjust staffing or forecast inputs and run the staffing analysis again.

## Scenarios And Evidence

The 25th, 50th, and 90th percentile cards are coherent simulated weeks ordered by total workload.

- **25th percentile:** about 25% of simulated workloads are at or below this lower-demand level.
- **50th percentile:** the median; half are at or below this level.
- **90th percentile:** about 90% are at or below this higher-demand planning level.

Each card shows bookings, workload, FTE, constrained staffing, spare or overflow hours, and vertically stacked cost figures. The staffing risk-cost table shows every evaluated staffing level and identifies the recommendation, manager proposal, and previous-week level.

## Calculation Methodology

```text
Central forecast = 0.40 x latest week + 0.30 x prior week
                 + 0.20 x two weeks ago + 0.10 x three weeks ago

Workload hours = sum(bookings by category x handling minutes) / 60
Raw FTE = workload hours / productive booking-processing hours per agent
Regular labor cost = agents x paid hours x hourly wage
Coverage probability = simulations fully handled in-house / total simulations
Overflow risk = 1 - coverage probability
Expected overflow commission = average simulated overflow bookings
                               x booking value x commission rate
Total weekly operating cost = regular labor cost + expected overflow commission
```

The model evaluates every feasible whole-agent level. It selects the lowest total-cost level meeting the coverage target. If the target is impossible within the configured maximum, it selects the maximum-coverage fallback and displays a warning.

The default simulation runs 5,000 normal-distribution trials with random seed 510, so unchanged inputs produce reproducible results.
