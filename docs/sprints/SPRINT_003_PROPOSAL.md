# Sprint 003 Proposal: Portfolio Snapshot + Holdings Foundation

- Date: 2026-07-17
- Status: Approved — Owner Decisions Resolved. Implementation Not Authorized.
- Baseline: main @ 3c5edec

## Context

Sprint 002 delivered Household, Investment Policy, Decision Journal, and Safe
Autopilot infrastructure. CompoundOS now has a documented household, a machine-
readable investment policy with immutable version history, an append-only
decision journal, and a self-driving autopilot. What it does not yet have is a
record of what the household actually holds.

The VISION states: "protect capital, encourage long-term compounding, enforce
disciplined decision-making, and provide explainable decision support." Without
a portfolio record, no Guardian can monitor, no policy allocation can be
compared, and no decision can reference actual positions.

## Candidate A: Manual Portfolio Snapshot + Holdings Foundation (RECOMMENDED)

The user manually records a point-in-time portfolio snapshot — asset names,
quantities, user-entered unit prices or total values, valuation date, and
optional classification. Immutable snapshots provide an auditable history.
This is the data foundation for every future module: Guardian comparison,
policy allocation delta, AI Committee review context, and read-only broker
reconciliation.

**Why this first:**
- Directly serves "protect capital" — users can see what they hold
- Minimal financial computation risk — all values are user-entered
- No market data dependency
- Foundation for Guardian's "what changed" observation
- Foundation for policy allocation vs. actual comparison
- Smallest complete demo: record snapshot → confirm → view history
- Data model reuses proven Policy/Decision immutability patterns

## Candidate B: Guardian Data Readiness + Observation Model

Design the data quality, observation record, and evidence boundary that
Guardian will need — but stop short of implementing threshold detection,
risk scoring, alerts, or automated response.

**Why not first:**
- Guardian observes *something*. Without portfolio data, it observes nothing.
- Risk of designing observation abstractions against hypothetical data
- Candidate A provides the concrete data Guardian would observe

## Candidate C: Notification and Escalation Infrastructure

Design generic event delivery, notification channels, and escalation state
model. Defer Guardian rules, investment advice, and automated trading.

**Why not first:**
- Notifications deliver information about *something*
- Without portfolio or Guardian observations, there is nothing to notify about
- High abstraction risk without concrete domain events
- CompoundOS is local-only (no authentication, no public deployment) —
  notification channels (email, push, SMS) are premature

## Recommendation

**Candidate A: Manual Portfolio Snapshot + Holdings Foundation.**

Rationale:
1. Directly serves "protect capital" — visibility into holdings is the
   foundational capital protection primitive
2. Enables future Guardian observation, policy allocation comparison,
   and AI Committee portfolio review
3. Minimal financial computation — all values user-entered
4. Reuses proven immutability patterns (Policy Version, Decision Snapshot)
5. Smallest demonstrable closed loop
6. No market data, broker, or notification dependency

Candidates B and C are deferred to Sprint 004+ as natural extensions
once portfolio data exists.

## Explicit Non-Goals

- Real-time or delayed market data
- Automatic price updates
- Broker synchronization
- Actual trading
- Rebalancing recommendations
- Performance or return calculations
- Tax lots, cost basis, realized/unrealized gains
- Suitability, eligibility, ranking, scoring
- Guardian threshold detection
- AI-generated holdings or classifications
- Multi-household or multi-tenancy
- Authentication or public deployment
