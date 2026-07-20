import { describe, expect, it, vi, afterEach } from "vitest";

import {
  createSession,
  getEvidence,
  getPrivacyPreview,
  getReport,
  getRunStatus,
  getSession,
  listSessions,
  recordOutcome,
  runSession,
  CommitteeApiError,
  CommitteeNetworkError,
} from "../../lib/committee-api";

afterEach(() => { vi.unstubAllGlobals(); });

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("Committee API client — exact 9 methods/paths", () => {
  it("1. POST /api/committee/sessions", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ id: "s1", status: "draft" }, 201)));
    await createSession({ title: "T", proposal_text: "P" });
    const c = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(c[0]).toContain("/api/committee/sessions");
    expect(c[1].method).toBe("POST");
  });

  it("2. GET /api/committee/sessions", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json([])));
    await listSessions();
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain("/api/committee/sessions");
  });

  it("3. GET /api/committee/sessions/{id}", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ id: "s1" })));
    await getSession("s1");
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain("/s1");
  });

  it("4. GET privacy-preview", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ session_id: "s1" })));
    await getPrivacyPreview("s1");
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain("privacy-preview");
  });

  it("5. POST /api/committee/sessions/{id}/run", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ status: "completed" }, 201)));
    await runSession("s1");
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1].method).toBe("POST");
  });

  it("6. GET /api/committee/runs/{id}", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ status: "completed" })));
    await getRunStatus("s1");
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain("/runs/s1");
  });

  it("7. GET /api/committee/reports/{id}", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ id: "r1", report_content: {} })));
    await getReport("r1");
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain("/reports/r1");
  });

  it("8. GET /api/committee/evidence/{session_id}", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json([])));
    await getEvidence("s1");
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain("/evidence/s1");
  });

  it("9. POST /api/committee/outcomes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ id: "o1", outcome: "accepted" }, 201)));
    await recordOutcome("s1", { outcome: "accepted" });
    const c = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(c[1].method).toBe("POST");
    expect(c[0]).toContain("outcomes");
  });
});

describe("Error mapping", () => {
  it("404 → CommitteeApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "not found" }, 404)));
    await expect(listSessions()).rejects.toThrow(CommitteeApiError);
  });
  it("422 → CommitteeApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "invalid" }, 422)));
    await expect(createSession({ title: "T", proposal_text: "P" })).rejects.toThrow(CommitteeApiError);
  });
  it("500 → CommitteeApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "server error" }, 500)));
    await expect(listSessions()).rejects.toThrow(CommitteeApiError);
  });
  it("network error → CommitteeNetworkError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(listSessions()).rejects.toThrow(CommitteeNetworkError);
  });
});

describe("Safety", () => {
  it("no retry on failure", async () => {
    let calls = 0;
    vi.stubGlobal("fetch", vi.fn(() => { calls++; return Promise.reject(new Error("fail")); }));
    await expect(listSessions()).rejects.toThrow(CommitteeNetworkError);
    expect(calls).toBe(1);
  });
  it("AbortSignal forwarding", async () => {
    const ac = new AbortController();
    vi.stubGlobal("fetch", vi.fn(() => json([])));
    await listSessions(undefined, ac.signal);
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1].signal).toBe(ac.signal);
  });
  it("path encoding special chars", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ id: "s%2f1" })));
    await getSession("s/1");
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain("s%2F1");
  });
});
