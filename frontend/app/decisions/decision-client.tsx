"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  appendCorrection,
  archiveDecision,
  confirmDraft,
  createDecision,
  Correction,
  DecisionAuditEvent,
  DecisionDetailResponse,
  DecisionListItem,
  DecisionStatus,
  DecisionTextField,
  DECISION_STATUSES,
  DECISION_TEXT_FIELDS,
  DECISION_TEXT_LIMITS,
  discardDraft,
  DraftDetail,
  listDecisions,
  readCorrections,
  readDecisionAudit,
  readDecisionDetail,
  SnapshotDetail,
  unarchiveDecision,
  updateDraft,
} from "../../lib/decision-api";

/* ------------------------------------------------------------------ */
/*  Notices                                                           */
/* ------------------------------------------------------------------ */

const NOTICE_OWN = "In CompoundOS, Decisions are your own. Nothing here is advice.";
const NOTICE_CONFIRM = "Confirming a Decision creates a permanent record of what you decided and why.";
const NOTICE_ARCHIVE = "Archived Decisions remain correctable — you can always add a dated Correction.";

const LOCAL_ONLY_NOTICE =
  "This Sprint 002 build is local-only and non-production. It has no authentication and must not be publicly exposed.";

/* ------------------------------------------------------------------ */
/*  Labels                                                           */
/* ------------------------------------------------------------------ */

const FIELD_LABELS: Record<DecisionTextField, string> = {
  title: "Title",
  decision_summary: "Decision summary",
  rationale: "Rationale",
  alternatives_considered: "Alternatives considered",
  risks_and_uncertainties: "Risks and uncertainties",
  evidence_or_sources: "Evidence or sources",
  expected_outcome: "Expected outcome",
  review_trigger: "Review trigger",
  notes: "Notes",
};

const STATUS_LABELS: Record<DecisionStatus, string> = {
  draft: "Draft",
  confirmed: "Confirmed",
  archived: "Archived",
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function isDecisionApiError(error: unknown): error is Error & { status: number } {
  return error instanceof Error && error.name === "DecisionApiError";
}

function conflictMessage(error: unknown): string | null {
  return isDecisionApiError(error) && error.status === 409 ? error.message : null;
}

function neutralMessage(error: unknown): string {
  if (isDecisionApiError(error)) {
    if (error.status === 404) return "The requested Decision record was not found.";
    if (error.status === 409) return "The Decision data changed in another operation. Reload before trying again.";
    if (error.status === 422) return "The request was not accepted. Check field formats, limits, and values.";
    if (error.status >= 500) return "The Decision service returned an unexpected server error.";
    return error.message;
  }
  if (error instanceof TypeError && error.message.includes("fetch")) {
    return "The Decision service connection is unavailable.";
  }
  return "The Decision request could not be completed.";
}

function unicodeLength(value: string): number {
  return Array.from(value).length;
}

/** decision_date: yesterday allowed, today allowed, future rejected */
function isFutureDate(dateString: string): boolean {
  if (!dateString) return false;
  const date = new Date(dateString + "T00:00:00");
  if (isNaN(date.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return date > today;
}

function formatDate(dateString: string | null): string {
  if (!dateString) return "Not set";
  return new Date(dateString + "T00:00:00").toLocaleDateString();
}

function formatDateTime(dateString: string | null): string {
  if (!dateString) return "—";
  return new Date(dateString).toLocaleString();
}

/** Extract text fields from a DraftDetail into a flat record */
function textFromDraft(draft: DraftDetail): Record<DecisionTextField, string> {
  return Object.fromEntries(
    DECISION_TEXT_FIELDS.map((f) => [f, (draft[f] ?? "") as string]),
  ) as Record<DecisionTextField, string>;
}

/** Compare two text records for dirty detection */
function textDirty(a: Record<DecisionTextField, string>, b: Record<DecisionTextField, string>): boolean {
  return DECISION_TEXT_FIELDS.some((f) => a[f].trim() !== b[f].trim());
}

/* ------------------------------------------------------------------ */
/*  ConflictPanel                                                     */
/* ------------------------------------------------------------------ */

function ConflictPanel({ message, onReload }: { message: string; onReload: () => void }) {
  return (
    <div className="error-panel" role="alert">
      <p>{message}</p>
      <button onClick={onReload} type="button">Reload server data</button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  FilterBadge                                                       */
/* ------------------------------------------------------------------ */

function FilterBadge({
  status,
  active,
  count,
  onClick,
}: {
  status: DecisionStatus | "active";
  active: boolean;
  count: number;
  onClick: () => void;
}) {
  return (
    <button
      aria-pressed={active}
      className={active ? "primary-button" : undefined}
      onClick={onClick}
      type="button"
    >
      {status === "active" ? "Active" : STATUS_LABELS[status]} ({count})
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  DecisionListPanel                                                 */
/* ------------------------------------------------------------------ */

function DecisionListPanel({
  decisions,
  total,
  loading,
  error,
  statusFilter,
  onFilterChange,
  selectedId,
  onSelect,
  onRetry,
  createTitle,
  onCreateTitleChange,
  onCreate,
  creating,
  createError,
}: {
  decisions: DecisionListItem[];
  total: number;
  loading: boolean;
  error: string | null;
  statusFilter: DecisionStatus | "active";
  onFilterChange: (status: DecisionStatus | "active") => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onRetry: () => void;
  createTitle: string;
  onCreateTitleChange: (title: string) => void;
  onCreate: () => void;
  creating: boolean;
  createError: string | null;
}) {
  const counts = useMemo(() => {
    const result: Record<DecisionStatus | "active", number> = { active: 0, draft: 0, confirmed: 0, archived: 0 };
    for (const d of decisions) {
      if (d.status in result) result[d.status]++;
      if (d.status === "draft" || d.status === "confirmed") result.active++;
    }
    return result;
  }, [decisions]);

  // Filter from active, draft, confirmed, archived — never shows a generic "all"
  const filterOptions = useMemo(() => ["active", ...DECISION_STATUSES] as const, []);

  return (
    <section className="panel" aria-labelledby="decision-list-heading">
      <div className="section-heading">
        <p className="eyebrow">Decision Journal</p>
        <h2 id="decision-list-heading">Decisions ({total})</h2>
        <p className="hint">Archived Decisions are hidden by default. Use the filter to view them.</p>
      </div>

      {/* Status filters */}
      <div className="actions" role="group" aria-label="Decision status filter">
        {filterOptions.map((status) => (
          <FilterBadge
            key={status}
            active={statusFilter === status}
            count={counts[status]}
            onClick={() => onFilterChange(status)}
            status={status}
          />
        ))}
      </div>

      {/* Error */}
      {error ? (
        <div className="error-panel" role="alert" style={{ marginTop: "1rem" }}>
          <p>{error}</p>
          <button disabled={loading} onClick={onRetry} type="button">Retry</button>
        </div>
      ) : null}

      {/* Loading */}
      {loading && !error ? <p role="status" style={{ marginTop: "1rem" }}>Loading Decisions…</p> : null}

      {/* Empty */}
      {!loading && !error && decisions.length === 0 ? (
        <p style={{ marginTop: "1rem" }}>No Decisions match the current filter.</p>
      ) : null}

      {/* Decision list */}
      {!loading && decisions.length > 0 ? (
        <ol className="version-list" style={{ marginTop: "1rem" }}>
          {decisions.map((d) => (
            <li key={d.id}>
              <div>
                <strong>{d.title || "Untitled Decision"}</strong>
                <span>
                  {STATUS_LABELS[d.status]}
                  {d.decision_date ? ` · ${formatDate(d.decision_date)}` : ""}
                  {d.correction_count > 0 ? ` · ${d.correction_count} correction${d.correction_count !== 1 ? "s" : ""}` : ""}
                </span>
              </div>
              <button
                aria-label={`View Decision ${d.title || "Untitled"}`}
                className={selectedId === d.id ? "primary-button" : undefined}
                onClick={() => onSelect(d.id)}
                type="button"
              >
                {selectedId === d.id ? "Selected" : "View"}
              </button>
            </li>
          ))}
        </ol>
      ) : null}

      {/* Create form */}
      <div style={{ marginTop: "1.5rem", borderTop: "1px solid var(--line)", paddingTop: "1.25rem" }}>
        <p className="eyebrow">New Decision</p>
        <div style={{ display: "flex", gap: "0.7rem", alignItems: "flex-start" }}>
          <label style={{ flex: 1, display: "grid", gap: "0.35rem", fontWeight: 650 }}>
            Decision title
            <input
              aria-label="New Decision title"
              disabled={creating}
              maxLength={DECISION_TEXT_LIMITS.title}
              onChange={(e) => onCreateTitleChange(e.target.value)}
              placeholder="Enter a title for the new Decision…"
              value={createTitle}
            />
          </label>
          <button
            aria-label="Create Decision"
            className="primary-button"
            disabled={creating || createTitle.trim().length === 0}
            onClick={onCreate}
            style={{ marginTop: "1.55rem" }}
            type="button"
          >
            {creating ? "Creating…" : "Create"}
          </button>
        </div>
        {createError ? <p className="error" role="alert" style={{ marginTop: "0.5rem" }}>{createError}</p> : null}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  DraftEditor                                                       */
/* ------------------------------------------------------------------ */

function DraftEditor({
  draft,
  onDirtyChange,
  onReload,
  onSaved,
  onDiscard,
}: {
  draft: DraftDetail;
  onDirtyChange: (dirty: boolean) => void;
  onReload: () => void;
  onSaved: (draft: DraftDetail, message: string) => void;
  onDiscard: () => void;
}) {
  const [form, setForm] = useState<Record<DecisionTextField, string>>(() => textFromDraft(draft));
  const [decisionDate, setDecisionDate] = useState<string>(draft.decision_date ?? "");
  const [reviewDate, setReviewDate] = useState<string>(draft.review_date ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);

  const dirty = useMemo(
    () =>
      textDirty(form, textFromDraft(draft)) ||
      (draft.decision_date ?? "") !== decisionDate ||
      (draft.review_date ?? "") !== reviewDate,
    [draft, form, decisionDate, reviewDate],
  );

  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;

    // Validate character limits
    const tooLong = DECISION_TEXT_FIELDS.find(
      (f) => unicodeLength(form[f].trim()) > DECISION_TEXT_LIMITS[f],
    );
    if (tooLong) {
      setError(`${FIELD_LABELS[tooLong]} exceeds its character limit.`);
      return;
    }

    // Validate dates
    if (decisionDate && isFutureDate(decisionDate)) {
      setError("Decision date cannot be in the future.");
      return;
    }
    if (reviewDate && isFutureDate(reviewDate)) {
      setError("Review date cannot be in the future.");
      return;
    }

    // Build changed fields — send null for emptied optional fields that had values
    const changed: Record<string, string | null> = {};
    for (const f of DECISION_TEXT_FIELDS) {
      const newVal = form[f].trim();
      const oldVal = (draft[f] ?? "").trim();
      if (newVal !== oldVal) {
        changed[f] = newVal || null;
      }
    }
    if (decisionDate !== (draft.decision_date ?? "")) {
      changed.decision_date = decisionDate || null;
    }
    if (reviewDate !== (draft.review_date ?? "")) {
      changed.review_date = reviewDate || null;
    }

    if (Object.keys(changed).length === 0) {
      setError("There are no changes to save.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setConflict(null);
    try {
      const saved = await updateDraft(draft.decision_id, draft.revision, changed);
      setForm(textFromDraft(saved));
      setDecisionDate(saved.decision_date ?? "");
      setReviewDate(saved.review_date ?? "");
      onSaved(saved, "Draft saved.");
    } catch (caught) {
      const msg = conflictMessage(caught);
      if (msg) setConflict(msg);
      else setError(neutralMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="draft-editor-heading">
      <div className="section-heading">
        <p className="eyebrow">Editable Draft · Revision {draft.revision}</p>
        <h2 id="draft-editor-heading">Draft editor</h2>
        <p className="hint">Fields are saved only when you choose Save draft.</p>
      </div>

      <form className="policy-form" onSubmit={save} noValidate>
        {DECISION_TEXT_FIELDS.map((field) => {
          const limit = DECISION_TEXT_LIMITS[field];
          const length = unicodeLength(form[field]);
          return (
            <label key={field}>
              <span className="label-row">
                <span>{FIELD_LABELS[field]}</span>
                <span className="field-badge">{field === "title" ? "Required" : "Optional"}</span>
              </span>
              <textarea
                aria-describedby={`${field}-hint`}
                aria-label={FIELD_LABELS[field]}
                onChange={(e) => setForm((c) => ({ ...c, [field]: e.target.value }))}
                value={form[field]}
              />
              <span className="hint" id={`${field}-hint`}>
                {length.toLocaleString()} / {limit.toLocaleString()} characters.
              </span>
            </label>
          );
        })}

        {/* Decision date */}
        <label>
          <span className="label-row">
            <span>Decision date</span>
            <span className="field-badge">Optional</span>
          </span>
          <input
            aria-describedby="decision-date-hint"
            aria-label="Decision date"
            onChange={(e) => setDecisionDate(e.target.value)}
            type="date"
            value={decisionDate}
          />
          <span className="hint" id="decision-date-hint">
            Yesterday and today are allowed. Future dates are rejected.
          </span>
          {decisionDate && isFutureDate(decisionDate) ? (
            <span className="error" role="alert">Decision date cannot be in the future.</span>
          ) : null}
        </label>

        {/* Review date */}
        <label>
          <span className="label-row">
            <span>Review date</span>
            <span className="field-badge">Optional</span>
          </span>
          <input
            aria-describedby="review-date-hint"
            aria-label="Review date"
            onChange={(e) => setReviewDate(e.target.value)}
            type="date"
            value={reviewDate}
          />
          <span className="hint" id="review-date-hint">
            Set a date to revisit this Decision. Future dates are rejected.
          </span>
          {reviewDate && isFutureDate(reviewDate) ? (
            <span className="error" role="alert">Review date cannot be in the future.</span>
          ) : null}
        </label>

        {error ? <p className="error" role="alert">{error}</p> : null}
        {conflict ? <ConflictPanel message={conflict} onReload={onReload} /> : null}

        <div className="actions">
          <button className="primary-button" disabled={submitting} type="submit">
            {submitting ? "Saving draft…" : "Save draft"}
          </button>
          <button
            className="danger-button"
            disabled={submitting}
            onClick={onDiscard}
            type="button"
          >
            Discard draft
          </button>
        </div>
      </form>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  SnapshotReadOnly                                                  */
/* ------------------------------------------------------------------ */

function SnapshotReadOnly({ snapshot, label }: { snapshot: SnapshotDetail; label: string }) {
  return (
    <div>
      <p className="eyebrow">{label} · Confirmed {formatDateTime(snapshot.confirmed_at)}</p>
      <dl className="summary-grid policy-summary">
        {DECISION_TEXT_FIELDS.map((f) => (
          <div key={f}>
            <dt>{FIELD_LABELS[f]}</dt>
            <dd>{(snapshot as unknown as Record<string, string | null>)[f] || "Not provided"}</dd>
          </div>
        ))}
        <div>
          <dt>Decision date</dt>
          <dd>{formatDate(snapshot.decision_date)}</dd>
        </div>
        <div>
          <dt>Review date</dt>
          <dd>{formatDate(snapshot.review_date)}</dd>
        </div>
        <div>
          <dt>Policy version</dt>
          <dd>Version {snapshot.policy_version_number}</dd>
        </div>
      </dl>
      {snapshot.snapshot_id ? (
        <p className="hint">Snapshot ID: {snapshot.snapshot_id}</p>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  ConfirmReview                                                     */
/* ------------------------------------------------------------------ */

function ConfirmReview({
  draft,
  dirty,
  decisionId,
  onConfirmed,
  onReload,
}: {
  draft: DraftDetail;
  dirty: boolean;
  decisionId: string;
  onConfirmed: () => void;
  onReload: () => void;
}) {
  const [reviewing, setReviewing] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);

  async function confirm() {
    if (dirty || !confirmed || submitting) return;
    setSubmitting(true);
    setError(null);
    setConflict(null);
    try {
      await confirmDraft(decisionId, draft.revision);
      onConfirmed();
    } catch (caught) {
      const msg = conflictMessage(caught);
      if (msg) setConflict(msg);
      else setError(neutralMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="confirm-heading">
      <div className="section-heading section-heading-row">
        <div>
          <p className="eyebrow">Explicit confirmation</p>
          <h2 id="confirm-heading">Confirm Decision</h2>
        </div>
        {!reviewing ? (
          <button disabled={dirty} onClick={() => setReviewing(true)} type="button">
            Review for confirmation
          </button>
        ) : null}
      </div>

      {dirty ? (
        <p className="notice" role="status">
          Save local changes before confirming. Confirmation uses only the saved server Draft.
        </p>
      ) : null}
      {!reviewing ? <p>Review the saved server snapshot before creating a permanent record.</p> : null}

      {reviewing ? (
        <div className="publish-review">
          <p>Current saved revision: {draft.revision}</p>
          <ul className="mechanical-checks">
            <li>Title: {draft.title.trim() ? "Present" : "Missing"}</li>
            <li>Decision date: {draft.decision_date ? formatDate(draft.decision_date) : "Not set"}</li>
            <li>Review date: {draft.review_date ? formatDate(draft.review_date) : "Not set"}</li>
          </ul>

          <dl className="summary-grid policy-summary">
            {DECISION_TEXT_FIELDS.map((f) => (
              <div key={f}>
                <dt>{FIELD_LABELS[f]}</dt>
                <dd>{(draft as unknown as Record<string, string | null>)[f] || "Not provided"}</dd>
              </div>
            ))}
          </dl>

          <aside className="notice" aria-label="Confirmation non-advisory notice">
            <strong>Recordkeeping only</strong>
            <p>{NOTICE_CONFIRM}</p>
          </aside>

          <label className="confirmation-row">
            <input
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              type="checkbox"
            />
            I confirm that I want to permanently record this Decision.
          </label>

          {error ? <p className="error" role="alert">{error}</p> : null}
          {conflict ? <ConflictPanel message={conflict} onReload={onReload} /> : null}

          <div className="actions">
            <button
              className="primary-button"
              disabled={dirty || !confirmed || submitting}
              onClick={() => void confirm()}
              type="button"
            >
              {submitting ? "Confirming…" : "Confirm Decision"}
            </button>
            <button disabled={submitting} onClick={() => setReviewing(false)} type="button">
              Close review
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  DecisionDetailView                                                */
/* ------------------------------------------------------------------ */

function DecisionDetailView({
  detail,
  onArchive,
  onUnarchive,
  archiving,
  archiveError,
}: {
  detail: DecisionDetailResponse;
  onArchive: (reason?: string) => void;
  onUnarchive: () => void;
  archiving: boolean;
  archiveError: string | null;
}) {
  const [tab, setTab] = useState<"effective" | "original">("effective");
  const [archiveReason, setArchiveReason] = useState("");
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(false);

  const status = detail.status;
  const snapshot = tab === "effective" ? detail.confirmed : detail.original;
  const hasOriginal = detail.original !== null;

  return (
    <section className="panel" aria-labelledby="decision-detail-heading">
      <div className="section-heading">
        <p className="eyebrow">{STATUS_LABELS[status]} · Created {formatDateTime(detail.created_at)}</p>
        <h2 id="decision-detail-heading">{snapshot?.title ?? detail.draft?.title ?? "Untitled Decision"}</h2>
        {detail.archived_at ? (
          <p className="hint">Archived {formatDateTime(detail.archived_at)}{detail.archive_reason ? ` — ${detail.archive_reason}` : ""}</p>
        ) : null}
      </div>

      {/* Original / Effective toggle */}
      {hasOriginal && status === "confirmed" ? (
        <div className="actions" role="group" aria-label="Snapshot view toggle">
          <button
            aria-pressed={tab === "effective"}
            className={tab === "effective" ? "primary-button" : undefined}
            onClick={() => setTab("effective")}
            type="button"
          >
            Effective
          </button>
          <button
            aria-pressed={tab === "original"}
            className={tab === "original" ? "primary-button" : undefined}
            onClick={() => setTab("original")}
            type="button"
          >
            Original
          </button>
        </div>
      ) : null}

      {snapshot ? (
        <SnapshotReadOnly
          label={tab === "effective" ? "Effective snapshot (latest Correction)" : "Original snapshot (first confirmation)"}
          snapshot={snapshot}
        />
      ) : (
        <p>No confirmed snapshot available.</p>
      )}

      {/* Archive / Unarchive actions */}
      {status === "archived" ? (
        <div className="actions" style={{ marginTop: "1rem" }}>
          <button
            disabled={archiving}
            onClick={onUnarchive}
            type="button"
          >
            {archiving ? "Unarchiving…" : "Unarchive Decision"}
          </button>
        </div>
      ) : null}

      {status === "confirmed" ? (
        <div style={{ marginTop: "1rem" }}>
          {!showArchiveConfirm ? (
            <button onClick={() => setShowArchiveConfirm(true)} type="button">
              Archive Decision…
            </button>
          ) : (
            <div className="confirmation-panel">
              <p><strong>Archive this Decision?</strong></p>
              <p className="hint">
                Archived Decisions can still receive Corrections and can be unarchived.
              </p>
              <label style={{ display: "grid", gap: "0.35rem", fontWeight: 650, marginBottom: "0.7rem" }}>
                Archive reason (optional)
                <input
                  aria-label="Archive reason"
                  onChange={(e) => setArchiveReason(e.target.value)}
                  placeholder="Why is this Decision being archived?"
                  value={archiveReason}
                />
              </label>
              <div className="actions">
                <button
                  disabled={archiving}
                  onClick={() => onArchive(archiveReason.trim() || undefined)}
                  type="button"
                >
                  {archiving ? "Archiving…" : "Confirm archive"}
                </button>
                <button disabled={archiving} onClick={() => setShowArchiveConfirm(false)} type="button">
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      ) : null}

      {archiveError ? <p className="error" role="alert" style={{ marginTop: "0.5rem" }}>{archiveError}</p> : null}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  CorrectionEditor                                                  */
/* ------------------------------------------------------------------ */

function CorrectionEditor({
  decisionId,
  onSaved,
}: {
  decisionId: string;
  onSaved: (correction: Correction) => void;
}) {
  const [form, setForm] = useState<Record<DecisionTextField, string>>(
    () => Object.fromEntries(DECISION_TEXT_FIELDS.map((f) => [f, ""])) as Record<DecisionTextField, string>,
  );
  const [decisionDate, setDecisionDate] = useState("");
  const [reviewDate, setReviewDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;

    // Validate required fields
    if (!form.title.trim()) {
      setError("Title is required.");
      return;
    }
    if (!form.decision_summary.trim()) {
      setError("Decision summary is required.");
      return;
    }
    if (!form.rationale.trim()) {
      setError("Rationale is required.");
      return;
    }
    if (!decisionDate) {
      setError("Decision date is required.");
      return;
    }

    // Validate limits
    const tooLong = DECISION_TEXT_FIELDS.find(
      (f) => unicodeLength(form[f].trim()) > DECISION_TEXT_LIMITS[f],
    );
    if (tooLong) {
      setError(`${FIELD_LABELS[tooLong]} exceeds its character limit.`);
      return;
    }

    // Validate dates
    if (isFutureDate(decisionDate)) {
      setError("Decision date cannot be in the future.");
      return;
    }
    if (reviewDate && isFutureDate(reviewDate)) {
      setError("Review date cannot be in the future.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const correction = await appendCorrection(decisionId, {
        title: form.title.trim(),
        decision_summary: form.decision_summary.trim(),
        rationale: form.rationale.trim(),
        decision_date: decisionDate,
        alternatives_considered: form.alternatives_considered.trim() || null,
        risks_and_uncertainties: form.risks_and_uncertainties.trim() || null,
        evidence_or_sources: form.evidence_or_sources.trim() || null,
        expected_outcome: form.expected_outcome.trim() || null,
        review_trigger: form.review_trigger.trim() || null,
        notes: form.notes.trim() || null,
        review_date: reviewDate || null,
      });
      // Reset form
      setForm(Object.fromEntries(DECISION_TEXT_FIELDS.map((f) => [f, ""])) as Record<DecisionTextField, string>);
      setDecisionDate("");
      setReviewDate("");
      onSaved(correction);
    } catch (caught) {
      setError(neutralMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="correction-editor-heading">
      <div className="section-heading">
        <p className="eyebrow">Dated Correction</p>
        <h2 id="correction-editor-heading">Append Correction</h2>
        <p className="hint">{NOTICE_ARCHIVE}</p>
      </div>

      <form className="policy-form" onSubmit={submit} noValidate>
        {DECISION_TEXT_FIELDS.map((field) => {
          const limit = DECISION_TEXT_LIMITS[field];
          const length = unicodeLength(form[field]);
          const required = ["title", "decision_summary", "rationale"].includes(field);
          return (
            <label key={field}>
              <span className="label-row">
                <span>{FIELD_LABELS[field]}</span>
                <span className="field-badge">{required ? "Required" : "Optional"}</span>
              </span>
              <textarea
                aria-describedby={`correction-${field}-hint`}
                aria-label={FIELD_LABELS[field]}
                onChange={(e) => setForm((c) => ({ ...c, [field]: e.target.value }))}
                value={form[field]}
              />
              <span className="hint" id={`correction-${field}-hint`}>
                {length.toLocaleString()} / {limit.toLocaleString()} characters.
              </span>
            </label>
          );
        })}

        <label>
          <span className="label-row">
            <span>Decision date</span>
            <span className="field-badge">Required</span>
          </span>
          <input
            aria-describedby="correction-decision-date-hint"
            aria-label="Decision date"
            onChange={(e) => setDecisionDate(e.target.value)}
            type="date"
            value={decisionDate}
          />
          <span className="hint" id="correction-decision-date-hint">
            Yesterday and today are allowed. Future dates are rejected.
          </span>
        </label>

        <label>
          <span className="label-row">
            <span>Review date</span>
            <span className="field-badge">Optional</span>
          </span>
          <input
            aria-describedby="correction-review-date-hint"
            aria-label="Review date"
            onChange={(e) => setReviewDate(e.target.value)}
            type="date"
            value={reviewDate}
          />
          <span className="hint" id="correction-review-date-hint">
            Set a date to revisit. Future dates are rejected.
          </span>
        </label>

        {error ? <p className="error" role="alert">{error}</p> : null}

        <div className="actions">
          <button className="primary-button" disabled={submitting} type="submit">
            {submitting ? "Appending Correction…" : "Append Correction"}
          </button>
        </div>
      </form>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  CorrectionHistory                                                 */
/* ------------------------------------------------------------------ */

function CorrectionHistory({
  items,
  loading,
  error,
  onRetry,
}: {
  items: Correction[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <section className="panel" aria-labelledby="correction-history-heading">
      <div className="section-heading">
        <p className="eyebrow">Newest first · Read-only</p>
        <h2 id="correction-history-heading">Correction history ({items.length})</h2>
      </div>

      {error ? (
        <div className="error-panel" role="alert">
          <p>{error}</p>
          <button disabled={loading} onClick={onRetry} type="button">
            Retry
          </button>
        </div>
      ) : null}

      {loading ? <p role="status">Loading Corrections…</p> : null}

      {!loading && items.length === 0 ? <p>No Corrections yet.</p> : null}

      {items.length > 0 ? (
        <ol className="timeline">
          {items.map((c) => (
            <li key={c.snapshot_id}>
              <strong>Correction #{c.correction_number}: {c.title}</strong>
              <span>{formatDate(c.decision_date)} · Created {formatDateTime(c.created_at)}</span>
              <span>{c.decision_summary}</span>
              {c.review_date ? <span>Review: {formatDate(c.review_date)}</span> : null}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  AuditTimeline                                                     */
/* ------------------------------------------------------------------ */

function AuditTimeline({
  events,
  loading,
  error,
  onRetry,
}: {
  events: DecisionAuditEvent[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <section className="panel" aria-labelledby="decision-audit-heading">
      <div className="section-heading">
        <p className="eyebrow">Latest server window · Read-only</p>
        <h2 id="decision-audit-heading">Decision audit timeline</h2>
        <p className="hint">
          Events are shown in the server-provided sequence order. This Slice exposes only the latest window.
        </p>
      </div>

      {error ? (
        <div className="error-panel" role="alert">
          <p>{error}</p>
          <button disabled={loading} onClick={onRetry} type="button">
            {loading ? "Retrying…" : "Retry"}
          </button>
        </div>
      ) : null}

      {loading && !error ? <p role="status">Loading Decision audit timeline…</p> : null}
      {!loading && events.length === 0 ? <p>No Decision audit events yet.</p> : null}
      {!loading && events.length > 0 ? (
        <ol className="timeline">
          {events.map((event) => (
            <li key={event.id}>
              <strong>{event.action}</strong>
              <span>{new Date(event.occurred_at).toLocaleString()}</span>
              <span>Actor: {event.actor}</span>
              {Object.entries(event.metadata).map(([key, value]) => (
                <span key={key}>
                  {key}: {Array.isArray(value) ? value.join(", ") : String(value)}
                </span>
              ))}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  DecisionClient — main orchestrator                                */
/* ------------------------------------------------------------------ */

export function DecisionClient() {
  /* ---- AbortController refs ---- */
  const listController = useRef<AbortController | null>(null);
  const detailController = useRef<AbortController | null>(null);
  const correctionController = useRef<AbortController | null>(null);
  const auditController = useRef<AbortController | null>(null);

  /* ---- Generation guards ---- */
  const listGeneration = useRef(0);
  const detailGeneration = useRef(0);
  const correctionGeneration = useRef(0);
  const auditGeneration = useRef(0);

  /* ---- State: list ---- */
  const [list, setList] = useState<DecisionListItem[]>([]);
  const [listTotal, setListTotal] = useState(0);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<DecisionStatus | "active">("active");

  /* ---- State: selected decision ---- */
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DecisionDetailResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  /* ---- State: draft editor dirty flag ---- */
  const [draftDirty, setDraftDirty] = useState(false);

  /* ---- State: corrections ---- */
  const [corrections, setCorrections] = useState<Correction[]>([]);
  const [correctionsLoading, setCorrectionsLoading] = useState(false);
  const [correctionsError, setCorrectionsError] = useState<string | null>(null);

  /* ---- State: audit ---- */
  const [auditEvents, setAuditEvents] = useState<DecisionAuditEvent[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  /* ---- State: UI ---- */
  const [createTitle, setCreateTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const [reloadConfirmation, setReloadConfirmation] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [archiving, setArchiving] = useState(false);

  /* ---- Load decision list ---- */
  const loadList = useCallback(async () => {
    listController.current?.abort();
    const controller = new AbortController();
    listController.current = controller;
    const generation = ++listGeneration.current;
    setListLoading(true);
    setListError(null);
    try {
      if (statusFilter === "active") {
        // Fetch draft + confirmed in parallel; archived is hidden by default
        const [draftResult, confirmedResult] = await Promise.all([
          listDecisions({ status: "draft" }, controller.signal),
          listDecisions({ status: "confirmed" }, controller.signal),
        ]);
        if (generation === listGeneration.current && !controller.signal.aborted) {
          const combined = [...draftResult.decisions, ...confirmedResult.decisions];
          setList(combined);
          setListTotal(combined.length);
        }
      } else {
        const result = await listDecisions({ status: statusFilter }, controller.signal);
        if (generation === listGeneration.current && !controller.signal.aborted) {
          setList(result.decisions);
          setListTotal(result.total);
        }
      }
    } catch (caught) {
      if (!isAbort(caught) && generation === listGeneration.current) {
        setListError(neutralMessage(caught));
      }
    } finally {
      if (generation === listGeneration.current && !controller.signal.aborted) {
        setListLoading(false);
      }
    }
  }, [statusFilter]);

  /* ---- Load detail for selected decision ---- */
  const loadDetail = useCallback(async (decisionId: string) => {
    detailController.current?.abort();
    const controller = new AbortController();
    detailController.current = controller;
    const generation = ++detailGeneration.current;
    setDetailLoading(true);
    setDetailError(null);
    setDetail(null);
    setDraftDirty(false);
    setArchiveError(null);
    try {
      const result = await readDecisionDetail(decisionId, controller.signal);
      if (generation === detailGeneration.current && !controller.signal.aborted) {
        setDetail(result);
      }
    } catch (caught) {
      if (!isAbort(caught) && generation === detailGeneration.current) {
        if (isDecisionApiError(caught) && caught.status === 404) {
          setDetailError("Decision not found. It may have been deleted.");
        } else {
          setDetailError(neutralMessage(caught));
        }
      }
    } finally {
      if (generation === detailGeneration.current && !controller.signal.aborted) {
        setDetailLoading(false);
      }
    }
  }, []);

  /* ---- Load corrections ---- */
  const loadCorrections = useCallback(async (decisionId: string) => {
    correctionController.current?.abort();
    const controller = new AbortController();
    correctionController.current = controller;
    const generation = ++correctionGeneration.current;
    setCorrectionsLoading(true);
    setCorrectionsError(null);
    try {
      const result = await readCorrections(decisionId, controller.signal);
      if (generation === correctionGeneration.current && !controller.signal.aborted) {
        setCorrections(result.corrections);
      }
    } catch (caught) {
      if (!isAbort(caught) && generation === correctionGeneration.current) {
        setCorrectionsError(neutralMessage(caught));
      }
    } finally {
      if (generation === correctionGeneration.current && !controller.signal.aborted) {
        setCorrectionsLoading(false);
      }
    }
  }, []);

  /* ---- Load audit for selected decision ---- */
  const loadAudit = useCallback(async (decisionId: string, afterMutation = false) => {
    auditController.current?.abort();
    const controller = new AbortController();
    auditController.current = controller;
    const generation = ++auditGeneration.current;
    setAuditLoading(true);
    setAuditError(null);
    try {
      const result = await readDecisionAudit(decisionId, undefined, controller.signal);
      if (generation === auditGeneration.current && !controller.signal.aborted) {
        setAuditEvents(result.events);
      }
    } catch (caught) {
      if (!isAbort(caught) && generation === auditGeneration.current) {
        setAuditError(
          afterMutation
            ? "The Decision mutation succeeded, but the audit timeline could not be refreshed."
            : "The Decision audit timeline could not be loaded.",
        );
      }
    } finally {
      if (generation === auditGeneration.current && !controller.signal.aborted) {
        setAuditLoading(false);
      }
    }
  }, []);

  /* ---- Select a decision ---- */
  const selectDecision = useCallback(
    (id: string) => {
      setSelectedId(id);
      void loadDetail(id);
      void loadCorrections(id);
      void loadAudit(id);
    },
    [loadDetail, loadCorrections, loadAudit],
  );

  /* ---- Create decision ---- */
  async function handleCreate() {
    if (creating || createTitle.trim().length === 0) return;
    setCreating(true);
    setCreateError(null);
    try {
      const created = await createDecision(createTitle.trim());
      setCreateTitle("");
      setSavedMessage(`Decision "${created.title}" created.`);
      // Select the new decision after list reload
      setSelectedId(created.id);
      await loadList();
      void loadDetail(created.id);
      void loadCorrections(created.id);
      void loadAudit(created.id);
    } catch (caught) {
      setCreateError(neutralMessage(caught));
    } finally {
      setCreating(false);
    }
  }

  /* ---- Archive / Unarchive ---- */
  async function handleArchive(reason?: string) {
    if (!selectedId || archiving) return;
    setArchiving(true);
    setArchiveError(null);
    try {
      await archiveDecision(selectedId, reason);
      setSavedMessage("Decision archived.");
      void loadDetail(selectedId);
      void loadList();
      void loadAudit(selectedId, true);
    } catch (caught) {
      setArchiveError(neutralMessage(caught));
    } finally {
      setArchiving(false);
    }
  }

  async function handleUnarchive() {
    if (!selectedId || archiving) return;
    setArchiving(true);
    setArchiveError(null);
    try {
      await unarchiveDecision(selectedId);
      setSavedMessage("Decision unarchived.");
      void loadDetail(selectedId);
      void loadList();
      void loadAudit(selectedId, true);
    } catch (caught) {
      setArchiveError(neutralMessage(caught));
    } finally {
      setArchiving(false);
    }
  }

  /* ---- Reload ---- */
  function requestReload() {
    if (draftDirty) {
      setReloadConfirmation(true);
    } else {
      void loadList();
      if (selectedId) {
        void loadDetail(selectedId);
        void loadCorrections(selectedId);
        void loadAudit(selectedId);
      }
    }
  }

  function forceReload() {
    setReloadConfirmation(false);
    setDraftDirty(false);
    void loadList();
    if (selectedId) {
      void loadDetail(selectedId);
      void loadCorrections(selectedId);
      void loadAudit(selectedId);
    }
  }

  /* ---- Draft saved callback ---- */
  function acceptDraft(saved: DraftDetail, message: string) {
    // Update detail's draft in place
    if (detail) {
      setDetail({ ...detail, draft: saved });
    }
    setSavedMessage(message);
    if (selectedId) void loadAudit(selectedId, true);
  }

  async function handleDiscardDraft() {
    if (!selectedId || !draft) return;
    try {
      await discardDraft(selectedId, draft.revision);
      setDetail(null);
      setDraftDirty(false);
      setSavedMessage("Draft discarded.");
      void loadList();
    } catch (caught) {
      setDetailError(neutralMessage(caught));
    }
  }

  /* ---- Correction saved callback ---- */
  function acceptCorrection(correction: Correction) {
    setCorrections((prev) => [correction, ...prev]);
    setSavedMessage(`Correction #${correction.correction_number} appended.`);
    if (selectedId) {
      void loadDetail(selectedId);
      void loadAudit(selectedId, true);
    }
  }

  /* ---- Filter change ---- */
  function handleFilterChange(status: DecisionStatus | "active") {
    setStatusFilter(status);
    // listLoad will be triggered by the useEffect below
  }

  /* ---- Initial load ---- */
  useEffect(() => {
    const timer = setTimeout(() => void loadList(), 0);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ---- Cleanup on unmount ---- */
  useEffect(() => {
    return () => {
      listController.current?.abort();
      detailController.current?.abort();
      correctionController.current?.abort();
      auditController.current?.abort();
    };
  }, []);

  /* ---- Derived helpers ---- */
  const isConfirmedOrArchived = detail?.status === "confirmed" || detail?.status === "archived";
  const isDraft = detail?.status === "draft";
  const draft = detail?.draft ?? null;

  return (
    <main className="policy-shell">
      <header className="page-header">
        <p className="eyebrow">CompoundOS · Sprint 002 Slice 3C</p>
        <h1>Decision Journal</h1>
        <p className="lede">
          Record your Decisions explicitly. Draft, confirm, correct — nothing is automatic.
        </p>
      </header>

      {/* Local-only notice */}
      <aside className="notice notice-warning" aria-label="Local-only limitation">
        <strong>Local-only, non-production limitation</strong>
        <p>{LOCAL_ONLY_NOTICE}</p>
      </aside>

      {/* Provisional non-advisory notices */}
      <aside className="notice" aria-label="Non-advisory notice — own">
        <strong>Your Decisions, your record</strong>
        <p>{NOTICE_OWN}</p>
      </aside>
      <aside className="notice" aria-label="Non-advisory notice — confirm">
        <strong>Confirmation is permanent</strong>
        <p>{NOTICE_CONFIRM}</p>
      </aside>
      <aside className="notice" aria-label="Non-advisory notice — archive">
        <strong>Corrections always possible</strong>
        <p>{NOTICE_ARCHIVE}</p>
      </aside>

      {/* Saved message */}
      {savedMessage ? (
        <p className="success-message" role="status">{savedMessage}</p>
      ) : null}

      {/* Reload confirmation */}
      {reloadConfirmation ? (
        <section className="confirmation-panel" role="alertdialog" aria-label="Discard local changes and reload">
          <p><strong>Reloading replaces unsaved edits.</strong></p>
          <p>Local Draft changes will be lost.</p>
          <div className="actions">
            <button onClick={forceReload} type="button">Discard local changes and reload</button>
            <button onClick={() => setReloadConfirmation(false)} type="button">Keep editing</button>
          </div>
        </section>
      ) : null}

      {/* Decision list panel — always visible */}
      <DecisionListPanel
        createError={createError}
        createTitle={createTitle}
        creating={creating}
        decisions={list}
        error={listError}
        loading={listLoading}
        onCreate={handleCreate}
        onCreateTitleChange={setCreateTitle}
        onFilterChange={handleFilterChange}
        onRetry={() => void loadList()}
        onSelect={selectDecision}
        selectedId={selectedId}
        statusFilter={statusFilter}
        total={listTotal}
      />

      {/* Workspace status bar when a decision is selected */}
      {selectedId && detail ? (
        <section className="workspace-status" aria-label="Decision status">
          <span>{STATUS_LABELS[detail.status]}</span>
          {draft ? <strong>Server revision {draft.revision}</strong> : null}
          <button onClick={requestReload} type="button">Reload workspace</button>
        </section>
      ) : null}

      {/* Detail loading */}
      {selectedId && detailLoading ? (
        <p role="status">Loading Decision detail…</p>
      ) : null}

      {/* Detail error */}
      {selectedId && detailError ? (
        <div className="error-panel" role="alert">
          <p>{detailError}</p>
          <button onClick={() => selectedId && loadDetail(selectedId)} type="button">
            Retry loading detail
          </button>
        </div>
      ) : null}

      {/* Draft editor — only when status is draft and draft exists */}
      {selectedId && detail && isDraft && draft ? (
        <DraftEditor
          draft={draft}
          key={`draft-${draft.decision_id}-${draft.revision}`}
          onDirtyChange={setDraftDirty}
          onDiscard={handleDiscardDraft}
          onReload={requestReload}
          onSaved={acceptDraft}
        />
      ) : null}

      {/* Confirm review — only when status is draft and draft exists */}
      {selectedId && detail && isDraft && draft ? (
        <ConfirmReview
          decisionId={selectedId}
          dirty={draftDirty}
          draft={draft}
          onConfirmed={() => {
            setDraftDirty(false);
            void loadDetail(selectedId);
            void loadAudit(selectedId, true);
            setSavedMessage("Decision confirmed.");
          }}
          onReload={requestReload}
        />
      ) : null}

      {/* Decision detail view — for confirmed or archived */}
      {selectedId && detail && isConfirmedOrArchived ? (
        <DecisionDetailView
          archiveError={archiveError}
          archiving={archiving}
          detail={detail}
          onArchive={handleArchive}
          onUnarchive={handleUnarchive}
          key={`detail-${detail.id}-${detail.status}`}
        />
      ) : null}

      {/* Correction editor — for confirmed or archived */}
      {selectedId && detail && isConfirmedOrArchived ? (
        <CorrectionEditor
          decisionId={selectedId}
          key={`correction-editor-${selectedId}`}
          onSaved={acceptCorrection}
        />
      ) : null}

      {/* Correction history */}
      {selectedId && detail && isConfirmedOrArchived ? (
        <CorrectionHistory
          error={correctionsError}
          items={corrections}
          loading={correctionsLoading}
          onRetry={() => selectedId && loadCorrections(selectedId)}
        />
      ) : null}

      {/* Audit timeline */}
      {selectedId && detail ? (
        <AuditTimeline
          error={auditError}
          events={auditEvents}
          loading={auditLoading}
          onRetry={() => selectedId && loadAudit(selectedId)}
        />
      ) : null}
    </main>
  );
}
