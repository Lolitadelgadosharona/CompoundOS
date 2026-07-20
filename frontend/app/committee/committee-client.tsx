/* eslint-disable  */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  createSession,
  getPrivacyPreview,
  getReport,
  getRunStatus,
  getSession,
  listSessions,
  recordOutcome,
  runSession,
  CommitteeApiError,
  CommitteeNetworkError,
  type OutcomeCreatePayload,
  type PrivacyPreview,
  type ReportDetail,
  type SessionDetail,
  type SessionSummary,
} from "../../lib/committee-api";

// ═══════════════════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════════════════

const NON_ADVISORY =
  "Committee analysis provides balanced multi-perspective decision support. It is not investment advice. You make the final decision.";
const PRIVACY_NOTE =
  "Only minimized structured facts and your proposal are sent to the provider. Full Policy text, Portfolio holdings, quantities, prices, and identifiers are never sent.";
const MANUAL_ONLY =
  "Committee sessions are completely manual. No automatic triggers from Guardian, Automation, Portfolio, or Schedules.";
const ROLES = [
  { key: "long_term_compounding", label: "Long-Term Compounding" },
  { key: "index_passive_investing", label: "Index / Passive Investing" },
  { key: "macroeconomic_context", label: "Macroeconomic Context" },
  { key: "risk_capital_preservation", label: "Risk & Capital Preservation" },
  { key: "devils_advocate", label: "Devil's Advocate" },
  { key: "policy_alignment_role", label: "Policy Alignment" },
  { key: "synthesis_chair", label: "Synthesis / Chair" },
] as const;

type View =
  | "list"
  | "create"
  | "detail"
  | "privacy-preview"
  | "running"
  | "report"
  | "outcome";

// ═══════════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════════

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    draft: "Draft", queued: "Queued", running: "Running",
    completed: "Completed", failed: "Failed",
  };
  return map[s] ?? s;
}

function directionLabel(d: string): string {
  const map: Record<string, string> = {
    aligned_with_policy: "Aligned with Policy",
    not_aligned_with_policy: "Not Aligned with Policy",
    conditionally_aligned: "Conditionally Aligned",
    insufficient_evidence: "Insufficient Evidence",
  };
  return map[d] ?? d;
}

// ═══════════════════════════════════════════════════════════════════════════
// Component
// ═══════════════════════════════════════════════════════════════════════════

export default function CommitteeClient() {
  // ── Core state ──
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<View>("list");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [household, setHousehold] = useState<boolean | null>(null);

  // ── Create state ──
  const [formTitle, setFormTitle] = useState("");
  const [formProposal, setFormProposal] = useState("");
  const [saving, setSaving] = useState(false);

  // ── Preview + run state ──
  const [preview, setPreview] = useState<PrivacyPreview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [running, setRunning] = useState(false);

  // ── Report + outcome state ──
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [outcomeVal, setOutcomeVal] = useState<string>("accepted");
  const [outcomeRationale, setOutcomeRationale] = useState("");
  const [outcomeSaving, setOutcomeSaving] = useState(false);

  // ── Abort ──
  const abortRef = useRef<AbortController | null>(null);
  const runAbortRef = useRef<AbortController | null>(null);
  const genRef = useRef(0);

  function newGen(): number { genRef.current += 1; return genRef.current; }

  // ═════════════════════════════════════════════════════════════════════════
  // Data loading
  // ═════════════════════════════════════════════════════════════════════════

  const loadList = useCallback(async () => {
    const gen = newGen();
    const ac = new AbortController();
    abortRef.current?.abort();
    abortRef.current = ac;
    setLoading(true);
    try {
      const data = await listSessions(undefined, ac.signal);
      if (gen !== genRef.current) return;
      setHousehold(true);
      setSessions(data);
      setError(null);
    } catch (err) {
      if (gen !== genRef.current) return;
      if (err instanceof CommitteeApiError && err.status === 404) {
        setHousehold(false);
      } else {
        setError(err instanceof CommitteeNetworkError ? err.message : "Unable to load committee data.");
      }
    } finally {
      if (gen === genRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadList();
    return () => { abortRef.current?.abort(); runAbortRef.current?.abort(); };
  }, [loadList]);

  // ═════════════════════════════════════════════════════════════════════════
  // Mutations
  // ═════════════════════════════════════════════════════════════════════════

  const loadPrivacyPreview = useCallback(async (id: string) => {
    setView("detail");
    setConfirmed(false);
    setPreview(null);
    try {
      const p = await getPrivacyPreview(id);
      setPreview(p);
      setView("privacy-preview");
    } catch (err) {
      setError(err instanceof CommitteeApiError ? err.message : "Failed to load privacy preview.");
    }
  }, []);

  const handleCreate = useCallback(async () => {
    if (saving) return;
    setSaving(true);
    try {
      const s = await createSession({ title: formTitle, proposal_text: formProposal });
      setSelectedId(s.id);
      await loadPrivacyPreview(s.id);
    } catch (err) {
      setError(err instanceof CommitteeApiError ? err.message : "Failed to create session.");
    } finally {
      setSaving(false);
    }
  }, [saving, formTitle, formProposal, loadPrivacyPreview]);

  const loadReport = useCallback(async (reportId: string) => {
    try {
      const r = await getReport(reportId);
      setReport(r);
      setView("report");
      setRunning(false);
    } catch (err) {
      setError("Failed to load report.");
      setRunning(false);
    }
  }, []);

  const handleRun = useCallback(async () => {
    if (running || !selectedId || !confirmed) return;
    setRunning(true);
    setError(null);
    try {
      const ac = new AbortController();
      runAbortRef.current = ac;
      const result = await runSession(selectedId, ac.signal);
      if (result.status === "completed" && result.report_id) {
        await loadReport(result.report_id);
      } else {
        // Poll for status
        let attempts = 0;
        const poll = async () => {
          if (attempts > 30) { setError("Session timed out."); setView("detail"); setRunning(false); return; }
          attempts++;
          const r = await getRunStatus(selectedId);
          if (r.status === "completed" && r.report_id) {
            await loadReport(r.report_id);
            setRunning(false);
          } else if (r.status === "failed") {
            setError("Committee session failed. Check validation or provider.");
            setView("detail");
            setRunning(false);
          } else {
            setTimeout(poll, 2000);
          }
        };
        setTimeout(poll, 2000);
      }
    } catch (err) {
      setError(err instanceof CommitteeApiError ? err.message : "Committee run failed.");
      setView("detail");
      setRunning(false);
    }
  }, [running, selectedId, confirmed, loadReport]);

  const loadDetail = useCallback(async (id: string) => {
    setSelectedId(id);
    try {
      const d = await getSession(id);
      setDetail(d);
      setView("detail");
      setError(null);
    } catch (err) {
      setError("Failed to load session detail.");
    }
  }, []);

  const handleOutcome = useCallback(async () => {
    if (outcomeSaving || !selectedId) return;
    setOutcomeSaving(true);
    try {
      const payload: OutcomeCreatePayload = {
        outcome: outcomeVal as OutcomeCreatePayload["outcome"],
        owner_rationale: outcomeRationale || undefined,
      };
      await recordOutcome(selectedId, payload);
      loadDetail(selectedId);
      setOutcomeRationale("");
    } catch (err) {
      setError(err instanceof CommitteeApiError ? err.message : "Failed to record outcome.");
    } finally {
      setOutcomeSaving(false);
    }
  }, [outcomeSaving, selectedId, outcomeVal, outcomeRationale, loadDetail]);

  // ═════════════════════════════════════════════════════════════════════════
  // Report display helpers
  // ═════════════════════════════════════════════════════════════════════════

  function renderReport() {
    if (!report) return null;
    const c = report.report_content;
    return (
      <section aria-label="Committee Report">
        <h2>Report</h2>
        <dl>
          <dt>Provider</dt><dd>{report.provider} / {report.model_id}</dd>
          <dt>Temperature</dt><dd>{report.temperature}</dd>
          <dt>Tokens</dt><dd>{report.input_tokens} in / {report.output_tokens} out</dd>
          <dt>Generated</dt><dd>{fmtTime(report.generated_at)}</dd>
        </dl>

        <h3>Direction</h3>
        <p aria-label="Recommended direction">{directionLabel(c.recommended_direction)}</p>

        {ROLES.map(({ key, label }) => {
          const roleContent = (c.sections as unknown as Record<string, string>)[key];
          return (
            <section key={key} aria-label={label}>
              <h4>{label}</h4>
              {key === "macroeconomic_context" && (!roleContent || roleContent.includes("Insufficient")) && (
                <p className="neutral" role="note"><strong>Insufficient current macro evidence.</strong> No external market data available.</p>
              )}
              <p>{roleContent || "—"}</p>
            </section>
          );
        })}

        <h3>Supporting Arguments</h3>
        <ul>{(c.supporting_arguments || []).map((a, i) => <li key={i}>{a}</li>)}</ul>

        <h3>Opposing Arguments</h3>
        <ul>{(c.opposing_arguments || []).map((a, i) => <li key={i}>{a}</li>)}</ul>

        <h3>Risks</h3>
        <ul>{(c.risks || []).map((r, i) => <li key={i}>{r}</li>)}</ul>

        <h3>Policy Alignment</h3>
        <p>{c.policy_alignment || "—"}</p>

        <h3>Minority Opinions</h3>
        {(c.minority_opinions || []).length > 0 ? (
          <ul>{(c.minority_opinions).map((o, i) => <li key={i}>{o}</li>)}</ul>
        ) : <p>None recorded.</p>}

        <h3>Limitations</h3>
        <ul>{(c.limitations || []).map((l, i) => <li key={i}>{l}</li>)}</ul>

        <h3>Evidence Citations</h3>
        {(c.evidence_citations || []).length > 0 ? (
          <ul>
            {c.evidence_citations.map((ec, i) => (
              <li key={i}>
                <span>ID: {ec.evidence_id}</span>
                {ec.citation_ref && <span> — {ec.citation_ref}</span>}
              </li>
            ))}
          </ul>
        ) : <p>No evidence citations.</p>}
        <p className="neutral">Any claim not citing evidence above is model inference — not based on provided evidence.</p>
      </section>
    );
  }

  // ═════════════════════════════════════════════════════════════════════════
  // Render
  // ═════════════════════════════════════════════════════════════════════════

  if (loading) {
    return <main className="shell" role="status" aria-label="Loading committee"><h1>AI Investment Committee</h1><p>Loading…</p></main>;
  }

  if (household === false) {
    return <main className="shell"><h1>AI Investment Committee</h1><p>No household profile found.</p><Link href="/household">Create Household</Link></main>;
  }

  // ── List ──
  if (view === "list") {
    return (
      <main className="shell" role="region" aria-label="Committee workspace">
        <h1>AI Investment Committee</h1>
        <p className="neutral">{NON_ADVISORY}</p>
        <p className="neutral">{MANUAL_ONLY}</p>
        {error && <div role="alert"><p>{error}</p><button onClick={() => setError(null)}>Dismiss</button></div>}

        <h2>Sessions</h2>
        {sessions.length === 0 && <p>No sessions. Create one to start.</p>}
        <ul role="list">
          {sessions.map((s) => (
            <li key={s.id}>
              <button onClick={() => loadDetail(s.id)} aria-label={`Session ${s.title}`}>
                {s.title} · {statusLabel(s.status)} · {fmtTime(s.created_at)}
              </button>
            </li>
          ))}
        </ul>

        <button onClick={() => { setView("create"); setFormTitle(""); setFormProposal(""); setError(null); }} aria-label="New session">New session</button>
        <nav><Link href="/">← Home</Link></nav>
      </main>
    );
  }

  // ── Create ──
  if (view === "create") {
    return (
      <main className="shell" role="region" aria-label="Create session">
        <h1>New Committee Session</h1>
        {error && <div role="alert"><p>{error}</p></div>}
        <label htmlFor="title">Title</label>
        <input id="title" value={formTitle} onChange={(e) => setFormTitle(e.target.value)} />
        <label htmlFor="proposal">Proposal</label>
        <textarea id="proposal" rows={5} value={formProposal} onChange={(e) => setFormProposal(e.target.value)} />
        <button onClick={handleCreate} disabled={saving || !formTitle.trim() || !formProposal.trim()} aria-label="Create session">
          {saving ? "Creating…" : "Create session"}
        </button>
        <button onClick={() => setView("list")}>Cancel</button>
      </main>
    );
  }

  // ── Detail ──
  if (view === "detail" && detail) {
    return (
      <main className="shell" role="region" aria-label="Session detail">
        <h1>{detail.title}</h1>
        <dl>
          <dt>Status</dt><dd>{statusLabel(detail.status)}</dd>
          <dt>Created</dt><dd>{fmtTime(detail.created_at)}</dd>
        </dl>
        <h3>Proposal</h3>
        <p>{detail.proposal_text}</p>

        {detail.report && (
          <button onClick={() => detail.report && loadReport(detail.report.id)} aria-label="View report">View report</button>
        )}

        {detail.status === "draft" && (
          <button onClick={() => loadPrivacyPreview(detail.id)} aria-label="Privacy preview">Privacy preview &amp; Run</button>
        )}

        {detail.status === "completed" && detail.report && (
          <section aria-label="Record outcome">
            <h3>Record Outcome</h3>
            <label htmlFor="outcome">Decision</label>
            <select id="outcome" value={outcomeVal} onChange={(e) => setOutcomeVal(e.target.value)}>
              <option value="accepted">Accept</option>
              <option value="rejected">Reject</option>
              <option value="deferred">Defer</option>
            </select>
            <label htmlFor="rationale">Rationale (optional)</label>
            <textarea id="rationale" rows={2} value={outcomeRationale} onChange={(e) => setOutcomeRationale(e.target.value)} />
            <button onClick={handleOutcome} disabled={outcomeSaving} aria-label="Record outcome">
              {outcomeSaving ? "Saving…" : "Record outcome"}
            </button>
          </section>
        )}

        {detail.outcomes.length > 0 && (
          <section aria-label="Outcome history">
            <h3>Outcome History</h3>
            <ul>
              {detail.outcomes.map((o) => (
                <li key={o.id}>{o.outcome} — {o.owner_rationale || "No rationale"} — {fmtTime(o.recorded_at)}</li>
              ))}
            </ul>
          </section>
        )}

        <h3>Evidence ({detail.evidence_items.length} items)</h3>
        {detail.evidence_items.length > 0 ? (
          <ul>
            {detail.evidence_items.map((e) => (
              <li key={e.id}>{e.source_type}: {e.source_title} ({e.confidence}) — {e.citation_ref}</li>
            ))}
          </ul>
        ) : <p>No evidence loaded.</p>}

        <button onClick={() => { setView("list"); setDetail(null); }}>← Back</button>
      </main>
    );
  }

  // ── Privacy Preview ──
  if (view === "privacy-preview" && preview) {
    return (
      <main className="shell" role="region" aria-label="Privacy preview">
        <h1>Privacy Preview</h1>
        <p className="neutral">{PRIVACY_NOTE}</p>

        <dl>
          <dt>Estimated input tokens</dt><dd>{preview.estimated_input_tokens} / {preview.max_input_tokens}</dd>
          <dt>Max output tokens</dt><dd>{preview.max_output_tokens}</dd>
          <dt>Max estimated cost</dt><dd>${preview.max_cost_usd}</dd>
        </dl>

        {preview.exceeds_budget && (
          <div role="alert"><p>Budget exceeded. Reduce proposal length.</p></div>
        )}

        <h3>Evidence to be sent ({preview.evidence_summary.length} items)</h3>
        {preview.evidence_summary.map((e) => (
          <p key={e.id}>{e.source_type}: {e.source_title} — {e.citation_ref} ({e.confidence})</p>
        ))}

        <label>
          <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
          I have reviewed the privacy preview. I understand only minimized structured facts and my proposal are sent to the provider. Full Policy text, Portfolio holdings, quantities, prices, and identifiers are never sent. I confirm this analysis is for decision support only and not investment advice.
        </label>

        <button onClick={handleRun} disabled={!confirmed || running || preview.exceeds_budget} aria-label="Run committee">
          {running ? "Running…" : "Run Committee"}
        </button>
        <button onClick={() => loadDetail(selectedId!)}>Cancel</button>
      </main>
    );
  }

  // ── Running ──
  if (view === "running") {
    return (
      <main className="shell" role="status" aria-label="Committee running">
        <h1>Committee Running</h1>
        <p>Analyzing your proposal… this may take up to 2 minutes.</p>
        <button onClick={() => { setRunning(false); setView("detail"); }}>Cancel</button>
      </main>
    );
  }

  // ── Report ──
  if (view === "report" && report) {
    return (
      <main className="shell" role="region" aria-label="Committee report">
        <h1>Committee Report</h1>
        {renderReport()}
        <button onClick={() => selectedId && loadDetail(selectedId)}>← Session detail</button>
        <nav><Link href="/">← Home</Link></nav>
      </main>
    );
  }

  return null;
}
