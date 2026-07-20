import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import CommitteeClient from "../../app/committee/committee-client";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const session = { id: "s1", household_id: "h1", parent_session_id: null, title: "Test", proposal_text: "Should we?", status: "draft", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
const detail = { ...session, evidence_items: [], report: null, outcomes: [] };
const previewOk = { session_id: "s1", evidence_summary: [], estimated_input_tokens: 100, exceeds_budget: false, max_input_tokens: 50000, max_output_tokens: 8000, max_cost_usd: "1.00" };

describe("CommitteeClient UI states", () => {
  it("loading state", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<CommitteeClient />);
    expect(screen.getByRole("status").textContent).toContain("Loading");
  });

  it("no household", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json({ detail: "not found" }, 404)));
    render(<CommitteeClient />);
    expect(await screen.findByText(/No household profile/)).toBeTruthy();
  });

  it("empty sessions", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json([])));
    render(<CommitteeClient />);
    expect(await screen.findByText(/No sessions/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /New session/ })).toBeTruthy();
  });

  it("session list", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json([session])));
    render(<CommitteeClient />);
    expect(await screen.findByRole("button", { name: /Session Test/ })).toBeTruthy();
  });

  it("create session", async () => {
    vi.stubGlobal("fetch", vi.fn((input: string, init?: RequestInit) => {
      if (String(input).includes("sessions") && init?.method === "POST") return json({ ...session, id: "s2" }, 201);
      return json([]);
    }));
    render(<CommitteeClient />);
    await screen.findByRole("button", { name: /New session/ });
    await userEvent.click(screen.getByRole("button", { name: /New session/ }));
    expect(screen.getByLabelText("Title")).toBeTruthy();
    expect(screen.getByLabelText("Proposal")).toBeTruthy();
  });

  it("no auto-run on page load", async () => {
    const mock = vi.fn((input: string) => json([]));
    vi.stubGlobal("fetch", mock);
    render(<CommitteeClient />);
    await screen.findByText(/No sessions/);
    const postCalls = mock.mock.calls.filter((c: unknown[]) => (c[1] as RequestInit)?.method === "POST");
    expect(postCalls).toHaveLength(0);
  });

  it("create flow — enters form, types, submits", async () => {
    vi.stubGlobal("fetch", vi.fn((input: string, init?: RequestInit) => {
      if (String(input).includes("sessions") && init?.method === "POST") return json({ ...session, id: "s2" }, 201);
      return json([]);
    }));
    render(<CommitteeClient />);
    await screen.findByRole("button", { name: /New session/ });
    await userEvent.click(screen.getByRole("button", { name: /New session/ }));
    expect(screen.getByLabelText("Title")).toBeTruthy();
    expect(screen.getByLabelText("Proposal")).toBeTruthy();
    await userEvent.type(screen.getByLabelText("Title"), "My Proposal");
    await userEvent.type(screen.getByLabelText("Proposal"), "Should we rebalance?");
    expect(screen.getByRole("button", { name: /Create session/ })).toBeTruthy();
  });

  it("neutral language — no buy/sell/hold", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json([])));
    render(<CommitteeClient />);
    await screen.findByText(/No sessions/);
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("Buy");
    expect(body).not.toContain("Sell");
    expect(body).toContain("decision support");
    expect(body).toContain("not investment advice");
  });

  it("accessible labels", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json([])));
    render(<CommitteeClient />);
    await screen.findByText(/No sessions/);
    expect(screen.getByRole("button", { name: /New session/ })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Home/ })).toBeTruthy();
  });
});
