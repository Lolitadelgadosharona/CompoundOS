import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HouseholdClient } from "./household-client";

const profile = {
  id: "household-1",
  household_name: "Wang Household",
  base_currency: "USD",
  investment_horizon: "Long term",
  liquidity_needs: "Flexible",
  risk_statement: "User-authored statement",
  notes: "Private notes",
  created_at: "2026-07-13T00:00:00Z",
  updated_at: "2026-07-13T00:00:00Z",
};

const auditEvent = {
  id: "event-1",
  household_id: profile.id,
  actor: "local-owner",
  action: "household.created",
  entity_type: "HouseholdProfile",
  entity_id: profile.id,
  occurred_at: "2026-07-13T00:00:00Z",
  metadata: { changed_fields: ["household_name"] },
};

const updatedAuditEvent = {
  ...auditEvent,
  id: "event-2",
  action: "household.updated",
  occurred_at: "2026-07-13T00:01:00Z",
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("HouseholdClient", () => {
  it("shows the empty state and both required limitations", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: "Not found" }, 404)));
    render(<HouseholdClient />);

    expect(await screen.findByRole("heading", { name: "Create the household profile" })).toBeTruthy();
    expect(screen.getByText(/local, single-user development only/)).toBeTruthy();
    expect(screen.getByText(/do not constitute investment, tax, or legal advice/)).toBeTruthy();
  });

  it("validates the create form before sending a request", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ detail: "Not found" }, 404));
    vi.stubGlobal("fetch", fetchMock);
    render(<HouseholdClient />);
    await screen.findByRole("heading", { name: "Create the household profile" });

    await userEvent.clear(screen.getByLabelText("Household name"));
    await userEvent.click(screen.getByRole("button", { name: "Create profile" }));
    expect(screen.getByRole("alert").textContent).toContain("Household name is required");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("creates a profile and renders the summary and audit timeline", async () => {
    let created = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        if (init?.method === "POST") {
          created = true;
          return jsonResponse(profile, 201);
        }
        if (url.endsWith("/audit-events")) return jsonResponse(created ? [auditEvent] : [], created ? 200 : 404);
        return created ? jsonResponse(profile) : jsonResponse({ detail: "Not found" }, 404);
      }),
    );
    render(<HouseholdClient />);
    await screen.findByRole("heading", { name: "Create the household profile" });

    await userEvent.type(screen.getByLabelText("Household name"), profile.household_name);
    await userEvent.click(screen.getByRole("button", { name: "Create profile" }));

    expect(await screen.findByRole("heading", { name: profile.household_name })).toBeTruthy();
    expect(screen.getByText("Profile created")).toBeTruthy();
    expect(screen.getByText("Actor: local-owner")).toBeTruthy();
  });

  it("loads an existing profile and saves edits", async () => {
    let current = profile;
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PATCH") {
        current = { ...profile, household_name: "Updated Household" };
        return jsonResponse(current);
      }
      if (url.endsWith("/audit-events")) return jsonResponse([auditEvent]);
      return jsonResponse(current);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<HouseholdClient />);
    await screen.findByRole("heading", { name: profile.household_name });

    await userEvent.click(screen.getByRole("button", { name: "Edit profile" }));
    const nameInput = screen.getByLabelText("Household name");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Updated Household");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("heading", { name: "Updated Household" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/households\/current$/),
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("shows a singleton conflict returned by the API", async () => {
    const fetchMock = vi.fn(async (_input: string | URL | Request, init?: RequestInit) => {
        if (init?.method === "POST") {
          return jsonResponse({ detail: "A household profile already exists" }, 409);
        }
        return jsonResponse({ detail: "Not found" }, 404);
      });
    vi.stubGlobal("fetch", fetchMock);
    render(<HouseholdClient />);
    await screen.findByRole("heading", { name: "Create the household profile" });
    await userEvent.type(screen.getByLabelText("Household name"), "Another Household");
    await userEvent.click(screen.getByRole("button", { name: "Create profile" }));

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("already exists");
    });
    expect((screen.getByLabelText("Household name") as HTMLInputElement).value).toBe(
      "Another Household",
    );
    expect(screen.queryByText("Household profile saved.")).toBeNull();
    expect(
      fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/audit-events")),
    ).toHaveLength(1);
  });

  it("keeps a created profile visible and retries only its failed audit refresh", async () => {
    let created = false;
    let auditRequests = 0;
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") {
        created = true;
        return jsonResponse(profile, 201);
      }
      if (url.endsWith("/audit-events")) {
        auditRequests += 1;
        if (!created) return jsonResponse([]);
        if (auditRequests === 2) return jsonResponse({ detail: "Unavailable" }, 503);
        return jsonResponse([auditEvent]);
      }
      return created ? jsonResponse(profile) : jsonResponse({ detail: "Not found" }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<HouseholdClient />);
    await screen.findByRole("heading", { name: "Create the household profile" });

    await userEvent.type(screen.getByLabelText("Household name"), profile.household_name);
    await userEvent.click(screen.getByRole("button", { name: "Create profile" }));

    expect(await screen.findByRole("heading", { name: profile.household_name })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Create the household profile" })).toBeNull();
    expect(screen.getByText("Household profile saved.")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain(
      "saved, but the audit timeline could not be refreshed",
    );

    await userEvent.click(screen.getByRole("button", { name: "Retry audit timeline" }));
    expect(await screen.findByText("Profile created")).toBeTruthy();
    await waitFor(() => {
      expect(screen.queryByText(/could not be refreshed/)).toBeNull();
    });
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(0);
    expect(auditRequests).toBe(3);
  });

  it("keeps an updated profile visible and retries only its failed audit refresh", async () => {
    let current = profile;
    let auditRequests = 0;
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PATCH") {
        current = { ...profile, household_name: "Updated Household" };
        return jsonResponse(current);
      }
      if (url.endsWith("/audit-events")) {
        auditRequests += 1;
        if (auditRequests === 2) return jsonResponse({ detail: "Unavailable" }, 503);
        return jsonResponse(auditRequests === 1 ? [auditEvent] : [auditEvent, updatedAuditEvent]);
      }
      return jsonResponse(current);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<HouseholdClient />);
    await screen.findByRole("heading", { name: profile.household_name });

    await userEvent.click(screen.getByRole("button", { name: "Edit profile" }));
    const nameInput = screen.getByLabelText("Household name");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Updated Household");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("heading", { name: "Updated Household" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
    expect(screen.getByText("Household profile saved.")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain(
      "saved, but the audit timeline could not be refreshed",
    );

    await userEvent.click(screen.getByRole("button", { name: "Retry audit timeline" }));
    expect(await screen.findByText("Profile updated")).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
    expect(auditRequests).toBe(3);
  });

  it("shows an existing profile when the initial audit request fails", async () => {
    let auditRequests = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        if (String(input).endsWith("/audit-events")) {
          auditRequests += 1;
          if (auditRequests === 1) return jsonResponse({ detail: "Unavailable" }, 503);
          return jsonResponse([auditEvent]);
        }
        return jsonResponse(profile);
      }),
    );
    render(<HouseholdClient />);

    expect(await screen.findByRole("heading", { name: profile.household_name })).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain(
      "profile is available, but the audit timeline could not be loaded",
    );
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Retry audit timeline" }));
    expect(await screen.findByText("Profile created")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(auditRequests).toBe(2);
  });

  it("does not render prohibited product surfaces", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) =>
        String(input).endsWith("/audit-events") ? jsonResponse([]) : jsonResponse(profile),
      ),
    );
    render(<HouseholdClient />);
    await screen.findByRole("heading", { name: profile.household_name });

    expect(screen.queryByText(/score/i)).toBeNull();
    expect(screen.queryByText(/guardian/i)).toBeNull();
    expect(screen.queryByText(/trading/i)).toBeNull();
    expect(screen.queryByText(/target allocation/i)).toBeNull();
  });
});
