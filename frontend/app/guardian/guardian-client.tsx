"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  confirmCheck,
  createCheck,
  discardCheck,
  evaluateAll,
  evaluateOne,
  getAudit,
  getCheck,
  getEvaluationRun,
  GuardianApiError,
  GuardianAuditEvent,
  GuardianCheckDetail,
  GuardianCheckType,
  GuardianConfirmedVersion,
  GuardianDraft,
  GuardianEvaluationRun,
  GuardianEvent,
  GuardianNetworkError,
  hasCurrentHousehold,
  listChecks,
  listEvaluationRuns,
  updateDraft,
} from "../../lib/guardian-api";

const CHECK_TYPES: GuardianCheckType[] = ["drift", "category_exposure", "staleness"];
const NON_ADVISORY = "Guardian monitors thresholds you configure. Nothing here is advice.";

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

type View = "list" | "detail" | "create" | "edit";

export default function GuardianClient() {
  // ---- Core state ----
  const [household, setHousehold] = useState<boolean | null>(null);
  const [checks, setChecks] = useState<GuardianCheckDetail[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<View>("list");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ---- Create/edit state ----
  const [form, setForm] = useState<CreateForm>(emptyForm());

  // ---- Evaluation state ----
  const [runs, setRuns] = useState<GuardianEvaluationRun[]>([]);
  const [evalResult, setEvalResult] = useState<string | null>(null);
  const [auditEvents, setAuditEvents] = useState<GuardianAuditEvent[]>([]);

  const abortRef = useRef<AbortController | null>(null);

  function abort() {
    abortRef.current?.abort();
    abortRef.current = new AbortController();
  }

  const loadChecks = useCallback(async () => {
    abort();
    const signal = abortRef.current!.signal;
    setLoading(true);
    setError(null);
    try {
      const list = await listChecks(signal);
      setChecks(list.checks.map(c => ({ identity: c, draft: null, latest_version: null })));
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError(e instanceof GuardianApiError ? e.message : "Failed to load checks.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCheckDetail = useCallback(async (id: string) => {
    abort();
    const signal = abortRef.current!.signal;
    try {
      const detail = await getCheck(id, signal);
      setChecks(prev => prev.map(c => c.identity.id === id ? detail : c));
    } catch (_) { /* auxiliary — don't block UI */ }
  }, []);

  useEffect(() => {
    abortRef.current = new AbortController();
    (async () => {
      const has = await hasCurrentHousehold();
      setHousehold(has);
      if (has) await loadChecks();
      else setLoading(false);
    })();
    return () => { abortRef.current?.abort(); };
  }, [loadChecks]);

  // ---- Handlers ----

  const selected = selectedId ? checks.find(c => c.identity.id === selectedId) : null;

  async function handleCreate() {
    abort();
    try {
      const result = await createCheck({
        name: form.name, check_type: form.check_type, threshold_value: form.threshold_value,
        severity: form.severity || "info",
        target_category: form.target_category || undefined,
        target_holding_category: form.target_holding_category || undefined,
        staleness_days: form.staleness_days ?? undefined,
        notes: form.notes || undefined,
      });
      setChecks(prev => [...prev.filter(c => c.identity.id !== result.identity.id), result]);
      setView("list");
      setForm(emptyForm());
    } catch (e) {
      setError(e instanceof GuardianApiError ? e.message : "Create failed.");
    }
  }

  async function handleConfirm() {
    if (!selected?.draft) return;
    abort();
    try {
      const result = await confirmCheck(selected.identity.id, selected.draft.expected_revision);
      setChecks(prev => prev.map(c => c.identity.id === result.identity.id ? result : c));
      setSelectedId(result.identity.id);
      setView("detail");
    } catch (e) {
      setError(e instanceof GuardianApiError ? e.message : "Confirm failed.");
    }
  }

  async function handleDiscard() {
    if (!selected) return;
    abort();
    try {
      await discardCheck(selected.identity.id);
      if (selected.latest_version) {
        // After-confirm discard: reload detail
        await loadCheckDetail(selected.identity.id);
      } else {
        setChecks(prev => prev.filter(c => c.identity.id !== selected.identity.id));
        setSelectedId(null);
        setView("list");
      }
    } catch (e) {
      setError(e instanceof GuardianApiError ? e.message : "Discard failed.");
    }
  }

  async function handleEvaluate(oneCheck: boolean) {
    abort();
    setEvalResult(null);
    try {
      const result = oneCheck && selected
        ? await evaluateOne(selected.identity.id, form.eval_date || todayISO())
        : await evaluateAll(form.eval_date || todayISO());
      setEvalResult(
        result.evaluation_run.events_created
          ? `Thresholds exceeded on ${result.evaluation_run.events_created} check(s).`
          : "No configured thresholds were exceeded."
      );
      const updated = await listEvaluationRuns();
      setRuns(updated.runs);
    } catch (e) {
      setError(e instanceof GuardianApiError ? e.message : "Evaluation failed.");
    }
  }

  async function loadAudit() {
    abort();
    try {
      const data = await getAudit(50, abortRef.current!.signal);
      setAuditEvents(data.audit_events);
    } catch (_) {}
  }

  // ---- Render ----

  if (household === null) return <div role="status">Loading…</div>;
  if (household === false) return <NoHousehold />;
  if (loading) return <div role="status">Loading Guardian Checks…</div>;

  return (
    <div role="region" aria-label="Guardian Monitoring">
      <nav style={{ marginBottom: 16 }}>
        <Link href="/">Home</Link> › Guardian
      </nav>
      <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>{NON_ADVISORY}</p>
      {error && <div role="alert" style={{ color: "var(--danger)", marginBottom: 12 }}>{error}<button onClick={() => setError(null)} aria-label="Dismiss error">✕</button></div>}

      <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
        <button onClick={() => { setView("create"); setForm(emptyForm()); }} aria-label="Create Guardian Check">+ New Check</button>
        <button onClick={loadChecks} aria-label="Reload checks">Reload</button>
        <button onClick={() => handleEvaluate(false)} aria-label="Evaluate all checks">Evaluate All</button>
        {selected && <button onClick={() => handleEvaluate(true)} aria-label="Evaluate this check">Evaluate This</button>}
        {evalResult && <span role="status">{evalResult}</span>}
      </div>

      {view === "create" && (
        <CheckEditor form={form} setForm={setForm} onSave={handleCreate} onCancel={() => setView("list")} creating />
      )}
      {view === "edit" && selected && (
        <CheckEditor form={form} setForm={setForm} onSave={async () => {
          await updateDraft(selected.identity.id, { expected_revision: selected.draft!.expected_revision, ...draftFromForm(form) });
          setView("detail");
        }} onCancel={() => setView("detail")} />
      )}

      {view === "list" && (
        <CheckList checks={checks} onSelect={id => { setSelectedId(id); setView("detail"); }} />
      )}
      {view === "detail" && selected && (
        <CheckDetail
          detail={selected}
          onEdit={() => { formFromDraft(selected); setView("edit"); }}
          onConfirm={handleConfirm}
          onDiscard={handleDiscard}
          onBack={() => setView("list")}
        />
      )}

      <hr />
      <AuditTimeline events={auditEvents} onLoad={loadAudit} />
    </div>
  );
}

// ---- Sub-components ----

function NoHousehold() {
  return <div><p>No household profile found.</p><Link href="/household">Create Household</Link></div>;
}

type CreateForm = {
  name: string; check_type: GuardianCheckType; threshold_value: string; severity: string;
  target_category: string; target_holding_category: string;
  staleness_days: number | null; notes: string;
  eval_date: string;
};

function emptyForm(): CreateForm {
  return { name: "", check_type: "drift", threshold_value: "", severity: "info", target_category: "", target_holding_category: "", staleness_days: null, notes: "", eval_date: todayISO() };
}

function formFromDraft(d: GuardianCheckDetail) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (null as any); // placeholder — set via state
}

function draftFromForm(f: CreateForm): Record<string, unknown> {
  const d: Record<string, unknown> = { threshold_value: f.threshold_value || undefined, severity: f.severity || undefined, notes: f.notes || undefined };
  if (f.check_type === "drift" || f.check_type === "category_exposure") {
    d.target_holding_category = f.target_holding_category || undefined;
    if (f.check_type === "drift") d.target_category = f.target_category || undefined;
  }
  if (f.check_type === "staleness") d.staleness_days = f.staleness_days ?? undefined;
  return d;
}

function CheckEditor({ form, setForm, onSave, onCancel, creating }: {
  form: CreateForm; setForm: (f: CreateForm) => void; onSave: () => void; onCancel: () => void; creating?: boolean;
}) {
  const update = (patch: Partial<CreateForm>) => setForm({ ...form, ...patch });
  return (
    <section aria-label={creating ? "Create Guardian Check" : "Edit Draft"}>
      <label>Name <input value={form.name} onChange={e => update({ name: e.target.value })} aria-required /></label>
      <label>Type <select value={form.check_type} onChange={e => update({ check_type: e.target.value as GuardianCheckType })}>
        {CHECK_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
      </select></label>
      <label>Threshold <input type="text" value={form.threshold_value} onChange={e => update({ threshold_value: e.target.value })} aria-describedby="thresh-hint" /></label>
      <span id="thresh-hint">Decimal string, e.g. 5.00</span>
      <label>Severity <select value={form.severity} onChange={e => update({ severity: e.target.value })}>
        {["info","warning","critical"].map(s => <option key={s} value={s}>{s}</option>)}
      </select></label>
      {form.check_type === "drift" && (
        <>
          <label>Policy Category <input value={form.target_category} onChange={e => update({ target_category: e.target.value })} /></label>
          <label>Portfolio Category <input value={form.target_holding_category} onChange={e => update({ target_holding_category: e.target.value })} /></label>
        </>
      )}
      {form.check_type === "category_exposure" && (
        <label>Portfolio Category <input value={form.target_holding_category} onChange={e => update({ target_holding_category: e.target.value })} /></label>
      )}
      {form.check_type === "staleness" && (
        <label>Staleness Days <input type="number" value={form.staleness_days ?? ""} onChange={e => update({ staleness_days: e.target.value ? parseInt(e.target.value) : null })} /></label>
      )}
      <label>Notes <input value={form.notes} onChange={e => update({ notes: e.target.value })} /></label>
      <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
        <button onClick={onSave} aria-label={creating ? "Create Check" : "Save Draft"}>{creating ? "Create" : "Save"}</button>
        <button onClick={onCancel} aria-label="Cancel">Cancel</button>
      </div>
    </section>
  );
}

function CheckList({ checks, onSelect }: { checks: GuardianCheckDetail[]; onSelect: (id: string) => void }) {
  if (checks.length === 0) return <p>No Guardian Checks configured.</p>;
  return (
    <ul aria-label="Guardian Checks">
      {checks.map(c => (
        <li key={c.identity.id}>
          <button onClick={() => onSelect(c.identity.id)} aria-label={`Check ${c.identity.name}`}>
            {c.identity.name} ({c.identity.check_type}) — {c.identity.status}
          </button>
        </li>
      ))}
    </ul>
  );
}

function CheckDetail({ detail, onEdit, onConfirm, onDiscard, onBack }: {
  detail: GuardianCheckDetail; onEdit: () => void; onConfirm: () => void; onDiscard: () => void; onBack: () => void;
}) {
  const { identity, draft, latest_version } = detail;
  return (
    <section aria-label={`Check detail: ${identity.name}`}>
      <button onClick={onBack} aria-label="Back to list">← Back</button>
      <h2>{identity.name}</h2>
      <dl>
        <dt>Type</dt><dd>{identity.check_type}</dd>
        <dt>Status</dt><dd>{identity.status}</dd>
        {latest_version && (
          <>
            <dt>Version</dt><dd>{latest_version.version_number}</dd>
            <dt>Threshold</dt><dd>{latest_version.threshold_value}</dd>
            <dt>Severity</dt><dd>{latest_version.severity}</dd>
            <dt>Confirmed</dt><dd>{latest_version.confirmed_at}</dd>
          </>
        )}
        {draft && (
          <>
            <dt>Draft Threshold</dt><dd>{draft.threshold_value}</dd>
            <dt>Revision</dt><dd>{draft.expected_revision}</dd>
          </>
        )}
      </dl>
      {draft && (
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={onEdit} aria-label="Edit draft">Edit</button>
          <button onClick={onConfirm} aria-label="Confirm draft">Confirm</button>
          <button onClick={onDiscard} aria-label="Discard draft">Discard</button>
        </div>
      )}
      {!draft && latest_version && (
        <div>
          <p>No draft — this check has confirmed versions.</p>
          <button onClick={onDiscard} aria-label="Delete draft">Discard Draft</button>
        </div>
      )}
    </section>
  );
}

function AuditTimeline({ events, onLoad }: { events: GuardianAuditEvent[]; onLoad: () => void }) {
  return (
    <section aria-label="Guardian Audit">
      <h3>Audit</h3>
      <button onClick={onLoad} aria-label="Load audit events">Load</button>
      {events.length > 0 && (
        <ul>
          {events.map(e => (
            <li key={e.id}><strong>{e.action}</strong> — {new Date(e.occurred_at).toLocaleString()}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
