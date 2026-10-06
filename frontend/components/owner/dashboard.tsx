"use client";
import { useState } from "react";
import Link from "next/link";
import { amount, planStatus, planExplanation } from "../../lib/owner-data";
import { wealthScenario } from "../../lib/wealth-scenario";
import {
  useOverview,
  Loading,
  AllocationTable,
  PurchaseTable,
  Governance,
  RiskCard,
  ConnectionsSummary,
} from "./shared";
export default function OwnerDashboard() {
  const { data, error } = useOverview();
  const [assumption, setAssumption] = useState(8),
    [horizon, setHorizon] = useState(20);
  if (!data)
    return (
      <main className="owner-shell">
        <Loading error={error} />
      </main>
    );
  const s = data.snapshot,
    a = data.analysis,
    c = s.candidates[0],
    currency = s.valuation.base_currency;
  return (
    <main className="owner-shell">
      <header className="owner-page-header">
        <div>
          <p className="eyebrow">YOUR PRIVATE FAMILY OFFICE</p>
          <h1>Your wealth, in perspective.</h1>
          <p>
            A clear view of your portfolio, this month’s capital and the
            decisions ahead.
          </p>
        </div>
        <small>
          DEMO workspace
          <br />
          As of {new Date(s.valuation.as_of).toLocaleString()}
        </small>
      </header>
      <section className="owner-summary-grid" aria-label="Wealth summary">
        {[
          ["Total Portfolio Value", amount(s.valuation.total_value, currency)],
          ["Investable Assets", amount(s.invested_value, currency)],
          ["Cash", amount(s.cash_value, currency)],
          [
            "Monthly Contribution",
            amount(
              s.configuration?.monthly_amount,
              s.configuration?.monthly_currency,
            ),
          ],
          ["Portfolio Return", "Not available"],
          [
            "Current Risk Status",
            !a
              ? "Not assessed"
              : a.guardian.status === "WARNING"
                ? "Needs attention"
                : a.guardian.status === "BLOCKED"
                  ? "Blocked"
                  : "Within checks",
          ],
          ["Latest Investment Plan Status", planStatus(c?.decision_status)],
        ].map(([label, value]) => (
          <article className="owner-summary" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
            {label === "Investable Assets" && (
              <small>Current investment holdings; excludes cash</small>
            )}
          </article>
        ))}
      </section>
      <section className="panel owner-monthly">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">THIS MONTH</p>
            <h2>Your investment plan</h2>
          </div>
          <Link className="primary-link" href="/investment-plan">
            Review Investment Plan
          </Link>
        </div>
        <p className="owner-capital">
          Available new capital{" "}
          <strong>
            {amount(
              s.configuration?.monthly_amount,
              s.configuration?.monthly_currency,
            )}
          </strong>
        </p>
        {a ? (
          <>
            <p className="hint">
              {amount(a.plan.new_capital, currency)} in base currency using DEMO
              FX. Planned new contribution, separate from current cash.
            </p>
            {!a.recommendation_ready && (
              <p className="notice notice-warning">
                This calculated proposal is blocked by safeguards. It cannot be
                approved.
              </p>
            )}
            <PurchaseTable analysis={a} currency={currency} />
            <h3>Why this plan?</h3>
            <p>{planExplanation(a.plan.rows)}</p>
            <Governance
              analysis={a}
              candidate={c}
              current={data.current_review}
            />
          </>
        ) : (
          <p className="notice notice-warning">
            An investment plan is not available. Review portfolio data and
            Policy before proceeding.
          </p>
        )}
      </section>
      <section className="panel">
        <div className="section-heading-row">
          <h2>Where your money is invested</h2>
          <Link href="/portfolio">View Portfolio →</Link>
        </div>
        <AllocationTable data={data} />
        <p className="hint">
          Weights include cash. Target and drift values come from the
          contribution engine.
        </p>
      </section>
      <div className="owner-two-column">
        <RiskCard data={data} />
        <section className="panel owner-card">
          <h2>Performance</h2>
          <p className="owner-value">Not available</p>
          <p>
            Reliable return metrics need dated valuations and cash flows. No
            return has been assumed.
          </p>
          <dl className="owner-detail-list">
            {["TWR", "IRR", "CAGR", "Maximum drawdown"].map((m) => (
              <div key={m}>
                <dt>{m}</dt>
                <dd>Not available</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
      <div className="owner-two-column">
        <ConnectionsSummary data={data} />
        <section className="panel owner-card">
          <div className="section-heading-row">
            <h2>Recent decisions</h2>
            <Link href="/decisions">View history →</Link>
          </div>
          {s.candidates
            .filter((c) => c.decision_id || c.decision_status === "rejected")
            .slice(0, 3)
            .map((c) => (
              <div key={c.id} className="owner-recent">
                <strong>Monthly contribution plan</strong>
                <span>
                  {c.evidence.valuation?.base_currency
                    ? amount(
                        c.evidence.plan.new_capital,
                        c.evidence.valuation.base_currency,
                      )
                    : "Amount not available"}{" "}
                  · {planStatus(c.decision_status)}
                </span>
              </div>
            ))}
          {!s.candidates.some((c) => c.decision_id || c.decision_status === "rejected") && (
            <p>No decisions recorded yet.</p>
          )}
        </section>
      </div>
      <section className="panel owner-scenario">
        <p className="eyebrow">SCENARIO · NOT FORECAST</p>
        <h2>Long-term wealth projection</h2>
        <p>
          Explore constant return assumptions. These are educational scenarios,
          not investment recommendations or predicted returns.
        </p>
        <div className="owner-scenario-inputs">
          <span>
            Starting portfolio: {amount(s.valuation.total_value, currency)}
          </span>
          <span>
            Monthly contribution:{" "}
            {amount(
              s.configuration?.monthly_amount,
              s.configuration?.monthly_currency,
            )}
          </span>
          <label>
            Annual return assumption{" "}
            <select
              value={assumption}
              onChange={(e) => setAssumption(Number(e.target.value))}
            >
              {[6, 8, 10].map((r) => (
                <option key={r} value={r}>
                  {r}%
                </option>
              ))}
            </select>
          </label>
          <label>
            Planning horizon{" "}
            <select
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
            >
              {[10, 20, 30].map((y) => (
                <option key={y} value={y}>
                  {y} years
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="owner-projection-grid">
          {[10, 20, 30].map((y) => {
            const value =
              s.valuation.total_value !== null && a
                ? wealthScenario(
                    Number(s.valuation.total_value),
                    Number(a.plan.new_capital),
                    assumption,
                    y,
                  )
                : null;
            return (
              <article key={y} className={horizon === y ? "is-selected" : ""}>
                <span>{y} years</span>
                <strong>
                  {value === null
                    ? "Not available"
                    : amount(String(value), currency)}
                </strong>
                <small>SCENARIO · NOT FORECAST</small>
              </article>
            );
          })}
        </div>
        <p className="hint">
          Month-end contributions; effective annual return converted to a
          monthly rate. Contribution and current DEMO FX are held constant.
          Taxes, fees, inflation and future FX changes are excluded. Scenarios
          never enter approval or recommendation evidence.
        </p>
      </section>
    </main>
  );
}
