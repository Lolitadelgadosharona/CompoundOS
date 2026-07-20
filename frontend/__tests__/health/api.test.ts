import { describe, expect, it, vi, afterEach } from "vitest";
import { getFullHealth, getLiveness, getReadiness } from "../../lib/health-api";

afterEach(() => { vi.unstubAllGlobals(); });

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("Health API client", () => {
  it("GET /api/health/live", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json({ alive: true, checked_at: "x" })));
    const r = await getLiveness();
    expect(r.alive).toBe(true);
  });

  it("GET /api/health/ready", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json({ ready: true, reason: "", checked_at: "x" })));
    const r = await getReadiness();
    expect(r.ready).toBe(true);
  });

  it("GET /api/health/full", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json({ overall: "healthy", components: [], checked_at: "x" })));
    const r = await getFullHealth();
    expect(r.overall).toBe("healthy");
  });

  it("AbortSignal", async () => {
    const ac = new AbortController();
    vi.stubGlobal("fetch", vi.fn(() => json({ alive: true, checked_at: "x" })));
    await getLiveness(ac.signal);
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1].signal).toBe(ac.signal);
  });
});
