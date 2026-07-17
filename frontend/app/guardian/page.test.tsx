import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import GuardianClient from "./guardian-client";

const household = { id: "h1", household_name: "Test", base_currency: "USD", investment_horizon: "L", liquidity_needs: "", risk_statement: "", notes: "", created_at: "", updated_at: "" };
const checkIdentity = { id: "c1", household_id: "h1", name: "Equity Drift", canonical_name: "equity drift", check_type: "drift" as const, status: "draft", created_at: null, updated_at: null };
const draft = { threshold_value: "5.00", target_category: "Global Equity", target_holding_category: "Global Equity", staleness_days: null, severity: "info", notes: null, expected_revision: 1, updated_at: "2026-01-01" };
const latestVersion = { id: "cv1", check_id: "c1", version_number: 1, check_type: "drift" as const, threshold_value: "5.00", target_category: "Global Equity", target_holding_category: "Global Equity", staleness_days: null, severity: "info", notes: null, confirmed_at: "2026-01-01" };
const checkDetail = { identity: checkIdentity, draft, latest_version: null };
const checkAfterDiscard = { identity: { ...checkIdentity, status: "draft" }, draft: null, latest_version: latestVersion };
const evalRun = { id: "r1", household_id: "h1", status: "completed", skip_reason: null, checks_evaluated: 1, events_created: 0, as_of_date: "2026-07-17", created_at: "2026-01-01" };
const evalRunExceeded = { ...evalRun, events_created: 1 };
const event = { id: "e1", evaluation_run_id: "r1", check_id: "c1", check_version_id: "cv1", check_type: "drift" as const, policy_version_id: "p1", portfolio_snapshot_id: "s1", exceeded: true, drift_pp: "40.00", exposure_pct: null, staleness_days_actual: null, as_of_date: "2026-07-17", detected_at: "2026-01-01" };

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function mockHousehold(has = true) {
  return vi.fn(async (input: string | URL | Request) => {
    const url = String(input);
    if (url.includes("/api/households/current")) return has ? jsonResponse(household) : new Response(null, { status: 404 });
    return new Response(null, { status: 404 });
  });
}

function mockChecks(resp = [checkIdentity]) {
  return vi.fn(async (input: string | URL | Request) => {
    const url = String(input);
    if (url.includes("/api/households/current")) return jsonResponse(household);
    if (url.includes("/api/guardian/checks") && !url.includes("evaluate") && !url.includes("draft") && !url.includes("events") && !url.includes("audit") && !url.includes("evaluations")) {
      return jsonResponse({ checks: resp });
    }
    return new Response(null, { status: 404 });
  });
}

describe("GuardianClient", () => {
  it("renders loading state", async () => {
    vi.stubGlobal("fetch", mockHousehold());
    render(<GuardianClient />);
    expect(screen.getByRole("status").textContent).toContain("Loading");
  });

  it("renders no-household state", async () => {
    vi.stubGlobal("fetch", mockHousehold(false));
    render(<GuardianClient />);
    expect(await screen.findByText(/No household profile found/)).toBeTruthy();
  });

  it("shows empty state when no checks", async () => {
    vi.stubGlobal("fetch", mockChecks([]));
    render(<GuardianClient />);
    expect(await screen.findByText("No Guardian Checks configured.")).toBeTruthy();
  });

  it("shows checks list", async () => {
    vi.stubGlobal("fetch", mockChecks());
    render(<GuardianClient />);
    expect(await screen.findByRole("button", { name: /Check Equity Drift/ })).toBeTruthy();
  });

  it("creates a drift check", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input); void init;
      if (url.includes("/api/households/current")) return jsonResponse(household);
      if (url.includes("/api/guardian/checks") && init?.method === "POST") return jsonResponse(checkDetail, 201);
      if (url.includes("/api/guardian/checks")) return jsonResponse({ checks: [checkIdentity] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Create Guardian Check/ });
    await userEvent.click(screen.getByRole("button", { name: /Create Guardian Check/ }));
    await userEvent.type(screen.getByLabelText("Name"), "Equity Drift");
    await userEvent.type(screen.getByLabelText(/Threshold/), "5.00");
    await userEvent.click(screen.getByRole("button", { name: /Create Check/ }));
    await waitFor(() => { expect(screen.getByRole("button", { name: /Check Equity Drift/ })).toBeTruthy(); });
  });

  it("shows per-type fields for staleness", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input); void init;
      if (url.includes("/api/households/current")) return jsonResponse(household);
      if (url.includes("/api/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Create Guardian Check/ });
    await userEvent.click(screen.getByRole("button", { name: /Create Guardian Check/ }));
    await userEvent.selectOptions(screen.getByLabelText("Type"), "staleness");
    expect(screen.getByLabelText("Staleness Days")).toBeTruthy();
    expect(screen.queryByLabelText("Policy Category")).toBeNull();
  });

  it("shows draft=null + version retained after discard", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input); void init;
      if (url.includes("/api/households/current")) return jsonResponse(household);
      if (url.includes("/api/guardian/checks") && !url.includes("c1")) return jsonResponse({ checks: [checkAfterDiscard.identity] });
      if (url.includes("/api/guardian/checks/c1") && !url.includes("draft")) return jsonResponse(checkAfterDiscard);
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Check Equity Drift/ });
    await userEvent.click(screen.getByRole("button", { name: /Check Equity Drift/ }));
    await screen.findByText(/No draft/);
    expect(screen.getByText("Version")).toBeTruthy();
    expect(screen.getByText("1")).toBeTruthy();
  });

  it("evaluate-all calls evaluate endpoint", async () => {
    let evaluated = false;
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input); void init;
      if (url.includes("/api/households/current")) return jsonResponse(household);
      if (url.includes("/api/guardian/evaluate") && !url.includes("evaluations")) { evaluated = true; return jsonResponse({ evaluation_run: evalRun, events: [] }); }
      if (url.includes("/api/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Evaluate all checks/ });
    await userEvent.click(screen.getByRole("button", { name: /Evaluate all checks/ }));
    await waitFor(() => { expect(evaluated).toBe(true); });
    expect(screen.getByText("No configured thresholds were exceeded.")).toBeTruthy();
  });

  it("renders exceeded Events message", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input); void init;
      if (url.includes("/api/households/current")) return jsonResponse(household);
      if (url.includes("/api/guardian/evaluate") && !url.includes("evaluations")) return jsonResponse({ evaluation_run: evalRunExceeded, events: [event] });
      if (url.includes("/api/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Evaluate all checks/ });
    await userEvent.click(screen.getByRole("button", { name: /Evaluate all checks/ }));
    await waitFor(() => { expect(screen.getByText(/Thresholds exceeded on 1 check/)).toBeTruthy(); });
  });

  it("does not call evaluate on mount", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/api/households/current")) return jsonResponse(household);
      if (url.includes("/api/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByText("No Guardian Checks configured.");
    const calls = fetchMock.mock.calls.map((c: unknown[]) => String(c[0]));
    expect(calls.filter((c: string) => c.includes("/evaluate"))).toHaveLength(0);
  });

  it("uses neutral, non-advisory language", async () => {
    vi.stubGlobal("fetch", mockChecks([]));
    render(<GuardianClient />);
    await screen.findByText("No Guardian Checks configured.");
    expect(screen.getByText(/Nothing here is advice/)).toBeTruthy();
    expect(screen.queryByText(/rebalance|recommend/i)).toBeNull();
  });

  it("has accessible buttons with aria-labels", async () => {
    vi.stubGlobal("fetch", mockChecks());
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Create Guardian Check/ });
    expect(screen.getByRole("button", { name: /Reload checks/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Evaluate all checks/ })).toBeTruthy();
    expect(screen.getByRole("region", { name: /Guardian Monitoring/ })).toBeTruthy();
  });

  it("shows error alert on API failure", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/api/households/current")) return jsonResponse(household);
      return new Response("error", { status: 500 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await waitFor(() => { expect(screen.getByRole("alert")).toBeTruthy(); });
    expect(screen.getByRole("alert").textContent).toContain("unexpected server error");
  });

  // ---- Evaluation skip states ----

  it("shows evaluation skipped for no published policy", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input); void init;
      if (url.includes("/api/households/current")) return jsonResponse(household);
      if (url.includes("/api/guardian/evaluate") && !url.includes("evaluations")) {
        return jsonResponse({ evaluation_run: { ...evalRun, status: "skipped_no_published_policy", skip_reason: "No published Policy version exists" }, events: [] });
      }
      if (url.includes("/api/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Evaluate all checks/ });
    await userEvent.click(screen.getByRole("button", { name: /Evaluate all checks/ }));
    await waitFor(() => { expect(screen.getByText("No configured thresholds were exceeded.")).toBeTruthy(); });
  });

  // ---- Confirm review + execute ----

  it("confirms a draft check", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input); void init;
      if (url.includes("/api/households/current")) return jsonResponse(household);
      if (url.includes("/api/guardian/checks/c1/draft/confirm") && init?.method === "POST") {
        return jsonResponse({ identity: { ...checkIdentity, status: "confirmed" }, draft: null, latest_version: latestVersion });
      }
      if (url.includes("/api/guardian/checks/c1") && !url.includes("draft")) return jsonResponse(checkDetail);
      if (url.includes("/api/guardian/checks") && !url.includes("c1")) return jsonResponse({ checks: [checkDetail.identity] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Check Equity Drift/ });
    await userEvent.click(screen.getByRole("button", { name: /Check Equity Drift/ }));
    await screen.findByText("Draft Threshold");
    await userEvent.click(screen.getByRole("button", { name: /Confirm/ }));
    await waitFor(() => { expect(screen.getByText("confirmed")).toBeTruthy(); });
  });

  // ---- Category exposure editor ----

  it("shows category_exposure fields without policy category", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input); void init;
      if (url.includes("/api/households/current")) return jsonResponse(household);
      if (url.includes("/api/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Create Guardian Check/ });
    await userEvent.click(screen.getByRole("button", { name: /Create Guardian Check/ }));
    await userEvent.selectOptions(screen.getByLabelText("Type"), "category_exposure");
    expect(screen.getByLabelText("Portfolio Category")).toBeTruthy();
    expect(screen.queryByLabelText("Policy Category")).toBeNull();
    expect(screen.queryByLabelText("Staleness Days")).toBeNull();
  });

  // ---- Aborted request does not crash UI ----

  it("recovers after an aborted detail request", async () => {
    let detailCalled = false;
    const fetchMock = vi.fn(async (input: string | URL | Request, _init?: RequestInit) => {
      const url = String(input); void _init;
      if (url.includes("/api/households/current")) return jsonResponse(household);
      if (url.includes("/api/guardian/checks/c1") && !url.includes("draft")) {
        detailCalled = true;
        throw new DOMException("aborted", "AbortError");
      }
      if (url.includes("/api/guardian/checks")) return jsonResponse({ checks: [checkAfterDiscard.identity] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Check Equity Drift/ });
    await userEvent.click(screen.getByRole("button", { name: /Check Equity Drift/ }));
    await waitFor(() => { expect(detailCalled).toBe(true); });
    // UI should not crash — still showing the region
    expect(screen.getByRole("region", { name: /Guardian Monitoring/ })).toBeTruthy();
  });

  // ---- Keyboard / aria-invalid ----

  it("has aria-describedby on threshold input", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input); void init;
      if (url.includes("/api/households/current")) return jsonResponse(household);
      if (url.includes("/api/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Create Guardian Check/ });
    await userEvent.click(screen.getByRole("button", { name: /Create Guardian Check/ }));
    expect(screen.getByLabelText(/Threshold/).getAttribute("aria-describedby")).toBeTruthy();
  });
});
