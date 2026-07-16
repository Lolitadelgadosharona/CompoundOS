export const POLICY_TEXT_FIELDS = [
  "objectives",
  "time_horizon",
  "liquidity",
  "diversification",
  "contribution_policy",
  "rebalancing_policy",
  "prohibited_assets",
  "leverage_policy",
  "decision_process",
  "notes",
] as const;

export type PolicyTextField = (typeof POLICY_TEXT_FIELDS)[number];

export const POLICY_TEXT_LIMITS: Record<PolicyTextField, number> = {
  objectives: 4000,
  time_horizon: 2000,
  liquidity: 4000,
  diversification: 4000,
  contribution_policy: 4000,
  rebalancing_policy: 4000,
  prohibited_assets: 4000,
  leverage_policy: 4000,
  decision_process: 4000,
  notes: 8000,
};

export const REQUIRED_PUBLISH_FIELDS = [
  "objectives",
  "time_horizon",
  "decision_process",
] as const satisfies readonly PolicyTextField[];

export type PolicyText = Record<PolicyTextField, string>;

export type Policy = {
  id: string;
  household_id: string;
  created_at: string;
  updated_at: string;
};

export type Allocation = {
  id: string;
  asset_class_name: string;
  target_percentage: string;
  sort_order: number;
};

export type PolicyDraft = PolicyText & {
  id: string;
  policy_id: string;
  source_version_id: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
  allocations: Allocation[];
};

export type PolicyVersionSummary = {
  id: string;
  version_number: number;
  status: "published" | "superseded";
  published_at: string;
  superseded_at: string | null;
};

export type PolicyVersion = PolicyText & PolicyVersionSummary & {
  policy_id: string;
  allocations: Allocation[];
};

export type PolicyVersionHistory = {
  items: PolicyVersionSummary[];
  next_before_version_number: number | null;
};

export type PolicyAuditEvent = {
  id: string;
  household_id: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  occurred_at: string;
  sequence_number: number;
  metadata: Record<string, string | number | string[]>;
};

export type AllocationInput = {
  asset_class_name: string;
  target_percentage: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class PolicyApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "PolicyApiError";
  }
}

export class PolicyNetworkError extends Error {
  constructor() {
    super("The Policy service connection is unavailable.");
    this.name = "PolicyNetworkError";
  }
}

function neutralErrorMessage(status: number): string {
  if (status === 400) {
    return "The request could not be completed because the record is mechanically incomplete or unchanged.";
  }
  if (status === 404) return "The requested Policy record was not found.";
  if (status === 409) {
    return "The Policy data changed in another operation. Reload before trying again.";
  }
  if (status === 422) {
    return "The request was not accepted. Check field formats, limits, and duplicate asset-class names.";
  }
  if (status >= 500) return "The Policy service returned an unexpected server error.";
  return "The Policy request could not be completed.";
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

async function fetchResponse(path: string, init: RequestInit = {}): Promise<Response> {
  try {
    return await fetch(`${API_BASE_URL}${path}`, init);
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw new PolicyNetworkError();
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetchResponse(path, init);
  if (!response.ok) throw new PolicyApiError(neutralErrorMessage(response.status), response.status);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function jsonRequest(method: string, payload: unknown, signal?: AbortSignal): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  };
}

export async function hasCurrentHousehold(signal?: AbortSignal): Promise<boolean> {
  const response = await fetchResponse("/api/households/current", {
    cache: "no-store",
    signal,
  });
  if (response.status === 404) return false;
  if (!response.ok) throw new PolicyApiError(neutralErrorMessage(response.status), response.status);
  return true;
}

export async function getCurrentPolicy(signal?: AbortSignal): Promise<Policy | null> {
  const response = await fetchResponse("/api/policies/current", {
    cache: "no-store",
    signal,
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new PolicyApiError(neutralErrorMessage(response.status), response.status);
  return (await response.json()) as Policy;
}

export function createPolicy(signal?: AbortSignal): Promise<{ policy: Policy; draft: PolicyDraft }> {
  return request("/api/policies", { method: "POST", signal });
}

export function getCurrentDraft(signal?: AbortSignal): Promise<PolicyDraft | null> {
  return request<PolicyDraft>("/api/policies/current/draft", {
    cache: "no-store",
    signal,
  }).catch((error: unknown) => {
    if (error instanceof PolicyApiError && error.status === 404) return null;
    throw error;
  });
}

export function updateDraftText(
  expectedRevision: number,
  changedFields: Partial<PolicyText>,
): Promise<PolicyDraft> {
  return request(
    "/api/policies/current/draft",
    jsonRequest("PATCH", { expected_revision: expectedRevision, ...changedFields }),
  );
}

export function replaceDraftAllocations(
  expectedRevision: number,
  items: AllocationInput[],
): Promise<PolicyDraft> {
  return request(
    "/api/policies/current/draft/allocations",
    jsonRequest("PUT", { expected_revision: expectedRevision, items }),
  );
}

export function discardDraft(expectedRevision: number): Promise<void> {
  return request(
    "/api/policies/current/draft/discard",
    jsonRequest("POST", { expected_revision: expectedRevision }),
  );
}

export function createDraft(sourceVersionId?: string): Promise<PolicyDraft> {
  const payload = sourceVersionId ? { source_version_id: sourceVersionId } : {};
  return request("/api/policies/current/draft", jsonRequest("POST", payload));
}

export function publishDraft(expectedRevision: number): Promise<PolicyVersion> {
  return request(
    "/api/policies/current/draft/publish",
    jsonRequest("POST", { expected_revision: expectedRevision, confirmation: true }),
  );
}

export function getCurrentPublished(signal?: AbortSignal): Promise<PolicyVersion | null> {
  return request<PolicyVersion>("/api/policies/current/published", {
    cache: "no-store",
    signal,
  }).catch((error: unknown) => {
    if (error instanceof PolicyApiError && error.status === 404) return null;
    throw error;
  });
}

export function getVersionHistory(
  beforeVersionNumber?: number,
  signal?: AbortSignal,
): Promise<PolicyVersionHistory> {
  const query = beforeVersionNumber
    ? `?before_version_number=${beforeVersionNumber}`
    : "";
  return request(`/api/policies/current/versions${query}`, { cache: "no-store", signal });
}

export function getVersion(versionNumber: number, signal?: AbortSignal): Promise<PolicyVersion> {
  return request(`/api/policies/current/versions/${versionNumber}`, {
    cache: "no-store",
    signal,
  });
}

export function getPolicyAuditEvents(signal?: AbortSignal): Promise<PolicyAuditEvent[]> {
  return request("/api/policies/current/audit-events", { cache: "no-store", signal });
}

function parseDigits(value: string): number | null {
  if (!value) return null;
  let result = 0;
  for (const character of value) {
    const digit = character.charCodeAt(0) - 48;
    if (digit < 0 || digit > 9) return null;
    result = result * 10 + digit;
  }
  return result;
}

export function percentageToHundredths(value: string): number | null {
  if (!/^\d+(?:\.\d{1,2})?$/.test(value)) return null;
  const [wholeText, fractionText = ""] = value.split(".");
  const whole = parseDigits(wholeText);
  const fraction = parseDigits(fractionText.padEnd(2, "0"));
  if (whole === null || fraction === null) return null;
  const hundredths = whole * 100 + fraction;
  if (hundredths <= 0 || hundredths > 10000) return null;
  return hundredths;
}

export function formatHundredths(value: number): string {
  const whole = Math.floor(value / 100);
  const fraction = String(value % 100).padStart(2, "0");
  return `${whole}.${fraction}`;
}

export function allocationTotal(items: AllocationInput[]): {
  hundredths: number | null;
  display: string;
} {
  let total = 0;
  for (const item of items) {
    const value = percentageToHundredths(item.target_percentage);
    if (value === null) return { hundredths: null, display: "Invalid input" };
    total += value;
  }
  return { hundredths: total, display: formatHundredths(total) };
}

export function normalizeAllocationDisplayName(value: string): string {
  return value.normalize("NFKC").trim().replace(/\s+/gu, " ");
}

function normalizedPercentage(value: string): string | null {
  const hundredths = percentageToHundredths(value);
  return hundredths === null ? null : formatHundredths(hundredths);
}

export function allocationsEqual(saved: Allocation[], edited: AllocationInput[]): boolean {
  if (saved.length !== edited.length) return false;
  return saved.every((item, index) => {
    const candidate = edited[index];
    return (
      normalizeAllocationDisplayName(item.asset_class_name) ===
        normalizeAllocationDisplayName(candidate.asset_class_name) &&
      item.target_percentage === normalizedPercentage(candidate.target_percentage)
    );
  });
}
