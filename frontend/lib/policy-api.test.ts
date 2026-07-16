import { afterEach, describe, expect, it, vi } from "vitest";

import {
  allocationTotal,
  allocationsEqual,
  createDraft,
  createPolicy,
  getPolicyAuditEvents,
  getVersionHistory,
  percentageToHundredths,
  PolicyApiError,
  PolicyNetworkError,
  publishDraft,
  replaceDraftAllocations,
  updateDraftText,
} from "./policy-api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Policy API client", () => {
  it("creates a Policy without sending a JSON null or request body", async () => {
    const fetchMock = vi.fn<
      (input: string | URL | Request, init?: RequestInit) => Promise<Response>
    >(
      async () => jsonResponse({ policy: {}, draft: {} }, 201),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createPolicy();

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/policies$/);
    expect(init).toEqual(expect.objectContaining({ method: "POST" }));
    expect(init?.body).toBeUndefined();
    expect(init?.headers).toBeUndefined();
  });

  it("uses the approved endpoints, methods, revisions, and decimal strings", async () => {
    const fetchMock = vi.fn<
      (input: string | URL | Request, init?: RequestInit) => Promise<Response>
    >(async () => jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);

    await updateDraftText(7, { objectives: "Owner text" });
    await replaceDraftAllocations(8, [
      { asset_class_name: "User entered", target_percentage: "12.50" },
    ]);
    await publishDraft(9);
    await createDraft("version-id");
    await getVersionHistory(3);

    expect(fetchMock.mock.calls.map(([url, init]) => [String(url), init?.method])).toEqual([
      [expect.stringMatching(/\/api\/policies\/current\/draft$/), "PATCH"],
      [expect.stringMatching(/\/api\/policies\/current\/draft\/allocations$/), "PUT"],
      [expect.stringMatching(/\/api\/policies\/current\/draft\/publish$/), "POST"],
      [expect.stringMatching(/\/api\/policies\/current\/draft$/), "POST"],
      [expect.stringMatching(/\/api\/policies\/current\/versions\?before_version_number=3$/), undefined],
    ]);
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      expected_revision: 8,
      items: [{ asset_class_name: "User entered", target_percentage: "12.50" }],
    });
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toEqual({
      expected_revision: 9,
      confirmation: true,
    });
    expect(JSON.parse(String(fetchMock.mock.calls[3][1]?.body))).toEqual({
      source_version_id: "version-id",
    });
  });

  it.each([404, 409, 422])("preserves HTTP %s as a typed neutral error", async (status) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "secret-marker owner payload" }, status)),
    );

    const error = await getPolicyAuditEvents().catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(PolicyApiError);
    expect((error as PolicyApiError).status).toBe(status);
    expect((error as Error).message).not.toContain("secret-marker");
  });

  it.each([
    [500, null],
    [500, "not-json"],
    [503, { detail: "secret-marker owner payload" }],
  ])("uses a neutral message for HTTP %s without reading the response body", async (status, body) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(body === null ? null : typeof body === "string" ? body : JSON.stringify(body), { status })),
    );

    const error = await getPolicyAuditEvents().catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(PolicyApiError);
    expect((error as Error).message).toBe("The Policy service returned an unexpected server error.");
    expect((error as Error).message).not.toContain("secret-marker");
  });

  it("distinguishes a network failure and preserves AbortError", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("private network detail"); }));
    await expect(getPolicyAuditEvents()).rejects.toBeInstanceOf(PolicyNetworkError);
    await expect(getPolicyAuditEvents()).rejects.toThrow("connection is unavailable");

    const abort = new DOMException("Aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn(async () => { throw abort; }));
    await expect(getPolicyAuditEvents()).rejects.toBe(abort);
  });

  it("does not retry a failed mutation", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ detail: "Conflict" }, 409));
    vi.stubGlobal("fetch", fetchMock);

    await expect(updateDraftText(1, { notes: "Private text" })).rejects.toBeInstanceOf(
      PolicyApiError,
    );
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("parses and sums exact integer hundredths without floating-point artifacts", () => {
    expect(percentageToHundredths("0.1")).toBe(10);
    expect(percentageToHundredths("0.2")).toBe(20);
    expect(allocationTotal([
      { asset_class_name: "One", target_percentage: "0.1" },
      { asset_class_name: "Two", target_percentage: "0.2" },
    ])).toEqual({ hundredths: 30, display: "0.30" });
    expect(allocationTotal([{ asset_class_name: "One", target_percentage: "99.99" }]).display).toBe("99.99");
    expect(allocationTotal([{ asset_class_name: "One", target_percentage: "100" }]).display).toBe("100.00");
    expect(allocationTotal([
      { asset_class_name: "One", target_percentage: "99.99" },
      { asset_class_name: "Two", target_percentage: "0.02" },
    ]).display).toBe("100.01");
  });

  it("rejects excess scale and never rounds it", () => {
    expect(percentageToHundredths("12.345")).toBeNull();
    expect(allocationTotal([{ asset_class_name: "One", target_percentage: "12.345" }])).toEqual({
      hundredths: null,
      display: "Invalid input",
    });
  });

  it("treats display case as meaningful while normalizing Unicode whitespace and percentages", () => {
    const saved = [{ id: "1", asset_class_name: "Cash Reserve", target_percentage: "40.00", sort_order: 0 }];
    expect(allocationsEqual(saved, [{ asset_class_name: "  Cash\u00a0 Reserve  ", target_percentage: "40" }])).toBe(true);
    expect(allocationsEqual(saved, [{ asset_class_name: "CASH RESERVE", target_percentage: "40.00" }])).toBe(false);
  });
});
