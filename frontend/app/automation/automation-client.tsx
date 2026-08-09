"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  createSchedule,
  deleteSchedule,
  getSchedule,
  getRun,
  getWorkerStatus,
  listRuns,
  listSchedules,
  manualTrigger,
  updateSchedule,
  type JobType,
  type RunDetailResponse,
  type RunResponse,
  type ScheduleResponse,
  type WorkerStatusResponse,
  AutomationApiError,
  AutomationNetworkError,
} from "../../lib/automation-api";

// ═══════════════════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════════════════

const JOB_TYPES: JobType[] = ["guardian.evaluate_all", "guardian.evaluate_one", "backup.daily"];
const NON_ADVISORY =
  "Automation manages local task scheduling and run history. Nothing here is advice.";
const DEFAULT_TIMEZONE = "UTC";
const DEFAULT_TIME = "09:00:00";

// ═══════════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════════

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function statusLabel(s: string): string {
  switch (s) {
    case "pending": return "Pending";
    case "running": return "Running";
    case "completed": return "Completed";
    case "failed": return "Failed";
    case "aborted": return "Aborted";
    default: return s;
  }
}

type View =
  | "list"
  | "create"
  | "detail"
  | "edit"
  | "runs"
  | "run-detail"
  | "trigger";

// ═══════════════════════════════════════════════════════════════════════════
// Component
// ═══════════════════════════════════════════════════════════════════════════

export default function AutomationClient() {
  // ── Core state ──
  const [household, setHousehold] = useState<boolean | null>(null);
  const [schedules, setSchedules] = useState<ScheduleResponse[]>([]);
  const [selectedScheduleId, setSelectedScheduleId] = useState<string | null>(
    null,
  );
  const [view, setView] = useState<View>("list");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ── Form state ──
  const [formJobType, setFormJobType] = useState<JobType>(
    "guardian.evaluate_all",
  );
  const [formTime, setFormTime] = useState(DEFAULT_TIME);
  const [formTimezone, setFormTimezone] = useState(DEFAULT_TIMEZONE);
  const [formCheckId, setFormCheckId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // ── Dirty state ──
  const [_dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState(false);

  // ── Runs state ──
  const [runs, setRuns] = useState<RunResponse[]>([]);
  const [selectedRun, setSelectedRun] = useState<RunDetailResponse | null>(
    null,
  );
  const [runsLoading, setRunsLoading] = useState(false);

  // ── Worker ──
  const [workerStatus, setWorkerStatus] = useState<
    WorkerStatusResponse | null
  >(null);

  // ── Trigger ──
  const [triggerTargetId, setTriggerTargetId] = useState<string | null>(null);
  const [triggerLoading, setTriggerLoading] = useState(false);

  // ── Abort controllers ──
  const mainAbortRef = useRef<AbortController | null>(null);
  const scheduleAbortRef = useRef<AbortController | null>(null);
  const runAbortRef = useRef<AbortController | null>(null);
  const workerAbortRef = useRef<AbortController | null>(null);
  const mainGenRef = useRef(0);
  const scheduleGenRef = useRef(0);
  const runGenRef = useRef(0);
  const workerGenRef = useRef(0);

  function newGen(ref: { current: number }): number {
    ref.current += 1;
    return ref.current;
  }

  // ═════════════════════════════════════════════════════════════════════════
  // Data loading
  // ═════════════════════════════════════════════════════════════════════════

  const loadCore = useCallback(async () => {
    const gen = newGen(mainGenRef);
    const ac = new AbortController();
    mainAbortRef.current?.abort();
    mainAbortRef.current = ac;
    setLoading(true);
    setError(null);
    try {
      const data = await listSchedules(ac.signal);
      if (gen !== mainGenRef.current) return;
      setHousehold(true);
      setSchedules(data);
    } catch (err) {
      if (gen !== mainGenRef.current) return;
      if (err instanceof AutomationApiError && err.status === 404) {
        setHousehold(false);
      } else {
        setError(
          err instanceof AutomationNetworkError
            ? err.message
            : "Unable to load automation data.",
        );
      }
    } finally {
      if (gen === mainGenRef.current) setLoading(false);
    }
  }, []);

  const loadScheduleDetail = useCallback(async (id: string) => {
    const gen = newGen(scheduleGenRef);
    const ac = new AbortController();
    scheduleAbortRef.current?.abort();
    scheduleAbortRef.current = ac;
    try {
      const data = await getSchedule(id, ac.signal);
      if (gen !== scheduleGenRef.current) return;
      setSchedules((prev) => prev.map((s) => (s.id === id ? data : s)));
      setSelectedScheduleId(id);
      setView("detail");
      setDirty(false);
      setConflict(false);
      setFormError(null);
    } catch {
      // stale abort or 404 — ignore
    }
  }, []);

  const loadRuns = useCallback(async () => {
    const gen = newGen(runGenRef);
    const ac = new AbortController();
    runAbortRef.current?.abort();
    runAbortRef.current = ac;
    setRunsLoading(true);
    try {
      const data = await listRuns(undefined, ac.signal);
      if (gen !== runGenRef.current) return;
      setRuns(data);
    } catch {
      // ignore stale responses
    } finally {
      if (gen === runGenRef.current) setRunsLoading(false);
    }
  }, []);

  const loadRunDetail = useCallback(async (id: string) => {
    const gen = newGen(runGenRef);
    const ac = new AbortController();
    runAbortRef.current?.abort();
    runAbortRef.current = ac;
    try {
      const data = await getRun(id, ac.signal);
      if (gen !== runGenRef.current) return;
      setSelectedRun(data);
      setView("run-detail");
    } catch {
      // ignore
    }
  }, []);

  const loadWorker = useCallback(async () => {
    const gen = newGen(workerGenRef);
    const ac = new AbortController();
    workerAbortRef.current?.abort();
    workerAbortRef.current = ac;
    try {
      const data = await getWorkerStatus(ac.signal);
      if (gen !== workerGenRef.current) return;
      setWorkerStatus(data);
    } catch {
      if (gen !== workerGenRef.current) return;
      setWorkerStatus(null);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadCore();
     
    loadWorker();
    return () => {
      mainAbortRef.current?.abort();
      workerAbortRef.current?.abort();
    };
  }, [loadCore, loadWorker]);

  // ═════════════════════════════════════════════════════════════════════════
  // Mutations
  // ═════════════════════════════════════════════════════════════════════════

  const handleCreate = useCallback(async () => {
    if (saving) return;
    if (formJobType === "guardian.evaluate_one" && !formCheckId.trim()) {
      setFormError("Check ID is required for evaluate_one.");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      await createSchedule({
        job_type: formJobType,
        job_params:
          formJobType === "guardian.evaluate_one"
            ? { check_id: formCheckId.trim() }
            : {},
        execution_time: formTime,
        timezone: formTimezone,
      });
      setView("list");
      setDirty(false);
      setConflict(false);
      await loadCore();
    } catch (err) {
      if (err instanceof AutomationApiError) {
        if (err.status === 409) {
          setConflict(true);
          setFormError("Conflict — another change was made. Reload to see latest.");
        } else {
          setFormError(err.message);
        }
      } else {
        setFormError("Network error — check backend.");
      }
    } finally {
      setSaving(false);
    }
  }, [saving, formJobType, formCheckId, formTime, formTimezone, loadCore]);

  const handleUpdate = useCallback(async () => {
    if (!selectedScheduleId || saving) return;
    setSaving(true);
    setFormError(null);
    try {
      const data = await updateSchedule(selectedScheduleId, {
        execution_time: formTime,
        timezone: formTimezone,
      });
      setSchedules((prev) =>
        prev.map((s) => (s.id === selectedScheduleId ? data : s)),
      );
      setView("detail");
      setDirty(false);
    } catch (err) {
      if (err instanceof AutomationApiError && err.status === 409) {
        setConflict(true);
        setFormError("Conflict — reload to see latest.");
      } else {
        setFormError(
          err instanceof AutomationApiError ? err.message : "Network error.",
        );
      }
    } finally {
      setSaving(false);
    }
  }, [selectedScheduleId, saving, formTime, formTimezone]);

  const handleEnable = useCallback(
    async (id: string) => {
      try {
        const data = await updateSchedule(id, { enabled: true });
        setSchedules((prev) => prev.map((s) => (s.id === id ? data : s)));
        if (selectedScheduleId === id) {
          setSelectedScheduleId(null);
          setView("list");
        }
      } catch {
        // ignore
      }
    },
    [selectedScheduleId],
  );

  const handleDisable = useCallback(
    async (id: string) => {
      try {
        const data = await updateSchedule(id, { enabled: false });
        setSchedules((prev) => prev.map((s) => (s.id === id ? data : s)));
      } catch {
        // ignore
      }
    },
    [],
  );

  const handleDelete = useCallback(
    async (id: string) => {
      try {
        await deleteSchedule(id);
        setSchedules((prev) => prev.filter((s) => s.id !== id));
        if (selectedScheduleId === id) {
          setSelectedScheduleId(null);
          setView("list");
        }
      } catch {
        // ignore
      }
    },
    [selectedScheduleId],
  );

  const handleManualTrigger = useCallback(async () => {
    if (!triggerTargetId || triggerLoading) return;
    setTriggerLoading(true);
    try {
      await manualTrigger({ job_definition_id: triggerTargetId });
      setTriggerTargetId(null);
      setView("list");
      loadRuns();
    } catch (err) {
      setFormError(
        err instanceof AutomationApiError
          ? err.message
          : "Manual trigger failed.",
      );
    } finally {
      setTriggerLoading(false);
    }
  }, [triggerTargetId, triggerLoading, loadRuns]);

  // ═════════════════════════════════════════════════════════════════════════
  // Navigation
  // ═════════════════════════════════════════════════════════════════════════

  const startEdit = useCallback(
    (s: ScheduleResponse) => {
      setSelectedScheduleId(s.id);
      setFormTime(s.execution_time);
      setFormTimezone(s.timezone);
      setView("edit");
      setDirty(false);
      setConflict(false);
      setFormError(null);
    },
    [],
  );

  const openTrigger = useCallback(
    (s: ScheduleResponse) => {
      setTriggerTargetId(s.job_definition_id);
      setView("trigger");
    },
    [],
  );

  const reload = useCallback(() => {
    loadCore();
    setDirty(false);
    setConflict(false);
  }, [loadCore]);

  // ═════════════════════════════════════════════════════════════════════════
  // Render
  // ═════════════════════════════════════════════════════════════════════════

  void _dirty;
  if (loading) {
    return (
      <main className="shell" role="status" aria-label="Loading automation">
        <h1>Automation</h1>
        <p>Loading&hellip;</p>
      </main>
    );
  }

  if (household === false) {
    return (
      <main className="shell">
        <h1>Automation</h1>
        <p>No household profile found.</p>
        <Link href="/household">Create Household</Link>
      </main>
    );
  }

  const selected = schedules.find((s) => s.id === selectedScheduleId);

  // ── List view ──
  if (view === "list") {
    return (
      <main className="shell" role="region" aria-label="Automation workspace">
        <h1>Automation</h1>
        <p className="neutral">{NON_ADVISORY}</p>

        {error && (
          <div role="alert">
            <p>{error}</p>
            <button onClick={() => setError(null)} aria-label="Dismiss error">
              Dismiss
            </button>
          </div>
        )}

        {/* Worker status */}
        {workerStatus && (
          <section aria-label="Worker status">
            <h2>Worker</h2>
            <p>
              Active workers: {workerStatus.worker_count} | Active leases:{" "}
              {workerStatus.active_leases} | Running:{" "}
              {workerStatus.running_runs}
            </p>
          </section>
        )}

        {/* Schedules */}
        <section aria-label="Schedules">
          <h2>Schedules</h2>
          {schedules.length === 0 && (
            <p>No schedules configured. Create one below.</p>
          )}
          <ul role="list">
            {schedules.map((s) => (
              <li key={s.id}>
                <button
                  onClick={() => loadScheduleDetail(s.id)}
                  aria-label={`Schedule ${s.job_type} at ${s.execution_time}`}
                >
                  {s.job_type} · {s.execution_time} · {s.timezone}{" "}
                  {s.enabled ? "(enabled)" : "(disabled)"}
                </button>
              </li>
            ))}
          </ul>
          <button
            onClick={() => {
              setFormJobType("guardian.evaluate_all");
              setFormTime(DEFAULT_TIME);
              setFormTimezone(DEFAULT_TIMEZONE);
              setFormCheckId("");
              setFormError(null);
              setConflict(false);
              setDirty(false);
              setView("create");
            }}
            aria-label="Create schedule"
          >
            Create schedule
          </button>
        </section>

        {/* Runs */}
        <section aria-label="Run history">
          <h2>Runs</h2>
          <button onClick={loadRuns} aria-label="Load run history">
            {runsLoading ? "Loading runs…" : "Load run history"}
          </button>
          {runs.length > 0 && (
            <ul role="list">
              {runs.map((r) => (
                <li key={r.id}>
                  <button
                    onClick={() => loadRunDetail(r.id)}
                    aria-label={`Run ${r.id}`}
                  >
                    {statusLabel(r.status)} · {r.triggered_by} ·{" "}
                    {fmtTime(r.scheduled_at)}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <nav aria-label="CompoundOS workspaces">
          <Link href="/">← Home</Link>
        </nav>
      </main>
    );
  }

  // ── Create view ──
  if (view === "create") {
    return (
      <main className="shell" role="region" aria-label="Create schedule">
        <h1>Create Schedule</h1>

        {formError && (
          <div role="alert">
            <p>{formError}</p>
            {conflict && <button onClick={reload}>Reload</button>}
          </div>
        )}

        <label htmlFor="job-type">Job type</label>
        <select
          id="job-type"
          value={formJobType}
          onChange={(e) => {
            setFormJobType(e.target.value as JobType);
            setDirty(true);
          }}
        >
          {JOB_TYPES.map((jt) => (
            <option key={jt} value={jt}>
              {jt}
            </option>
          ))}
        </select>

        {formJobType === "guardian.evaluate_one" && (
          <>
            <label htmlFor="check-id">Check ID</label>
            <input
              id="check-id"
              type="text"
              value={formCheckId}
              onChange={(e) => {
                setFormCheckId(e.target.value);
                setDirty(true);
              }}
              aria-describedby={formError ? "form-error" : undefined}
              aria-invalid={!!formError}
            />
          </>
        )}

        <label htmlFor="exec-time">Execution time</label>
        <input
          id="exec-time"
          type="time"
          step="1"
          value={formTime}
          onChange={(e) => {
            setFormTime(e.target.value);
            setDirty(true);
          }}
        />

        <label htmlFor="timezone">Timezone (IANA)</label>
        <input
          id="timezone"
          type="text"
          value={formTimezone}
          onChange={(e) => {
            setFormTimezone(e.target.value);
            setDirty(true);
          }}
        />

        <p className="neutral">
          Schedules are created disabled. Enable explicitly after review. DST
          transitions are handled by the backend; displayed times are
          authoritative server values.
        </p>

        <button
          onClick={handleCreate}
          disabled={saving}
          aria-label="Create schedule"
        >
          {saving ? "Creating…" : "Create schedule"}
        </button>
        <button onClick={() => setView("list")}>Cancel</button>
        <Link href="/">← Home</Link>
      </main>
    );
  }

  // ── Detail view ──
  if (view === "detail" && selected) {
    return (
      <main className="shell" role="region" aria-label="Schedule detail">
        <h1>{selected.job_type}</h1>
        <dl>
          <dt>Status</dt>
          <dd>{selected.enabled ? "Enabled" : "Disabled"}</dd>
          <dt>Time</dt>
          <dd>{selected.execution_time}</dd>
          <dt>Timezone</dt>
          <dd>{selected.timezone}</dd>
          <dt>Next run (UTC)</dt>
          <dd>{fmtTime(selected.next_run_at)}</dd>
          <dt>Created</dt>
          <dd>{fmtTime(selected.created_at)}</dd>
        </dl>

        <div>
          {!selected.enabled ? (
            <button
              onClick={() => handleEnable(selected.id)}
              aria-label="Enable schedule"
            >
              Enable
            </button>
          ) : (
            <button
              onClick={() => handleDisable(selected.id)}
              aria-label="Disable schedule"
            >
              Disable
            </button>
          )}
          <button onClick={() => startEdit(selected)} aria-label="Edit schedule">
            Edit
          </button>
          <button
            onClick={() => handleDelete(selected.id)}
            aria-label="Delete schedule"
          >
            Delete
          </button>
          <button onClick={() => openTrigger(selected)} aria-label="Trigger run now">
            Trigger run now
          </button>
        </div>

        <button onClick={() => setView("list")}>← Back</button>
      </main>
    );
  }

  // ── Edit view ──
  if (view === "edit" && selected) {
    return (
      <main className="shell" role="region" aria-label="Edit schedule">
        <h1>Edit {selected.job_type}</h1>

        {formError && (
          <div role="alert">
            <p>{formError}</p>
            {conflict && <button onClick={reload}>Reload</button>}
          </div>
        )}

        <label htmlFor="edit-time">Execution time</label>
        <input
          id="edit-time"
          type="time"
          step="1"
          value={formTime}
          onChange={(e) => {
            setFormTime(e.target.value);
            setDirty(true);
          }}
        />

        <label htmlFor="edit-tz">Timezone (IANA)</label>
        <input
          id="edit-tz"
          type="text"
          value={formTimezone}
          onChange={(e) => {
            setFormTimezone(e.target.value);
            setDirty(true);
          }}
        />

        <button onClick={handleUpdate} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
        <button onClick={() => setView("detail")}>Cancel</button>
      </main>
    );
  }

  // ── Runs view ──
  if (view === "runs") {
    return (
      <main className="shell" role="region" aria-label="Run history">
        <h1>Run History</h1>
        {runsLoading && <p>Loading…</p>}
        {!runsLoading && runs.length === 0 && <p>No runs.</p>}
        <ul role="list">
          {runs.map((r) => (
            <li key={r.id}>
              <button
                onClick={() => loadRunDetail(r.id)}
                aria-label={`Run ${statusLabel(r.status)}`}
              >
                {statusLabel(r.status)} · {r.triggered_by} ·{" "}
                {fmtTime(r.scheduled_at)}
              </button>
            </li>
          ))}
        </ul>
        <button onClick={() => setView("list")}>← Back</button>
      </main>
    );
  }

  // ── Run detail view ──
  if (view === "run-detail" && selectedRun) {
    return (
      <main className="shell" role="region" aria-label="Run detail">
        <h1>Run {selectedRun.id.slice(0, 8)}</h1>
        <dl>
          <dt>Status</dt>
          <dd>{statusLabel(selectedRun.status)}</dd>
          <dt>Triggered by</dt>
          <dd>{selectedRun.triggered_by}</dd>
          <dt>Scheduled</dt>
          <dd>{fmtTime(selectedRun.scheduled_at)}</dd>
          <dt>Started</dt>
          <dd>{fmtTime(selectedRun.started_at)}</dd>
          <dt>Completed</dt>
          <dd>{fmtTime(selectedRun.completed_at)}</dd>
        </dl>

        <h2>Attempts</h2>
        {selectedRun.attempts.length === 0 && <p>No attempts recorded.</p>}
        <ul role="list">
          {selectedRun.attempts.map((a) => (
            <li key={a.id}>
              <p>
                Attempt #{a.attempt_number}: {statusLabel(a.status)}
              </p>
              {a.error_message && (
                <p className="neutral">Error: {a.error_message}</p>
              )}
              <p>Started: {fmtTime(a.started_at)}</p>
              <p>Completed: {fmtTime(a.completed_at)}</p>
            </li>
          ))}
        </ul>

        <button onClick={() => setView("list")}>← Back</button>
      </main>
    );
  }

  // ── Trigger confirmation ──
  if (view === "trigger") {
    const target = schedules.find(
      (s) => s.job_definition_id === triggerTargetId,
    );
    return (
      <main className="shell" role="region" aria-label="Manual trigger">
        <h1>Manual Trigger</h1>
        <p>
          Trigger a manual run for{" "}
          {target ? `${target.job_type} schedule` : "this job"}?
        </p>
        <p className="neutral">
          This creates a new run. It does not modify existing runs.
        </p>

        {formError && (
          <div role="alert">
            <p>{formError}</p>
          </div>
        )}

        <button
          onClick={handleManualTrigger}
          disabled={triggerLoading}
          aria-label="Confirm trigger"
        >
          {triggerLoading ? "Triggering…" : "Confirm trigger"}
        </button>
        <button onClick={() => { setTriggerTargetId(null); setView("detail"); }}>
          Cancel
        </button>
      </main>
    );
  }

  return null;
}
