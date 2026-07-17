export type PortfolioStatus = "draft" | "active";

export type Portfolio = {
  id: string;
  household_id: string;
  status: PortfolioStatus;
  created_at: string;
};

export type Holding = {
  id: string;
  asset_name: string;
  asset_category: string;
  quantity: string;
  unit_price: string;
  total_value: string;
  valuation_date: string;
  notes: string | null;
  sort_order: number;
};

export type PortfolioDraft = {
  portfolio_id: string;
  expected_revision: number;
  valuation_date: string | null;
  notes: string | null;
  updated_at: string;
  holdings: Holding[];
};

export type PortfolioCreateData = {
  portfolio: Portfolio;
  draft: PortfolioDraft;
};

export type PortfolioSnapshotSummary = {
  id: string;
  version_number: number;
  status: string;
  confirmed_at: string | null;
  holding_count: number | null;
  valuation_date: string;
};

export type PortfolioSnapshotDetail = PortfolioSnapshotSummary & {
  portfolio_id: string;
  notes: string | null;
  holdings: Holding[];
};

export type PortfolioSnapshotHistory = {
  items: PortfolioSnapshotSummary[];
  next_before_version_number: number | null;
};

export type PortfolioAuditEvent = {
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

export type HoldingInput = {
  asset_name: string;
  asset_category: string;
  quantity: string;
  unit_price: string;
  valuation_date: string;
  notes?: string;
  sort_order?: number;
};

export type CurrentPortfolioState = {
  portfolio: { status: PortfolioStatus };
  draft?: PortfolioDraft;
  latest_snapshot?: PortfolioSnapshotDetail;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class PortfolioApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "PortfolioApiError";
  }
}

export class PortfolioNetworkError extends Error {
  constructor() {
    super("The Portfolio service connection is unavailable.");
    this.name = "PortfolioNetworkError";
  }
}

function neutralErrorMessage(status: number): string {
  if (status === 400) {
    return "The request could not be completed because the record is mechanically incomplete or unchanged.";
  }
  if (status === 404) return "The requested Portfolio record was not found.";
  if (status === 409) {
    return "The Portfolio data changed in another operation. Reload before trying again.";
  }
  if (status === 422) {
    return "The request was not accepted. Check field formats and limits.";
  }
  if (status >= 500) return "The Portfolio service returned an unexpected server error.";
  return "The Portfolio request could not be completed.";
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

async function fetchResponse(path: string, init: RequestInit = {}): Promise<Response> {
  try {
    return await fetch(`${API_BASE_URL}${path}`, init);
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw new PortfolioNetworkError();
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetchResponse(path, init);
  if (!response.ok) throw new PortfolioApiError(neutralErrorMessage(response.status), response.status);
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
  if (!response.ok) throw new PortfolioApiError(neutralErrorMessage(response.status), response.status);
  return true;
}

export async function getCurrentPortfolio(signal?: AbortSignal): Promise<CurrentPortfolioState | null> {
  const response = await fetchResponse("/api/portfolio", {
    cache: "no-store",
    signal,
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new PortfolioApiError(neutralErrorMessage(response.status), response.status);
  return (await response.json()) as CurrentPortfolioState;
}

export async function createPortfolioDraft(signal?: AbortSignal): Promise<PortfolioCreateData> {
  const response = await fetch(`${API_BASE_URL}/api/portfolio/draft`, {
    method: "POST",
    cache: "no-store",
    signal,
  });
  if (!response.ok) throw new PortfolioApiError(neutralErrorMessage(response.status), response.status);
  return (await response.json()) as PortfolioCreateData;
}

export async function updateDraftMetadata(
  expectedRevision: number,
  fields: { valuation_date?: string | null; notes?: string | null },
): Promise<PortfolioDraft> {
  return request(
    "/api/portfolio/draft",
    jsonRequest("PATCH", { expected_revision: expectedRevision, ...fields }),
  );
}

export async function replaceDraftHoldings(
  expectedRevision: number,
  items: HoldingInput[],
): Promise<PortfolioDraft> {
  return request(
    "/api/portfolio/draft/holdings",
    jsonRequest("PUT", { expected_revision: expectedRevision, items }),
  );
}

export async function confirmDraft(expectedRevision: number): Promise<PortfolioSnapshotDetail> {
  return request(
    "/api/portfolio/draft/confirm",
    jsonRequest("POST", { expected_revision: expectedRevision, confirmation: true }),
  );
}

export async function discardDraft(expectedRevision: number): Promise<PortfolioSnapshotDetail | undefined> {
  const response = await fetchResponse(
    "/api/portfolio/draft/discard",
    jsonRequest("POST", { expected_revision: expectedRevision }),
  );
  if (response.status === 204) return undefined;
  if (!response.ok) throw new PortfolioApiError(neutralErrorMessage(response.status), response.status);
  return (await response.json()) as PortfolioSnapshotDetail;
}

export async function getSnapshotHistory(
  beforeVersionNumber?: number,
  signal?: AbortSignal,
): Promise<PortfolioSnapshotHistory> {
  const query = beforeVersionNumber
    ? `?before_version_number=${beforeVersionNumber}&limit=20`
    : "?limit=20";
  return request(`/api/portfolio/snapshots${query}`, { cache: "no-store", signal });
}

export async function getSnapshotDetail(
  snapshotId: string,
  signal?: AbortSignal,
): Promise<PortfolioSnapshotDetail> {
  return request(`/api/portfolio/snapshots/${snapshotId}`, {
    cache: "no-store",
    signal,
  });
}

export async function getPortfolioAudit(
  beforeSequenceNumber?: number,
  signal?: AbortSignal,
): Promise<PortfolioAuditEvent[]> {
  const query = beforeSequenceNumber
    ? `?before_sequence_number=${beforeSequenceNumber}&limit=50`
    : "?limit=50";
  return request(`/api/portfolio/audit${query}`, { cache: "no-store", signal });
}

// ---------------------------------------------------------------------------
// Decimal helpers (non-authoritative, client-side estimation only)
// ---------------------------------------------------------------------------

export function isCash(category: string): boolean {
  return category.trim().toLowerCase() === "cash";
}

export function formatDecimal(value: string): string {
  // Strip trailing zeros for display; "100.00000000" → "100"
  const trimmed = value.replace(/0+$/, "").replace(/\.$/, "");
  return trimmed || "0";
}

export function isValidQuantity(value: string): boolean {
  return /^\d+(?:\.\d{1,8})?$/.test(value) && parseFloat(value) > 0;
}

export function isValidUnitPrice(value: string): boolean {
  return /^\d+(?:\.\d{1,4})?$/.test(value) && parseFloat(value) >= 0;
}

export function isValidValuationDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const d = new Date(value + "T00:00:00");
  if (isNaN(d.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return d <= today;
}

export function isFutureValuationDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const d = new Date(value + "T00:00:00");
  if (isNaN(d.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return d > today;
}

/**
 * Non-authoritative client-side total_value estimation.
 * The server total_value is the authoritative value.
 */
export function estimateTotal(quantity: string, unitPrice: string): string | null {
  if (!isValidQuantity(quantity) || !isValidUnitPrice(unitPrice)) return null;
  // Use integer arithmetic to avoid IEEE 754:
  // Convert both strings to integer hundredths-of-cents (×10000 for price, ×100000000 for quantity)
  // then compute and round to cents.
  const qParts = quantity.split(".");
  const qWhole = qParts[0];
  const qFrac = (qParts[1] ?? "").padEnd(8, "0");
  // quantity as integer hundred-millionths
  const qInt = BigInt(qWhole + qFrac); // e.g., "100" + "00000000" = 10000000000

  const pParts = unitPrice.split(".");
  const pWhole = pParts[0];
  const pFrac = (pParts[1] ?? "").padEnd(4, "0");
  const pInt = BigInt(pWhole + pFrac); // e.g., "150" + "5000" = 1505000

  // qInt * pInt gives result in (10^8 * 10^4) = 10^12 denominator
  // We want cents (10^2 denominator), so divide by 10^10
  const product = qInt * pInt;
  const HALF = BigInt(5_000_000_000); // 0.5 in 10^10 units
  const rounded = (product + HALF) / BigInt(10_000_000_000);
  const whole = rounded / BigInt(100);
  const cents = rounded % BigInt(100);
  return `${whole}.${String(cents).padStart(2, "0")}`;
}
