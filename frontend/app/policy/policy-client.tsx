"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  AllocationInput,
  allocationTotal,
  allocationsEqual,
  createDraft,
  createPolicy,
  discardDraft,
  getCurrentDraft,
  getCurrentPolicy,
  getCurrentPublished,
  getPolicyAuditEvents,
  getVersion,
  getVersionHistory,
  hasCurrentHousehold,
  POLICY_TEXT_FIELDS,
  POLICY_TEXT_LIMITS,
  Policy,
  PolicyApiError,
  PolicyAuditEvent,
  PolicyDraft,
  PolicyText,
  PolicyTextField,
  PolicyVersion,
  PolicyVersionSummary,
  publishDraft,
  replaceDraftAllocations,
  REQUIRED_PUBLISH_FIELDS,
  updateDraftText,
} from "../../lib/policy-api";

const LOCAL_ONLY_NOTICE =
  "This Sprint 002 build is local-only and non-production. It has no authentication and must not be publicly exposed.";

const NON_ADVISORY_NOTICE =
  "CompoundOS records information you enter. It does not evaluate whether an investment policy or decision is suitable, appropriate, or likely to succeed. Policy links and validations are for recordkeeping only and do not constitute investment, tax, or legal advice.";

const FIELD_LABELS: Record<PolicyTextField, string> = {
  objectives: "Objectives",
  time_horizon: "Time horizon",
  liquidity: "Liquidity",
  diversification: "Diversification",
  contribution_policy: "Contribution policy",
  rebalancing_policy: "Rebalancing policy",
  prohibited_assets: "Prohibited assets",
  leverage_policy: "Leverage policy",
  decision_process: "Decision process",
  notes: "Notes",
};

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function conflictMessage(error: unknown): string | null {
  return error instanceof PolicyApiError && error.status === 409 ? error.message : null;
}

function neutralMessage(error: unknown): string {
  return error instanceof PolicyApiError
    ? error.message
    : "The Policy request could not be completed.";
}

function textFromDraft(draft: PolicyDraft): PolicyText {
  return Object.fromEntries(POLICY_TEXT_FIELDS.map((field) => [field, draft[field]])) as PolicyText;
}

function allocationInputs(draft: PolicyDraft): AllocationInput[] {
  return draft.allocations.map(({ asset_class_name, target_percentage }) => ({
    asset_class_name,
    target_percentage,
  }));
}

function unicodeLength(value: string): number {
  return Array.from(value).length;
}

type DraftMutationResult = (draft: PolicyDraft, message: string) => void;

function ConflictPanel({ message, onReload }: { message: string; onReload: () => void }) {
  return (
    <div className="error-panel" role="alert">
      <p>{message}</p>
      <button onClick={onReload} type="button">Reload server data</button>
    </div>
  );
}

function DraftTextEditor({
  draft,
  onReload,
  onSaved,
}: {
  draft: PolicyDraft;
  onReload: () => void;
  onSaved: DraftMutationResult;
}) {
  const [form, setForm] = useState<PolicyText>(() => textFromDraft(draft));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    const tooLong = POLICY_TEXT_FIELDS.find(
      (field) => unicodeLength(form[field].trim()) > POLICY_TEXT_LIMITS[field],
    );
    if (tooLong) {
      setError(`${FIELD_LABELS[tooLong]} exceeds its character limit.`);
      return;
    }

    const changed = Object.fromEntries(
      POLICY_TEXT_FIELDS.flatMap((field) => {
        const value = form[field].trim();
        return value === draft[field] ? [] : [[field, value]];
      }),
    ) as Partial<PolicyText>;
    if (Object.keys(changed).length === 0) {
      setError("There are no text changes to save.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setConflict(null);
    try {
      const saved = await updateDraftText(draft.revision, changed);
      setForm(textFromDraft(saved));
      onSaved(saved, "Policy text saved.");
    } catch (caught) {
      const message = conflictMessage(caught);
      if (message) setConflict(message);
      else setError(neutralMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="policy-text-heading">
      <div className="section-heading">
        <p className="eyebrow">User-entered record</p>
        <h2 id="policy-text-heading">Policy text</h2>
        <p className="hint">Fields are saved only when you choose Save policy text.</p>
      </div>
      <form className="policy-form" onSubmit={save} noValidate>
        {POLICY_TEXT_FIELDS.map((field) => {
          const required = REQUIRED_PUBLISH_FIELDS.includes(
            field as (typeof REQUIRED_PUBLISH_FIELDS)[number],
          );
          const length = unicodeLength(form[field]);
          return (
            <label key={field}>
              <span className="label-row">
                <span>{FIELD_LABELS[field]}</span>
                <span className="field-badge">
                  {required ? "Required to publish" : "Optional"}
                </span>
              </span>
              <textarea
                aria-label={FIELD_LABELS[field]}
                aria-describedby={`${field}-hint`}
                onChange={(event) =>
                  setForm((current) => ({ ...current, [field]: event.target.value }))
                }
                value={form[field]}
              />
              <span className="hint" id={`${field}-hint`}>
                {length.toLocaleString()} / {POLICY_TEXT_LIMITS[field].toLocaleString()} characters.
                {required ? " Publication checks presence only." : " Optional for publication."}
              </span>
            </label>
          );
        })}
        {error ? <p className="error" role="alert">{error}</p> : null}
        {conflict ? <ConflictPanel message={conflict} onReload={onReload} /> : null}
        <div className="actions">
          <button className="primary-button" disabled={submitting} type="submit">
            {submitting ? "Saving policy text…" : "Save policy text"}
          </button>
        </div>
      </form>
    </section>
  );
}

type EditableAllocation = AllocationInput & { localId: string };

function editableAllocations(draft: PolicyDraft): EditableAllocation[] {
  return draft.allocations.map((item) => ({
    localId: item.id,
    asset_class_name: item.asset_class_name,
    target_percentage: item.target_percentage,
  }));
}

function AllocationEditor({
  draft,
  onReload,
  onSaved,
}: {
  draft: PolicyDraft;
  onReload: () => void;
  onSaved: DraftMutationResult;
}) {
  const nextId = useRef(0);
  const [rows, setRows] = useState<EditableAllocation[]>(() => editableAllocations(draft));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);

  const inputs = useMemo<AllocationInput[]>(
    () => rows.map(({ asset_class_name, target_percentage }) => ({ asset_class_name, target_percentage })),
    [rows],
  );
  const total = allocationTotal(inputs);

  function updateRow(index: number, field: keyof AllocationInput, value: string) {
    setRows((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, [field]: value } : row)),
    );
  }

  function move(index: number, direction: -1 | 1) {
    setRows((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  async function save() {
    if (submitting) return;
    if (inputs.some((item) => !item.asset_class_name.trim())) {
      setError("Each allocation row needs an asset-class name before saving.");
      return;
    }
    if (total.hundredths === null && inputs.length > 0) {
      setError("Percentages must be integers or decimal strings with at most two places, greater than 0 and no more than 100.");
      return;
    }
    if (allocationsEqual(draft.allocations, inputs)) {
      setError("There are no allocation changes to save.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setConflict(null);
    try {
      const saved = await replaceDraftAllocations(draft.revision, inputs);
      setRows(editableAllocations(saved));
      onSaved(saved, "Draft allocations saved.");
    } catch (caught) {
      const message = conflictMessage(caught);
      if (message) setConflict(message);
      else setError(neutralMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="allocation-heading">
      <div className="section-heading section-heading-row">
        <div>
          <p className="eyebrow">User-entered target record</p>
          <h2 id="allocation-heading">Draft allocation</h2>
          <p className="hint">Integer or at most two decimal places. No value is rounded.</p>
        </div>
        <button
          onClick={() => {
            nextId.current += 1;
            setRows((current) => [
              ...current,
              { localId: `new-${nextId.current}`, asset_class_name: "", target_percentage: "" },
            ]);
          }}
          type="button"
        >
          Add allocation row
        </button>
      </div>

      {rows.length === 0 ? <p>No allocation rows in this Draft.</p> : null}
      <ol className="allocation-editor">
        {rows.map((row, index) => (
          <li key={row.localId}>
            <label>
              Asset-class name
              <input
                maxLength={200}
                onChange={(event) => updateRow(index, "asset_class_name", event.target.value)}
                value={row.asset_class_name}
              />
            </label>
            <label>
              Target percentage
              <input
                inputMode="decimal"
                onChange={(event) => updateRow(index, "target_percentage", event.target.value)}
                value={row.target_percentage}
              />
            </label>
            <div className="row-actions" aria-label={`Reorder allocation row ${index + 1}`}>
              <button disabled={index === 0} onClick={() => move(index, -1)} type="button">Move up</button>
              <button disabled={index === rows.length - 1} onClick={() => move(index, 1)} type="button">Move down</button>
              <button
                onClick={() => setRows((current) => current.filter((_, rowIndex) => rowIndex !== index))}
                type="button"
              >
                Remove
              </button>
            </div>
          </li>
        ))}
      </ol>

      <div className="total-panel" role="status">
        <strong>Draft allocation total: {total.display}%</strong>
        <span>
          {total.hundredths === 10000
            ? "Mechanically complete at exactly 100.00%. This is not system approval."
            : "A Draft may remain incomplete; publication requires exactly 100.00%."}
        </span>
      </div>
      {error ? <p className="error" role="alert">{error}</p> : null}
      {conflict ? <ConflictPanel message={conflict} onReload={onReload} /> : null}
      <div className="actions">
        <button className="primary-button" disabled={submitting} onClick={() => void save()} type="button">
          {submitting ? "Saving allocations…" : "Save allocations"}
        </button>
      </div>
    </section>
  );
}

function PolicyTextReadOnly({ value }: { value: PolicyText }) {
  return (
    <dl className="summary-grid policy-summary">
      {POLICY_TEXT_FIELDS.map((field) => (
        <div key={field}>
          <dt>{FIELD_LABELS[field]}</dt>
          <dd>{value[field] || "Not provided"}</dd>
        </div>
      ))}
    </dl>
  );
}

function AllocationReadOnly({ items }: { items: AllocationInput[] }) {
  const total = allocationTotal(items);
  return (
    <div>
      <ul className="allocation-readonly">
        {items.map((item, index) => (
          <li key={`${item.asset_class_name}-${index}`}>
            <span>{item.asset_class_name}</span>
            <strong>{item.target_percentage}%</strong>
          </li>
        ))}
      </ul>
      <p><strong>Exact total: {total.display}%</strong></p>
    </div>
  );
}

function PublishReview({
  draft,
  onPublished,
  onReload,
}: {
  draft: PolicyDraft;
  onPublished: (version: PolicyVersion) => void;
  onReload: () => void;
}) {
  const [reviewing, setReviewing] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);
  const total = allocationTotal(allocationInputs(draft));

  async function publish() {
    if (!confirmed || submitting) return;
    setSubmitting(true);
    setError(null);
    setConflict(null);
    try {
      onPublished(await publishDraft(draft.revision));
    } catch (caught) {
      const message = conflictMessage(caught);
      if (message) setConflict(message);
      else setError(neutralMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="publish-heading">
      <div className="section-heading section-heading-row">
        <div>
          <p className="eyebrow">Explicit confirmation</p>
          <h2 id="publish-heading">Publish review</h2>
        </div>
        {!reviewing ? <button onClick={() => setReviewing(true)} type="button">Review for publication</button> : null}
      </div>
      {!reviewing ? <p>Review the saved server snapshot before creating an immutable Version.</p> : null}
      {reviewing ? (
        <div className="publish-review">
          <p>Current saved revision: {draft.revision}</p>
          <ul className="mechanical-checks">
            {REQUIRED_PUBLISH_FIELDS.map((field) => (
              <li key={field}>{FIELD_LABELS[field]}: {draft[field].trim() ? "Present" : "Missing"}</li>
            ))}
            <li>Allocation total: {total.display}%</li>
          </ul>
          <PolicyTextReadOnly value={draft} />
          <AllocationReadOnly items={allocationInputs(draft)} />
          <aside className="notice" aria-label="Publication non-advisory notice">
            <strong>Recordkeeping only</strong>
            <p>{NON_ADVISORY_NOTICE}</p>
          </aside>
          <label className="confirmation-row">
            <input
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
              type="checkbox"
            />
            I confirm that I want to publish this saved Draft as an immutable Version.
          </label>
          {error ? <p className="error" role="alert">{error}</p> : null}
          {conflict ? <ConflictPanel message={conflict} onReload={onReload} /> : null}
          <div className="actions">
            <button
              className="primary-button"
              disabled={!confirmed || submitting}
              onClick={() => void publish()}
              type="button"
            >
              {submitting ? "Publishing…" : "Publish immutable Version"}
            </button>
            <button disabled={submitting} onClick={() => setReviewing(false)} type="button">Close review</button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function VersionView({ version, heading = "Current Published Version" }: { version: PolicyVersion; heading?: string }) {
  return (
    <section className="panel" aria-labelledby={`version-${version.version_number}-heading`}>
      <div className="section-heading">
        <p className="eyebrow">Immutable · {version.status === "published" ? "Published" : "Superseded"}</p>
        <h2 id={`version-${version.version_number}-heading`}>{heading} · Version {version.version_number}</h2>
        <p className="hint">Published {new Date(version.published_at).toLocaleString()}</p>
      </div>
      <p><strong>Published versions cannot be edited.</strong> Changes require a new Draft and publication.</p>
      <PolicyTextReadOnly value={version} />
      <AllocationReadOnly items={version.allocations} />
    </section>
  );
}

function VersionHistory({
  items,
  loading,
  error,
  nextCursor,
  onLoadMore,
}: {
  items: PolicyVersionSummary[];
  loading: boolean;
  error: string | null;
  nextCursor: number | null;
  onLoadMore: () => void;
}) {
  const detailController = useRef<AbortController | null>(null);
  const [detail, setDetail] = useState<PolicyVersion | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => () => detailController.current?.abort(), []);

  async function selectVersion(versionNumber: number) {
    detailController.current?.abort();
    const controller = new AbortController();
    detailController.current = controller;
    setDetailLoading(true);
    setDetailError(null);
    try {
      setDetail(await getVersion(versionNumber, controller.signal));
    } catch (caught) {
      if (!isAbort(caught)) setDetailError(neutralMessage(caught));
    } finally {
      if (!controller.signal.aborted) setDetailLoading(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="history-heading">
      <div className="section-heading">
        <p className="eyebrow">Newest first · Read-only</p>
        <h2 id="history-heading">Version history</h2>
      </div>
      {error ? <p className="error" role="alert">{error}</p> : null}
      {items.length === 0 && !loading ? <p>No published Versions yet.</p> : null}
      <ol className="version-list">
        {items.map((item) => (
          <li key={item.id}>
            <div>
              <strong>Version {item.version_number}</strong>
              <span>{item.status === "published" ? "Published" : "Superseded"}</span>
              <span>{new Date(item.published_at).toLocaleString()}</span>
            </div>
            <button onClick={() => void selectVersion(item.version_number)} type="button">View immutable detail</button>
          </li>
        ))}
      </ol>
      {nextCursor !== null ? (
        <button disabled={loading} onClick={onLoadMore} type="button">
          {loading ? "Loading more Versions…" : "Load more Versions"}
        </button>
      ) : null}
      {detailLoading ? <p role="status">Loading Version detail…</p> : null}
      {detailError ? <p className="error" role="alert">{detailError}</p> : null}
      {detail ? <VersionView heading="Historical Version" version={detail} /> : null}
    </section>
  );
}

function AuditTimeline({
  events,
  loading,
  error,
  onRetry,
}: {
  events: PolicyAuditEvent[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <section className="panel" aria-labelledby="policy-audit-heading">
      <div className="section-heading">
        <p className="eyebrow">Latest server window · Read-only</p>
        <h2 id="policy-audit-heading">Policy audit timeline</h2>
        <p className="hint">
          Events are shown in the server-provided sequence order. This Slice exposes only the latest window and has no cursor for earlier events.
        </p>
      </div>
      {error ? (
        <div className="error-panel" role="alert">
          <p>{error}</p>
          <button disabled={loading} onClick={onRetry} type="button">
            {loading ? "Retrying audit timeline…" : "Retry audit timeline"}
          </button>
        </div>
      ) : null}
      {loading && !error ? <p role="status">Loading Policy audit timeline…</p> : null}
      {!loading && events.length === 0 ? <p>No Policy audit events yet.</p> : null}
      {!loading && events.length > 0 ? (
        <ol className="timeline">
          {events.map((event) => (
            <li key={event.id}>
              <strong>{event.action}</strong>
              <span>{new Date(event.occurred_at).toLocaleString()}</span>
              <span>Actor: {event.actor}</span>
              <span>Sequence: {event.sequence_number}</span>
              {Object.entries(event.metadata).map(([key, value]) => (
                <span key={key}>{key}: {Array.isArray(value) ? value.join(", ") : value}</span>
              ))}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}

export function PolicyClient() {
  const loadController = useRef<AbortController | null>(null);
  const auditController = useRef<AbortController | null>(null);
  const loadSequence = useRef(0);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [hasHousehold, setHasHousehold] = useState<boolean | null>(null);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [draft, setDraft] = useState<PolicyDraft | null>(null);
  const [published, setPublished] = useState<PolicyVersion | null>(null);
  const [history, setHistory] = useState<PolicyVersionSummary[]>([]);
  const [nextHistoryCursor, setNextHistoryCursor] = useState<number | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [auditEvents, setAuditEvents] = useState<PolicyAuditEvent[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [mutation, setMutation] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const [discardConfirmation, setDiscardConfirmation] = useState(false);
  const [workspaceEpoch, setWorkspaceEpoch] = useState(0);

  const loadWorkspace = useCallback(async () => {
    loadController.current?.abort();
    const controller = new AbortController();
    loadController.current = controller;
    loadSequence.current += 1;
    const sequence = loadSequence.current;
    setInitialLoading(true);
    setLoadError(null);
    setMutationError(null);
    try {
      const [householdExists, currentPolicy] = await Promise.all([
        hasCurrentHousehold(controller.signal),
        getCurrentPolicy(controller.signal),
      ]);
      if (controller.signal.aborted || sequence !== loadSequence.current) return;
      setHasHousehold(householdExists);
      setPolicy(currentPolicy);

      if (!householdExists || !currentPolicy) {
        setDraft(null);
        setPublished(null);
        setHistory([]);
        setNextHistoryCursor(null);
        setAuditEvents([]);
        setAuditError(null);
        return;
      }

      const [draftResult, publishedResult, historyResult, auditResult] = await Promise.all([
        getCurrentDraft(controller.signal),
        getCurrentPublished(controller.signal),
        getVersionHistory(undefined, controller.signal),
        getPolicyAuditEvents(controller.signal).then(
          (events) => ({ ok: true as const, events }),
          (error: unknown) => ({ ok: false as const, error }),
        ),
      ]);
      if (controller.signal.aborted || sequence !== loadSequence.current) return;
      setDraft(draftResult);
      setPublished(publishedResult);
      setHistory(historyResult.items);
      setNextHistoryCursor(historyResult.next_before_version_number);
      setWorkspaceEpoch((current) => current + 1);
      if (auditResult.ok) {
        setAuditEvents(auditResult.events);
        setAuditError(null);
      } else if (!isAbort(auditResult.error)) {
        setAuditError("Policy data is available, but the audit timeline could not be loaded.");
      }
    } catch (caught) {
      if (!isAbort(caught)) setLoadError(neutralMessage(caught));
    } finally {
      if (!controller.signal.aborted && sequence === loadSequence.current) {
        setInitialLoading(false);
        setAuditLoading(false);
      }
    }
  }, []);

  const refreshAudit = useCallback(async (afterMutation = false) => {
    auditController.current?.abort();
    const controller = new AbortController();
    auditController.current = controller;
    setAuditLoading(true);
    setAuditError(null);
    try {
      setAuditEvents(await getPolicyAuditEvents(controller.signal));
    } catch (caught) {
      if (!isAbort(caught)) {
        setAuditError(
          afterMutation
            ? "The Policy mutation succeeded, but the audit timeline could not be refreshed."
            : "The Policy audit timeline could not be loaded.",
        );
      }
    } finally {
      if (!controller.signal.aborted) setAuditLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadWorkspace(), 0);
    return () => {
      window.clearTimeout(timer);
      loadController.current?.abort();
      auditController.current?.abort();
    };
  }, [loadWorkspace]);

  function acceptDraft(saved: PolicyDraft, message: string) {
    setDraft(saved);
    setSavedMessage(message);
    setMutationError(null);
    void refreshAudit(true);
  }

  async function handleCreatePolicy() {
    if (mutation) return;
    setMutation("create-policy");
    setMutationError(null);
    setSavedMessage(null);
    try {
      const created = await createPolicy();
      setPolicy(created.policy);
      setDraft(created.draft);
      setPublished(null);
      setHistory([]);
      setNextHistoryCursor(null);
      setSavedMessage("Investment Policy and initial Draft created.");
      void refreshAudit(true);
    } catch (caught) {
      if (caught instanceof PolicyApiError && caught.status === 409) await loadWorkspace();
      else setMutationError(neutralMessage(caught));
    } finally {
      setMutation(null);
    }
  }

  async function handleCreateDraft(sourceVersionId?: string) {
    if (mutation) return;
    setMutation(sourceVersionId ? "copy-draft" : "blank-draft");
    setMutationError(null);
    try {
      const created = await createDraft(sourceVersionId);
      setDraft(created);
      setSavedMessage(sourceVersionId ? "Draft copied from the current Published Version." : "Blank Draft created.");
      void refreshAudit(true);
    } catch (caught) {
      if (caught instanceof PolicyApiError && caught.status === 409) await loadWorkspace();
      else setMutationError(neutralMessage(caught));
    } finally {
      setMutation(null);
    }
  }

  async function handleDiscard() {
    if (!draft || mutation) return;
    setMutation("discard");
    setMutationError(null);
    try {
      await discardDraft(draft.revision);
      setSavedMessage("Draft discarded. Published Versions were not changed.");
      setDiscardConfirmation(false);
      await loadWorkspace();
    } catch (caught) {
      setMutationError(neutralMessage(caught));
    } finally {
      setMutation(null);
    }
  }

  async function loadMoreHistory() {
    if (nextHistoryCursor === null || historyLoading) return;
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const page = await getVersionHistory(nextHistoryCursor);
      setHistory((current) => {
        const byNumber = new Map(current.map((item) => [item.version_number, item]));
        page.items.forEach((item) => byNumber.set(item.version_number, item));
        return [...byNumber.values()].sort((left, right) => right.version_number - left.version_number);
      });
      setNextHistoryCursor(page.next_before_version_number);
    } catch (caught) {
      setHistoryError(neutralMessage(caught));
    } finally {
      setHistoryLoading(false);
    }
  }

  async function handlePublished(version: PolicyVersion) {
    setPublished(version);
    setDraft(null);
    setSavedMessage(`Version ${version.version_number} published.`);
    setHistoryLoading(true);
    try {
      const refreshed = await getVersionHistory();
      setHistory(refreshed.items);
      setNextHistoryCursor(refreshed.next_before_version_number);
      setHistoryError(null);
    } catch (caught) {
      setHistoryError(neutralMessage(caught));
    } finally {
      setHistoryLoading(false);
    }
    void refreshAudit(true);
  }

  return (
    <main className="policy-shell">
      <header className="page-header">
        <p className="eyebrow">CompoundOS · Sprint 002 Slice 2C</p>
        <h1>Investment Policy</h1>
        <p className="lede">Record user-authored Policy text and target percentages through explicit, reviewable saves.</p>
      </header>

      <aside className="notice notice-warning" aria-label="Local-only limitation">
        <strong>Local-only, non-production limitation</strong>
        <p>{LOCAL_ONLY_NOTICE}</p>
      </aside>
      <aside className="notice" aria-label="Non-advisory notice">
        <strong>Recordkeeping only</strong>
        <p>{NON_ADVISORY_NOTICE}</p>
        <p>CompoundOS does not provide investment advice, recommendations, or trade instructions.</p>
      </aside>

      {initialLoading ? <p role="status">Loading Household and Policy state…</p> : null}
      {loadError ? (
        <div className="error-panel" role="alert">
          <p>{loadError}</p>
          <button onClick={() => void loadWorkspace()} type="button">Try again</button>
        </div>
      ) : null}
      {savedMessage ? <p className="success-message" role="status">{savedMessage}</p> : null}
      {mutationError ? <ConflictPanel message={mutationError} onReload={() => void loadWorkspace()} /> : null}

      {!initialLoading && !loadError && hasHousehold === false ? (
        <section className="panel" aria-labelledby="missing-household-heading">
          <p className="eyebrow">Household prerequisite</p>
          <h2 id="missing-household-heading">Create the Household profile first</h2>
          <p>The sole HouseholdProfile must exist before an Investment Policy record can be created.</p>
          <Link className="primary-link" href="/household">Open Household profile</Link>
        </section>
      ) : null}

      {!initialLoading && !loadError && hasHousehold && !policy ? (
        <section className="panel" aria-labelledby="empty-policy-heading">
          <p className="eyebrow">Empty Policy workspace</p>
          <h2 id="empty-policy-heading">No Investment Policy record yet</h2>
          <p>Create the stable Policy and an empty Draft. CompoundOS will not add text, asset classes, or percentages for you.</p>
          <button
            className="primary-button"
            disabled={mutation !== null}
            onClick={() => void handleCreatePolicy()}
            type="button"
          >
            {mutation === "create-policy" ? "Creating policy draft…" : "Create policy draft"}
          </button>
        </section>
      ) : null}

      {!initialLoading && !loadError && policy && draft ? (
        <>
          <section className="workspace-status" aria-label="Draft status">
            <span>Editable Draft</span>
            <strong>Server revision {draft.revision}</strong>
          </section>
          <DraftTextEditor key={`text-${draft.id}-${workspaceEpoch}`} draft={draft} onReload={() => void loadWorkspace()} onSaved={acceptDraft} />
          <AllocationEditor key={`allocations-${draft.id}-${workspaceEpoch}`} draft={draft} onReload={() => void loadWorkspace()} onSaved={acceptDraft} />
          <PublishReview draft={draft} onPublished={(version) => void handlePublished(version)} onReload={() => void loadWorkspace()} />
          <section className="panel" aria-labelledby="discard-heading">
            <p className="eyebrow">Draft lifecycle</p>
            <h2 id="discard-heading">Discard Draft</h2>
            <p>Discarding removes only this editable Draft. It does not delete the Policy or any Published Version.</p>
            {!discardConfirmation ? (
              <button onClick={() => setDiscardConfirmation(true)} type="button">Discard Draft…</button>
            ) : (
              <div className="confirmation-panel">
                <p><strong>Confirm Draft discard?</strong></p>
                <div className="actions">
                  <button disabled={mutation !== null} onClick={() => void handleDiscard()} type="button">
                    {mutation === "discard" ? "Discarding Draft…" : "Confirm discard Draft"}
                  </button>
                  <button disabled={mutation !== null} onClick={() => setDiscardConfirmation(false)} type="button">Cancel</button>
                </div>
              </div>
            )}
          </section>
        </>
      ) : null}

      {!initialLoading && !loadError && policy && !draft ? (
        <>
          {published ? <VersionView version={published} /> : (
            <section className="panel">
              <h2>No Draft is open</h2>
              <p>The stable Policy exists, but it has no editable Draft or Published Version.</p>
            </section>
          )}
          <section className="panel" aria-labelledby="new-draft-heading">
            <p className="eyebrow">Explicit new work</p>
            <h2 id="new-draft-heading">Create a new Draft</h2>
            <div className="actions">
              <button disabled={mutation !== null} onClick={() => void handleCreateDraft()} type="button">
                {mutation === "blank-draft" ? "Creating blank Draft…" : "Start blank"}
              </button>
              {published ? (
                <button disabled={mutation !== null} onClick={() => void handleCreateDraft(published.id)} type="button">
                  {mutation === "copy-draft" ? "Copying current Published…" : "Copy current Published"}
                </button>
              ) : null}
            </div>
          </section>
        </>
      ) : null}

      {!initialLoading && !loadError && policy ? (
        <>
          <VersionHistory
            error={historyError}
            items={history}
            loading={historyLoading}
            nextCursor={nextHistoryCursor}
            onLoadMore={() => void loadMoreHistory()}
          />
          <AuditTimeline
            error={auditError}
            events={auditEvents}
            loading={auditLoading}
            onRetry={() => void refreshAudit()}
          />
        </>
      ) : null}
    </main>
  );
}
