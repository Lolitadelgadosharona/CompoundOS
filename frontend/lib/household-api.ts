export type HouseholdInput = {
  household_name: string;
  base_currency: string;
  investment_horizon: string;
  liquidity_needs: string;
  risk_statement: string;
  notes: string;
};

export type HouseholdProfile = HouseholdInput & {
  id: string;
  created_at: string;
  updated_at: string;
};

export type AuditEvent = {
  id: string;
  household_id: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  occurred_at: string;
  metadata: { changed_fields?: string[] };
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class HouseholdApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function responseError(response: Response): Promise<HouseholdApiError> {
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  const message =
    typeof body?.detail === "string" ? body.detail : `Request failed with status ${response.status}`;
  return new HouseholdApiError(message, response.status);
}

export async function getCurrentHousehold(): Promise<HouseholdProfile | null> {
  const response = await fetch(`${API_BASE_URL}/api/households/current`, { cache: "no-store" });
  if (response.status === 404) return null;
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as HouseholdProfile;
}

export async function createHousehold(payload: HouseholdInput): Promise<HouseholdProfile> {
  const response = await fetch(`${API_BASE_URL}/api/households`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as HouseholdProfile;
}

export async function updateHousehold(payload: HouseholdInput): Promise<HouseholdProfile> {
  const response = await fetch(`${API_BASE_URL}/api/households/current`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as HouseholdProfile;
}

export async function getAuditEvents(): Promise<AuditEvent[]> {
  const response = await fetch(`${API_BASE_URL}/api/households/current/audit-events`, {
    cache: "no-store",
  });
  if (response.status === 404) return [];
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as AuditEvent[];
}
