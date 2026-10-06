"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  amount,
  ownerApi,
  planStatus,
  committeeOpinion,
  Candidate,
} from "../../lib/owner-data";
import { useOverview, Loading, Badge } from "./shared";
type RecordRow = {
  id: string;
  title: string;
  status: string;
  created_at: string;
  confirmed_at?: string;
};
type Detail = {
  status: string;
  effective_snapshot: {
    title: string;
    decision_summary: string;
    rationale: string;
    evidence_or_sources: string;
    decision_date: string;
  } | null;
  original_snapshot: unknown;
};
export default function OwnerDecisions() {
  const { data, error } = useOverview();
  const [rows, setRows] = useState<RecordRow[] | null>(null),
    [detail, setDetail] = useState<Detail | null>(null),
    [problem, setProblem] = useState(""),
    [rejected, setRejected] = useState<Candidate | null>(null);
  useEffect(() => {
    let alive = true;
    ownerApi<{ items: RecordRow[] }>("decisions")
      .then((d) => {
        if (alive) setRows(d.items);
      })
      .catch(() => {
        if (alive)
          setProblem("Your decision history is unavailable. Please refresh.");
      });
    return () => {
      alive = false;
    };
  }, []);
  const history: RecordRow[] | null =
    rows && data
      ? [
          ...rows,
          ...data.snapshot.candidates
            .filter((c) => c.decision_status === "rejected" && !c.decision_id)
            .map((c) => ({
              id: "audit:" + c.id,
              title: "Rejected demo proposal",
              status: "rejected",
              created_at: c.created_at,
            })),
        ]
      : rows;
  return (
    <main className="owner-shell">
      <header className="owner-page-header">
        <div>
          <p className="eyebrow">YOUR DECISIONS</p>
          <h1>Decision history</h1>
          <p>
            Your choices, the reasons behind them, and the safeguards reviewed
            at the time.
          </p>
        </div>
        <Link href="/investment-plan">Review this month’s plan →</Link>
      </header>
      {!data || !rows ? (
        <Loading error={problem || error} />
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="owner-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Decision</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th>Policy</th>
                  <th>Guardian</th>
                  <th>Committee</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {history?.map((r) => {
                  const c = data.snapshot.candidates.find(
                    (c) => c.decision_id === r.id || `audit:${c.id}` === r.id,
                  );
                  const currency = c?.evidence.valuation?.base_currency;
                  return (
                    <tr key={r.id}>
                      <td>
                        {new Date(
                          r.confirmed_at ?? r.created_at,
                        ).toLocaleDateString()}
                      </td>
                      <td>
                        {r.title.includes("contribution plan")
                          ? "Monthly contribution plan"
                          : r.title}
                      </td>
                      <td>
                        {c && currency
                          ? amount(c.evidence.plan.new_capital, currency)
                          : "Not available"}
                      </td>
                      <td>{planStatus(c?.decision_status ?? r.status)}</td>
                      <td>{c?.evidence.policy.status ?? "Not recorded"}</td>
                      <td>{c?.evidence.guardian.status ?? "Not recorded"}</td>
                      <td>
                        {c?.committee_report
                          ? committeeOpinion(
                              c.committee_report.recommended_direction,
                            )
                          : "Not reviewed"}
                      </td>
                      <td>
                        <button
                          onClick={() => {
                            if (r.id.startsWith("audit:")) {
                              setRejected(c ?? null);
                              setDetail(null);
                            } else {
                              setRejected(null);
                              void ownerApi<Detail>(`decisions/${r.id}`)
                                .then(setDetail)
                                .catch(() =>
                                  setProblem("Unable to open this decision."),
                                );
                            }
                          }}
                        >
                          View decision
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {history?.length === 0 && <p>No decisions recorded yet.</p>}
          <p className="hint">
            Safeguards and Committee opinions are recorded history, not fresh
            authorization.
          </p>
        </section>
      )}
      {rejected && (
        <section className="panel">
          <h2>Rejected demo proposal</h2>
          <p>
            This rejection is preserved in Audit. No confirmed Journal snapshot
            or trade was created.
          </p>
          <details>
            <summary>Review recorded proposal</summary>
            <pre className="owner-code">
              {JSON.stringify(rejected.evidence, null, 2)}
            </pre>
          </details>
        </section>
      )}
      {problem && <p role="alert">{problem}</p>}
      {detail && (
        <section className="panel">
          <div className="section-heading-row">
            <h2>{detail.effective_snapshot?.title ?? "Decision record"}</h2>
            <Badge status={planStatus(detail.status)} />
          </div>
          <p>
            {detail.effective_snapshot?.decision_summary ??
              "Draft — open the Journal for details."}
          </p>
          <details>
            <summary>Journal, evidence & audit</summary>
            <p>{detail.effective_snapshot?.evidence_or_sources}</p>
            <details>
              <summary>Original calculation record</summary>
              <pre className="owner-code">
                {detail.effective_snapshot?.rationale}
              </pre>
            </details>
            <Link href="/governance/journal">
              Open Journal and Audit timeline →
            </Link>
          </details>
        </section>
      )}
      <p>
        <Link href="/governance/journal">Detailed Journal & Governance →</Link>
      </p>
    </main>
  );
}
