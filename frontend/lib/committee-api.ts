/** Sprint 006 Slice C — Committee API client (9 endpoints). */

// ═══════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════

export interface SessionCreatePayload {
  title: string;
  proposal_text: string;
}

export interface SessionSummary {
  id: string;
  household_id: string;
  parent_session_id: string | null;
  title: string;
  proposal_text: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SessionDetail extends SessionSummary {
  evidence_items: EvidenceSummary[];
  report: ReportSummary | null;
  outcomes: OutcomeSummary[];
}

export interface EvidenceSummary {
  id: string;
  source_type: string;
  source_title: string;
  citation_ref: string;
  confidence: string;
  provenance: string;
  structured_facts?: Record<string, unknown>;
  as_of?: string;
}

export interface PrivacyPreview {
  session_id: string;
  evidence_summary: EvidenceSummary[];
  estimated_input_tokens: number;
  exceeds_budget: boolean;
  max_input_tokens: number;
  max_output_tokens: number;
  max_cost_usd: string;
}

export interface RunResult {
  session_id: string;
  status: string;
  report_id: string | null;
}

export interface ReportDetail {
  id: string;
  session_id: string;
  provider: string;
  model_id: string;
  model_version: string | null;
  prompt_version: string;
  schema_version: string;
  temperature: number;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost: number | null;
  report_content: ReportContent;
  content_hash: string;
  generated_at: string;
  created_at: string;
}

export interface ReportContent {
  supporting_arguments: string[];
  opposing_arguments: string[];
  risks: string[];
  policy_alignment: string;
  minority_opinions: string[];
  evidence_citations: EvidenceCitation[];
  limitations: string[];
  recommended_direction: string;
  sections: RoleSections;
}

export interface RoleSections {
  long_term_compounding: string;
  index_passive_investing: string;
  macroeconomic_context: string;
  risk_capital_preservation: string;
  devils_advocate: string;
  policy_alignment_role: string;
  synthesis_chair: string;
}

export interface EvidenceCitation {
  evidence_id: string;
  citation_ref?: string;
  claim?: string;
}

export interface OutcomeCreatePayload {
  outcome: "accepted" | "rejected" | "deferred";
  owner_rationale?: string;
}

export interface OutcomeSummary {
  id: string;
  outcome: string;
  owner_rationale: string | null;
  recorded_at: string;
}

export interface ReportSummary {
  id: string;
  provider: string;
  model_id: string;
  prompt_version: string;
  input_tokens: number | null;
  output_tokens: number | null;
  generated_at: string;
  content_hash: string;
}

// ═══════════════════════════════════════════════════════════════════════════
// Errors
// ═══════════════════════════════════════════════════════════════════════════

export class CommitteeApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "CommitteeApiError";
    this.status = status;
  }
}

export class CommitteeNetworkError extends Error {
  constructor() {
    super("Committee service unavailable — check that the backend is running.");
    this.name = "CommitteeNetworkError";
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════════

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

function url(path: string, params?: Record<string, string>): string {
  const u = new URL(path, BASE);
  if (params) {
    Object.entries(params).forEach(([k, v]) => u.searchParams.set(k, v));
  }
  return u.toString();
}

async function request<T>(
  path: string,
  options: RequestInit & { signal?: AbortSignal; params?: Record<string, string> } = {},
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
      throw new CommitteeApiError(
        body?.detail ?? `Committee API error: ${resp.status}`,
        resp.status,
      );
    }
    return body as T;
  } catch (err) {
    if (err instanceof CommitteeApiError) throw err;
    throw new CommitteeNetworkError();
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 9-endpoint client
// ═══════════════════════════════════════════════════════════════════════════

/** 1. POST /api/committee/sessions */
export function createSession(
  payload: SessionCreatePayload,
  signal?: AbortSignal,
): Promise<SessionSummary> {
  return request<SessionSummary>("/api/committee/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

/** 2. GET /api/committee/sessions */
export function listSessions(
  params?: { limit?: number; offset?: number },
  signal?: AbortSignal,
): Promise<SessionSummary[]> {
  const sp: Record<string, string> = {};
  if (params?.limit) sp.limit = String(params.limit);
  if (params?.offset) sp.offset = String(params.offset);
  return request<SessionSummary[]>("/api/committee/sessions", { signal, params: sp });
}

/** 3. GET /api/committee/sessions/{id} */
export function getSession(
  id: string,
  signal?: AbortSignal,
): Promise<SessionDetail> {
  return request<SessionDetail>(
    `/api/committee/sessions/${encodeURIComponent(id)}`,
    { signal },
  );
}

/** 4. GET /api/committee/sessions/{id}/privacy-preview */
export function getPrivacyPreview(
  id: string,
  signal?: AbortSignal,
): Promise<PrivacyPreview> {
  return request<PrivacyPreview>(
    `/api/committee/sessions/${encodeURIComponent(id)}/privacy-preview`,
    { signal },
  );
}

/** 5. POST /api/committee/sessions/{id}/run */
export function runSession(
  id: string,
  signal?: AbortSignal,
): Promise<RunResult> {
  return request<RunResult>(
    `/api/committee/sessions/${encodeURIComponent(id)}/run`,
    { method: "POST", body: "{}", signal },
  );
}

/** 6. GET /api/committee/runs/{id} */
export function getRunStatus(
  id: string,
  signal?: AbortSignal,
): Promise<RunResult> {
  return request<RunResult>(
    `/api/committee/runs/${encodeURIComponent(id)}`,
    { signal },
  );
}

/** 7. GET /api/committee/reports/{id} */
export function getReport(
  id: string,
  signal?: AbortSignal,
): Promise<ReportDetail> {
  return request<ReportDetail>(
    `/api/committee/reports/${encodeURIComponent(id)}`,
    { signal },
  );
}

/** 8. GET /api/committee/evidence/{session_id} */
export function getEvidence(
  sessionId: string,
  signal?: AbortSignal,
): Promise<EvidenceSummary[]> {
  return request<EvidenceSummary[]>(
    `/api/committee/evidence/${encodeURIComponent(sessionId)}`,
    { signal },
  );
}

/** 9. POST /api/committee/outcomes */
export function recordOutcome(
  sessionId: string,
  payload: OutcomeCreatePayload,
  signal?: AbortSignal,
): Promise<OutcomeSummary> {
  return request<OutcomeSummary>(
    `/api/committee/outcomes?session_id=${encodeURIComponent(sessionId)}`,
    { method: "POST", body: JSON.stringify(payload), signal },
  );
}
