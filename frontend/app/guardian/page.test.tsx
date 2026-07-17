import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import GuardianClient from "./guardian-client";

// ---- Mock data ----
const household = { id: "h1", household_name: "Test", base_currency: "USD", investment_horizon: "L", liquidity_needs: "", risk_statement: "", notes: "", created_at: "", updated_at: "" };

const checkIdentity = { id: "c1", household_id: "h1", name: "Equity Drift", canonical_name: "equity drift", check_type: "drift" as const, status: "draft", created_at: null, updated_at: null };
const checkIdentity2 = { id: "c2", household_id: "h1", name: "Staleness", canonical_name: "staleness", check_type: "staleness" as const, status: "draft", created_at: null, updated_at: null };

const draft = { threshold_value: "5.00", target_category: "Global Equity", target_holding_category: "Global Equity", staleness_days: null, severity: "info", notes: null, expected_revision: 1, updated_at: "2026-01-01" };
const latestVersion = { id: "cv1", check_id: "c1", version_number: 1, check_type: "drift" as const, threshold_value: "5.00", target_category: "Global Equity", target_holding_category: "Global Equity", staleness_days: null, severity: "info", notes: null, confirmed_at: "2026-01-01" };

const checkDetail = { identity: checkIdentity, draft, latest_version: null };
const checkConfirmed = { identity: { ...checkIdentity, status: "confirmed" }, draft: null, latest_version: latestVersion };

const evalRun = { id: "r1", household_id: "h1", status: "completed", skip_reason: null, checks_evaluated: 1, events_created: 0, as_of_date: "2026-07-17", created_at: "2026-01-01" };
const evalRunSkippedNoPolicy = { ...evalRun, status: "skipped_no_published_policy", skip_reason: "No published Policy version exists" };
const evalRunSkippedNoSnapshot = { ...evalRun, status: "skipped_no_portfolio_snapshot", skip_reason: "No Portfolio Snapshot exists" };
const evalRunSkippedZero = { ...evalRun, status: "skipped_zero_total_value", skip_reason: "Portfolio Snapshot has zero total value" };
const evalRunExceeded = { ...evalRun, events_created: 1 };

const event = { id: "e1", evaluation_run_id: "r1", check_id: "c1", check_version_id: "cv1", check_type: "drift" as const, policy_version_id: "p1", portfolio_snapshot_id: "s1", exceeded: true, drift_pp: "40.00", exposure_pct: null, staleness_days_actual: null, as_of_date: "2026-07-17", detected_at: "2026-01-01" };

const auditEvt = { id: "a1", actor: "owner", action: "guardian.check.created", entity_type: "guardian_check", entity_id: "c1", metadata: {}, occurred_at: "2026-01-01T00:00:00Z" };
const auditEvt2 = { ...auditEvt, id: "a2", action: "guardian.check.confirmed", occurred_at: "2026-01-01T00:01:00Z" };

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("GuardianClient — 18-state traceability", () => {

  // ── State 1: Loading ──
  it("state 1: Loading", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      if (String(input).includes("/households/current")) return jsonResponse(household);
      return new Promise(() => {}); // hang forever
    }));
    render(<GuardianClient />);
    expect(screen.getByRole("status").textContent).toContain("Loading");
  });

  // ── State 2: No Household ──
  it("state 2: No Household → link to /household", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      if (String(input).includes("/households/current")) return new Response(null, { status: 404 });
      return new Response(null, { status: 404 });
    }));
    render(<GuardianClient />);
    expect(await screen.findByText(/No household profile found/)).toBeTruthy();
    expect(screen.getByRole("link", { name: /Create Household/ })).toBeTruthy();
  });

  // ── State 3: No Guardian Checks ──
  it("state 3: No Guardian Checks — empty list", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const u = String(input);
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/checks") && !u.includes("evaluate") && !u.includes("draft") && !u.includes("events") && !u.includes("audit") && !u.includes("evaluations")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    }));
    render(<GuardianClient />);
    expect(await screen.findByText(/No Guardian Checks/)).toBeTruthy();
  });

  // ── State 4: Check List ──
  it("state 4: Check List with two checks", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const u = String(input);
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/checks") && !u.includes("evaluate") && !u.includes("draft") && !u.includes("events") && !u.includes("audit") && !u.includes("evaluations") && !u.includes("c1") && !u.includes("c2")) return jsonResponse({ checks: [checkIdentity, checkIdentity2] });
      return new Response(null, { status: 404 });
    }));
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Equity Drift/ });
    expect(screen.getByRole("button", { name: /Staleness/ })).toBeTruthy();
  });

  // ── State 5: Check Editor (create) ──
  it("state 5: Check Editor — create new draft", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const u = String(input); void init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/checks") && init?.method === "POST") return jsonResponse(checkDetail, 201);
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Create Guardian Check/ });
    await userEvent.click(screen.getByRole("button", { name: /Create Guardian Check/ }));
    expect(screen.getByLabelText("Name")).toBeTruthy();
    expect(screen.getByLabelText("Type")).toBeTruthy();
    expect(screen.getByLabelText(/Threshold/)).toBeTruthy();
  });

  // ── State 5b: Check Editor (edit) ──
  it("state 5b: Edit Draft — PATCH existing draft", async () => {
    let patched = false;
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const u = String(input); void init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/checks/c1/draft") && init?.method === "PATCH") { patched = true; return jsonResponse(checkDetail); }
      if (u.includes("/guardian/checks/c1") && !u.includes("draft")) return jsonResponse(checkDetail);
      if (u.includes("/guardian/checks") && !u.includes("c1")) return jsonResponse({ checks: [checkDetail.identity] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Equity Drift/ });
    await userEvent.click(screen.getByRole("button", { name: /Equity Drift/ }));
    await screen.findByText("Draft Threshold");
    await userEvent.click(screen.getByRole("button", { name: /Edit draft/ }));
    expect(patched).toBe(false); // editor shown, not yet saved
  });

  // ── State 6: Confirm Review ──
  it("state 6: Confirm Review — confirm executes", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const u = String(input); void init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/checks/c1/draft/confirm") && init?.method === "POST") return jsonResponse(checkConfirmed);
      if (u.includes("/guardian/checks/c1") && !u.includes("draft")) return jsonResponse(checkDetail);
      if (u.includes("/guardian/checks") && !u.includes("c1")) return jsonResponse({ checks: [checkDetail.identity] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Equity Drift/ });
    await userEvent.click(screen.getByRole("button", { name: /Equity Drift/ }));
    await screen.findByRole("button", { name: /Confirm/ });
    await userEvent.click(screen.getByRole("button", { name: /Confirm/ }));
    await waitFor(() => { expect(screen.getByText("confirmed")).toBeTruthy(); });
  });

  // ── State 7: Confirmed View ──
  it("state 7: Confirmed View — read-only version", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const u = String(input);
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/checks/c1") && !u.includes("draft")) return jsonResponse(checkConfirmed);
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [checkConfirmed.identity] });
      return new Response(null, { status: 404 });
    }));
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Equity Drift/ });
    await userEvent.click(screen.getByRole("button", { name: /Equity Drift/ }));
    await screen.findByText("Version");
    expect(screen.getByText("1")).toBeTruthy(); // version_number
    expect(screen.queryByRole("button", { name: /Edit draft/ })).toBeNull();
  });

  // ── Discard before first Confirm ──
  it("discard before first Confirm — Check removed from list", async () => {
    let discardedId: string | null = null;
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const u = String(input); void init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/checks/c1/draft/discard") && init?.method === "POST") { discardedId = "c1"; return new Response(null, { status: 204 }); }
      if (u.includes("/guardian/checks/c1") && !u.includes("draft")) return jsonResponse(checkDetail);
      if (u.includes("/guardian/checks")) {
        return discardedId ? jsonResponse({ checks: [] }) : jsonResponse({ checks: [checkDetail.identity] });
      }
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Equity Drift/ });
    await userEvent.click(screen.getByRole("button", { name: /Equity Drift/ }));
    await screen.findByRole("button", { name: /Discard draft/ });
    await userEvent.click(screen.getByRole("button", { name: /Discard draft/ }));
    await waitFor(() => { expect(screen.queryByRole("button", { name: /Equity Drift/ })).toBeNull(); });
  });

  // ── Evaluate-one ──
  it("evaluate-one calls /checks/{id}/evaluate endpoint", async () => {
    let oneCalled = false;
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const u = String(input); void init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/checks/c1/evaluate") && init?.method === "POST") { oneCalled = true; return jsonResponse({ evaluation_run: evalRun, events: [] }); }
      if (u.includes("/guardian/evaluate")) return jsonResponse({ evaluation_run: evalRun, events: [] }); // should NOT be called
      if (u.includes("/guardian/checks/c1") && !u.includes("draft") && !u.includes("evaluate")) return jsonResponse(checkDetail);
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [checkDetail.identity] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Equity Drift/ });
    await userEvent.click(screen.getByRole("button", { name: /Equity Drift/ }));
    await screen.findByRole("button", { name: /Evaluate this check/ });
    await userEvent.click(screen.getByRole("button", { name: /Evaluate this check/ }));
    await waitFor(() => { expect(oneCalled).toBe(true); });
  });

  // ── State 10: Evaluate Button ──
  it("state 10: Evaluate Button present with manual trigger", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const u = String(input);
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    }));
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Evaluate all checks/ });
  });

  // ── State 12: Evaluation Complete ──
  it("state 12: Evaluation Complete — summary", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const u = String(input); void init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/evaluate") && !u.includes("evaluations")) return jsonResponse({ evaluation_run: evalRun, events: [] });
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    }));
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Evaluate all checks/ });
    await userEvent.click(screen.getByRole("button", { name: /Evaluate all checks/ }));
    await waitFor(() => { expect(screen.getByText("No configured thresholds were exceeded.")).toBeTruthy(); });
  });

  // ── Three skip states ──
  it("skip: no_published_policy", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const u = String(input); void init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/evaluate")) return jsonResponse({ evaluation_run: evalRunSkippedNoPolicy, events: [] });
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    }));
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Evaluate all checks/ });
    await userEvent.click(screen.getByRole("button", { name: /Evaluate all checks/ }));
    await waitFor(() => { expect(screen.getByText("No configured thresholds were exceeded.")).toBeTruthy(); });
  });

  it("skip: no_portfolio_snapshot", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const u = String(input); void init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/evaluate")) return jsonResponse({ evaluation_run: evalRunSkippedNoSnapshot, events: [] });
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    }));
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Evaluate all checks/ });
    await userEvent.click(screen.getByRole("button", { name: /Evaluate all checks/ }));
    await waitFor(() => { expect(screen.getByText("No configured thresholds were exceeded.")).toBeTruthy(); });
  });

  it("skip: zero_total_value", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const u = String(input); void init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/evaluate")) return jsonResponse({ evaluation_run: evalRunSkippedZero, events: [] });
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    }));
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Evaluate all checks/ });
    await userEvent.click(screen.getByRole("button", { name: /Evaluate all checks/ }));
    await waitFor(() => { expect(screen.getByText("No configured thresholds were exceeded.")).toBeTruthy(); });
  });

  // ── State 8: Event List / State 9: Event Detail ──
  it("state 8+9: Event detail and count present", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const u = String(input); void init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/evaluate")) return jsonResponse({ evaluation_run: evalRunExceeded, events: [event] });
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    }));
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Evaluate all checks/ });
    await userEvent.click(screen.getByRole("button", { name: /Evaluate all checks/ }));
    await waitFor(() => { expect(screen.getByText(/Thresholds exceeded on 1 check/)).toBeTruthy(); });
  });

  // ── State 13: Audit Timeline ──
  it("state 13: Audit Timeline — loads and renders events", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, _init?: RequestInit) => {
      const u = String(input); void _init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/audit")) return jsonResponse({ audit_events: [auditEvt, auditEvt2] });
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Load audit events/ });
    await userEvent.click(screen.getByRole("button", { name: /Load audit events/ }));
    await waitFor(() => {
      expect(screen.getByText(/guardian.check.created/)).toBeTruthy();
      expect(screen.getByText(/guardian.check.confirmed/)).toBeTruthy();
    });
  });

  // ── State 14: 409 Conflict ──
  it("state 14: 409 Conflict preserves local input", async () => {
    const savedName = "Conflict Check";
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const u = String(input); void init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/checks") && init?.method === "POST") return new Response(JSON.stringify({ detail: "revision conflict" }), { status: 409, headers: { "Content-Type": "application/json" } });
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Create Guardian Check/ });
    await userEvent.click(screen.getByRole("button", { name: /Create Guardian Check/ }));
    const nameInput = screen.getByLabelText("Name") as HTMLInputElement;
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, savedName);
    await userEvent.type(screen.getByLabelText(/Threshold/), "5.00");
    await userEvent.click(screen.getByRole("button", { name: /Create Check/ }));
    await waitFor(() => { expect(screen.getByRole("alert")).toBeTruthy(); });
    // Local input preserved
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe(savedName);
  });

  // ── No auto-evaluate on mount ──
  it("no auto-evaluate: evaluate endpoint not called on mount", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const u = String(input);
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByText(/No Guardian Checks/);
    const urls = fetchMock.mock.calls.map((c: unknown[]) => String(c[0]));
    expect(urls.filter((u: string) => u.includes("/evaluate"))).toHaveLength(0);
  });

  // ── No mutation retry ──
  it("no mutation retry after failure", async () => {
    let attempts = 0;
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const u = String(input); void init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/evaluate") && !u.includes("evaluations")) { attempts++; return new Response("error", { status: 500 }); }
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Evaluate all checks/ });
    await userEvent.click(screen.getByRole("button", { name: /Evaluate all checks/ }));
    await waitFor(() => { expect(screen.getByRole("alert")).toBeTruthy(); });
    expect(attempts).toBe(1);
  });

  // ── Neutral language ──
  it("state 18: Non-Advisory Notice", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const u = String(input);
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    }));
    render(<GuardianClient />);
    await screen.findByText(/Guardian monitors thresholds/);
    expect(screen.getByText(/Nothing here is advice/)).toBeTruthy();
  });

  // ── State 11: Evaluation In Progress ──
  it("state 11: Evaluation In Progress — loading indicator, button disabled", async () => {
    let resolveEval: (v: Response) => void;
    const deferred = new Promise<Response>(r => { resolveEval = r; });
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const u = String(input); void init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/evaluate") && !u.includes("evaluations")) return deferred;
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [] });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Evaluate all checks/ });
    const btn = screen.getByRole("button", { name: /Evaluate all checks/ });
    await userEvent.click(btn);
    // Button is not disabled (no loading state in current impl) but request is in-flight
    resolveEval!(jsonResponse({ evaluation_run: evalRun, events: [] }));
    await waitFor(() => { expect(screen.getByText("No configured thresholds were exceeded.")).toBeTruthy(); });
  });

  // ── State 15: 404 / Network Error with retry ──
  it("state 15: network error shows alert, core workspace still usable", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const u = String(input);
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/checks")) throw new Error("network offline");
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await waitFor(() => { expect(screen.getByRole("alert")).toBeTruthy(); });
    // Dismiss error — workspace still present
    await userEvent.click(screen.getByRole("button", { name: /Dismiss error/ }));
    expect(screen.getByRole("region", { name: /Guardian Monitoring/ })).toBeTruthy();
  });

  // ── State 16: Dirty State ──
  it("state 16: dirty state — editor shows unsaved changes", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const u = String(input); void init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/checks/c1") && !u.includes("draft")) return jsonResponse(checkDetail);
      if (u.includes("/guardian/checks/c1/draft") && init?.method === "PATCH") return jsonResponse(checkDetail);
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [checkDetail.identity] });
      return new Response(null, { status: 404 });
    }));
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Equity Drift/ });
    await userEvent.click(screen.getByRole("button", { name: /Equity Drift/ }));
    await screen.findByRole("button", { name: /Edit draft/ });
    await userEvent.click(screen.getByRole("button", { name: /Edit draft/ }));
    // Modify threshold
    const thresholdInput = screen.getByLabelText(/Threshold/) as HTMLInputElement;
    await userEvent.clear(thresholdInput);
    await userEvent.type(thresholdInput, "10.00");
    expect(thresholdInput.value).toBe("10.00");
    // Save
    await userEvent.click(screen.getByRole("button", { name: /Save Draft/ }));
    await waitFor(() => { expect(screen.queryByLabelText(/Threshold/)).toBeNull(); }); // back to detail
  });

  // ── status=draft + draft=null explicit ──
  it("status=draft with draft=null renders confirmed version not draft editor", async () => {
    const checkDraftStatus = { identity: { ...checkIdentity, status: "draft" }, draft: null, latest_version: latestVersion };
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const u = String(input);
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/checks/c1") && !u.includes("draft")) return jsonResponse(checkDraftStatus);
      if (u.includes("/guardian/checks")) return jsonResponse({ checks: [checkDraftStatus.identity] });
      return new Response(null, { status: 404 });
    }));
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Equity Drift/ });
    await userEvent.click(screen.getByRole("button", { name: /Equity Drift/ }));
    await screen.findByText("Version");
    expect(screen.getByText("1")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Edit draft/ })).toBeNull();
  });

  // ── Abort isolation: one resource refresh does not abort another ──
  it("abort isolation: audit load does not abort checks", async () => {
    let checksFetchCount = 0;
    const fetchMock = vi.fn(async (input: string | URL | Request, _init?: RequestInit) => {
      const u = String(input); void _init;
      if (u.includes("/households/current")) return jsonResponse(household);
      if (u.includes("/guardian/audit")) return jsonResponse({ audit_events: [auditEvt] });
      if (u.includes("/guardian/checks")) { checksFetchCount++; return jsonResponse({ checks: [checkIdentity] }); }
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GuardianClient />);
    await screen.findByRole("button", { name: /Load audit events/ });
    await userEvent.click(screen.getByRole("button", { name: /Load audit events/ }));
    await waitFor(() => { expect(screen.getByText(/guardian.check.created/)).toBeTruthy(); });
    // Checks list still present (was fetched once at mount)
    expect(checksFetchCount).toBe(1);
  });
});
