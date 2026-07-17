import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PortfolioClient } from "../../app/portfolio/portfolio-client";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const holding1 = {
  id: "h-1",
  asset_name: "Apple Inc.",
  asset_category: "equity",
  quantity: "100.00000000",
  unit_price: "150.5000",
  total_value: "15050.00",
  valuation_date: "2026-07-15",
  notes: null,
  sort_order: 0,
};

const holding2 = {
  id: "h-2",
  asset_name: "Operating Cash",
  asset_category: "cash",
  quantity: "50000.00000000",
  unit_price: "1.0000",
  total_value: "50000.00",
  valuation_date: "2026-07-15",
  notes: null,
  sort_order: 1,
};

const draft = {
  portfolio_id: "port-1",
  expected_revision: 3,
  valuation_date: "2026-07-15",
  notes: "Quarterly review",
  updated_at: "2026-07-15T00:00:00Z",
  holdings: [holding1, holding2],
};

const snapshot = {
  id: "snap-1",
  portfolio_id: "port-1",
  version_number: 1,
  status: "current",
  confirmed_at: "2026-07-15T00:00:00Z",
  holding_count: 2,
  valuation_date: "2026-07-15",
  notes: "First snapshot",
  holdings: [holding1, holding2],
};

const auditEvents = [
  {
    id: "audit-1",
    household_id: "household-1",
    actor: "local-owner",
    action: "portfolio.draft.created",
    entity_type: "portfolio",
    entity_id: "port-1",
    occurred_at: "2026-07-15T00:00:00Z",
    sequence_number: 1,
    metadata: {},
  },
  {
    id: "audit-2",
    household_id: "household-1",
    actor: "local-owner",
    action: "portfolio.snapshot.confirmed",
    entity_type: "portfolio",
    entity_id: "port-1",
    occurred_at: "2026-07-15T01:00:00Z",
    sequence_number: 2,
    metadata: { snapshot_version_number: 1, holding_count: 2 },
  },
];

type ServerState = {
  household: boolean;
  portfolioState: object | null;
  createStatus: number;
  discardStatus: number;
  discardResult: object | null;
  confirmStatus: number;
  putStatus: number;
  patchStatus: number;
  historyResult: object;
  auditResult: object[];
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function defaultState(overrides: Partial<ServerState> = {}): ServerState {
  return {
    household: true,
    portfolioState: {
      portfolio: { status: "active" },
      latest_snapshot: { ...snapshot, holdings: [] },
    },
    createStatus: 201,
    discardStatus: 204,
    discardResult: null,
    confirmStatus: 201,
    putStatus: 200,
    patchStatus: 200,
    historyResult: { items: [], next_before_version_number: null },
    auditResult: auditEvents,
    ...overrides,
  };
}

function serverFetch(
  state: ServerState,
  intercept?: (
    url: string,
    method: string,
    init?: RequestInit,
  ) => Response | Promise<Response> | undefined,
) {
  return vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const intercepted = intercept?.(url, method, init);
    if (intercepted) return await intercepted;

    if (url.endsWith("/api/households/current")) {
      return state.household
        ? jsonResponse({ id: "household-1" })
        : jsonResponse({}, 404);
    }
    if (url.endsWith("/api/portfolio") && method === "GET") {
      return state.portfolioState
        ? jsonResponse(state.portfolioState)
        : jsonResponse({}, 404);
    }
    if (url.endsWith("/api/portfolio/draft") && method === "POST") {
      if (state.createStatus === 409) return jsonResponse({}, 409);
      return jsonResponse(
        {
          portfolio: { id: "port-1", household_id: "household-1", status: "draft", created_at: "..." },
          draft: { ...draft, holdings: [] },
        },
        state.createStatus,
      );
    }
    if (url.endsWith("/api/portfolio/draft/holdings") && method === "PUT") {
      if (state.putStatus === 409) return jsonResponse({}, 409);
      if (state.putStatus === 422) return jsonResponse({ detail: "validation error" }, 422);
      const payload = JSON.parse(String(init?.body));
      return jsonResponse({
        ...draft,
        expected_revision: payload.expected_revision + 1,
        holdings: payload.items.map((item: Record<string, unknown>, i: number) => ({
          ...item,
          id: `saved-${i}`,
          total_value: item.asset_category === "cash" ? item.quantity + ".00" : "15050.00",
          sort_order: i,
          notes: item.notes || null,
        })),
      });
    }
    if (url.endsWith("/api/portfolio/draft/confirm") && method === "POST") {
      if (state.confirmStatus === 409) return jsonResponse({}, 409);
      return jsonResponse(snapshot, state.confirmStatus);
    }
    if (url.endsWith("/api/portfolio/draft/discard") && method === "POST") {
      return jsonResponse(state.discardResult, state.discardStatus);
    }
    if (url.endsWith("/api/portfolio/draft") && method === "PATCH") {
      if (state.patchStatus === 409) return jsonResponse({}, 409);
      const payload = JSON.parse(String(init?.body));
      return jsonResponse({
        ...draft,
        expected_revision: payload.expected_revision + 1,
        valuation_date: payload.valuation_date ?? null,
        notes: payload.notes ?? null,
      });
    }
    if (url.includes("/api/portfolio/snapshots/") && method === "GET") {
      return jsonResponse(snapshot);
    }
    if (url.includes("/api/portfolio/snapshots") && method === "GET") {
      return jsonResponse(state.historyResult);
    }
    if (url.includes("/api/portfolio/audit") && method === "GET") {
      return jsonResponse(state.auditResult);
    }
    return jsonResponse({ detail: "Unhandled test request" }, 500);
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("PortfolioClient", () => {
  it("shows loading then the missing-Household prerequisite", async () => {
    const state = defaultState({ household: false, portfolioState: null });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    expect(screen.getByRole("status").textContent).toContain("Loading Portfolio");
    expect(await screen.findByText("Create the Household profile first")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open Household profile" }).getAttribute("href")).toBe(
      "/household",
    );
  });

  it("shows no-portfolio state with create button", async () => {
    const state = defaultState({ portfolioState: null });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    expect(await screen.findByRole("button", { name: "Create portfolio draft" })).toBeTruthy();
  });

  it("creates a portfolio draft and enters editor", async () => {
    const state = defaultState({ portfolioState: null });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    await userEvent.click(await screen.findByRole("button", { name: "Create portfolio draft" }));
    expect(await screen.findByRole("heading", { name: "Draft Holdings" })).toBeTruthy();
  });

  it("shows current snapshot when no draft exists", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "active" },
        latest_snapshot: snapshot,
      },
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    expect(await screen.findByText(/Current Snapshot/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Create new draft" })).toBeTruthy();
  });

  it("shows draft editor with existing draft", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft: { ...draft, holdings: [] },
      },
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    expect(await screen.findByRole("heading", { name: "Draft Holdings" })).toBeTruthy();
  });

  it("shows draft with current snapshot when both exist", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft: { ...draft, holdings: [] },
        latest_snapshot: { ...snapshot, holdings: [] },
      },
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    expect(await screen.findByRole("heading", { name: "Draft Holdings" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Snapshot History" })).toBeTruthy();
  });

  it("adds, edits, and saves holdings", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft: { ...draft, holdings: [] },
      },
    });
    const fetchMock = serverFetch(state);
    vi.stubGlobal("fetch", fetchMock);
    render(<PortfolioClient />);

    await screen.findByRole("heading", { name: "Draft Holdings" });

    // Add a holding
    await userEvent.click(screen.getByRole("button", { name: "Add holding row" }));
    const nameInputs = screen.getAllByLabelText(/Asset name/);
    expect(nameInputs.length).toBe(1);

    // Fill in fields
    await userEvent.type(nameInputs[0], "Apple Inc.");
    await userEvent.type(screen.getByLabelText(/Asset category/), "equity");
    await userEvent.type(screen.getByLabelText(/Quantity/), "100");
    await userEvent.type(screen.getByLabelText(/Unit price/), "150.50");

    // Save
    await userEvent.click(screen.getByRole("button", { name: "Save holdings" }));
    await waitFor(() => {
      const putCalls = fetchMock.mock.calls.filter(
        ([, init]) => init?.method === "PUT",
      );
      expect(putCalls.length).toBe(1);
      const payload = JSON.parse(String(putCalls[0]?.[1]?.body));
      expect(payload.items[0].asset_name).toBe("Apple Inc.");
    });
  });

  it("shows cash hint when cash category is used", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft: { ...draft, holdings: [] },
      },
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    await screen.findByRole("heading", { name: "Draft Holdings" });
    await userEvent.click(screen.getByRole("button", { name: "Add holding row" }));
    await userEvent.type(screen.getByLabelText(/Asset category/), "cash");

    expect(screen.getByText(/Cash holdings use unit_price 1.00/)).toBeTruthy();
  });

  it("shows private asset hint", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft: { ...draft, holdings: [] },
      },
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    await screen.findByRole("heading", { name: "Draft Holdings" });
    await userEvent.click(screen.getByRole("button", { name: "Add holding row" }));
    await userEvent.type(screen.getByLabelText(/Asset category/), "private");

    expect(screen.getByText(/User-entered private asset valuation/)).toBeTruthy();
  });

  it("displays zero holdings warning", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft: { ...draft, holdings: [] },
      },
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    await screen.findByRole("heading", { name: "Draft Holdings" });
    expect(screen.getByText(/0 holdings — no assets recorded/)).toBeTruthy();
  });

  it("enters confirm review and confirms", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft,
      },
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    await screen.findByRole("heading", { name: "Draft Holdings" });

    // Save holdings first to clear dirty state
    await userEvent.click(screen.getByRole("button", { name: "Save holdings" }));
    await waitFor(() => {
      expect(screen.queryByText("Unsaved changes")).toBeNull();
    });

    await userEvent.click(screen.getByRole("button", { name: "Review and confirm" }));
    expect(await screen.findByRole("heading", { name: "Confirm Snapshot" })).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: "Confirm snapshot" }));
    expect(await screen.findByText(/Current Snapshot/)).toBeTruthy();
  });

  it("removes a holding row", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft: { ...draft },
      },
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    await screen.findByRole("heading", { name: "Draft Holdings" });

    const removeButtons = screen.getAllByLabelText(/Remove/);
    expect(removeButtons.length).toBe(2);
    await userEvent.click(removeButtons[0]);
    expect(screen.getAllByLabelText(/Remove/).length).toBe(1);
  });

  it("reorders holdings", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft: { ...draft },
      },
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    await screen.findByRole("heading", { name: "Draft Holdings" });

    const moveUpButton = screen.getByLabelText("Move Operating Cash up");
    await userEvent.click(moveUpButton);

    // After moving up, Operating Cash should be first
    const nameInputs = screen.getAllByLabelText(/Asset name/);
    expect((nameInputs[0] as HTMLInputElement).value).toBe("Operating Cash");
    expect((nameInputs[1] as HTMLInputElement).value).toBe("Apple Inc.");
  });

  it("shows conflict panel on 409 and preserves inputs", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft: { ...draft, holdings: [] },
      },
      putStatus: 409,
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    await screen.findByRole("heading", { name: "Draft Holdings" });

    await userEvent.click(screen.getByRole("button", { name: "Add holding row" }));
    const nameInput = screen.getByLabelText(/Asset name/);
    await userEvent.type(nameInput, "My Stock");

    await userEvent.click(screen.getByRole("button", { name: "Save holdings" }));
    expect(await screen.findByRole("button", { name: "Reload server data" })).toBeTruthy();
    expect((nameInput as HTMLInputElement).value).toBe("My Stock");
  });

  it("shows error when core load fails", async () => {
    const state = defaultState({
      household: true,
      portfolioState: null, // will trigger first fetch that returns 404, then serverFetch also returns state
    });
    // Force portfolio GET to 500
    const fetchMock = serverFetch(state, (url, method) => {
      if (url.endsWith("/api/portfolio") && method === "GET") {
        return jsonResponse({}, 500);
      }
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PortfolioClient />);

    expect(await screen.findByText(/unexpected server error/)).toBeTruthy();
  });

  it("keeps core usable when history fails", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft: { ...draft, holdings: [] },
      },
      historyResult: { detail: "error" }, // will return as 200 but fail parsing — let's use 500 instead
    });
    const fetchMock = serverFetch(state, (url, method) => {
      if (url.includes("/api/portfolio/snapshots") && !url.includes("/snapshots/") && method === "GET") {
        return jsonResponse({}, 503);
      }
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PortfolioClient />);

    expect(await screen.findByRole("heading", { name: "Draft Holdings" })).toBeTruthy();
    expect(await screen.findByText(/unexpected server error/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save holdings" })).toBeTruthy();
  });

  it("keeps core usable when audit fails", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft: { ...draft, holdings: [] },
      },
    });
    const fetchMock = serverFetch(state, (url, method) => {
      if (url.includes("/api/portfolio/audit") && method === "GET") {
        return jsonResponse({}, 503);
      }
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PortfolioClient />);

    expect(await screen.findByRole("heading", { name: "Draft Holdings" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save holdings" })).toBeTruthy();
  });

  it("discards draft with confirmation for never-confirmed", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft: { ...draft, holdings: [] },
      },
      discardStatus: 204,
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    await screen.findByRole("heading", { name: "Draft Holdings" });
    await userEvent.click(screen.getByRole("button", { name: "Discard draft" }));

    expect(confirmSpy).toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it("displays audit timeline events", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "active" },
        latest_snapshot: snapshot,
      },
      auditResult: auditEvents,
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    expect(await screen.findByText("portfolio.draft.created")).toBeTruthy();
    expect(screen.getByText("portfolio.snapshot.confirmed")).toBeTruthy();
  });

  it("displays local-only and non-advisory notices", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "active" },
        latest_snapshot: snapshot,
      },
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    expect(await screen.findByText(/runs locally/)).toBeTruthy();
    expect(screen.getByText(/Nothing here is advice./)).toBeTruthy();
  });

  it("shows snapshot detail when selected from history", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "active" },
        latest_snapshot: snapshot,
      },
      historyResult: {
        items: [
          {
            id: "snap-1",
            version_number: 1,
            status: "current",
            confirmed_at: "2026-07-15T00:00:00Z",
            holding_count: 2,
            valuation_date: "2026-07-15",
          },
        ],
        next_before_version_number: null,
      },
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    await screen.findByText("v1");
    await userEvent.click(screen.getByRole("button", { name: "View snapshot version 1" }));
    // After clicking View, there should be two SnapshotView components visible
    const snapshots = await screen.findAllByText(/Snapshot v1 —/);
    expect(snapshots.length).toBeGreaterThanOrEqual(2);
  });

  it("updates draft metadata", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft: { ...draft, holdings: [] },
      },
    });
    const fetchMock = serverFetch(state);
    vi.stubGlobal("fetch", fetchMock);
    render(<PortfolioClient />);

    await screen.findByRole("heading", { name: "Draft Holdings" });

    const notesInput = screen.getByLabelText("Draft notes");
    await userEvent.type(notesInput, "Updated notes");
    await userEvent.click(screen.getByRole("button", { name: "Save metadata" }));

    await waitFor(() => {
      const patchCalls = fetchMock.mock.calls.filter(
        ([, init]) => init?.method === "PATCH",
      );
      expect(patchCalls.length).toBe(1);
    });
  });

  it("rejects future valuation date", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft: { ...draft, holdings: [] },
      },
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    await screen.findByRole("heading", { name: "Draft Holdings" });
    await userEvent.click(screen.getByRole("button", { name: "Add holding row" }));

    const dateInput = screen.getAllByLabelText(/Valuation date/)[1]; // second one is the holding row's
    await userEvent.clear(dateInput);
    await userEvent.type(dateInput, "2099-12-31");

    expect(screen.getByText("Date must not be in the future")).toBeTruthy();
  });

  it("rejects invalid quantity", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "draft" },
        draft: { ...draft, holdings: [] },
      },
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    await screen.findByRole("heading", { name: "Draft Holdings" });
    await userEvent.click(screen.getByRole("button", { name: "Add holding row" }));

    const qtyInput = screen.getByLabelText(/Quantity/);
    await userEvent.type(qtyInput, "0");

    expect(screen.getByText(/Quantity must be > 0/)).toBeTruthy();
  });

  it("shows read-only holdings table in snapshot detail", async () => {
    const state = defaultState({
      portfolioState: {
        portfolio: { status: "active" },
        latest_snapshot: snapshot,
      },
      historyResult: {
        items: [
          {
            id: "snap-1",
            version_number: 1,
            status: "current",
            confirmed_at: "2026-07-15T00:00:00Z",
            holding_count: 2,
            valuation_date: "2026-07-15",
          },
        ],
        next_before_version_number: null,
      },
    });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PortfolioClient />);

    // The current snapshot is shown directly — SnapshotView renders
    const snapshots = await screen.findAllByText(/Snapshot v1 —/);
    expect(snapshots.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Apple Inc.")).toBeTruthy();
    expect(screen.getByText("15050")).toBeTruthy();
  });
});
