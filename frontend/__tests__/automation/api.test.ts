import { describe, expect, it, vi, afterEach } from "vitest";

import {
  createSchedule,
  deleteSchedule,
  getRun,
  getSchedule,
  getWorkerStatus,
  listRuns,
  listSchedules,
  manualTrigger,
  updateSchedule,
  AutomationApiError,
  AutomationNetworkError,
} from "../../lib/automation-api";

afterEach(() => {
  vi.unstubAllGlobals();
});

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// ════════════════════════════════════════════════════════════════════
// Exact 9 methods / paths
// ════════════════════════════════════════════════════════════════════

describe("Automation API client — exact 9 methods/paths", () => {
  it("1. POST /api/automation/schedules", async () => {
    const expected = { id: "s1", job_definition_id: "jd1", job_type: "guardian.evaluate_all", job_params: {}, execution_time: "09:00:00", timezone: "UTC", next_run_at: "2026-01-01T00:00:00Z", enabled: false, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(expected, 201)));
    const r = await createSchedule({ job_type: "guardian.evaluate_all", execution_time: "09:00:00" });
    expect(r).toEqual(expected);
    const call = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call[0]).toContain("/api/automation/schedules");
    const init = call[1];
    expect(init.method).toBe("POST");
  });

  it("2. GET /api/automation/schedules", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json([])));
    await listSchedules();
    const call = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call[0]).toContain("/api/automation/schedules");
    const init = call[1] ?? {};
    expect(init.method).toBeUndefined();
  });

  it("3. GET /api/automation/schedules/{id}", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ id: "s1" })));
    await getSchedule("s1");
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain("/api/automation/schedules/s1");
  });

  it("4. PATCH /api/automation/schedules/{id}", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ id: "s1", enabled: true })));
    await updateSchedule("s1", { enabled: true });
    const init = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("PATCH");
  });

  it("5. DELETE /api/automation/schedules/{id}", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await deleteSchedule("s1");
    const init = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("DELETE");
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain("/s1");
  });

  it("6. GET /api/automation/runs", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json([])));
    await listRuns();
    const call = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call[0]).toContain("/api/automation/runs");
  });

  it("7. GET /api/automation/runs/{id}", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ id: "r1", attempts: [] })));
    await getRun("r1");
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain("/api/automation/runs/r1");
  });

  it("8. POST /api/automation/runs", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ id: "r2", status: "pending" }, 201)));
    await manualTrigger({ job_definition_id: "jd1" });
    const init = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain("/api/automation/runs");
  });

  it("9. GET /api/automation/worker/status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ worker_count: 1, active_leases: 0, running_runs: 0 })));
    await getWorkerStatus();
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain("/api/automation/worker/status");
  });
});

// ════════════════════════════════════════════════════════════════════
// Error mapping
// ════════════════════════════════════════════════════════════════════

describe("Automation error mapping", () => {
  it("404 maps to AutomationApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(json({ detail: "not found" }, 404)),
    );
    await expect(listSchedules()).rejects.toThrow(AutomationApiError);
  });

  it("409 maps to AutomationApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(json({ detail: "conflict" }, 409)),
    );
    await expect(createSchedule({ job_type: "guardian.evaluate_all", execution_time: "09:00" }))
      .rejects.toThrow(AutomationApiError);
  });

  it("422 maps to AutomationApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(json({ detail: "invalid" }, 422)),
    );
    await expect(createSchedule({ job_type: "guardian.evaluate_all", execution_time: "09:00" }))
      .rejects.toThrow(AutomationApiError);
  });

  it("500 maps to AutomationApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(json({ detail: "server error" }, 500)),
    );
    await expect(listSchedules()).rejects.toThrow(AutomationApiError);
  });

  it("network error maps to AutomationNetworkError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(listSchedules()).rejects.toThrow(AutomationNetworkError);
  });
});

// ════════════════════════════════════════════════════════════════════
// Path encoding / contracts
// ════════════════════════════════════════════════════════════════════

describe("Path encoding and contracts", () => {
  it("encodes schedule ID with special chars", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ id: "s%2f1" })));
    await getSchedule("s/1");
    const url = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).not.toContain("/s/1");
    expect(url).toContain("s%2F1");
  });

  it("preserves timezone string", async () => {
    let body: string | null = null;
    vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => {
      body = init?.body as string;
      return json({ id: "s1", timezone: "Asia/Tokyo" }, 201);
    }));
    await createSchedule({ job_type: "guardian.evaluate_all", execution_time: "09:00:00", timezone: "Asia/Tokyo" });
    expect(JSON.parse(body!).timezone).toBe("Asia/Tokyo");
  });

  it("forwards AbortSignal", async () => {
    const ac = new AbortController();
    const caught = false;
    vi.stubGlobal("fetch", vi.fn((_u: string, init?: RequestInit) => {
      expect(init?.signal).toBe(ac.signal);
      return json([]);
    }));
    await listSchedules(ac.signal);
    const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls[0][1].signal).toBe(ac.signal);
    expect(caught).toBe(false); // signal was passed
  });

  it("no retry on failure", async () => {
    let calls = 0;
    vi.stubGlobal("fetch", vi.fn(() => { calls++; return Promise.reject(new Error("fail")); }));
    await expect(listSchedules()).rejects.toThrow(AutomationNetworkError);
    expect(calls).toBe(1);
  });

  it("runs pagination params", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json([])));
    await listRuns({ limit: 10, offset: 5 });
    const url = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain("limit=10");
    expect(url).toContain("offset=5");
  });
});
