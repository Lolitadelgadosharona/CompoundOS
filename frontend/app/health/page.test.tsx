import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import HealthClient from "../../app/health/health-client";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function json(body: unknown) {
  return new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
}

describe("HealthClient", () => {
  it("loading state", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<HealthClient />);
    expect(screen.getByText(/Loading/)).toBeTruthy();
  });

  it("healthy state", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json({
      overall: "healthy", components: [
        { component: "database", status: "healthy", reason: "OK" },
      ], checked_at: "2026-01-01T00:00:00Z",
    })));
    render(<HealthClient />);
    expect(await screen.findByLabelText(/Status healthy/)).toBeTruthy();
  });

  it("read-only — no repair buttons", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json({
      overall: "degraded", components: [], checked_at: "2026-01-01T00:00:00Z",
    })));
    render(<HealthClient />);
    await screen.findByText(/Health dashboard/i);
    expect(document.body.textContent).not.toContain("Repair");
    expect(document.body.textContent).not.toContain("Restart");
    expect(document.body.textContent).toContain("read-only");
  });

  it("GET only on page load", async () => {
    const mock = vi.fn(() => json({ overall: "healthy", components: [], checked_at: "x" }));
    vi.stubGlobal("fetch", mock);
    render(<HealthClient />);
    await screen.findByRole("button", { name: /Refresh/ });
    const methods = mock.mock.calls.map((c: unknown[]) => (c[1] as RequestInit)?.method);
    expect(methods.every((m: string | undefined) => !m || m === "GET")).toBe(true);
  });

  it("accessible labels", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json({
      overall: "healthy", components: [
        { component: "database", status: "healthy", reason: "OK" },
      ], checked_at: "x",
    })));
    render(<HealthClient />);
    await screen.findByRole("button", { name: /Refresh/ });
    expect(screen.getByRole("link", { name: /Home/ })).toBeTruthy();
  });
});
