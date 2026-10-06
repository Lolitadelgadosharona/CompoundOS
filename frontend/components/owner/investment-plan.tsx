"use client";
import { useState } from "react";
import Link from "next/link";
import CommitteeDiscussionPanel from "./committee-discussion";
import {
  ownerApi,
  amount,
  planExplanation,
  Candidate,
  ownerFinding,
  committeeText,
  candidateLifecycle,
  Overview,
} from "../../lib/owner-data";
import {
  useOverview,
  Loading,
  AllocationTable,
  PurchaseTable,
  Governance,
} from "./shared";
export default function OwnerInvestmentPlan() {
  const { data: initial, error } = useOverview();
  const [updated, setUpdated] = useState<Overview | null>(null);
  const data = updated ?? initial;
  const [selection, setSelected] = useState<Candidate | null>(null),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [problem, setProblem] = useState(""),
    [disclosure, setDisclosure] = useState(false),
    [consent, setConsent] = useState(false);
  const selected =
    selection ??
    data?.active_candidate ??
    (data?.current_review ? data.snapshot.candidates[0] : null);
  const act = async (fn: () => Promise<void>) => {
    setBusy(true);
    setProblem("");
    try {
      await fn();
      setUpdated(await ownerApi<Overview>("investment/owner-overview"));
    } catch (e) {
      setProblem(
        e instanceof Error ? e.message : "Unable to complete this step.",
      );
    } finally {
      setBusy(false);
    }
  };
  if (!data)
    return (
      <main className="owner-shell">
        <Loading error={error} />
      </main>
    );
  const a = selected?.evidence ?? data.analysis,
    currency = data.snapshot.valuation.base_currency;
  const refresh = async () => {
    if (selected)
      setSelected(
        await ownerApi<Candidate>(`investment/candidates/${selected.id}`),
      );
  };
  return (
    <main className="owner-shell">
      <header className="owner-page-header">
        <div>
          <p className="eyebrow">THIS MONTH</p>
          <h1>Your investment plan</h1>
          <p>
            New money first. Understand the plan, review safeguards, then make
            your decision.
          </p>
        </div>
        <Link href="/">Back to Dashboard</Link>
      </header>
      {problem && (
        <p role="alert" className="error-panel">
          {problem}
        </p>
      )}
      {message && (
        <p role="status" className="success-message">
          {message}
        </p>
      )}
      <section className="owner-summary-grid">
        <article className="owner-summary">
          <span>New capital</span>
          <strong>
            {amount(
              data.snapshot.configuration?.monthly_amount,
              data.snapshot.configuration?.monthly_currency,
            )}
          </strong>
          <small>
            {a
              ? amount(a.plan.new_capital, currency) + " using DEMO FX"
              : "Conversion not available"}
          </small>
        </article>
        <article className="owner-summary">
          <span>Current portfolio</span>
          <strong>
            {amount(data.snapshot.valuation.total_value, currency)}
          </strong>
        </article>
        <article className="owner-summary">
          <span>Review status</span>
          <strong>
            {selected
              ? candidateLifecycle(a, selected)
              : (data.committee_discussion?.state ?? "CANDIDATE")}
          </strong>
        </article>
      </section>
      {a ? (
        <>
          <section className="panel">
            <h2>CANDIDATE ALLOCATION</h2>
            <p>
              Awaiting Committee Review. Calculated amounts are not approved
              purchases.
            </p>
            <PurchaseTable analysis={a} currency={currency} />
            <h3>Why this plan?</h3>
            <p>{planExplanation(a.plan.rows)}</p>
            <p>
              Retained contribution: {amount(a.plan.retained_cash, currency)}.
              No selling is proposed.
            </p>
          </section>
          <section className="panel">
            <h2>Current holdings vs Owner-approved strategic allocation</h2>
            <p>
              Holdings never define targets. DEMO strategy; no automatic sale of
              non-target assets.
            </p>
            <p>
              {data.strategy?.targets
                .filter((t) => Number(t.weight) === 0)
                .map(
                  (t) => `${t.symbol}: strategic target 0% — outside strategy`,
                )
                .join(" · ")}
            </p>
            <AllocationTable
              data={selected ? { ...data, analysis: selected.evidence } : data}
            />
          </section>
          <section className="panel" id="governance">
            <h2>Policy & Guardian</h2>
            <Governance analysis={a} candidate={selected ?? undefined} />
            {a.policy.findings.map((f, i) => (
              <p key={i}>{f}</p>
            ))}
            {a.guardian.findings.map((f, i) => (
              <p key={i} className="owner-risk-note">
                {ownerFinding(f.detail, data)}
              </p>
            ))}
            {!a.recommendation_ready && (
              <p className="notice notice-warning">
                Safeguards block this proposal. Approval is unavailable.
              </p>
            )}
          </section>
        </>
      ) : (
        <section className="panel">
          <h2>Plan unavailable</h2>
          <p>
            Refresh portfolio data and review your Policy before preparing a
            plan.
          </p>
          <details>
            <summary>What needs attention?</summary>
            <p>{data.unavailable_reason}</p>
          </details>
        </section>
      )}
      <section className="panel" id="committee">
        <h2>Investment Committee</h2>
        <p className="owner-simulated">
          SIMULATED COMMITTEE · NOT REAL AI ANALYSIS
        </p>
        {selected?.committee_report ? (
          <>
            <p>
              Opinion:{" "}
              {selected.committee_report.recommended_direction ===
              "aligned_with_policy"
                ? "Supportive"
                : selected.committee_report.recommended_direction ===
                    "not_aligned_with_policy"
                  ? "Not supportive"
                  : "Further review needed"}{" "}
              · Confidence: {"NOT AVAILABLE"}
            </p>
            <div className="owner-two-column">
              <div>
                <h3>Supporting reasons</h3>
                <ul>
                  {selected.committee_report.supporting_arguments.map(
                    (s, i) => (
                      <li key={i}>{committeeText(s)}</li>
                    ),
                  )}
                </ul>
              </div>
              <div>
                <h3>Opposing reasons</h3>
                <ul>
                  {selected.committee_report.opposing_arguments.map((s, i) => (
                    <li key={i}>{committeeText(s)}</li>
                  ))}
                </ul>
              </div>
            </div>
            <h3>Risks</h3>
            <ul>
              {selected.committee_report.risks.map((s, i) => (
                <li key={i}>{committeeText(s)}</li>
              ))}
            </ul>
          </>
        ) : (
          <p>
            Prepare a plan, then request a simulated review of its exact
            evidence. Existing evidence validation still applies.
          </p>
        )}
        <p>
          Lifecycle: CANDIDATE → REVIEWING → READY_FOR_DECISION → APPROVED /
          REJECTED. Safeguards may set BLOCKED; missing required evidence
          remains NOT EVALUATED.
        </p>
        <div className="actions">
          {!selected && (
            <button
              className="primary-button"
              disabled={busy || !a}
              onClick={() =>
                void act(async () => {
                  setSelected(
                    await ownerApi<Candidate>("investment/candidates", {
                      funding: "monthly",
                    }),
                  );
                  setMessage(
                    "Candidate saved. Review its safeguards; blocked candidates cannot begin governance review. Holdings and cash were unchanged.",
                  );
                })
              }
            >
              Review with Investment Committee
            </button>
          )}
          {selected && (
            <>
              <button
                disabled={
                  busy ||
                  !a?.recommendation_ready ||
                  !["not_requested", "draft"].includes(
                    selected.committee_status,
                  ) ||
                  selected.decision_status === "rejected"
                }
                onClick={() =>
                  void act(async () => {
                    setSelected(
                      await ownerApi<Candidate>(
                        `investment/candidates/${selected.id}/committee-preview`,
                        {},
                      ),
                    );
                    setDisclosure(true);
                    setConsent(false);
                  })
                }
              >
                Review with Investment Committee
              </button>
              <button
                className="primary-button"
                disabled={
                  busy ||
                  selected.decision_status !== "draft" ||
                  selected.committee_report?.recommended_direction !==
                    "aligned_with_policy" ||
                  !a?.recommendation_ready
                }
                onClick={() =>
                  void act(async () => {
                    const r = await ownerApi<{ execution: string }>(
                      `investment/candidates/${selected.id}/approve`,
                      {},
                    );
                    if (r.execution !== "PREVIEW_ONLY")
                      throw new Error("Unexpected approval type.");
                    await refresh();
                    setMessage(
                      "Demo plan approved and saved to Decisions. No order or trade was created.",
                    );
                  })
                }
              >
                Approve Plan
              </button>
              <button
                disabled={
                  busy ||
                  ["confirmed", "archived", "rejected"].includes(
                    selected.decision_status,
                  )
                }
                onClick={() =>
                  void act(async () => {
                    await ownerApi(
                      `investment/candidates/${selected.id}/reject`,
                      {},
                    );
                    await refresh();
                    setMessage("Demo plan rejected. Its history is preserved.");
                  })
                }
              >
                Reject Plan
              </button>
            </>
          )}
        </div>
        {disclosure && selected && (
          <div className="notice">
            <h3>Local simulated review</h3>
            <p>
              Your DEMO portfolio, plan and safeguards are processed locally.
              Nothing is sent to DeepSeek or an external AI provider.
            </p>
            <label>
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />{" "}
              I reviewed the plan and agree to local simulated analysis.
            </label>
            <div className="actions">
              <button
                disabled={busy || !consent}
                onClick={() =>
                  void act(async () => {
                    setSelected(
                      await ownerApi<Candidate>(
                        `investment/candidates/${selected.id}/committee`,
                        {
                          confirmation: true,
                          content_hash: selected.content_hash,
                        },
                      ),
                    );
                    setDisclosure(false);
                    setMessage(
                      "Simulated review completed. Inspect reasons, risks and safeguards before deciding.",
                    );
                  })
                }
              >
                Run SIMULATED COMMITTEE
              </button>
            </div>
          </div>
        )}
      </section>
      {data.committee_discussion && (
        <CommitteeDiscussionPanel
          report={data.committee_discussion}
          data={data}
        />
      )}
      <section className="panel">
        <h2>Evidence & records</h2>
        <details>
          <summary>Inspect calculations and evidence</summary>
          <p>
            As of{" "}
            {new Date(
              a?.as_of ?? data.snapshot.valuation.as_of,
            ).toLocaleString()}{" "}
            · DEMO prices and FX
          </p>
          <p>
            Owner approval remains mandatory. These records cannot authorize
            real execution.
          </p>
          {selected?.committee_report?.evidence_citations?.map((c, i) => (
            <p key={i}>
              {c.claim}
              <small> · {c.citation_ref}</small>
            </p>
          ))}
          <details>
            <summary>Calculation record</summary>
            <pre className="owner-code">{JSON.stringify(a, null, 2)}</pre>
          </details>
        </details>
        <p>
          <Link href="/decisions">Decision history →</Link> ·{" "}
          <Link href="/investment">Advanced portfolio setup →</Link>
        </p>
      </section>
    </main>
  );
}
