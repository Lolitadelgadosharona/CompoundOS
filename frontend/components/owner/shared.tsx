"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  amount,
  pct,
  ownerApi,
  committeeOpinion,
  ownerFinding,
  reasonFor,
  Overview,
  Analysis,
  Candidate,
} from "../../lib/owner-data";
export function useOverview() {
  const [data, setData] = useState<Overview | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    ownerApi<Overview>("investment/owner-overview")
      .then((d) => {
        if (alive) setData(d);
      })
      .catch(() => {
        if (alive)
          setError(
            "Your portfolio is temporarily unavailable. Please refresh the page.",
          );
      });
    return () => {
      alive = false;
    };
  }, []);
  return { data, error };
}
export function Loading({ error }: { error: string }) {
  return error ? (
    <p role="alert" className="notice-warning notice">
      {error}
    </p>
  ) : (
    <p role="status">Opening your family office…</p>
  );
}
export function Badge({ status }: { status: string }) {
  return (
    <span
      className={`owner-badge ${["BLOCK", "BLOCKED", "REJECT", "rejected"].includes(status) ? "is-block" : ["WARNING", "HOLD", "Overweight"].includes(status) ? "is-warning" : "is-neutral"}`}
    >
      {status}
    </span>
  );
}
export function AllocationTable({ data }: { data: Overview }) {
  const held = data.snapshot.positions.filter((p) => p.kind === "position");
  const plan = data.analysis?.plan.rows ?? [];
  const rows = [
    ...held.map((p) => ({
      id: p.asset_id,
      symbol: p.symbol,
      value: p.value,
      weight: p.weight,
    })),
    ...plan
      .filter((r) => !held.some((p) => p.asset_id === r.asset_id))
      .map((r) => ({
        id: r.asset_id,
        symbol: r.symbol,
        value: "0",
        weight: r.current_weight,
      })),
  ];
  return (
    <div className="owner-table-wrap">
      <table className="owner-table">
        <thead>
          <tr>
            <th>Asset</th>
            <th>Current value</th>
            <th>Current %</th>
            <th>Target %</th>
            <th>Drift</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => {
            const r = plan.find((r) => r.asset_id === p.id),
              configured = data.snapshot.configuration?.targets.find(
                (t) => t.asset_id === p.id,
              );
            return (
              <tr key={p.id}>
                <td>
                  <strong>{p.symbol}</strong>
                </td>
                <td>
                  {amount(p.value, data.snapshot.valuation.base_currency)}
                </td>
                <td>{pct(r?.current_weight ?? p.weight)}</td>
                <td>
                  {pct(
                    r?.target_weight ??
                      configured?.weight ??
                      (data.snapshot.configuration ? "0" : undefined),
                  )}
                  {!configured && data.snapshot.configuration && (
                    <small>
                      {" "}
                      · NON-TARGET HOLDING · Outside strategic allocation · No
                      automatic sale
                    </small>
                  )}
                </td>
                <td>
                  {r ? (
                    <>
                      <Badge
                        status={
                          Number(r.underweight) > 0
                            ? "Underweight"
                            : Number(r.overweight) > 0
                              ? "Overweight"
                              : "On target"
                        }
                      />{" "}
                      <small>
                        {Number(r.absolute_drift).toLocaleString("en-US", {
                          maximumFractionDigits: 2,
                        })}{" "}
                        pp
                      </small>
                    </>
                  ) : !configured && data.snapshot.configuration ? (
                    "Outside strategy — no automatic sale"
                  ) : (
                    "NOT EVALUATED"
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
export function PurchaseTable({
  analysis,
  currency,
}: {
  analysis: Analysis;
  currency: string;
}) {
  return (
    <div className="owner-table-wrap">
      <table className="owner-table">
        <thead>
          <tr>
            <th>Asset</th>
            <th>Candidate amount</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {analysis.plan.rows.map((r) => (
            <tr key={r.asset_id}>
              <td>{r.symbol}</td>
              <td>{amount(r.buy_amount, currency)}</td>
              <td>{reasonFor(r)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function Governance({
  analysis,
  candidate,
  current = true,
}: {
  analysis: Analysis | null;
  candidate?: Candidate;
  current?: boolean;
}) {
  const direction = current
    ? candidate?.committee_report?.recommended_direction
    : undefined;
  return (
    <div className="owner-governance">
      <div>
        <span>POLICY</span>
        <Badge
          status={
            !analysis
              ? "NOT ASSESSED"
              : analysis.policy.status === "BLOCKED"
                ? "BLOCK"
                : analysis.policy.status
          }
        />
      </div>
      <div>
        <span>GUARDIAN</span>
        <Badge
          status={
            !analysis
              ? "NOT ASSESSED"
              : analysis.guardian.status === "BLOCKED"
                ? "BLOCK"
                : analysis.guardian.status
          }
        />
      </div>
      <div>
        <span>INVESTMENT COMMITTEE</span>
        <Badge status={committeeOpinion(direction)} />
        <small>
          {direction ? "SIMULATED opinion" : "Current review required"} ·
          Confidence: {direction ? "NOT AVAILABLE" : "NOT AVAILABLE"}
        </small>
      </div>
    </div>
  );
}
export function RiskCard({ data }: { data: Overview }) {
  const a = data.analysis;
  const concentration =
    a?.guardian.findings.filter((f) => f.check === "concentration") ?? [];
  return (
    <section className="panel owner-card">
      <h2>Risk & safeguards</h2>
      <p className="owner-value">
        {!a
          ? "NOT EVALUATED"
          : a.guardian.status === "BLOCKED"
            ? "Plan blocked"
            : a.guardian.status === "WARNING"
              ? "Needs attention"
              : a.guardian.status === "NOT EVALUATED"
                ? "NOT EVALUATED"
                : "Within checked limits"}
      </p>
      <dl className="owner-detail-list">
        <div>
          <dt>Plan concentration</dt>
          <dd>
            {!a
              ? "Not available"
              : concentration.length
                ? "Limit exceeded"
                : "Within checked limits"}
          </dd>
        </div>
        <div>
          <dt>Equity exposure</dt>
          <dd>NOT EVALUATED — no complete verified look-through</dd>
        </div>
        <div>
          <dt>Liquidity / Cash</dt>
          <dd>
            {amount(
              data.snapshot.cash_value,
              data.snapshot.valuation.base_currency,
            )}
          </dd>
        </div>
        <div>
          <dt>Policy findings</dt>
          <dd>{a ? a.policy.findings.length : "Not assessed"}</dd>
        </div>
        <div>
          <dt>Guardian findings</dt>
          <dd>{a ? a.guardian.findings.length : "Not assessed"}</dd>
        </div>
      </dl>
      <p>
        Data coverage: NOT EVALUATED — sector classification / ETF look-through
        and macro evidence unavailable.
      </p>
      {a?.guardian.findings.map((f, i) => (
        <p key={i} className="owner-risk-note">
          {f.severity === "not_evaluated"
            ? "NOT EVALUATED: "
            : "RISK DETECTED: "}
          {ownerFinding(f.detail, data)}
        </p>
      ))}
      <Link href="/investment-plan#governance">Review safeguards →</Link>
    </section>
  );
}
export function ConnectionsSummary({ data }: { data: Overview }) {
  return (
    <section className="panel owner-card">
      <div className="section-heading-row">
        <h2>Your accounts</h2>
        <Link href="/accounts">Connect Broker →</Link>
      </div>
      <ul className="owner-account-list">
        {data.connections.brokers.map((b) => (
          <li key={b.name}>
            <span>{b.name}</span>
            <small>{b.status} · {b.connection_type ?? "Planned"} · Read only</small>
          </li>
        ))}
        <li>
          <span>Manual Portfolio</span>
          <small>
            {data.connections.manual.status === "CONNECTED"
              ? "Connected · Local records"
              : "Not Connected"}
          </small>
        </li>
      </ul>
      <p className="hint">
        Broker reads require separate local Owner setup and authorization. Manual records remain local.
      </p>
    </section>
  );
}
