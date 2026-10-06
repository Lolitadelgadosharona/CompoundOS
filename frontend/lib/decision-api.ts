/* Decision Journal API client — typed browser boundary for Slice 3C. */

export const DECISION_TEXT_FIELDS = [
  "title",
  "decision_summary",
  "rationale",
  "alternatives_considered",
  "risks_and_uncertainties",
  "evidence_or_sources",
  "expected_outcome",
  "review_trigger",
  "notes",
] as const;

export type DecisionTextField = (typeof DECISION_TEXT_FIELDS)[number];

export const DECISION_TEXT_LIMITS: Record<DecisionTextField, number> = {
  title: 500,
  decision_summary: 8_000,
  rationale: 8_000,
  alternatives_considered: 8_000,
  risks_and_uncertainties: 8_000,
  evidence_or_sources: 8_000,
  expected_outcome: 4_000,
  review_trigger: 4_000,
  notes: 8_000,
};

export const DECISION_STATUSES = ["draft", "confirmed", "archived"] as const;
export type DecisionStatus = (typeof DECISION_STATUSES)[number];

export type DecisionListItem = {
  id: string;
  title: string | null;
  status: DecisionStatus;
  decision_date: string | null;
  created_at: string;
  confirmed_at: string | null;
  archived_at: string | null;
  correction_count: number;
};

export type DecisionListResponse = {
  decisions: DecisionListItem[];
  total: number;
};

export type DraftDetail = {
  decision_id: string;
  title: string;
  decision_summary: string | null;
  rationale: string | null;
  alternatives_considered: string | null;
  risks_and_uncertainties: string | null;
  evidence_or_sources: string | null;
  expected_outcome: string | null;
  review_trigger: string | null;
  notes: string | null;
  decision_date: string | null;
  review_date: string | null;
  revision: number;
  status: DecisionStatus;
};

export type SnapshotDetail = {
  title: string;
  decision_summary: string;
  rationale: string;
  alternatives_considered: string | null;
  risks_and_uncertainties: string | null;
  evidence_or_sources: string | null;
  expected_outcome: string | null;
  review_trigger: string | null;
  notes: string | null;
  decision_date: string;
  review_date: string | null;
  confirmed_at: string;
  policy_version_number: number | null;
  snapshot_id: string | null;
};

export type DecisionDetailResponse = {
  id: string;
  household_id: string;
  status: DecisionStatus;
  created_at: string;
  archived_at: string | null;
  archive_reason: string | null;
  draft: DraftDetail | null;
  confirmed: SnapshotDetail | null;
  original: SnapshotDetail | null;
};

export type Correction = {
  correction_number: number;
  title: string;
  decision_summary: string;
  rationale: string;
  alternatives_considered: string | null;
  risks_and_uncertainties: string | null;
  evidence_or_sources: string | null;
  expected_outcome: string | null;
  review_trigger: string | null;
  notes: string | null;
  decision_date: string;
  review_date: string | null;
  created_at: string;
  snapshot_id: string;
};

export type CorrectionListResponse = {
  corrections: Correction[];
  total: number;
};

export type DecisionAuditEvent = {
  id: string;
  action: string;
  occurred_at: string;
  actor: string;
  metadata: Record<string, unknown>;
};

export type DecisionAuditListResponse = {
  events: DecisionAuditEvent[];
  has_more: boolean;
};

export type DecisionCreateResponse = {
  id: string;
  title: string;
  revision: number;
};

export type ConfirmResponse = {
  id: string;
  status: DecisionStatus;
};

export type ArchiveResponse = ConfirmResponse & {
  archived_at: string;
  archive_reason: string | null;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";
const BASE_PATH = "/api/decisions";

class DecisionApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body: unknown,
  ) {
    super(message);
    this.name = "DecisionApiError";
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new DecisionApiError(
      body?.detail ?? `HTTP ${res.status}`,
      res.status,
      body,
    );
  }
  return res.json() as Promise<T>;
}

export async function createDecision(title: string, signal?: AbortSignal): Promise<DecisionCreateResponse> {
  return request<DecisionCreateResponse>(`${API_BASE_URL}${BASE_PATH}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
    signal,
  });
}

export async function listDecisions(
  params?: { status?: DecisionStatus; limit?: number; cursor?: string },
  signal?: AbortSignal,
): Promise<DecisionListResponse> {
  const url = new URL(`${API_BASE_URL}${BASE_PATH}`, window.location.origin);
  if (params?.status) url.searchParams.set("status", params.status);
  if (params?.limit) url.searchParams.set("limit", String(params.limit));
  if (params?.cursor) url.searchParams.set("cursor", params.cursor);
  if (process.env.NEXT_PUBLIC_COMPOUNDOS_PREVIEW_MODE === "true") {
    const data = await request<{items: DecisionListItem[]}>(url.toString(), {signal});
    return {decisions:data.items, total:data.items.length};
  }
  return request<DecisionListResponse>(url.toString(), { signal });
}

export async function readDraft(decisionId: string, signal?: AbortSignal): Promise<DraftDetail> {
  return request<DraftDetail>(`${API_BASE_URL}${BASE_PATH}/${decisionId}/draft`, { signal });
}

export async function updateDraft(
  decisionId: string,
  expectedRevision: number,
  fields: Partial<Record<DecisionTextField, string | null>> & { decision_date?: string | null; review_date?: string | null },
  signal?: AbortSignal,
): Promise<DraftDetail> {
  return request<DraftDetail>(`${API_BASE_URL}${BASE_PATH}/${decisionId}/draft`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected_revision: expectedRevision, ...fields }),
    signal,
  });
}

export async function discardDraft(decisionId: string, expectedRevision: number, signal?: AbortSignal): Promise<void> {
  await request<unknown>(`${API_BASE_URL}${BASE_PATH}/${decisionId}/draft/discard`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected_revision: expectedRevision }),
    signal,
  });
}

export async function confirmDraft(
  decisionId: string,
  expectedRevision: number,
  signal?: AbortSignal,
): Promise<ConfirmResponse> {
  return request<ConfirmResponse>(`${API_BASE_URL}${BASE_PATH}/${decisionId}/draft/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected_revision: expectedRevision, confirmation: true }),
    signal,
  });
}

export async function readDecisionDetail(decisionId: string, signal?: AbortSignal): Promise<DecisionDetailResponse> {
  if (process.env.NEXT_PUBLIC_COMPOUNDOS_PREVIEW_MODE === "true") {
    const raw = await request<DecisionDetailResponse & {original_snapshot:SnapshotDetail|null; effective_snapshot:SnapshotDetail|null}>(`${API_BASE_URL}${BASE_PATH}/${decisionId}`, {signal});
    const audit = await readDecisionAudit(decisionId,undefined,signal);
    const event = audit.events.find(e => e.action === "decision.confirmed");
    const number = event?.metadata.policy_version_number;
    const snapshot = (value:SnapshotDetail|null):SnapshotDetail|null => value ? {...value,
      policy_version_number:typeof number === "number" ? number : null,
      snapshot_id:value.snapshot_id ?? null} : null;
    return {...raw, original:snapshot(raw.original_snapshot), confirmed:snapshot(raw.effective_snapshot),
      draft:raw.status === "draft" ? await readDraft(decisionId,signal) : null};
  }
  return request<DecisionDetailResponse>(`${API_BASE_URL}${BASE_PATH}/${decisionId}`, { signal });
}

export async function archiveDecision(
  decisionId: string,
  archiveReason?: string,
  signal?: AbortSignal,
): Promise<ArchiveResponse> {
  return request<ArchiveResponse>(`${API_BASE_URL}${BASE_PATH}/${decisionId}/archive`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ archive_reason: archiveReason ?? null }),
    signal,
  });
}

export async function unarchiveDecision(decisionId: string, signal?: AbortSignal): Promise<ConfirmResponse> {
  return request<ConfirmResponse>(`${API_BASE_URL}${BASE_PATH}/${decisionId}/unarchive`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
    signal,
  });
}

export async function readCorrections(decisionId: string, signal?: AbortSignal): Promise<CorrectionListResponse> {
  if (process.env.NEXT_PUBLIC_COMPOUNDOS_PREVIEW_MODE === "true") {
    const data = await request<{items:Correction[]}>(`${API_BASE_URL}${BASE_PATH}/${decisionId}/corrections`,{signal});
    return {corrections:data.items,total:data.items.length};
  }
  return request<CorrectionListResponse>(`${API_BASE_URL}${BASE_PATH}/${decisionId}/corrections`, { signal });
}

export async function appendCorrection(
  decisionId: string,
  fields: {
    title: string;
    decision_summary: string;
    rationale: string;
    decision_date: string;
    alternatives_considered?: string | null;
    risks_and_uncertainties?: string | null;
    evidence_or_sources?: string | null;
    expected_outcome?: string | null;
    review_trigger?: string | null;
    notes?: string | null;
    review_date?: string | null;
  },
  signal?: AbortSignal,
): Promise<Correction> {
  return request<Correction>(`${API_BASE_URL}${BASE_PATH}/${decisionId}/corrections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
    signal,
  });
}

export async function readDecisionAudit(
  decisionId: string,
  params?: { before_sequence_number?: number; limit?: number },
  signal?: AbortSignal,
): Promise<DecisionAuditListResponse> {
  const auditPath = process.env.NEXT_PUBLIC_COMPOUNDOS_PREVIEW_MODE === "true" ? "audit-events" : "audit";
  const url = new URL(`${API_BASE_URL}${BASE_PATH}/${decisionId}/${auditPath}`, window.location.origin);
  if (params?.before_sequence_number) url.searchParams.set("before_sequence_number", String(params.before_sequence_number));
  if (params?.limit) url.searchParams.set("limit", String(params.limit));
  if (process.env.NEXT_PUBLIC_COMPOUNDOS_PREVIEW_MODE === "true") {
    const data = await request<{items:DecisionAuditEvent[]; next_before_sequence_number:number|null}>(url.toString(),{signal});
    return {events:data.items,has_more:data.next_before_sequence_number !== null};
  }
  return request<DecisionAuditListResponse>(url.toString(), { signal });
}

export type { DecisionApiError };
