/** Sprint 005 Slice C — Automation API client (9 endpoints). */

// ═══════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════

export type JobType = "guardian.evaluate_all" | "guardian.evaluate_one" | "backup.daily";

export interface ScheduleCreatePayload {
  job_type: JobType;
  job_params?: Record<string, unknown>;
  execution_time: string; // HH:MM:SS
  timezone?: string;
}

export interface ScheduleResponse {
  id: string;
  job_definition_id: string;
  job_type: string;
  job_params: Record<string, unknown>;
  execution_time: string;
  timezone: string;
  next_run_at: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ScheduleUpdatePayload {
  execution_time?: string;
  timezone?: string;
  enabled?: boolean;
}

export interface RunResponse {
  id: string;
  job_definition_id: string;
  schedule_id: string | null;
  status: string;
  triggered_by: string;
  scheduled_at: string;
  started_at: string | null;
  completed_at: string | null;
  household_id: string;
}

export interface AttemptResponse {
  id: string;
  run_id: string;
  attempt_number: number;
  status: string;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface RunDetailResponse extends RunResponse {
  attempts: AttemptResponse[];
}

export interface ManualTriggerPayload {
  job_definition_id: string;
}

export interface WorkerStatusResponse {
  worker_count: number;
  active_leases: number;
  running_runs: number;
}

// ═══════════════════════════════════════════════════════════════════════════
// Errors
// ═══════════════════════════════════════════════════════════════════════════

export class AutomationApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "AutomationApiError";
    this.status = status;
  }
}

export class AutomationNetworkError extends Error {
  constructor() {
    super("Automation service unavailable — check that the backend is running.");
    this.name = "AutomationNetworkError";
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════════

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

function url(path: string, params?: Record<string, string>): string {
  const u = new URL(path, BASE);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      u.searchParams.set(k, v);
    }
  }
  return u.toString();
}

async function request<T>(
  path: string,
  options: RequestInit & {
    signal?: AbortSignal;
    params?: Record<string, string>;
  } = {},
): Promise<T> {
  const { signal, params, ...init } = options;
  try {
    const resp = await fetch(url(path, params), {
      ...init,
      signal,
      headers: { "Content-Type": "application/json", ...init.headers },
    });
    if (resp.status === 204) return undefined as unknown as T;
    const body = await resp.json();
    if (!resp.ok) {
      throw new AutomationApiError(
        body?.detail ?? `Automation API error: ${resp.status}`,
        resp.status,
      );
    }
    return body as T;
  } catch (err) {
    if (err instanceof AutomationApiError) throw err;
    throw new AutomationNetworkError();
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 9-endpoint client
// ═══════════════════════════════════════════════════════════════════════════

/** 1. POST /api/automation/schedules */
export function createSchedule(
  payload: ScheduleCreatePayload,
  signal?: AbortSignal,
): Promise<ScheduleResponse> {
  return request<ScheduleResponse>("/api/automation/schedules", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

/** 2. GET /api/automation/schedules */
export function listSchedules(
  signal?: AbortSignal,
): Promise<ScheduleResponse[]> {
  return request<ScheduleResponse[]>("/api/automation/schedules", { signal });
}

/** 3. GET /api/automation/schedules/{id} */
export function getSchedule(
  id: string,
  signal?: AbortSignal,
): Promise<ScheduleResponse> {
  return request<ScheduleResponse>(
    `/api/automation/schedules/${encodeURIComponent(id)}`,
    { signal },
  );
}

/** 4. PATCH /api/automation/schedules/{id} */
export function updateSchedule(
  id: string,
  payload: ScheduleUpdatePayload,
  signal?: AbortSignal,
): Promise<ScheduleResponse> {
  return request<ScheduleResponse>(
    `/api/automation/schedules/${encodeURIComponent(id)}`,
    { method: "PATCH", body: JSON.stringify(payload), signal },
  );
}

/** 5. DELETE /api/automation/schedules/{id} */
export function deleteSchedule(
  id: string,
  signal?: AbortSignal,
): Promise<void> {
  return request<void>(
    `/api/automation/schedules/${encodeURIComponent(id)}`,
    { method: "DELETE", signal },
  );
}

/** 6. GET /api/automation/runs */
export function listRuns(
  params?: { job_type?: string; limit?: number; offset?: number },
  signal?: AbortSignal,
): Promise<RunResponse[]> {
  const sp: Record<string, string> = {};
  if (params?.job_type) sp.job_type = params.job_type;
  if (params?.limit) sp.limit = String(params.limit);
  if (params?.offset) sp.offset = String(params.offset);
  return request<RunResponse[]>("/api/automation/runs", {
    signal,
    params: sp,
  });
}

/** 7. GET /api/automation/runs/{id} */
export function getRun(
  id: string,
  signal?: AbortSignal,
): Promise<RunDetailResponse> {
  return request<RunDetailResponse>(
    `/api/automation/runs/${encodeURIComponent(id)}`,
    { signal },
  );
}

/** 8. POST /api/automation/runs */
export function manualTrigger(
  payload: ManualTriggerPayload,
  signal?: AbortSignal,
): Promise<RunResponse> {
  return request<RunResponse>("/api/automation/runs", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

/** 9. GET /api/automation/worker/status */
export function getWorkerStatus(
  signal?: AbortSignal,
): Promise<WorkerStatusResponse> {
  return request<WorkerStatusResponse>("/api/automation/worker/status", {
    signal,
  });
}
