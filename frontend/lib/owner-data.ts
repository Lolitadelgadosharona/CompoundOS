export type PlanRow = {
  asset_id: string;
  symbol: string;
  current_weight: string;
  target_weight: string;
  absolute_drift: string;
  underweight: string;
  overweight: string;
  buy_amount: string;
  post_weight: string;
};
export type Analysis = {
  as_of: string;
  recommendation_ready: boolean;
  valuation?: { base_currency: string };
  plan: {
    new_capital: string;
    retained_cash: string;
    reason: string;
    rows: PlanRow[];
  };
  policy: { status: string; findings: string[] };
  guardian: {
    status: string;
    findings: { check: string; detail: string; severity: string }[];
  };
  monthly_contribution: { amount: string; currency: string };
};
export type Candidate = {
  id: string;
  decision_id?: string;
  decision_status: string;
  committee_status: string;
  content_hash: string;
  created_at: string;
  expires_at: string;
  evidence: Analysis;
  committee_report?: {
    recommended_direction: string;
    confidence?: string;
    supporting_arguments: string[];
    opposing_arguments: string[];
    risks: string[];
    evidence_citations?: { claim: string; citation_ref: string }[];
    limitations?: string[];
  };
};
export type Connections = {
  brokers: {
    name: string;
    status: string;
    mode: string;
    available: boolean;
    capabilities: string[];
  }[];
  manual: { name: string; status: string; mode: string };
  credentials_accepted: boolean;
  order_execution_supported: boolean;
};
export type CommitteeDiscussion = {
  state: string;
  overall: string;
  review_kind: string;
  confidence: string;
  perspectives: {
    name: string;
    view: string;
    key_reason: string;
    data_limitations: string;
    evidence_references: { citation_ref: string; claim: string }[];
  }[];
  supporting_case: string[];
  opposing_case: string[];
  key_risks: string[];
  data_limitations: string[];
  what_changes_mind: string[];
  alternatives: string[];
  modification: string;
  questions: { question: string; answer: string }[];
};
export type Overview = {
  active_candidate?: Candidate | null;
  strategy?: {
    version_id: string;
    approval: string;
    targets: {
      asset_id: string | null;
      symbol: string;
      weight: string;
      status: string;
      metadata: Record<string, string>;
    }[];
  } | null;
  committee_discussion?: CommitteeDiscussion;
  snapshot: {
    valuation: {
      total_value: string | null;
      base_currency: string;
      status: string;
      as_of: string;
      data_mode?: string;
      reasons: string[];
    };
    invested_value: string | null;
    cash_value: string | null;
    positions: {
      id: string;
      asset_id: string;
      symbol: string;
      kind: string;
      value: string | null;
      weight: string | null;
      quality: string;
    }[];
    configuration: {
      monthly_amount: string;
      monthly_currency: string;
      targets: { asset_id: string; symbol: string; weight: string }[];
    } | null;
    accounts: { id: string; name: string; source: string; currency: string }[];
    candidates: Candidate[];
  };
  analysis: Analysis | null;
  unavailable_reason: string | null;
  current_review: boolean;
  connections: Connections;
};
export async function ownerApi<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`/api/${path}`, {
    method: body === undefined ? "GET" : "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error(
      data.detail ?? "Please refresh and review your information.",
    );
  }
  return r.json();
}
export const amount = (value: string | null | undefined, currency = "USD") =>
  value == null
    ? "Not available"
    : `${currency} ${Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
export const pct = (value: string | null | undefined) =>
  value == null
    ? "Not available"
    : `${Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 })}%`;
export const planStatus = (status?: string) =>
  ({
    confirmed: "Demo plan approved",
    draft: "Awaiting your decision",
    rejected: "Rejected",
    archived: "Archived",
    not_reviewed: "Not reviewed",
  })[status ?? ""] ?? "No plan prepared";
export const committeeOpinion = (direction?: string) =>
  direction === "aligned_with_policy"
    ? "APPROVE"
    : direction === "not_aligned_with_policy"
      ? "REJECT"
      : "HOLD";
export function reasonFor(row: PlanRow) {
  if (Number(row.buy_amount) > 0)
    return "Below target — new capital fills this gap.";
  if (Number(row.overweight) > 0)
    return "Above target — no additional purchase proposed.";
  if (Number(row.underweight) > 0)
    return "Below target — no capital assigned in this proposal.";
  return "At target — no additional purchase proposed.";
}
export function planExplanation(rows: PlanRow[]) {
  const receiving = rows
    .filter((r) => Number(r.buy_amount) > 0)
    .map((r) => r.symbol);
  const above = rows
    .filter((r) => Number(r.overweight) > 0)
    .map((r) => r.symbol);
  return `${receiving.length ? `New capital is directed to ${receiving.join(", ")} to reduce allocation gaps.` : "No purchases are proposed with the available contribution."}${above.length ? ` ${above.join(", ")} ${above.length === 1 ? "is" : "are"} above target and receive no additional capital.` : ""} No selling is required.`;
}

export function ownerFinding(detail: string, data: Overview) {
  const ids = [
    ...data.snapshot.positions.map((p) => ({
      id: p.asset_id,
      symbol: p.symbol,
    })),
    ...(data.snapshot.configuration?.targets ?? []).map((t) => ({
      id: t.asset_id,
      symbol: t.symbol,
    })),
  ];
  return detail.replace(
    /[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/gi,
    (id) => ids.find((p) => p.id === id)?.symbol ?? "asset",
  );
}

export const committeeText = (text: string) =>
  text
    .replace(/^\[model inference\]\s*/i, "")
    .replace(/^SIMULATED COMMITTEE:\s*/i, "");

export function candidateLifecycle(
  analysis: Analysis | null,
  candidate?: Candidate | null,
) {
  if (candidate?.decision_status === "rejected") return "REJECTED";
  if (
    candidate?.decision_status === "confirmed" ||
    candidate?.decision_status === "archived"
  )
    return "APPROVED";
  if (!analysis) return "NOT EVALUATED";
  if (
    analysis.guardian.status === "BLOCKED" ||
    analysis.policy.status === "BLOCKED"
  )
    return "BLOCKED";
  if (!analysis.recommendation_ready) return "NOT EVALUATED";
  if (
    candidate?.committee_status === "running" ||
    candidate?.committee_status === "queued"
  )
    return "REVIEWING";
  if (candidate?.committee_status === "completed")
    return candidate.committee_report?.recommended_direction ===
      "aligned_with_policy" && candidate.decision_status === "draft"
      ? "READY_FOR_DECISION"
      : "HOLD";
  return "CANDIDATE";
}
