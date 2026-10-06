import { afterEach, expect, it, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import CommitteeDiscussionPanel from "./committee-discussion";
import { AllocationTable } from "./shared";
import OwnerDashboard from "./dashboard";
import { CommitteeDiscussion, Overview } from "../../lib/owner-data";
vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));
const overview: Overview = {
  snapshot: {
    valuation: {
      total_value: "100000",
      base_currency: "USD",
      status: "COMPLETE",
      as_of: "2026-10-06",
      reasons: [],
    },
    invested_value: "100000",
    cash_value: "0",
    positions: [
      {
        id: "apple",
        asset_id: "a",
        symbol: "AAPL",
        kind: "position",
        value: "20000",
        weight: "20",
        quality: "DEMO",
      },
    ],
    configuration: {
      monthly_amount: "10000",
      monthly_currency: "CNY",
      targets: [{ asset_id: "v", symbol: "VTI", weight: "100" }],
    },
    accounts: [],
    candidates: [],
  },
  analysis: null,
  unavailable_reason: "Missing evidence",
  current_review: false,
  connections: {
    brokers: [],
    manual: { name: "Manual", status: "CONNECTED", mode: "LOCAL" },
    credentials_accepted: false,
    order_execution_supported: false,
  },
};
const report: CommitteeDiscussion = {
  state: "BLOCKED",
  overall: "BLOCKED",
  review_kind: "DISCUSSION ONLY — GOVERNANCE REVIEW INCOMPLETE",
  confidence: "NOT AVAILABLE",
  perspectives: [
    "LONG-TERM INVESTOR",
    "INDEX INVESTOR",
    "RISK MANAGER",
    "MACRO ANALYST",
    "QUANT ANALYST",
    "DEVIL'S ADVOCATE",
  ].map((name) => ({
    name,
    view: name === "MACRO ANALYST" ? "NOT EVALUATED" : "CAUTION",
    key_reason: "Supplied evidence only",
    data_limitations: "No current macro evidence",
    evidence_references: [],
  })),
  supporting_case: ["Contribution discipline"],
  opposing_case: ["Incomplete exposures"],
  key_risks: ["Known concentration violation"],
  data_limitations: ["Missing look-through"],
  what_changes_mind: ["Fresh governance"],
  alternatives: ["Retain contribution as cash"],
  modification: "DEFERRED — changes require a new candidate and new review",
  questions: [
    {
      question: "What evidence is missing?",
      answer: "Look-through and macro evidence unavailable",
    },
  ],
};
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("separates imported non-target holdings from strategy without a sell action", () => {
  render(<AllocationTable data={overview} />);
  expect(screen.getByText(/NON-TARGET HOLDING/)).toBeTruthy();
  expect(screen.getAllByText(/0%/).length).toBeGreaterThan(0);
  expect(screen.queryByRole("button", { name: /sell/i })).toBeNull();
});
it("renders distinct perspectives, unknown macro and no invented confidence", () => {
  render(<CommitteeDiscussionPanel report={report} />);
  for (const p of report.perspectives)
    expect(screen.getByRole("heading", { name: p.name })).toBeTruthy();
  expect(screen.getByText("NOT EVALUATED")).toBeTruthy();
  expect(screen.getByText(/Confidence: NOT AVAILABLE/)).toBeTruthy();
  expect(screen.getByText(/GOVERNANCE REVIEW INCOMPLETE/)).toBeTruthy();
  expect(
    screen.getByRole("button", { name: /override/ }).hasAttribute("disabled"),
  ).toBe(true);
});
it("answers locally and cannot silently change the candidate or call an external model", () => {
  const f = vi.fn();
  vi.stubGlobal("fetch", f);
  render(<CommitteeDiscussionPanel report={report} />);
  fireEvent.click(
    screen.getByRole("button", { name: "What evidence is missing?" }),
  );
  expect(screen.getByRole("status").textContent).toContain(
    "macro evidence unavailable",
  );
  expect(f).not.toHaveBeenCalled();
});
for (const state of ["BLOCKED", "NOT EVALUATED", "READY_FOR_DECISION", "HOLD"])
  it(`prominent Action Required reflects ${state}`, async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ...overview,
          committee_discussion: { ...report, state },
        }),
      }),
    );
    render(<OwnerDashboard />);
    await screen.findByRole("region", { name: "Action required" });
    const section = screen.getByRole("region", { name: "Action required" });
    expect(section.textContent).toContain(state);
    expect(section.querySelector("a")?.getAttribute("href")).toBe(
      "/investment-plan#governance",
    );
  });

it("keeps a persisted blocked candidate visible after reload without enabling approval", async () => {
  const { default: OwnerInvestmentPlan } = await import("./investment-plan");
  const a = {
    as_of: "2026-10-06",
    recommendation_ready: false,
    plan: {
      new_capital: "100",
      retained_cash: "0",
      reason: "engine",
      rows: [],
    },
    policy: { status: "PASS", findings: [] },
    guardian: { status: "BLOCKED", findings: [] },
    monthly_contribution: { amount: "10000", currency: "CNY" },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...overview,
        analysis: a,
        active_candidate: {
          id: "candidate",
          decision_status: "not_reviewed",
          committee_status: "not_requested",
          content_hash: "hash",
          created_at: "2026-10-06",
          expires_at: "2026-10-07",
          evidence: a,
        },
      }),
    }),
  );
  render(<OwnerInvestmentPlan />);
  await screen.findByRole("button", { name: "Approve Plan" });
  expect(
    screen
      .getByRole("button", { name: "Approve Plan" })
      .hasAttribute("disabled"),
  ).toBe(true);
  expect(
    screen
      .getByRole("button", {
        name: "Review with Investment Committee",
      })
      .hasAttribute("disabled"),
  ).toBe(true);
  expect(screen.getByRole("button", { name: "Reject Plan" })).toBeTruthy();
});
