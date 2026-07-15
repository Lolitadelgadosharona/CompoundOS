import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PolicyClient } from "./policy-client";

const emptyText = {
  objectives: "",
  time_horizon: "",
  liquidity: "",
  diversification: "",
  contribution_policy: "",
  rebalancing_policy: "",
  prohibited_assets: "",
  leverage_policy: "",
  decision_process: "",
  notes: "",
};

const policy = {
  id: "policy-1",
  household_id: "household-1",
  created_at: "2026-07-14T00:00:00Z",
  updated_at: "2026-07-14T00:00:00Z",
};

const draft = {
  ...emptyText,
  id: "draft-1",
  policy_id: policy.id,
  source_version_id: null,
  revision: 3,
  created_at: "2026-07-14T00:00:00Z",
  updated_at: "2026-07-14T00:00:00Z",
  allocations: [
    { id: "allocation-1", asset_class_name: "First user class", target_percentage: "60.00", sort_order: 0 },
    { id: "allocation-2", asset_class_name: "Second user class", target_percentage: "40.00", sort_order: 1 },
  ],
};

const version = {
  ...emptyText,
  objectives: "Owner objective",
  time_horizon: "Owner horizon",
  decision_process: "Owner process",
  id: "version-id-2",
  policy_id: policy.id,
  version_number: 2,
  status: "published" as const,
  published_at: "2026-07-14T02:00:00Z",
  superseded_at: null,
  allocations: draft.allocations,
};

const auditEvents = [
  {
    id: "audit-10",
    household_id: "household-1",
    actor: "local-owner",
    action: "policy.created",
    entity_type: "InvestmentPolicy",
    entity_id: policy.id,
    occurred_at: "2026-07-14T03:00:00Z",
    sequence_number: 10,
    metadata: {},
  },
  {
    id: "audit-11",
    household_id: "household-1",
    actor: "local-owner",
    action: "policy.draft.updated",
    entity_type: "InvestmentPolicy",
    entity_id: policy.id,
    occurred_at: "2026-07-14T01:00:00Z",
    sequence_number: 11,
    metadata: { draft_revision: 3 },
  },
];

type ServerState = {
  household: boolean;
  policy: typeof policy | null;
  draft: typeof draft | null;
  published: typeof version | null;
  history: Array<{
    id: string;
    version_number: number;
    status: "published" | "superseded";
    published_at: string;
    superseded_at: string | null;
  }>;
  nextCursor: number | null;
  audit: typeof auditEvents;
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
    policy,
    draft,
    published: null,
    history: [],
    nextCursor: null,
    audit: auditEvents,
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
      return state.household ? jsonResponse({ id: "household-1" }) : jsonResponse({}, 404);
    }
    if (url.endsWith("/api/policies/current") && method === "GET") {
      return state.policy ? jsonResponse(state.policy) : jsonResponse({}, 404);
    }
    if (url.endsWith("/api/policies/current/draft") && method === "GET") {
      return state.draft ? jsonResponse(state.draft) : jsonResponse({}, 404);
    }
    if (url.endsWith("/api/policies/current/published")) {
      return state.published ? jsonResponse(state.published) : jsonResponse({}, 404);
    }
    if (url.includes("/api/policies/current/versions/") && method === "GET") {
      return jsonResponse(state.published ?? version);
    }
    if (url.includes("/api/policies/current/versions") && method === "GET") {
      return jsonResponse({ items: state.history, next_before_version_number: state.nextCursor });
    }
    if (url.endsWith("/api/policies/current/audit-events")) return jsonResponse(state.audit);
    if (url.endsWith("/api/policies") && method === "POST") {
      state.policy = policy;
      state.draft = draft;
      return jsonResponse({ policy, draft }, 201);
    }
    if (url.endsWith("/api/policies/current/draft") && method === "PATCH") {
      const payload = JSON.parse(String(init?.body));
      state.draft = { ...draft, ...payload, revision: payload.expected_revision + 1 };
      return jsonResponse(state.draft);
    }
    if (url.endsWith("/api/policies/current/draft/allocations") && method === "PUT") {
      const payload = JSON.parse(String(init?.body));
      state.draft = {
        ...draft,
        revision: payload.expected_revision + 1,
        allocations: payload.items.map((item: { asset_class_name: string; target_percentage: string }, index: number) => ({
          ...item,
          id: `saved-${index}`,
          sort_order: index,
        })),
      };
      return jsonResponse(state.draft);
    }
    if (url.endsWith("/api/policies/current/draft/publish") && method === "POST") {
      state.draft = null;
      state.published = version;
      return jsonResponse(version, 201);
    }
    if (url.endsWith("/api/policies/current/draft/discard") && method === "POST") {
      state.draft = null;
      return jsonResponse(null, 204);
    }
    if (url.endsWith("/api/policies/current/draft") && method === "POST") {
      state.draft = { ...draft, source_version_id: JSON.parse(String(init?.body)).source_version_id ?? null };
      return jsonResponse(state.draft, 201);
    }
    return jsonResponse({ detail: "Unhandled test request" }, 500);
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("PolicyClient", () => {
  it("shows accessible loading then the missing-Household prerequisite without creating Policy", async () => {
    const state = defaultState({ household: false, policy: null, draft: null, audit: [] });
    const fetchMock = serverFetch(state);
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);

    expect(screen.getByRole("status").textContent).toContain("Loading Household and Policy");
    expect(await screen.findByRole("heading", { name: "Create the Household profile first" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open Household profile" }).getAttribute("href")).toBe("/household");
    expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith("/api/policies") && init?.method === "POST")).toBe(false);
  });

  it("creates an empty Policy once and adopts its server Draft", async () => {
    const state = defaultState({ policy: null, draft: null, audit: [] });
    const fetchMock = serverFetch(state);
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);

    await userEvent.dblClick(await screen.findByRole("button", { name: "Create policy draft" }));
    expect(await screen.findByText("Server revision 3")).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([url, init]) => String(url).endsWith("/api/policies") && init?.method === "POST")).toHaveLength(1);
    const createInit = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith("/api/policies") && init?.method === "POST")?.[1];
    expect(createInit?.body).toBeUndefined();
  });

  it("reloads server state after a create conflict", async () => {
    const state = defaultState({ policy: null, draft: null });
    let conflict = true;
    const fetchMock = serverFetch(state, (url, method) => {
      if (url.endsWith("/api/policies") && method === "POST" && conflict) {
        conflict = false;
        state.policy = policy;
        state.draft = draft;
        return jsonResponse({}, 409);
      }
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);

    await userEvent.click(await screen.findByRole("button", { name: "Create policy draft" }));
    expect(await screen.findByText("Server revision 3")).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/api/policies/current")).length).toBeGreaterThan(1);
  });

  it("renders ten neutral fields with three required and seven optional publication markers", async () => {
    vi.stubGlobal("fetch", serverFetch(defaultState()));
    render(<PolicyClient />);

    await screen.findByRole("heading", { name: "Policy text" });
    expect(screen.getAllByRole("textbox")).toHaveLength(10 + 4);
    expect(screen.getAllByText("Required to publish")).toHaveLength(3);
    expect(screen.getAllByText("Optional")).toHaveLength(7);
    expect(screen.getByLabelText("Objectives").getAttribute("placeholder")).toBeNull();
  });

  it("does not send a no-op and sends only changed text with expected revision", async () => {
    const state = defaultState();
    const fetchMock = serverFetch(state);
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Policy text" });

    await userEvent.click(screen.getByRole("button", { name: "Save policy text" }));
    expect(screen.getByRole("alert").textContent).toContain("no text changes");
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(0);

    await userEvent.type(screen.getByLabelText("Notes"), "Owner note");
    await userEvent.click(screen.getByRole("button", { name: "Save policy text" }));
    expect(await screen.findByText("Server revision 4")).toBeTruthy();
    const patchCall = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(JSON.parse(String(patchCall?.[1]?.body))).toEqual({
      expected_revision: 3,
      notes: "Owner note",
    });
  });

  it("keeps local text on 409 and offers a server reload", async () => {
    const state = defaultState();
    const fetchMock = serverFetch(state, (url, method) =>
      url.endsWith("/api/policies/current/draft") && method === "PATCH"
        ? jsonResponse({ detail: "secret-marker" }, 409)
        : undefined,
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Policy text" });

    await userEvent.type(screen.getByLabelText("Objectives"), "Local owner input");
    await userEvent.click(screen.getByRole("button", { name: "Save policy text" }));
    expect(await screen.findByRole("button", { name: "Reload server data" })).toBeTruthy();
    expect((screen.getByLabelText("Objectives") as HTMLTextAreaElement).value).toBe("Local owner input");
    expect(screen.getByRole("alert").textContent).not.toContain("secret-marker");
  });

  it("keeps unsaved allocation edits when policy text is saved", async () => {
    const state = defaultState();
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Policy text" });

    const allocationName = screen.getAllByLabelText("Asset-class name")[0];
    await userEvent.clear(allocationName);
    await userEvent.type(allocationName, "Unsaved allocation edit");
    await userEvent.type(screen.getByLabelText("Notes"), "Saved text edit");
    await userEvent.click(screen.getByRole("button", { name: "Save policy text" }));

    expect(await screen.findByText("Server revision 4")).toBeTruthy();
    expect((screen.getAllByLabelText("Asset-class name")[0] as HTMLInputElement).value).toBe(
      "Unsaved allocation edit",
    );
  });

  it("adds, reorders, removes, and saves the complete string-backed allocation collection", async () => {
    const state = defaultState();
    const fetchMock = serverFetch(state);
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Draft allocation" });

    await userEvent.click(screen.getByRole("button", { name: "Save allocations" }));
    expect(screen.getByRole("alert").textContent).toContain("no allocation changes");

    await userEvent.click(screen.getByRole("button", { name: "Add allocation row" }));
    const names = screen.getAllByLabelText("Asset-class name");
    const percentages = screen.getAllByLabelText("Target percentage");
    await userEvent.type(names[2], "Third user class");
    await userEvent.type(percentages[2], "0.25");
    expect(screen.getByText("Draft allocation total: 100.25%")).toBeTruthy();
    await userEvent.click(screen.getAllByRole("button", { name: "Move up" })[2]);
    await userEvent.click(screen.getAllByRole("button", { name: "Remove" })[0]);
    await userEvent.click(screen.getByRole("button", { name: "Save allocations" }));

    await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PUT")).toHaveLength(1));
    expect(await screen.findByText("Server revision 4")).toBeTruthy();
    const payload = JSON.parse(String(fetchMock.mock.calls.find(([, init]) => init?.method === "PUT")?.[1]?.body));
    expect(payload.expected_revision).toBe(3);
    expect(payload.items).toEqual([
      { asset_class_name: "Third user class", target_percentage: "0.25" },
      { asset_class_name: "Second user class", target_percentage: "40.00" },
    ]);
  });

  it("retains allocation input and shows a neutral duplicate-name 422", async () => {
    const state = defaultState();
    const fetchMock = serverFetch(state, (url, method) =>
      url.endsWith("/allocations") && method === "PUT"
        ? jsonResponse({ detail: [{ msg: "secret-marker duplicate" }] }, 422)
        : undefined,
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Draft allocation" });

    const firstName = screen.getAllByLabelText("Asset-class name")[0];
    await userEvent.clear(firstName);
    await userEvent.type(firstName, "SECOND USER CLASS");
    await userEvent.click(screen.getByRole("button", { name: "Save allocations" }));
    expect(await screen.findByText(/duplicate asset-class names/)).toBeTruthy();
    expect((firstName as HTMLInputElement).value).toBe("SECOND USER CLASS");
    expect(screen.getByRole("alert").textContent).not.toContain("secret-marker");
  });

  it("requires explicit publication confirmation and sends the exact saved revision once", async () => {
    const readyDraft = {
      ...draft,
      objectives: "Owner objective",
      time_horizon: "Owner horizon",
      decision_process: "Owner process",
    };
    const state = defaultState({ draft: readyDraft });
    const fetchMock = serverFetch(state);
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);

    await userEvent.click(await screen.findByRole("button", { name: "Review for publication" }));
    expect(screen.getAllByText(/do not constitute investment, tax, or legal advice/)).toHaveLength(2);
    const publishButton = screen.getByRole("button", { name: "Publish immutable Version" });
    expect((publishButton as HTMLButtonElement).disabled).toBe(true);
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.dblClick(publishButton);

    expect(await screen.findByRole("heading", { name: /Current Published Version · Version 2/ })).toBeTruthy();
    const publishCalls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/publish"));
    expect(publishCalls).toHaveLength(1);
    expect(JSON.parse(String(publishCalls[0][1]?.body))).toEqual({ expected_revision: 3, confirmation: true });
    expect(screen.getByText("Published versions cannot be edited.", { exact: false })).toBeTruthy();
  });

  it.each([
    [400, /mechanically incomplete/],
    [409, /Reload server data/],
  ])("handles publish HTTP %s without retrying", async (status, expected) => {
    const readyDraft = {
      ...draft,
      objectives: "Owner objective",
      time_horizon: "Owner horizon",
      decision_process: "Owner process",
    };
    const state = defaultState({ draft: readyDraft });
    const fetchMock = serverFetch(state, (url, method) =>
      url.endsWith("/publish") && method === "POST"
        ? jsonResponse({ detail: "secret-marker" }, status)
        : undefined,
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);

    await userEvent.click(await screen.findByRole("button", { name: "Review for publication" }));
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "Publish immutable Version" }));
    expect(await screen.findByText(expected)).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/publish"))).toHaveLength(1);
    expect(screen.queryByText("secret-marker")).toBeNull();
  });

  it("creates only blank or current-Published Drafts and exposes no historical restore", async () => {
    const state = defaultState({ draft: null, published: version, history: [version] });
    const fetchMock = serverFetch(state);
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: /Current Published Version/ });

    expect(screen.getByRole("button", { name: "Start blank" })).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Copy current Published" }));
    const draftCreate = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/api/policies/current/draft") && init?.method === "POST",
    );
    expect(JSON.parse(String(draftCreate?.[1]?.body))).toEqual({ source_version_id: version.id });
    expect(screen.queryByRole("button", { name: /restore/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /delete published/i })).toBeNull();
  });

  it("paginates newest-first history without duplicates and reads immutable detail", async () => {
    const version3 = { ...version, id: "version-3", version_number: 3, status: "published" as const };
    const version2 = { ...version, id: "version-2", version_number: 2, status: "superseded" as const, superseded_at: "2026-07-14T03:00:00Z" };
    const version1 = { ...version, id: "version-1", version_number: 1, status: "superseded" as const, superseded_at: "2026-07-14T02:00:00Z" };
    const state = defaultState({ draft: null, published: version3, history: [version3, version2], nextCursor: 2 });
    let moreLoaded = false;
    const fetchMock = serverFetch(state, (url, method) => {
      if (url.includes("before_version_number=2") && method === "GET") {
        moreLoaded = true;
        return jsonResponse({ items: [version2, version1], next_before_version_number: null });
      }
      if (url.endsWith("/versions/1")) return jsonResponse(version1);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    const historySection = await screen.findByRole("heading", { name: "Version history" });
    const historyPanel = historySection.closest("section") as HTMLElement;
    expect(within(historyPanel).getAllByText(/Version [23]/).map((node) => node.textContent)).toEqual(["Version 3", "Version 2"]);

    await userEvent.click(screen.getByRole("button", { name: "Load more Versions" }));
    await waitFor(() => expect(moreLoaded).toBe(true));
    expect(within(historyPanel).getAllByText("Version 2")).toHaveLength(1);
    expect(within(historyPanel).getByText("Version 1")).toBeTruthy();
    await userEvent.click(within(historyPanel).getAllByRole("button", { name: "View immutable detail" })[2]);
    expect(await within(historyPanel).findByRole("heading", { name: /Historical Version · Version 1/ })).toBeTruthy();
    expect(within(historyPanel).queryByRole("button", { name: /restore/i })).toBeNull();
  });

  it("keeps server sequence order and retries only audit GET after a successful mutation", async () => {
    const state = defaultState();
    let auditRequests = 0;
    const fetchMock = serverFetch(state, (url, method) => {
      if (url.endsWith("/audit-events")) {
        auditRequests += 1;
        if (auditRequests === 2) return jsonResponse({}, 503);
      }
      if (url.endsWith("/api/policies/current/draft") && method === "PATCH") {
        const saved = { ...draft, notes: "Saved note", revision: 4 };
        state.draft = saved;
        return jsonResponse(saved);
      }
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    const auditHeading = await screen.findByRole("heading", { name: "Policy audit timeline" });
    const auditPanel = auditHeading.closest("section") as HTMLElement;
    expect(within(auditPanel).getAllByRole("listitem").map((node) => within(node).getByText(/policy\./).textContent)).toEqual([
      "policy.created",
      "policy.draft.updated",
    ]);

    await userEvent.type(screen.getByLabelText("Notes"), "Saved note");
    await userEvent.click(screen.getByRole("button", { name: "Save policy text" }));
    expect(await screen.findByText("Policy text saved.")).toBeTruthy();
    expect(await within(auditPanel).findByText(/mutation succeeded, but the audit timeline/)).toBeTruthy();
    await userEvent.click(within(auditPanel).getByRole("button", { name: "Retry audit timeline" }));
    await waitFor(() => expect(auditRequests).toBe(3));
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
  });

  it("requires discard confirmation, sends the revision, and prevents repeat submission", async () => {
    const state = defaultState();
    const fetchMock = serverFetch(state);
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Discard Draft" });

    await userEvent.click(screen.getByRole("button", { name: "Discard Draft…" }));
    const confirm = screen.getByRole("button", { name: "Confirm discard Draft" });
    await userEvent.dblClick(confirm);
    await screen.findByRole("heading", { name: "No Draft is open" });
    const calls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/discard"));
    expect(calls).toHaveLength(1);
    expect(JSON.parse(String(calls[0][1]?.body))).toEqual({ expected_revision: 3 });
  });

  it("keeps the Draft and offers Reload after a discard conflict", async () => {
    const state = defaultState();
    const fetchMock = serverFetch(state, (url, method) =>
      url.endsWith("/discard") && method === "POST" ? jsonResponse({}, 409) : undefined,
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Discard Draft" });

    await userEvent.click(screen.getByRole("button", { name: "Discard Draft…" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm discard Draft" }));
    expect(await screen.findByRole("button", { name: "Reload server data" })).toBeTruthy();
    expect(screen.getByText("Server revision 3")).toBeTruthy();
  });

  it("shows safety boundaries and no prohibited product operations", async () => {
    vi.stubGlobal("fetch", serverFetch(defaultState()));
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Policy text" });

    expect(screen.getByText(/local-only and non-production/)).toBeTruthy();
    expect(screen.getByText(/no authentication/)).toBeTruthy();
    expect(screen.getByText(/does not evaluate whether an investment policy/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /AI|Guardian|Broker|trade|recommend/i })).toBeNull();
  });

  it("aborts outstanding initial requests when unmounted", async () => {
    const signals: AbortSignal[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: string | URL | Request, init?: RequestInit) => {
        if (init?.signal) signals.push(init.signal);
        return new Promise<Response>(() => undefined);
      }),
    );
    const view = render(<PolicyClient />);
    await waitFor(() => expect(signals.length).toBe(2));
    view.unmount();
    expect(signals.every((signal) => signal.aborted)).toBe(true);
  });
});
