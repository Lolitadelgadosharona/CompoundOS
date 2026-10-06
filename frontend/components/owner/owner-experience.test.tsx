import { afterEach, expect, it, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import OwnerDashboard from "./dashboard";
import OwnerAccounts from "./accounts";
import OwnerDecisions from "./decisions";
import OwnerInvestmentPlan from "./investment-plan";
import OwnerNavigation from "./navigation";
import PreviewNotice from "./preview-notice";
import type { Overview } from "../../lib/owner-data";
import { wealthScenario } from "../../lib/wealth-scenario";
vi.mock("next/navigation", () => ({ usePathname: () => "/" }));
vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...rest
  }: {
    children: React.ReactNode;
    href: string;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));
const data: Overview = {
  snapshot: {
    valuation: {
      total_value: "100000",
      base_currency: "USD",
      status: "COMPLETE",
      as_of: "2026-10-06T12:00:00Z",
      data_mode: "DEMO",
      reasons: [],
    },
    invested_value: "99000",
    cash_value: "1000",
    positions: [
      {
        id: "p",
        asset_id: "vti",
        symbol: "VTI",
        kind: "position",
        value: "99000",
        weight: "99",
        quality: "DEMO",
      },
    ],
    configuration: {
      monthly_amount: "10000",
      monthly_currency: "CNY",
      targets: [{ asset_id: "vti", symbol: "VTI", weight: "100" }],
    },
    accounts: [],
    candidates: [],
  },
  analysis: {
    as_of: "2026-10-06T12:00:00Z",
    valuation: { base_currency: "USD" },
    recommendation_ready: true,
    plan: {
      new_capital: "1400",
      retained_cash: "0",
      reason: "engine",
      rows: [
        {
          asset_id: "vti",
          symbol: "VTI",
          current_weight: "99",
          target_weight: "100",
          absolute_drift: "-1",
          underweight: "1",
          overweight: "0",
          buy_amount: "1400",
          post_weight: "100",
        },
      ],
    },
    policy: { status: "PASS", findings: [] },
    guardian: {
      status: "WARNING",
      findings: [
        {
          check: "sector",
          detail: "Unclassified sector warning",
          severity: "warning",
        },
      ],
    },
    monthly_contribution: { amount: "10000", currency: "CNY" },
  },
  current_review: false,
  unavailable_reason: null,
  connections: {
    brokers: ["Interactive Brokers", "Fidelity", "Charles Schwab"].map(
      (name) => ({
        name,
        status: "NOT_CONNECTED",
        mode: "READ_ONLY",
        available: false,
        capabilities: ["ACCOUNT_READ"],
      }),
    ),
    manual: {
      name: "Manual Portfolio",
      status: "CONNECTED",
      mode: "LOCAL_RECORDS",
    },
    credentials_accepted: false,
    order_execution_supported: false,
  },
};
function mockFetch(extra?: unknown) {
  const fetchMock = vi
    .fn()
    .mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        json: async () =>
          url.endsWith("/connections")
            ? data.connections
            : url.endsWith("/decisions")
              ? { items: extra ?? [] }
              : data,
      }),
    );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
it("renders wealth, actual contribution-engine proposal, allocation and safeguards", async () => {
  mockFetch();
  render(<OwnerDashboard />);
  await screen.findByText("Your wealth, in perspective.");
  expect(screen.getByText("Total Portfolio Value")).toBeTruthy();
  expect(screen.getAllByText("CNY 10,000").length).toBeGreaterThan(0);
  expect(screen.getAllByText("USD 1,400").length).toBeGreaterThan(0);
  expect(screen.getByText("Underweight")).toBeTruthy();
  expect(screen.getByText("PASS")).toBeTruthy();
  expect(screen.getByText("WARNING")).toBeTruthy();
  expect(screen.getByText("HOLD")).toBeTruthy();
  expect(
    screen
      .getByRole("link", { name: "Review Investment Plan" })
      .getAttribute("href"),
  ).toBe("/investment-plan");
  expect(screen.queryByText(/SPRINT/)).toBeNull();
});
it("never invents performance or presents educational scenarios as forecasts", async () => {
  mockFetch();
  render(<OwnerDashboard />);
  await screen.findByText("Your wealth, in perspective.");
  expect(screen.getAllByText("Not available").length).toBeGreaterThan(3);
  expect(screen.getAllByText(/SCENARIO.*NOT FORECAST/).length).toBeGreaterThan(
    2,
  );
  fireEvent.change(screen.getByLabelText("Annual return assumption"), {
    target: { value: "6" },
  });
  expect(
    (screen.getByLabelText("Annual return assumption") as HTMLSelectElement)
      .value,
  ).toBe("6");
});
it("shows unavailable valuations without fabricating zeros", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue({
        ok: true,
        json: async () => ({
          ...data,
          snapshot: {
            ...data.snapshot,
            valuation: { ...data.snapshot.valuation, total_value: null },
            invested_value: null,
            cash_value: null,
          },
          analysis: null,
        }),
      }),
  );
  render(<OwnerDashboard />);
  await screen.findByText("Your wealth, in perspective.");
  expect(screen.getAllByText("Not available").length).toBeGreaterThan(3);
  expect(screen.getByText(/investment plan is not available/)).toBeTruthy();
});
it("shows read-only disconnected brokers and never sends a connect/order request", async () => {
  const f = mockFetch();
  render(<OwnerAccounts />);
  await screen.findByText("Interactive Brokers");
  expect(screen.getAllByText("Not Connected").length).toBe(3);
  expect(screen.getAllByText("READ ONLY · PLANNED").length).toBe(3);
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.getByText("Order execution is not supported.")).toBeTruthy();
  expect(f.mock.calls.every((call) => call[1].method === "GET")).toBe(true);
});
it("shows Owner decision history instead of raw audit rows", async () => {
  mockFetch([
    {
      id: "d",
      title: "PREVIEW contribution plan",
      status: "confirmed",
      created_at: "2026-10-06T12:00:00Z",
    },
  ]);
  render(<OwnerDecisions />);
  await screen.findByText("Demo plan approved");
  expect(screen.getByText("Monthly contribution plan")).toBeTruthy();
  expect(screen.getByRole("button", { name: "View decision" })).toBeTruthy();
  expect(screen.queryByText("AuditEvent")).toBeNull();
});
it("keeps approval unavailable until actual Committee validation", async () => {
  mockFetch();
  render(<OwnerInvestmentPlan />);
  await screen.findByText("Proposed purchases");
  expect(
    screen.queryByRole("button", { name: "APPROVE DEMO PLAN" }),
  ).toBeNull();
  expect(
    screen.getByText("SIMULATED COMMITTEE · NOT REAL AI ANALYSIS"),
  ).toBeTruthy();
  expect(
    screen.getByRole("button", { name: "Prepare DEMO plan for review" }),
  ).toBeTruthy();
});
it("offers coherent navigation with household inside Settings", () => {
  render(<OwnerNavigation />);
  expect(screen.getByText("AI FAMILY OFFICE")).toBeTruthy();
  for (const name of [
    "Dashboard",
    "Portfolio",
    "Investment Plan",
    "Committee",
    "Policy",
    "Accounts",
    "Decisions",
    "Settings",
  ])
    expect(screen.getByRole("link", { name })).toBeTruthy();
  expect(screen.queryByRole("link", { name: "Household" })).toBeNull();
});
it("scenario arithmetic is isolated and handles zero assumptions without invented amounts", () => {
  expect(wealthScenario(100, 10, 0, 1)).toBe(220);
  expect(wealthScenario(100, 0, 8, 10)).toBeCloseTo(
    100 * Math.pow(1.08, 10),
    6,
  );
  expect(wealthScenario(NaN, 10, 8, 10)).toBeNull();
  expect(wealthScenario(100, -1, 8, 10)).toBeNull();
});

it("retains explicit Preview, DEMO, simulated and no-trades warnings", () => {
  render(<PreviewNotice />);
  expect(screen.getByRole("note").textContent).toContain("OWNER PREVIEW");
  expect(screen.getByRole("note").textContent).toContain("DEMO DATA");
  expect(screen.getByRole("note").textContent).toContain("SIMULATED COMMITTEE");
  expect(screen.getByRole("note").textContent).toContain(
    "NO REAL INVESTMENT RECOMMENDATION",
  );
  expect(screen.getByRole("note").textContent).toContain(
    "NO TRADES WILL BE EXECUTED",
  );
});

it("preserves Audit-only rejected proposals in history without fabricating Journal records", async () => {
  const candidate = {
    id: "rejected-demo",
    decision_status: "rejected",
    committee_status: "not_requested",
    content_hash: "hash",
    created_at: "2026-10-06T12:00:00Z",
    expires_at: "2026-10-06T13:00:00Z",
    evidence: data.analysis!,
  };
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation((url: string) =>
        Promise.resolve({
          ok: true,
          json: async () =>
            url.endsWith("/decisions")
              ? { items: [] }
              : {
                  ...data,
                  snapshot: { ...data.snapshot, candidates: [candidate] },
                },
        }),
      ),
  );
  render(<OwnerDecisions />);
  await screen.findByText("Rejected demo proposal");
  expect(screen.getByText("Rejected")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "View decision" }));
  expect(screen.getByText(/rejection is preserved in Audit/)).toBeTruthy();
});
