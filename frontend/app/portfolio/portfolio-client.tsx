"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  confirmDraft,
  createPortfolioDraft,
  discardDraft,
  estimateTotal,
  formatDecimal,
  getCurrentPortfolio,
  getPortfolioAudit,
  getSnapshotDetail,
  getSnapshotHistory,
  hasCurrentHousehold,
  Holding,
  HoldingInput,
  isCash,
  isFutureValuationDate,
  isValidQuantity,
  isValidUnitPrice,
  PortfolioApiError,
  PortfolioAuditEvent,
  PortfolioCreateData,
  PortfolioDraft,
  PortfolioNetworkError,
  PortfolioSnapshotDetail,
  PortfolioSnapshotSummary,
  replaceDraftHoldings,
  updateDraftMetadata,
} from "../../lib/portfolio-api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LOCAL_ONLY_NOTICE =
  "CompoundOS runs locally. Your data stays on your machine.";
const NON_ADVISORY_NOTICE =
  "Portfolio snapshots are your own records. Nothing here is advice.";
const CASH_HINT =
  "Cash holdings use unit_price 1.00 — the quantity represents the cash amount.";
const PRIVATE_ASSET_HINT =
  "User-entered private asset valuation — no market price implied.";
const ZERO_HOLDINGS_WARNING =
  "0 holdings — no assets recorded. You may still confirm an empty snapshot if you intend to record a zero-asset state.";

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function neutralMessage(error: unknown): string {
  if (error instanceof PortfolioNetworkError) return error.message;
  return error instanceof PortfolioApiError
    ? error.message
    : "The Portfolio request could not be completed.";
}

function holdingInputFromHolding(h: Holding): HoldingInput {
  return {
    asset_name: h.asset_name,
    asset_category: h.asset_category,
    quantity: formatDecimal(h.quantity),
    unit_price: formatDecimal(h.unit_price),
    valuation_date: h.valuation_date,
    notes: h.notes ?? "",
  };
}

function holdingsEqual(saved: Holding[], edited: HoldingInput[]): boolean {
  if (saved.length !== edited.length) return false;
  return saved.every((item, i) => {
    const e = edited[i];
    return (
      item.asset_name === e.asset_name &&
      item.asset_category === e.asset_category &&
      formatDecimal(item.quantity) === e.quantity &&
      formatDecimal(item.unit_price) === e.unit_price &&
      item.valuation_date === e.valuation_date &&
      (item.notes ?? "") === (e.notes ?? "")
    );
  });
}

function blankHolding(): HoldingInput {
  return {
    asset_name: "",
    asset_category: "",
    quantity: "",
    unit_price: "",
    valuation_date: todayISO(),
    notes: "",
  };
}

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

function ConflictPanel({ message, onReload }: { message: string; onReload: () => void }) {
  return (
    <div className="error-panel" role="alert">
      <p>{message}</p>
      <button onClick={onReload} type="button">Reload server data</button>
    </div>
  );
}

function SnapshotSummaryRow({
  snapshot,
  onSelect,
}: {
  snapshot: PortfolioSnapshotSummary;
  onSelect: (id: string) => void;
}) {
  return (
    <tr>
      <td>v{snapshot.version_number}</td>
      <td>{snapshot.valuation_date}</td>
      <td>{snapshot.holding_count ?? 0} holdings</td>
      <td>{snapshot.status}</td>
      <td>
        <button
          onClick={() => onSelect(snapshot.id)}
          type="button"
          aria-label={`View snapshot version ${snapshot.version_number}`}
        >
          View
        </button>
      </td>
    </tr>
  );
}

function HoldingRow({
  holding,
  index,
  totalHoldings,
  onUpdate,
  onRemove,
  onMoveUp,
  onMoveDown,
}: {
  holding: HoldingInput;
  index: number;
  totalHoldings: number;
  onUpdate: (index: number, field: keyof HoldingInput, value: string) => void;
  onRemove: (index: number) => void;
  onMoveUp: (index: number) => void;
  onMoveDown: (index: number) => void;
}) {
  const itemLabel = holding.asset_name || `Holding ${index + 1}`;
  const qtyError = holding.quantity && !isValidQuantity(holding.quantity)
    ? "Quantity must be > 0, up to 8 decimal places"
    : "";
  const priceError = holding.unit_price && !isValidUnitPrice(holding.unit_price)
    ? "Price must be >= 0, up to 4 decimal places"
    : "";
  const cashPriceError =
    isCash(holding.asset_category) && holding.unit_price && holding.unit_price !== "1"
    ? 'Cash holdings must have unit_price 1.00'
    : "";
  const dateError = holding.valuation_date && isFutureValuationDate(holding.valuation_date)
    ? "Date must not be in the future"
    : "";

  const estimated = estimateTotal(holding.quantity, holding.unit_price);

  return (
    <tr>
      <td>
        <button
          type="button"
          onClick={() => onMoveUp(index)}
          disabled={index === 0}
          aria-label={`Move ${itemLabel} up`}
        >
          ↑
        </button>
        <button
          type="button"
          onClick={() => onMoveDown(index)}
          disabled={index === totalHoldings - 1}
          aria-label={`Move ${itemLabel} down`}
        >
          ↓
        </button>
      </td>
      <td>
        <input
          type="text"
          value={holding.asset_name}
          onChange={(e) => onUpdate(index, "asset_name", e.target.value)}
          maxLength={500}
          required
          aria-label={`Asset name for ${itemLabel}`}
        />
      </td>
      <td>
        <input
          type="text"
          value={holding.asset_category}
          onChange={(e) => onUpdate(index, "asset_category", e.target.value)}
          maxLength={200}
          required
          aria-label={`Asset category for ${itemLabel}`}
        />
      </td>
      <td>
        <input
          type="text"
          value={holding.quantity}
          onChange={(e) => onUpdate(index, "quantity", e.target.value)}
          required
          aria-label={`Quantity for ${itemLabel}`}
          aria-invalid={!!qtyError ? "true" : undefined}
        />
        {qtyError && <span className="field-error" role="alert">{qtyError}</span>}
      </td>
      <td>
        <input
          type="text"
          value={holding.unit_price}
          onChange={(e) => onUpdate(index, "unit_price", e.target.value)}
          required
          aria-label={`Unit price for ${itemLabel}`}
          aria-invalid={!!priceError || !!cashPriceError ? "true" : undefined}
        />
        {(priceError || cashPriceError) && (
          <span className="field-error" role="alert">{priceError || cashPriceError}</span>
        )}
      </td>
      <td>
        <input
          type="date"
          value={holding.valuation_date}
          onChange={(e) => onUpdate(index, "valuation_date", e.target.value)}
          max={todayISO()}
          required
          aria-label={`Valuation date for ${itemLabel}`}
          aria-invalid={!!dateError ? "true" : undefined}
        />
        {dateError && <span className="field-error" role="alert">{dateError}</span>}
      </td>
      <td>
        <input
          type="text"
          value={holding.notes ?? ""}
          onChange={(e) => onUpdate(index, "notes", e.target.value)}
          maxLength={8000}
          aria-label={`Notes for ${itemLabel}`}
        />
      </td>
      <td className="mono-cell">
        {estimated ? (
          <span title="Non-authoritative client-side estimate — server total_value is authoritative">
            ~{estimated}
          </span>
        ) : (
          <span>—</span>
        )}
      </td>
      <td>
        <button
          type="button"
          onClick={() => onRemove(index)}
          aria-label={`Remove ${itemLabel}`}
        >
          ✕
        </button>
      </td>
    </tr>
  );
}

function ReadonlyHoldingRow({ holding }: { holding: Holding }) {
  return (
    <tr>
      <td>{holding.asset_name}</td>
      <td>{holding.asset_category}</td>
      <td>{formatDecimal(holding.quantity)}</td>
      <td>{formatDecimal(holding.unit_price)}</td>
      <td>{holding.valuation_date}</td>
      <td className="mono-cell">{formatDecimal(holding.total_value)}</td>
      <td>{holding.notes || "—"}</td>
    </tr>
  );
}

function HoldingsEditor({
  holdings,
  saved,
  onHoldingsChange,
  onSave,
  saving,
  saveError,
  canSave,
}: {
  holdings: HoldingInput[];
  saved: Holding[] | null;
  onHoldingsChange: (h: HoldingInput[]) => void;
  onSave: () => void;
  saving: boolean;
  saveError: string | null;
  canSave: boolean;
}) {
  const dirty = saved ? !holdingsEqual(saved, holdings) : holdings.length > 0;
  const hasCash = holdings.some((h) => isCash(h.asset_category));

  const updateField = (index: number, field: keyof HoldingInput, value: string) => {
    const next = [...holdings];
    next[index] = { ...next[index], [field]: value };
    onHoldingsChange(next);
  };

  const addRow = () => {
    onHoldingsChange([...holdings, blankHolding()]);
  };

  const removeRow = (index: number) => {
    onHoldingsChange(holdings.filter((_, i) => i !== index));
  };

  const moveRow = (from: number, to: number) => {
    if (to < 0 || to >= holdings.length) return;
    const next = [...holdings];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    onHoldingsChange(next);
  };

  const zeroHoldings = holdings.length === 0;

  return (
    <div className="panel">
      <div className="section-heading section-heading-row">
        <h2 id="holdings-heading">Draft Holdings</h2>
        <div>
          {dirty && (
            <span className="dirty-marker">Unsaved changes</span>
          )}
          <button
            type="button"
            onClick={onSave}
            disabled={!canSave || !dirty || saving}
            aria-label="Save holdings"
          >
            {saving ? "Saving…" : "Save holdings"}
          </button>
        </div>
      </div>

      {hasCash && (
        <div className="notice" role="note">
          <p>{CASH_HINT}</p>
        </div>
      )}

      {holdings.some((h) => h.asset_category.toLowerCase() === "private") && (
        <div className="notice" role="note">
          <p>{PRIVATE_ASSET_HINT}</p>
        </div>
      )}

      {saveError && (
        <div className="error-panel" role="alert">
          <p>{saveError}</p>
        </div>
      )}

      {zeroHoldings && (
        <div className="notice notice-warning" role="alert">
          <p>{ZERO_HOLDINGS_WARNING}</p>
        </div>
      )}

      <table aria-labelledby="holdings-heading">
        <thead>
          <tr>
            <th>Order</th>
            <th>Asset name</th>
            <th>Category</th>
            <th>Quantity</th>
            <th>Unit price</th>
            <th>Valuation date</th>
            <th>Notes</th>
            <th>Est. total</th>
            <th>Remove</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h, i) => (
            <HoldingRow
              key={i}
              holding={h}
              index={i}
              totalHoldings={holdings.length}
              onUpdate={updateField}
              onRemove={removeRow}
              onMoveUp={(idx) => moveRow(idx, idx - 1)}
              onMoveDown={(idx) => moveRow(idx, idx + 1)}
            />
          ))}
        </tbody>
      </table>

      <button
        type="button"
        onClick={addRow}
        aria-label="Add holding row"
        style={{ marginTop: "0.5rem" }}
      >
        + Add holding
      </button>
    </div>
  );
}

function SnapshotView({ snapshot }: { snapshot: PortfolioSnapshotDetail }) {
  return (
    <div className="panel">
      <div className="section-heading">
        <h2>Snapshot v{snapshot.version_number} — {snapshot.valuation_date}</h2>
      </div>
      <p>
        Status: {snapshot.status}
        {snapshot.confirmed_at && ` · Confirmed ${new Date(snapshot.confirmed_at).toLocaleString()}`}
        {snapshot.holding_count !== null && ` · ${snapshot.holding_count} holdings`}
      </p>
      {snapshot.notes && <p>{snapshot.notes}</p>}
      {snapshot.holdings.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Asset name</th>
              <th>Category</th>
              <th>Quantity</th>
              <th>Unit price</th>
              <th>Valuation date</th>
              <th>Total (authoritative)</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {snapshot.holdings.map((h) => (
              <ReadonlyHoldingRow key={h.id} holding={h} />
            ))}
          </tbody>
        </table>
      ) : (
        <p className="notice notice-warning" role="alert">
          {ZERO_HOLDINGS_WARNING}
        </p>
      )}
    </div>
  );
}

function ConfirmReview({
  draft,
  onConfirm,
  onCancel,
  confirming,
  zeroHoldings,
}: {
  draft: PortfolioDraft;
  onConfirm: () => void;
  onCancel: () => void;
  confirming: boolean;
  zeroHoldings: boolean;
}) {
  return (
    <div className="panel">
      <div className="section-heading">
        <h2>Confirm Snapshot</h2>
      </div>
      <p>
        Review your portfolio snapshot before confirming. Once confirmed, the snapshot
        becomes an immutable record.
      </p>
      {draft.valuation_date && (
        <p>Valuation date: {draft.valuation_date}</p>
      )}
      {draft.notes && <p>Notes: {draft.notes}</p>}
      <p>Revision: {draft.expected_revision}</p>
      <p>Holdings: {draft.holdings.length}</p>

      {zeroHoldings && (
        <div className="notice notice-warning" role="alert">
          <p>{ZERO_HOLDINGS_WARNING}</p>
        </div>
      )}

      {draft.holdings.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Asset name</th>
              <th>Category</th>
              <th>Quantity</th>
              <th>Unit price</th>
              <th>Total (authoritative)</th>
              <th>Valuation date</th>
            </tr>
          </thead>
          <tbody>
            {draft.holdings.map((h) => (
              <tr key={h.id}>
                <td>{h.asset_name}</td>
                <td>{h.asset_category}</td>
                <td>{formatDecimal(h.quantity)}</td>
                <td>{formatDecimal(h.unit_price)}</td>
                <td className="mono-cell">{formatDecimal(h.total_value)}</td>
                <td>{h.valuation_date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem" }}>
        <button
          type="button"
          onClick={onConfirm}
          disabled={confirming}
          className="primary-button"
          aria-label="Confirm snapshot"
        >
          {confirming ? "Confirming…" : "Confirm snapshot"}
        </button>
        <button type="button" onClick={onCancel} disabled={confirming}>
          Cancel
        </button>
      </div>
    </div>
  );
}

function SnapshotHistoryPanel({
  history,
  selectedSnapshot,
  loadingDetail,
  onSelect,
  onLoadMore,
  loading,
  error,
  onRetry,
}: {
  history: PortfolioSnapshotSummary[];
  selectedSnapshot: PortfolioSnapshotDetail | null;
  loadingDetail: boolean;
  onSelect: (id: string) => void;
  onLoadMore: () => void;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <div className="panel">
      <div className="section-heading section-heading-row">
        <h2>Snapshot History</h2>
      </div>

      {error ? (
        <div className="error-panel" role="alert">
          <p>{error}</p>
          <button type="button" onClick={onRetry} aria-label="Retry snapshot history">
            Retry
          </button>
        </div>
      ) : history.length === 0 && !loading ? (
        <p>No snapshots yet.</p>
      ) : (
        <>
          <table>
            <thead>
              <tr>
                <th>Version</th>
                <th>Date</th>
                <th>Holdings</th>
                <th>Status</th>
                <th>View</th>
              </tr>
            </thead>
            <tbody>
              {history.map((s) => (
                <SnapshotSummaryRow key={s.id} snapshot={s} onSelect={onSelect} />
              ))}
            </tbody>
          </table>
          <button
            type="button"
            onClick={onLoadMore}
            disabled={loading}
            style={{ marginTop: "0.5rem" }}
          >
            {loading ? "Loading…" : "Load more"}
          </button>
        </>
      )}

      {loadingDetail && <p>Loading snapshot detail…</p>}
      {selectedSnapshot && <SnapshotView snapshot={selectedSnapshot} />}
    </div>
  );
}

function AuditPanel({
  events,
  loading,
  error,
  onRetry,
  onLoadMore,
}: {
  events: PortfolioAuditEvent[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onLoadMore: () => void;
}) {
  return (
    <div className="panel">
      <div className="section-heading section-heading-row">
        <h2>Audit Timeline</h2>
      </div>

      {error ? (
        <div className="error-panel" role="alert">
          <p>{error}</p>
          <button type="button" onClick={onRetry} aria-label="Retry audit timeline">
            Retry
          </button>
        </div>
      ) : events.length === 0 && !loading ? (
        <p>No audit events recorded.</p>
      ) : (
        <>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Action</th>
                <th>Occurred</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <td className="mono-cell">{e.sequence_number}</td>
                  <td>{e.action}</td>
                  <td>{new Date(e.occurred_at).toLocaleString()}</td>
                  <td>
                    {Object.keys(e.metadata).length > 0
                      ? JSON.stringify(e.metadata)
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button
            type="button"
            onClick={onLoadMore}
            disabled={loading}
            style={{ marginTop: "0.5rem" }}
          >
            {loading ? "Loading…" : "Load more"}
          </button>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Client Component
// ---------------------------------------------------------------------------

type ViewState =
  | { kind: "loading" }
  | { kind: "no-household" }
  | { kind: "error"; message: string }
  | { kind: "no-portfolio" }
  | { kind: "draft-editor"; draft: PortfolioDraft; savedHoldings: Holding[] }
  | { kind: "confirm-review"; draft: PortfolioDraft; zeroHoldings: boolean }
  | { kind: "current-snapshot"; snapshot: PortfolioSnapshotDetail }
  | { kind: "draft-and-snapshot"; draft: PortfolioDraft; snapshot: PortfolioSnapshotDetail; savedHoldings: Holding[] };

export function PortfolioClient() {
  // Core state
  const [view, setView] = useState<ViewState>({ kind: "loading" });
  const [conflictMessage, setConflictMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [holdsDirty, setHoldsDirty] = useState(false);

  // Local holding edits
  const [localHoldings, setLocalHoldings] = useState<HoldingInput[]>([]);

  // Draft metadata edits
  const [draftValuationDate, setDraftValuationDate] = useState<string>("");
  const [draftNotes, setDraftNotes] = useState<string>("");
  const [metaDirty, setMetaDirty] = useState(false);
  const [metaSaving, setMetaSaving] = useState(false);

  // Auxiliary state
  const [history, setHistory] = useState<PortfolioSnapshotSummary[]>([]);
  const [historyCursor, setHistoryCursor] = useState<number | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [selectedSnapshot, setSelectedSnapshot] = useState<PortfolioSnapshotDetail | null>(null);
  const [snapshotDetailLoading, setSnapshotDetailLoading] = useState(false);

  const [auditEvents, setAuditEvents] = useState<PortfolioAuditEvent[]>([]);
  const [auditCursor, setAuditCursor] = useState<number | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  const [discarding, setDiscarding] = useState(false);
  const [confirmReload, setConfirmReload] = useState(false);

  // Generation guards
  const genRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const histAbortRef = useRef<AbortController | null>(null);
  const auditAbortRef = useRef<AbortController | null>(null);
  const histGenRef = useRef(0);
  const auditGenRef = useRef(0);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const nextGen = useCallback(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    genRef.current += 1;
    return { signal: controller.signal, generation: genRef.current };
  }, []);

  // ---------------------------------------------------------------------------
  // Core data loading
  // ---------------------------------------------------------------------------

  const loadCore = useCallback(async () => {
    setConflictMessage(null);
    const { signal, generation } = nextGen();
    setView({ kind: "loading" });

    try {
      const hasHousehold = await hasCurrentHousehold(signal);
      if (generation !== genRef.current) return;
      if (!hasHousehold) {
        setView({ kind: "no-household" });
        return;
      }

      const portfolioState = await getCurrentPortfolio(signal);
      if (generation !== genRef.current) return;

      if (!portfolioState) {
        setView({ kind: "no-portfolio" });
        return;
      }

      const { draft, latest_snapshot } = portfolioState;

      if (draft && latest_snapshot) {
        setView({
          kind: "draft-and-snapshot",
          draft,
          snapshot: latest_snapshot,
          savedHoldings: draft.holdings,
        });
        setLocalHoldings(draft.holdings.map(holdingInputFromHolding));
        setDraftValuationDate(draft.valuation_date ?? "");
        setDraftNotes(draft.notes ?? "");
        setMetaDirty(false);
        setHoldsDirty(false);
      } else if (draft) {
        setView({
          kind: "draft-editor",
          draft,
          savedHoldings: draft.holdings,
        });
        setLocalHoldings(draft.holdings.map(holdingInputFromHolding));
        setDraftValuationDate(draft.valuation_date ?? "");
        setDraftNotes(draft.notes ?? "");
        setMetaDirty(false);
        setHoldsDirty(false);
      } else if (latest_snapshot) {
        setView({ kind: "current-snapshot", snapshot: latest_snapshot });
      } else {
        setView({ kind: "no-portfolio" });
      }
    } catch (error) {
      if (isAbort(error)) return;
      if (generation !== genRef.current) return;
      setView({ kind: "error", message: neutralMessage(error) });
    }
  }, [nextGen]);

  // Load auxiliary (history + audit) independently
  const loadHistory = useCallback(async () => {
    histAbortRef.current?.abort();
    const controller = new AbortController();
    histAbortRef.current = controller;
    histGenRef.current += 1;
    const generation = histGenRef.current;
    const signal = controller.signal;
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const result = await getSnapshotHistory(undefined, signal);
      if (generation !== histGenRef.current) return;
      setHistory(result.items);
      setHistoryCursor(result.next_before_version_number);
    } catch (error) {
      if (isAbort(error)) return;
      if (generation !== histGenRef.current) return;
      setHistoryError(neutralMessage(error));
    } finally {
      if (generation === histGenRef.current) setHistoryLoading(false);
    }
  }, []);

  const loadAudit = useCallback(async () => {
    auditAbortRef.current?.abort();
    const controller = new AbortController();
    auditAbortRef.current = controller;
    auditGenRef.current += 1;
    const generation = auditGenRef.current;
    const signal = controller.signal;
    setAuditLoading(true);
    setAuditError(null);
    try {
      const events = await getPortfolioAudit(undefined, signal);
      if (generation !== auditGenRef.current) return;
      setAuditEvents(events);
      setAuditCursor(events.length >= 50 ? events[events.length - 1].sequence_number : null);
    } catch (error) {
      if (isAbort(error)) return;
      if (generation !== auditGenRef.current) return;
      setAuditError(neutralMessage(error));
    } finally {
      if (generation === auditGenRef.current) setAuditLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadCore().then(() => {
      loadHistory();
      loadAudit();
    });
  }, [loadCore, loadHistory, loadAudit]);

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  const handleCreate = useCallback(async () => {
    setConflictMessage(null);
    try {
      const result: PortfolioCreateData = await createPortfolioDraft();
      const { draft } = result;
      setView({
        kind: "draft-editor",
        draft,
        savedHoldings: draft.holdings,
      });
      setLocalHoldings(draft.holdings.map(holdingInputFromHolding));
      setDraftValuationDate(draft.valuation_date ?? "");
      setDraftNotes(draft.notes ?? "");
      setMetaDirty(false);
      setHoldsDirty(false);
      loadHistory();
      loadAudit();
    } catch (error) {
      if (error instanceof PortfolioApiError && error.status === 409) {
        setConflictMessage(error.message);
        loadCore();
        return;
      }
      setSaveError(neutralMessage(error));
    }
  }, [loadCore, loadHistory, loadAudit]);

  const handleSaveHoldings = useCallback(async () => {
    if (view.kind !== "draft-editor" && view.kind !== "draft-and-snapshot") return;

    const draft = view.draft;
    const saved = view.kind === "draft-and-snapshot" ? view.savedHoldings : view.savedHoldings;

    if (holdingsEqual(saved, localHoldings)) {
      setSaveError("No holdings changes to save.");
      return;
    }

    setConflictMessage(null);
    setSaveError(null);
    setSaving(true);

    try {
      const items: HoldingInput[] = localHoldings.map((h, i) => ({
        ...h,
        sort_order: i,
      }));
      const updated = await replaceDraftHoldings(draft.expected_revision, items);
      const nextView =
        view.kind === "draft-and-snapshot"
          ? { kind: "draft-and-snapshot" as const, draft: updated, snapshot: view.snapshot, savedHoldings: updated.holdings }
          : { kind: "draft-editor" as const, draft: updated, savedHoldings: updated.holdings };
      setView(nextView);
      setLocalHoldings(updated.holdings.map(holdingInputFromHolding));
      setHoldsDirty(false);
      setSaveError(null);
      loadHistory();
      loadAudit();
    } catch (error) {
      if (error instanceof PortfolioApiError && error.status === 409) {
        setConflictMessage(error.message);
      } else {
        setSaveError(neutralMessage(error));
      }
    } finally {
      setSaving(false);
    }
  }, [view, localHoldings, loadHistory, loadAudit]);

  const handleUpdateMetadata = useCallback(async () => {
    if (view.kind !== "draft-editor" && view.kind !== "draft-and-snapshot") return;
    if (!metaDirty) return;

    setMetaSaving(true);
    setConflictMessage(null);

    try {
      const draft = view.draft;
      const fields: { valuation_date?: string | null; notes?: string | null } = {};
      const savedValDate = draft.valuation_date ?? "";
      const savedNotes = draft.notes ?? "";

      if (draftValuationDate !== savedValDate) {
        fields.valuation_date = draftValuationDate || null;
      }
      if (draftNotes !== savedNotes) {
        fields.notes = draftNotes || null;
      }

      if (Object.keys(fields).length === 0) {
        setMetaDirty(false);
        setMetaSaving(false);
        return;
      }

      const updated = await updateDraftMetadata(draft.expected_revision, fields);
      const nextView =
        view.kind === "draft-and-snapshot"
          ? { kind: "draft-and-snapshot" as const, draft: updated, snapshot: view.snapshot, savedHoldings: view.savedHoldings }
          : { kind: "draft-editor" as const, draft: updated, savedHoldings: view.savedHoldings };
      setView(nextView);
      setDraftValuationDate(updated.valuation_date ?? "");
      setDraftNotes(updated.notes ?? "");
      setMetaDirty(false);
    } catch (error) {
      if (error instanceof PortfolioApiError && error.status === 409) {
        setConflictMessage(error.message);
      } else {
        setSaveError(neutralMessage(error));
      }
    } finally {
      setMetaSaving(false);
    }
  }, [view, metaDirty, draftValuationDate, draftNotes]);

  const handleEnterConfirmReview = useCallback(() => {
    if (view.kind !== "draft-editor" && view.kind !== "draft-and-snapshot") return;
    const draft = view.draft;
    setView({ kind: "confirm-review", draft, zeroHoldings: draft.holdings.length === 0 });
  }, [view]);

  const handleConfirmExecute = useCallback(async () => {
    if (view.kind !== "confirm-review") return;
    const draft = view.draft;

    setConfirming(true);
    try {
      const snapshot = await confirmDraft(draft.expected_revision);
      setView({ kind: "current-snapshot", snapshot });
      setLocalHoldings([]);
      loadHistory();
      loadAudit();
    } catch (error) {
      if (error instanceof PortfolioApiError && error.status === 409) {
        setConflictMessage(error.message);
      } else {
        setSaveError(neutralMessage(error));
      }
    } finally {
      setConfirming(false);
    }
  }, [view, loadHistory, loadAudit]);

  const handleDiscard = useCallback(async () => {
    if (view.kind !== "draft-editor" && view.kind !== "draft-and-snapshot") return;

    const hasExistingSnapshot = view.kind === "draft-and-snapshot";
    const draft = view.draft;

    if (!hasExistingSnapshot) {
      // Confirm discard of entire portfolio identity
      if (!window.confirm("Discarding the draft will delete the entire portfolio. This cannot be undone. Continue?")) {
        return;
      }
    }

    setDiscarding(true);
    try {
      const result = await discardDraft(draft.expected_revision);
      if (result) {
        // Discard returned a snapshot (after-confirm discard)
        setView({ kind: "current-snapshot", snapshot: result });
      } else {
        // Identity deletion (never-confirmed discard) → reload
        loadCore();
        loadHistory();
        loadAudit();
      }
    } catch (error) {
      if (error instanceof PortfolioApiError && error.status === 409) {
        setConflictMessage(error.message);
      } else {
        setSaveError(neutralMessage(error));
      }
    } finally {
      setDiscarding(false);
    }
  }, [view, loadCore, loadHistory, loadAudit]);

  const handleReload = useCallback(() => {
    const hasLocalChanges = holdsDirty || metaDirty;
    if (hasLocalChanges) {
      setConfirmReload(true);
    } else {
      loadCore().then(() => {
        loadHistory();
        loadAudit();
      });
    }
  }, [holdsDirty, metaDirty, loadCore, loadHistory, loadAudit]);

  const handleConfirmReload = useCallback(async () => {
    setConfirmReload(false);
    try {
      await loadCore();
      setHoldsDirty(false);
      setMetaDirty(false);
      loadHistory();
      loadAudit();
    } catch {
      // Keep dirty state on failed reload
    }
  }, [loadCore, loadHistory, loadAudit]);

  const handleCancelReload = useCallback(() => {
    setConfirmReload(false);
  }, []);

  const handleLoadMoreHistory = useCallback(async () => {
    if (historyCursor === null) return;
    histAbortRef.current?.abort();
    const controller = new AbortController();
    histAbortRef.current = controller;
    histGenRef.current += 1;
    const generation = histGenRef.current;
    const signal = controller.signal;
    setHistoryLoading(true);
    try {
      const result = await getSnapshotHistory(historyCursor, signal);
      if (generation !== histGenRef.current) return;
      setHistory((prev) => [...prev, ...result.items]);
      setHistoryCursor(result.next_before_version_number);
    } catch (error) {
      if (isAbort(error)) return;
      if (generation !== histGenRef.current) return;
      setHistoryError(neutralMessage(error));
    } finally {
      if (generation === histGenRef.current) setHistoryLoading(false);
    }
  }, [historyCursor]);

  const handleLoadMoreAudit = useCallback(async () => {
    if (auditCursor === null) return;
    auditAbortRef.current?.abort();
    const controller = new AbortController();
    auditAbortRef.current = controller;
    auditGenRef.current += 1;
    const generation = auditGenRef.current;
    const signal = controller.signal;
    setAuditLoading(true);
    try {
      const events = await getPortfolioAudit(auditCursor, signal);
      if (generation !== auditGenRef.current) return;
      setAuditEvents((prev) => [...prev, ...events]);
      setAuditCursor(events.length >= 50 ? events[events.length - 1].sequence_number : null);
    } catch (error) {
      if (isAbort(error)) return;
      if (generation !== auditGenRef.current) return;
      setAuditError(neutralMessage(error));
    } finally {
      if (generation === auditGenRef.current) setAuditLoading(false);
    }
  }, [auditCursor]);

  const handleSelectSnapshot = useCallback(async (id: string) => {
    setSelectedSnapshot(null);
    setSnapshotDetailLoading(true);
    const { signal, generation } = nextGen();
    try {
      const detail = await getSnapshotDetail(id, signal);
      if (generation !== genRef.current) return;
      setSelectedSnapshot(detail);
    } catch (error) {
      if (isAbort(error)) return;
    } finally {
      if (generation === genRef.current) setSnapshotDetailLoading(false);
    }
  }, [nextGen]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="shell">
      {/* Notices */}
      <div className="notice" role="note">
        <p>{LOCAL_ONLY_NOTICE}</p>
      </div>
      <div className="notice" role="note">
        <p>{NON_ADVISORY_NOTICE}</p>
      </div>

      {/* Reload confirmation */}
      {confirmReload && (
        <div className="notice notice-warning" role="alert">
          <p>You have unsaved changes. Reloading will discard them.</p>
          <button type="button" onClick={handleConfirmReload}>
            Discard local changes and reload
          </button>
          <button type="button" onClick={handleCancelReload}>
            Keep editing
          </button>
        </div>
      )}

      {/* Global conflict */}
      {conflictMessage && (
        <ConflictPanel message={conflictMessage} onReload={handleReload} />
      )}

      {/* Loading */}
      {view.kind === "loading" && (
        <div role="status">
          <p>Loading Portfolio…</p>
        </div>
      )}

      {/* No Household */}
      {view.kind === "no-household" && (
        <div>
          <h1>Create the Household profile first</h1>
          <p>The Household profile is required before you can create a Portfolio.</p>
          <Link href="/household" className="primary-link">
            Open Household profile
          </Link>
        </div>
      )}

      {/* Error */}
      {view.kind === "error" && (
        <div className="error-panel" role="alert">
          <p>{view.message}</p>
          <button type="button" onClick={handleReload}>Retry</button>
        </div>
      )}

      {/* No Portfolio */}
      {view.kind === "no-portfolio" && (
        <div className="panel">
          <h1>Portfolio</h1>
          <p>Create your first portfolio snapshot.</p>
          <button
            type="button"
            onClick={handleCreate}
            className="primary-button"
            aria-label="Create portfolio draft"
          >
            Create portfolio draft
          </button>
        </div>
      )}

      {/* Draft Editor (standalone, no snapshot) */}
      {(view.kind === "draft-editor" || view.kind === "draft-and-snapshot") && (
        <>
          <div className="page-header">
            <p className="eyebrow">Portfolio</p>
            <h1>Portfolio draft</h1>
          </div>

          <div className="panel">
            <div className="section-heading">
              <h3>Draft Metadata</h3>
            </div>
            <div style={{ display: "grid", gap: "0.5rem", maxWidth: "30rem" }}>
              <label>
                Valuation date
                <input
                  type="date"
                  value={draftValuationDate}
                  onChange={(e) => {
                    setDraftValuationDate(e.target.value);
                    setMetaDirty(true);
                  }}
                  max={todayISO()}
                  aria-label="Draft valuation date"
                />
              </label>
              <label>
                Notes
                <textarea
                  value={draftNotes}
                  onChange={(e) => {
                    setDraftNotes(e.target.value);
                    setMetaDirty(true);
                  }}
                  maxLength={8000}
                  rows={3}
                  aria-label="Draft notes"
                />
              </label>
              {metaDirty && (
                <button
                  type="button"
                  onClick={handleUpdateMetadata}
                  disabled={metaSaving}
                  aria-label="Save metadata"
                >
                  {metaSaving ? "Saving…" : "Save metadata"}
                </button>
              )}
            </div>
          </div>

          <HoldingsEditor
            holdings={localHoldings}
            saved={
              view.kind === "draft-and-snapshot"
                ? view.savedHoldings
                : view.savedHoldings
            }
            onHoldingsChange={(h) => {
              setLocalHoldings(h);
              setHoldsDirty(true);
            }}
            onSave={handleSaveHoldings}
            saving={saving}
            saveError={saveError}
            canSave={true}
          />

          <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
            <button
              type="button"
              className="primary-button"
              onClick={handleEnterConfirmReview}
              disabled={holdsDirty || metaDirty || confirming}
              aria-label="Review and confirm"
            >
              Review and confirm
            </button>
            <button
              type="button"
              onClick={handleDiscard}
              disabled={discarding}
              aria-label="Discard draft"
            >
              {discarding ? "Discarding…" : "Discard draft"}
            </button>
            <button type="button" onClick={handleReload} aria-label="Reload workspace">
              Reload workspace
            </button>
          </div>
        </>
      )}

      {/* Confirm Review */}
      {view.kind === "confirm-review" && (
        <ConfirmReview
          draft={view.draft}
          onConfirm={handleConfirmExecute}
          onCancel={() => {
            setView({
              kind: "draft-editor",
              draft: view.draft,
              savedHoldings: view.draft.holdings,
            });
          }}
          confirming={confirming}
          zeroHoldings={view.zeroHoldings}
        />
      )}

      {/* Current Snapshot */}
      {view.kind === "current-snapshot" && (
        <>
          <div className="page-header">
            <p className="eyebrow">Portfolio</p>
            <h1>Current Snapshot v{view.snapshot.version_number}</h1>
          </div>
          <SnapshotView snapshot={view.snapshot} />
          <div style={{ marginTop: "1rem" }}>
            <button
              type="button"
              onClick={handleCreate}
              className="primary-button"
              aria-label="Create new draft"
            >
              Create new draft
            </button>
          </div>
        </>
      )}

      {/* Auxiliary panels: history and audit (always shown when portfolio exists) */}
      {(view.kind === "draft-editor" ||
        view.kind === "draft-and-snapshot" ||
        view.kind === "current-snapshot" ||
        view.kind === "confirm-review") && (
        <>
          <SnapshotHistoryPanel
            history={history}
            selectedSnapshot={selectedSnapshot}
            loadingDetail={snapshotDetailLoading}
            onSelect={handleSelectSnapshot}
            onLoadMore={handleLoadMoreHistory}
            loading={historyLoading}
            error={historyError}
            onRetry={loadHistory}
          />
          <AuditPanel
            events={auditEvents}
            loading={auditLoading}
            error={auditError}
            onRetry={loadAudit}
            onLoadMore={handleLoadMoreAudit}
          />
        </>
      )}
    </div>
  );
}
