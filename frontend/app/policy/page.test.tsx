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
  draft: (Omit<typeof draft, "source_version_id"> & { source_version_id: string | null }) | null;
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
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
      const { expected_revision, ...changed } = payload;
      state.draft = {
        ...(state.draft ?? draft),
        ...changed,
        revision: expected_revision + 1,
        updated_at: "2026-07-14T04:00:00Z",
      };
      return jsonResponse(state.draft);
    }
    if (url.endsWith("/api/policies/current/draft/allocations") && method === "PUT") {
      const payload = JSON.parse(String(init?.body));
      state.draft = {
        ...(state.draft ?? draft),
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
    await userEvent.click(screen.getByRole("button", { name: "Move Third user class up" }));
    await userEvent.click(screen.getByRole("button", { name: "Remove First user class" }));
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

  it("keeps the core Draft usable when initial history loading fails", async () => {
    const fetchMock = serverFetch(defaultState(), (url, method) =>
      url.includes("/api/policies/current/versions") && method === "GET"
        ? jsonResponse({}, 503)
        : undefined,
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);

    expect(await screen.findByRole("heading", { name: "Policy text" })).toBeTruthy();
    expect(await screen.findByText("The Policy service returned an unexpected server error.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save policy text" })).toBeTruthy();
  });

  it("keeps Published visible and retries only history after history failure", async () => {
    const state = defaultState({ draft: null, published: version });
    let failHistory = true;
    const fetchMock = serverFetch(state, (url, method) => {
      if (url.includes("/versions") && !url.includes("/versions/") && method === "GET" && failHistory) {
        failHistory = false;
        return jsonResponse({}, 503);
      }
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    expect(await screen.findByRole("heading", { name: /Current Published Version · Version 2/ })).toBeTruthy();
    const callsBeforeRetry = fetchMock.mock.calls.length;
    await userEvent.click(await screen.findByRole("button", { name: "Retry Version history" }));
    await waitFor(() => expect(fetchMock.mock.calls.length).toBe(callsBeforeRetry + 1));
    expect(String(fetchMock.mock.calls.at(-1)?.[0])).toContain("/versions");
    expect(screen.queryByRole("button", { name: "Retry Version history" })).toBeNull();
  });

  it("keeps the Draft usable when audit fails and retries only audit", async () => {
    let failAudit = true;
    const fetchMock = serverFetch(defaultState(), (url) => {
      if (url.endsWith("/audit-events") && failAudit) {
        failAudit = false;
        return jsonResponse({}, 503);
      }
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    expect(await screen.findByRole("heading", { name: "Policy text" })).toBeTruthy();
    const callsBeforeRetry = fetchMock.mock.calls.length;
    await userEvent.click(await screen.findByRole("button", { name: "Retry audit timeline" }));
    await waitFor(() => expect(fetchMock.mock.calls.length).toBe(callsBeforeRetry + 1));
    expect(String(fetchMock.mock.calls.at(-1)?.[0])).toContain("/audit-events");
  });

  it("shows a core error when the Draft request fails", async () => {
    vi.stubGlobal("fetch", serverFetch(defaultState(), (url, method) =>
      url.endsWith("/api/policies/current/draft") && method === "GET" ? jsonResponse({}, 500) : undefined,
    ));
    render(<PolicyClient />);
    expect(await screen.findByText("The Policy service returned an unexpected server error.")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Policy text" })).toBeNull();
  });

  it("blocks publication until both text and allocation edits are saved", async () => {
    const state = defaultState({ draft: { ...draft, objectives: "Goal", time_horizon: "Long", decision_process: "Review" } });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Policy text" });

    await userEvent.type(screen.getByLabelText("Notes"), "Local note");
    const allocationName = screen.getAllByLabelText("Asset-class name")[0];
    await userEvent.clear(allocationName);
    await userEvent.type(allocationName, "First User Class");
    expect((screen.getByRole("button", { name: "Review for publication" }) as HTMLButtonElement).disabled).toBe(true);

    await userEvent.click(screen.getByRole("button", { name: "Save policy text" }));
    await screen.findByText("Policy text saved.");
    expect((screen.getByRole("button", { name: "Review for publication" }) as HTMLButtonElement).disabled).toBe(true);

    await userEvent.click(screen.getByRole("button", { name: "Save allocations" }));
    await screen.findByText("Draft allocations saved.");
    await waitFor(() => expect((screen.getByRole("button", { name: "Review for publication" }) as HTMLButtonElement).disabled).toBe(false));
  });

  it("returns to clean when text and allocation order are restored", async () => {
    const state = defaultState({ draft: { ...draft, objectives: "Goal", time_horizon: "Long", decision_process: "Review" } });
    vi.stubGlobal("fetch", serverFetch(state));
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Policy text" });
    const review = screen.getByRole("button", { name: "Review for publication" }) as HTMLButtonElement;
    expect(review.disabled).toBe(false);

    await userEvent.type(screen.getByLabelText("Notes"), "temporary");
    expect(review.disabled).toBe(true);
    await userEvent.clear(screen.getByLabelText("Notes"));
    await waitFor(() => expect(review.disabled).toBe(false));

    await userEvent.click(screen.getByRole("button", { name: "Move Second user class up" }));
    expect(review.disabled).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Move Second user class down" }));
    await waitFor(() => expect(review.disabled).toBe(false));
  });

  it("protects both editors from a reload and preserves them when the reload fails", async () => {
    let failReload = false;
    const fetchMock = serverFetch(defaultState(), (url, method) =>
      failReload && url.endsWith("/api/policies/current/draft") && method === "GET"
        ? jsonResponse({}, 503)
        : undefined,
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Policy text" });
    await userEvent.type(screen.getByLabelText("Notes"), "Unsaved text");
    const allocationName = screen.getAllByLabelText("Asset-class name")[0];
    await userEvent.clear(allocationName);
    await userEvent.type(allocationName, "Unsaved allocation");
    const before = fetchMock.mock.calls.length;

    await userEvent.click(screen.getByRole("button", { name: "Reload workspace" }));
    expect(screen.getByText(/Both Policy text and Draft allocation/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Keep editing" }));
    expect(fetchMock.mock.calls).toHaveLength(before);

    failReload = true;
    await userEvent.click(screen.getByRole("button", { name: "Reload workspace" }));
    await userEvent.click(screen.getByRole("button", { name: "Discard local changes and reload" }));
    expect(await screen.findByText("The Policy service returned an unexpected server error.")).toBeTruthy();
    expect((screen.getByLabelText("Notes") as HTMLTextAreaElement).value).toBe("Unsaved text");
    expect((screen.getAllByLabelText("Asset-class name")[0] as HTMLInputElement).value).toBe("Unsaved allocation");
  });

  it("lets only the newest audit refresh update the timeline", async () => {
    const first = deferred<Response>();
    const second = deferred<Response>();
    let requests = 0;
    const fetchMock = serverFetch(defaultState(), (url) => {
      if (url.endsWith("/audit-events")) {
        requests += 1;
        return requests === 1 ? first.promise : second.promise;
      }
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Policy text" });
    await userEvent.click(screen.getByRole("button", { name: "Reload workspace" }));
    await waitFor(() => expect(requests).toBe(2));
    second.resolve(jsonResponse([{ ...auditEvents[1], id: "new-audit", action: "policy.newest", sequence_number: 20 }]));
    expect(await screen.findByText("policy.newest")).toBeTruthy();
    first.resolve(jsonResponse([{ ...auditEvents[0], id: "old-audit", action: "policy.stale", sequence_number: 1 }]));
    await waitFor(() => expect(screen.queryByText("policy.stale")).toBeNull());
  });

  it("aborts an old audit request and ignores its later rejection", async () => {
    const first = deferred<Response>();
    const captured: { firstSignal?: AbortSignal } = {};
    let requests = 0;
    const fetchMock = serverFetch(defaultState(), (url, _method, init) => {
      if (url.endsWith("/audit-events")) {
        requests += 1;
        if (requests === 1) {
          captured.firstSignal = init?.signal as AbortSignal;
          return first.promise;
        }
        return jsonResponse([{ ...auditEvents[1], id: "latest", action: "policy.latest" }]);
      }
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Policy text" });
    await userEvent.click(screen.getByRole("button", { name: "Reload workspace" }));
    expect(await screen.findByText("policy.latest")).toBeTruthy();
    expect(captured.firstSignal?.aborted).toBe(true);
    first.reject(new TypeError("stale failure"));
    await waitFor(() => expect(screen.queryByText(/audit timeline could not/)).toBeNull());
  });

  it("lets only the newest history refresh update the collection", async () => {
    const first = deferred<Response>();
    const second = deferred<Response>();
    let requests = 0;
    const newest = { ...version, id: "newest", version_number: 9 };
    const stale = { ...version, id: "stale", version_number: 1 };
    const fetchMock = serverFetch(defaultState({ published: version }), (url, method) => {
      if (url.includes("/versions") && !url.includes("/versions/") && method === "GET") {
        requests += 1;
        return requests === 1 ? first.promise : second.promise;
      }
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Policy text" });
    await userEvent.click(screen.getByRole("button", { name: "Reload workspace" }));
    await waitFor(() => expect(requests).toBe(2));
    second.resolve(jsonResponse({ items: [newest, newest], next_before_version_number: null }));
    expect(await screen.findByText("Version 9")).toBeTruthy();
    first.resolve(jsonResponse({ items: [stale], next_before_version_number: null }));
    await waitFor(() => expect(screen.queryByText("Version 1")).toBeNull());
    expect(screen.getAllByText("Version 9")).toHaveLength(1);
  });

  it("invalidates a pending Load more when workspace history refreshes", async () => {
    const oldPage = deferred<Response>();
    const version3 = { ...version, id: "version-3", version_number: 3 };
    const version4 = { ...version, id: "version-4", version_number: 4 };
    const version1 = { ...version, id: "version-1", version_number: 1 };
    const state = defaultState({ history: [version3], nextCursor: 3 });
    let pageRequests = 0;
    const fetchMock = serverFetch(state, (url, method) => {
      if (url.includes("before_version_number=3") && method === "GET") {
        pageRequests += 1;
        return oldPage.promise;
      }
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByText("Version 3");
    await userEvent.dblClick(screen.getByRole("button", { name: "Load more Versions" }));
    expect(pageRequests).toBe(1);
    state.history = [version4];
    state.nextCursor = null;
    await userEvent.click(screen.getByRole("button", { name: "Reload workspace" }));
    expect(await screen.findByText("Version 4")).toBeTruthy();
    oldPage.resolve(jsonResponse({ items: [version1], next_before_version_number: null }));
    await waitFor(() => expect(screen.queryByText("Version 1")).toBeNull());
    expect(screen.queryByText("Version 3")).toBeNull();
  });

  it("validates allocation names by normalized Unicode code points without native truncation", async () => {
    const fetchMock = serverFetch(defaultState());
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Draft allocation" });
    const name = screen.getAllByLabelText("Asset-class name")[0] as HTMLInputElement;
    expect(name.maxLength).toBe(-1);
    await userEvent.clear(name);
    await userEvent.type(name, "😀".repeat(201));
    await userEvent.click(screen.getByRole("button", { name: "Save allocations" }));
    expect(screen.getByText(/200 characters or fewer/)).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PUT")).toHaveLength(0);
  });

  it("enforces the 200-code-point boundary for ASCII and mixed astral text", async () => {
    const fetchMock = serverFetch(defaultState());
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Draft allocation" });
    const name = screen.getAllByLabelText("Asset-class name")[0];
    await userEvent.clear(name);
    await userEvent.type(name, "a".repeat(199) + "😀");
    await userEvent.click(screen.getByRole("button", { name: "Save allocations" }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PUT")).toHaveLength(1));

    const adopted = screen.getAllByLabelText("Asset-class name")[0];
    await userEvent.clear(adopted);
    await userEvent.type(adopted, "a".repeat(201));
    await userEvent.click(screen.getByRole("button", { name: "Save allocations" }));
    expect(screen.getByText(/200 characters or fewer/)).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PUT")).toHaveLength(1);
  });

  it("allows exactly 200 emoji and treats a case-only display edit as a save", async () => {
    const state = defaultState();
    const fetchMock = serverFetch(state);
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Draft allocation" });
    const name = screen.getAllByLabelText("Asset-class name")[0];
    await userEvent.clear(name);
    await userEvent.type(name, "😀".repeat(200));
    await userEvent.click(screen.getByRole("button", { name: "Save allocations" }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PUT")).toHaveLength(1));

    const savedName = screen.getAllByLabelText("Asset-class name")[0];
    await userEvent.clear(savedName);
    await userEvent.type(savedName, "CASH");
    await userEvent.click(screen.getByRole("button", { name: "Save allocations" }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PUT")).toHaveLength(2));
  });

  it("treats trim and collapsed Unicode whitespace as allocation no-ops", async () => {
    const state = defaultState({ draft: {
      ...draft,
      allocations: [{ ...draft.allocations[0], asset_class_name: "Cash Reserve" }],
    } });
    const fetchMock = serverFetch(state);
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Draft allocation" });
    const name = screen.getByLabelText("Asset-class name");
    await userEvent.clear(name);
    await userEvent.type(name, "  Cash\u00a0  Reserve  ");
    await userEvent.click(screen.getByRole("button", { name: "Save allocations" }));
    expect(screen.getByText(/no allocation changes/)).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PUT")).toHaveLength(0);
  });

  it("shows current Published provenance beside an editable Draft", async () => {
    vi.stubGlobal("fetch", serverFetch(defaultState({ draft: { ...draft, source_version_id: version.id }, published: version })));
    render(<PolicyClient />);
    expect(await screen.findByRole("heading", { name: "Current Published Version · Version 2" })).toBeTruthy();
    expect(screen.getByText("This Draft started from current Published.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /edit|delete|restore/i })).toBeNull();
  });

  it("labels blank Draft provenance without mixing it into Published content", async () => {
    vi.stubGlobal("fetch", serverFetch(defaultState({ published: version })));
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Current Published Version · Version 2" });
    expect(screen.getByText("This Draft started blank.")).toBeTruthy();
  });

  it("gives row controls unique names that update with the row name", async () => {
    vi.stubGlobal("fetch", serverFetch(defaultState()));
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Draft allocation" });
    expect(screen.getByRole("button", { name: "Move First user class down" })).toBeTruthy();
    expect((screen.getByRole("button", { name: "Move First user class up" }) as HTMLButtonElement).disabled).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Add allocation row" }));
    expect(screen.getByRole("button", { name: "Remove allocation row 3" })).toBeTruthy();
    await userEvent.type(screen.getAllByLabelText("Asset-class name")[2], "Owner category");
    expect(screen.getByRole("button", { name: "Remove Owner category" })).toBeTruthy();
    expect((screen.getByRole("button", { name: "Move Owner category down" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it.each(["network", "server"])("recovers the text mutation button after a %s failure", async (kind) => {
    const state = defaultState();
    let failed = false;
    const fetchMock = serverFetch(state, (url, method) => {
      if (!failed && url.endsWith("/api/policies/current/draft") && method === "PATCH") {
        failed = true;
        if (kind === "network") return Promise.reject(new TypeError("private connection detail"));
        return jsonResponse({ detail: "secret-marker" }, 500);
      }
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PolicyClient />);
    await screen.findByRole("heading", { name: "Policy text" });
    await userEvent.type(screen.getByLabelText("Notes"), "Owner note");
    await userEvent.click(screen.getByRole("button", { name: "Save policy text" }));
    expect(await screen.findByText(kind === "network"
      ? "The Policy service connection is unavailable."
      : "The Policy service returned an unexpected server error.")).toBeTruthy();
    const save = screen.getByRole("button", { name: "Save policy text" }) as HTMLButtonElement;
    expect(save.disabled).toBe(false);
    await userEvent.click(save);
    expect(await screen.findByText("Policy text saved.")).toBeTruthy();
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
