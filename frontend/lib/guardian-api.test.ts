import { afterEach, describe, expect, it, vi } from "vitest";

import {
  GuardianApiError,
  GuardianNetworkError,
  createCheck,
  listChecks,
  getCheck,
  confirmCheck,
  discardCheck,
  evaluateAll,
  getAudit,
} from "./guardian-api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Guardian API client", () => {
  const checkResponse = {
    identity: { id: "c1", household_id: "h1", name: "Drift", canonical_name: "drift", check_type: "drift", status: "draft", created_at: null, updated_at: null },
    draft: { threshold_value: "5.00", target_category: "eq", target_holding_category: "eq", staleness_days: null, severity: "info", notes: null, expected_revision: 1, updated_at: "2026-01-01" },
    latest_version: null,
  };

  it("POST /api/guardian/checks creates a check", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(checkResponse, 201)));
    const result = await createCheck({ name: "Drift", check_type: "drift", threshold_value: "5.00", target_category: "eq", target_holding_category: "eq" });
    expect(result.identity.name).toBe("Drift");
    expect(result.draft?.threshold_value).toBe("5.00");
  });

  it("GET /api/guardian/checks lists checks", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ checks: [checkResponse.identity] })));
    const result = await listChecks();
    expect(result.checks).toHaveLength(1);
  });

  it("GET /api/guardian/checks/{id} gets detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(checkResponse)));
    const result = await getCheck("c1");
    expect(result.identity.id).toBe("c1");
  });

  it("discard on 204 returns void", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    const result = await discardCheck("c1");
    expect(result).toBeUndefined();
  });

  it("404 maps to GuardianApiError with neutral message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not found", { status: 404 })));
    await expect(getCheck("nope")).rejects.toThrow(GuardianApiError);
    await expect(getCheck("nope")).rejects.toThrow("was not found");
  });

  it("network error maps to GuardianNetworkError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("net")));
    await expect(getCheck("x")).rejects.toThrow(GuardianNetworkError);
  });

  it("AbortError is re-thrown", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError")));
    await expect(getCheck("x")).rejects.toThrow(DOMException);
  });

  it("evaluateAll hits /api/guardian/evaluate", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({
      evaluation_run: { id: "r1", household_id: "h1", status: "completed", skip_reason: null, checks_evaluated: 1, events_created: 0, as_of_date: "2026-07-17", created_at: "2026-01-01" },
      events: [],
    })));
    const result = await evaluateAll("2026-07-17");
    expect(result.evaluation_run.id).toBe("r1");
  });

  it("confirm uses /draft/confirm path", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((_: string) => {
      const url = _ as string;
      expect(url).toContain("/api/guardian/checks/c1/draft/confirm");
      return Promise.resolve(jsonResponse(checkResponse));
    }));
    await confirmCheck("c1", 1);
  });

  it("audit uses correct path", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((_: string) => {
      expect(_ as string).toContain("/api/guardian/audit");
      return Promise.resolve(jsonResponse({ audit_events: [] }));
    }));
    await getAudit();
  });
});
