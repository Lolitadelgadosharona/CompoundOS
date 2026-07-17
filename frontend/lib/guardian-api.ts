export type GuardianCheckType = "drift" | "category_exposure" | "staleness";

export type GuardianIdentity = {
  id: string;
  household_id: string;
  name: string;
  canonical_name: string;
  check_type: GuardianCheckType;
  status: string;
  created_at: string | null;
  updated_at: string | null;
};

export type GuardianDraft = {
  threshold_value: string;
  target_category: string | null;
  target_holding_category: string | null;
  staleness_days: number | null;
  severity: string;
  notes: string | null;
  expected_revision: number;
  updated_at: string;
};

export type GuardianConfirmedVersion = {
  id: string;
  check_id: string;
  version_number: number;
  check_type: GuardianCheckType;
  threshold_value: string;
  target_category: string | null;
  target_holding_category: string | null;
  staleness_days: number | null;
  severity: string;
  notes: string | null;
  confirmed_at: string;
};

export type GuardianCheckDetail = {
  identity: GuardianIdentity;
  draft: GuardianDraft | null;
  latest_version: GuardianConfirmedVersion | null;
};

export type GuardianCheckListResponse = {
  checks: GuardianIdentity[];
};

export type GuardianEvent = {
  id: string;
  evaluation_run_id: string;
  check_id: string;
  check_version_id: string;
  check_type: GuardianCheckType;
  policy_version_id: string;
  portfolio_snapshot_id: string;
  exceeded: boolean;
  drift_pp: string | null;
  exposure_pct: string | null;
  staleness_days_actual: number | null;
  as_of_date: string;
  detected_at: string;
};

export type GuardianEvaluationRun = {
  id: string;
  household_id: string;
  status: string;
  skip_reason: string | null;
  checks_evaluated: number;
  events_created: number;
  as_of_date: string;
  created_at: string;
};

export type GuardianEvaluateResponse = {
  evaluation_run: GuardianEvaluationRun;
  events: GuardianEvent[];
};

export type GuardianAuditEvent = {
  id: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  metadata: Record<string, unknown>;
  occurred_at: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class GuardianApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "GuardianApiError";
  }
}

export class GuardianNetworkError extends Error {
  constructor() {
    super("The Guardian service connection is unavailable.");
    this.name = "GuardianNetworkError";
  }
}

function neutralErrorMessage(status: number): string {
  if (status === 404) return "The requested Guardian record was not found.";
  if (status === 409) return "The Guardian data changed in another operation. Reload before trying again.";
  if (status === 422) return "The request was not accepted. Check field formats and limits.";
  if (status >= 500) return "The Guardian service returned an unexpected server error.";
  return "The Guardian request could not be completed.";
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

async function fetchResponse(path: string, init: RequestInit = {}): Promise<Response> {
  try {
    return await fetch(`${API_BASE_URL}${path}`, init);
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw new GuardianNetworkError();
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetchResponse(path, init);
  if (!response.ok) throw new GuardianApiError(neutralErrorMessage(response.status), response.status);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function jsonRequest(method: string, payload: unknown, signal?: AbortSignal): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload), signal };
}

// ---- Check Lifecycle ----

export async function createCheck(data: {
  name: string; check_type: GuardianCheckType; threshold_value: string;
  severity?: string; target_category?: string; target_holding_category?: string;
  staleness_days?: number; notes?: string;
}, signal?: AbortSignal): Promise<GuardianCheckDetail> {
  return request("/api/guardian/checks", jsonRequest("POST", data, signal));
}

export async function listChecks(signal?: AbortSignal): Promise<GuardianCheckListResponse> {
  return request("/api/guardian/checks", { cache: "no-store", signal });
}

export async function getCheck(checkId: string, signal?: AbortSignal): Promise<GuardianCheckDetail> {
  return request(`/api/guardian/checks/${checkId}`, { cache: "no-store", signal });
}

export async function updateDraft(checkId: string, data: {
  expected_revision: number; threshold_value?: string; target_category?: string | null;
  target_holding_category?: string | null; staleness_days?: number | null;
  severity?: string; notes?: string | null;
}, signal?: AbortSignal): Promise<GuardianCheckDetail> {
  return request(`/api/guardian/checks/${checkId}/draft`, jsonRequest("PATCH", data, signal));
}

export async function confirmCheck(checkId: string, expectedRevision: number, signal?: AbortSignal): Promise<GuardianCheckDetail> {
  return request(`/api/guardian/checks/${checkId}/draft/confirm`, jsonRequest("POST", { expected_revision: expectedRevision, confirmation: true }, signal));
}

export async function discardCheck(checkId: string, signal?: AbortSignal): Promise<void> {
  return request(`/api/guardian/checks/${checkId}/draft/discard`, jsonRequest("POST", { confirmation: true }, signal));
}

// ---- Evaluation ----

export async function evaluateAll(asOfDate: string, signal?: AbortSignal): Promise<GuardianEvaluateResponse> {
  return request("/api/guardian/evaluate", jsonRequest("POST", { as_of_date: asOfDate, confirmation: true }, signal));
}

export async function evaluateOne(checkId: string, asOfDate: string, signal?: AbortSignal): Promise<GuardianEvaluateResponse> {
  return request(`/api/guardian/checks/${checkId}/evaluate`, jsonRequest("POST", { as_of_date: asOfDate, confirmation: true }, signal));
}

// ---- History ----

export async function listEvaluationRuns(limit = 50, signal?: AbortSignal): Promise<{ runs: GuardianEvaluationRun[] }> {
  return request(`/api/guardian/evaluations?limit=${limit}`, { cache: "no-store", signal });
}

export async function getEvaluationRun(runId: string, signal?: AbortSignal): Promise<{ evaluation_run: GuardianEvaluationRun; events: GuardianEvent[] }> {
  return request(`/api/guardian/evaluations/${runId}`, { cache: "no-store", signal });
}

export async function listEvents(limit = 50, signal?: AbortSignal): Promise<{ events: GuardianEvent[] }> {
  return request(`/api/guardian/events?limit=${limit}`, { cache: "no-store", signal });
}

export async function getEvent(eventId: string, signal?: AbortSignal): Promise<GuardianEvent> {
  return request(`/api/guardian/events/${eventId}`, { cache: "no-store", signal });
}

export async function getAudit(limit = 50, signal?: AbortSignal): Promise<{ audit_events: GuardianAuditEvent[] }> {
  return request(`/api/guardian/audit?limit=${limit}`, { cache: "no-store", signal });
}

export async function hasCurrentHousehold(signal?: AbortSignal): Promise<boolean> {
  const response = await fetchResponse("/api/households/current", { cache: "no-store", signal });
  if (response.status === 404) return false;
  if (!response.ok) throw new GuardianApiError(neutralErrorMessage(response.status), response.status);
  return true;
}
