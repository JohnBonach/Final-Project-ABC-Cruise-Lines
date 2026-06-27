# ABC Cruise Lines DSS Improvement Proposal

## Product Direction

Transform the current long-form staffing dashboard into **Voyage Command**, a visual manager cockpit that connects reservation demand, workforce capacity, direct-channel economics, and weekly pricing action. The current staffing engine remains authoritative; the new module adds explicitly simulated commercial decisions grounded in the course brief.

## Manager Decisions

### 1. Reservation Workforce

**Question:** How many in-house reservation agents should ABC schedule next week?

This remains the existing tested probabilistic decision: forecast demand, evaluate capacity and overflow risk, compare the model recommendation with the manager plan, and minimize weekly labor plus expected overflow commission subject to the coverage target.

### 2. Direct-Channel Strategy

**Question:** What in-house booking-capture target creates an attractive annual business case?

Planning inputs:

- Annual commissionable revenue: `$80M` baseline from the supplied prototype.
- Blended travel-agent commission: `12.5%`, midpoint of the brief's 10-15% range.
- Current in-house capture: `0%` baseline because the fictional company is fully outsourced.
- Target in-house capture: `50%` industry benchmark from the brief.
- Annual DSS operating cost: `$1M` transparent planning assumption.

Core outputs:

- Commission paid now and at target.
- Gross commission avoided.
- Net annual benefit after DSS operating cost.
- Target attainment gap and recommendation status.

At the baseline, the model shows `$5M` gross commission avoided and `$4M` net annual benefit, aligning with the sponsor narrative.

### 3. Weekly Commercial Action

**Question:** Should ABC protect yield, hold fares, or promote demand next week?

The recommender reuses the applied forecast, P25/P50/P90 outlooks, average booking values, expected overflow risk, spare capacity, and commission rate. It evaluates three transparent planning actions:

- `Protect Yield`: `+10%` modeled fare move when demand is pressing against capacity.
- `Hold`: no fare change when demand and capacity are balanced.
- `Promote`: `-8%` modeled fare move plus a configurable campaign cost when meaningful capacity is idle.

Demand response uses a clearly labeled synthetic elasticity assumption. The recommendation is constrained by operational guardrails: do not promote into material overflow risk, and do not protect yield when material spare capacity should be filled.

## Information Architecture

Use four top-level tabs without a sidebar:

1. **Command Deck** - visual hero, decision brief, KPI strip, demand trend, and model-versus-manager comparison.
2. **Workforce Planner** - staffing controls, forecast adjustments, assumptions, and plan comparison.
3. **Commercial Strategy** - direct-channel business case and weekly pricing/promotion recommendation.
4. **Scenarios & Evidence** - P25/P50/P90 outlooks, risk-cost table, raw analysis, methodology, and exports.

## Visual Direction

- Mood: refined maritime operations room, not a generic analytics template.
- Palette: deep navy `#082A44`, ocean `#0B6E8A`, sea-glass `#BFE7E5`, warm brass `#C9A14A`, mist `#F2F6F5`, coral alert `#C85B4B`.
- Typography: Georgia for editorial display moments and Trebuchet MS for compact operational UI; both are broadly available without adding a network dependency.
- Assets: use `abc_cruise_logo_v5.svg` for identity and `reservation-bg.jpg` for an atmospheric hero treatment. Avoid the 75 MB video in the Streamlit dashboard.
- Motion: one restrained page-load reveal and deliberate hover lift on decision cards; no continuous animation.
- Responsive behavior: tabs and metric columns stack naturally; the hero reduces display type and image intensity below 760 px.

## Integrity And Scope

- All new commercial numbers are labeled as scenario estimates, not observed facts.
- No live reservation, pricing, or shipboard integration is claimed.
- The original staffing calculations and exports remain available.
- New pure decision functions receive unit tests; the complete regression suite remains a release gate.
