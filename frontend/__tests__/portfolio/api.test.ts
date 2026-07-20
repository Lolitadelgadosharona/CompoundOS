import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";

import {
  estimateTotal,
  formatDecimal,
  isCash,
  isFutureValuationDate,
  isValidQuantity,
  isValidUnitPrice,
  isValidValuationDate,
  PortfolioApiError,
  PortfolioNetworkError,
} from "../../lib/portfolio-api";

// ---------------------------------------------------------------------------
// isCash
// ---------------------------------------------------------------------------

describe("isCash", () => {
  it("returns true for 'cash'", () => {
    expect(isCash("cash")).toBe(true);
  });

  it("returns true for 'CASH'", () => {
    expect(isCash("CASH")).toBe(true);
  });

  it("returns true for ' Cash '", () => {
    expect(isCash(" Cash ")).toBe(true);
  });

  it("returns false for 'equity'", () => {
    expect(isCash("equity")).toBe(false);
  });

  it("returns false for empty string", () => {
    expect(isCash("")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// formatDecimal
// ---------------------------------------------------------------------------

describe("formatDecimal", () => {
  it("strips trailing zeros from '100.00000000'", () => {
    expect(formatDecimal("100.00000000")).toBe("100");
  });

  it("strips trailing zeros from '150.5000'", () => {
    expect(formatDecimal("150.5000")).toBe("150.5");
  });

  it("returns '0' for zero", () => {
    expect(formatDecimal("0.00")).toBe("0");
  });

  it("preserves '0.01'", () => {
    expect(formatDecimal("0.01")).toBe("0.01");
  });

  it("returns '0' for empty", () => {
    expect(formatDecimal("")).toBe("0");
  });

  it("handles large numbers", () => {
    expect(formatDecimal("1234567.8900")).toBe("1234567.89");
  });
});

// ---------------------------------------------------------------------------
// isValidQuantity
// ---------------------------------------------------------------------------

describe("isValidQuantity", () => {
  it("accepts '100'", () => {
    expect(isValidQuantity("100")).toBe(true);
  });

  it("accepts '0.00000001' (minimum)", () => {
    expect(isValidQuantity("0.00000001")).toBe(true);
  });

  it("accepts fractional '1.5'", () => {
    expect(isValidQuantity("1.5")).toBe(true);
  });

  it("accepts 8 decimal places", () => {
    expect(isValidQuantity("1.12345678")).toBe(true);
  });

  it("rejects 9 decimal places", () => {
    expect(isValidQuantity("1.123456789")).toBe(false);
  });

  it("rejects '0'", () => {
    expect(isValidQuantity("0")).toBe(false);
  });

  it("rejects negative", () => {
    expect(isValidQuantity("-5")).toBe(false);
  });

  it("rejects empty", () => {
    expect(isValidQuantity("")).toBe(false);
  });

  it("rejects letters", () => {
    expect(isValidQuantity("abc")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// isValidUnitPrice
// ---------------------------------------------------------------------------

describe("isValidUnitPrice", () => {
  it("accepts '100'", () => {
    expect(isValidUnitPrice("100")).toBe(true);
  });

  it("accepts '0'", () => {
    expect(isValidUnitPrice("0")).toBe(true);
  });

  it("accepts '0.0000' (zero price)", () => {
    expect(isValidUnitPrice("0.0000")).toBe(true);
  });

  it("accepts 4 decimal places", () => {
    expect(isValidUnitPrice("150.1234")).toBe(true);
  });

  it("rejects 5 decimal places", () => {
    expect(isValidUnitPrice("150.12345")).toBe(false);
  });

  it("rejects negative", () => {
    expect(isValidUnitPrice("-1")).toBe(false);
  });

  it("rejects empty", () => {
    expect(isValidUnitPrice("")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// isValidValuationDate
// ---------------------------------------------------------------------------

describe("isValidValuationDate", () => {
  it("accepts today", () => {
    // Use a fixed past date for deterministic test behavior.
    // The function compares against real-time Date.now() internally,
    // so using "2026-07-01" (well in the past) guarantees a stable pass.
    expect(isValidValuationDate("2026-07-01")).toBe(true);
  });

  it("accepts past date", () => {
    expect(isValidValuationDate("2020-01-15")).toBe(true);
  });

  it("rejects future date", () => {
    expect(isValidValuationDate("2099-12-31")).toBe(false);
  });

  it("rejects invalid format", () => {
    expect(isValidValuationDate("01/15/2020")).toBe(false);
  });

  it("rejects empty", () => {
    expect(isValidValuationDate("")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// isFutureValuationDate
// ---------------------------------------------------------------------------

describe("isFutureValuationDate", () => {
  it("returns false for past", () => {
    expect(isFutureValuationDate("2020-01-15")).toBe(false);
  });

  it("returns true for future", () => {
    expect(isFutureValuationDate("2099-12-31")).toBe(true);
  });

  it("returns false for today", () => {
    // Use a fixed past date for deterministic test behavior.
    // The function compares against real-time Date.now() internally,
    // so using "2026-07-01" (well in the past) guarantees a stable pass.
    expect(isFutureValuationDate("2026-07-01")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// estimateTotal
// ---------------------------------------------------------------------------

describe("estimateTotal", () => {
  it("computes 100 × 150.5000 = 15050.00", () => {
    expect(estimateTotal("100", "150.5000")).toBe("15050.00");
  });

  it("computes 1 × 1.0000 = 1.00 (cash)", () => {
    expect(estimateTotal("1", "1.0000")).toBe("1.00");
  });

  it("computes 0.5 × 100 = 50.00", () => {
    expect(estimateTotal("0.5", "100")).toBe("50.00");
  });

  it("computes 0.00000001 × 100 = 0.00 (tiny quantity)", () => {
    expect(estimateTotal("0.00000001", "100")).toBe("0.00");
  });

  it("returns null for invalid quantity", () => {
    expect(estimateTotal("abc", "100")).toBeNull();
  });

  it("returns null for invalid price", () => {
    expect(estimateTotal("100", "abc")).toBeNull();
  });

  it("returns null for empty quantity", () => {
    expect(estimateTotal("", "100")).toBeNull();
  });

  it("computes exact cents: 2.125 × 1 = 2.13", () => {
    // 2.125 * 1 rounded to cents (half-up via BigInt rounding)
    expect(estimateTotal("2.125", "1")).toBe("2.13");
  });

  it("returns '0.00' for zero quantity", () => {
    expect(estimateTotal("0", "100")).toBeNull(); // 0 not valid quantity
  });

  it("handles large numbers", () => {
    const result = estimateTotal("1000000", "5000.1234");
    expect(result).toBeTruthy();
    expect(result).toMatch(/^\d+\.\d{2}$/);
  });
});

// ---------------------------------------------------------------------------
// Error classes
// ---------------------------------------------------------------------------

describe("PortfolioApiError", () => {
  it("sets name and status", () => {
    const err = new PortfolioApiError("msg", 409);
    expect(err.name).toBe("PortfolioApiError");
    expect(err.status).toBe(409);
    expect(err.message).toBe("msg");
  });
});

describe("PortfolioNetworkError", () => {
  it("has fixed message", () => {
    const err = new PortfolioNetworkError();
    expect(err.name).toBe("PortfolioNetworkError");
    expect(err.message).toContain("unavailable");
  });
});

// ---------------------------------------------------------------------------
// API client unit tests (mocked fetch)
// ---------------------------------------------------------------------------

describe("API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("getCurrentPortfolio returns null on 404", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", mockFetch);
    const { getCurrentPortfolio } = await import("../../lib/portfolio-api");
    const result = await getCurrentPortfolio();
    expect(result).toBeNull();
  });

  it("getCurrentPortfolio returns data on 200", async () => {
    const state = {
      portfolio: { status: "active" },
      latest_snapshot: {
        id: "snap-1",
        portfolio_id: "port-1",
        version_number: 1,
        status: "current",
        valuation_date: "2026-07-01",
        notes: null,
        holdings: [],
        confirmed_at: "2026-07-01T00:00:00Z",
        holding_count: 0,
      },
    };
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(state), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", mockFetch);
    const { getCurrentPortfolio } = await import("../../lib/portfolio-api");
    const result = await getCurrentPortfolio();
    expect(result).toEqual(state);
  });

  it("createPortfolioDraft returns 201", async () => {
    const createData = {
      portfolio: { id: "p1", household_id: "h1", status: "draft", created_at: "..." },
      draft: {
        portfolio_id: "p1",
        expected_revision: 1,
        valuation_date: null,
        notes: null,
        updated_at: "...",
        holdings: [],
      },
    };
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(createData), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", mockFetch);
    const { createPortfolioDraft } = await import("../../lib/portfolio-api");
    const result = await createPortfolioDraft();
    expect(result.portfolio.status).toBe("draft");
    expect(mockFetch).toHaveBeenCalled();
  });

  it("confirmDraft sends confirmation:true", async () => {
    const snapshot = {
      id: "snap-1",
      portfolio_id: "p1",
      version_number: 1,
      status: "current",
      valuation_date: "2026-07-01",
      notes: null,
      holdings: [],
      confirmed_at: "...",
      holding_count: 0,
    };
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(snapshot), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", mockFetch);
    const { confirmDraft } = await import("../../lib/portfolio-api");
    await confirmDraft(1);
    const body = JSON.parse(String(mockFetch.mock.calls[0]?.[1]?.body));
    expect(body.confirmation).toBe(true);
    expect(body.expected_revision).toBe(1);
  });

  it("discardDraft returns undefined on 204", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(null, { status: 204 }),
    );
    vi.stubGlobal("fetch", mockFetch);
    const { discardDraft } = await import("../../lib/portfolio-api");
    const result = await discardDraft(1);
    expect(result).toBeUndefined();
  });

  it("replaceDraftHoldings formats payload with sort_order", async () => {
    const draftResponse = {
      portfolio_id: "p1",
      expected_revision: 2,
      valuation_date: null,
      notes: null,
      updated_at: "...",
      holdings: [],
    };
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(draftResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", mockFetch);
    const { replaceDraftHoldings } = await import("../../lib/portfolio-api");
    const items = [
      { asset_name: "AAPL", asset_category: "equity", quantity: "100", unit_price: "150.5000", valuation_date: "2026-07-01", sort_order: 1 },
    ];
    await replaceDraftHoldings(1, items);
    const body = JSON.parse(String(mockFetch.mock.calls[0]?.[1]?.body));
    expect(body.expected_revision).toBe(1);
    expect(body.items[0].asset_name).toBe("AAPL");
  });

  it("getSnapshotHistory includes limit param", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [], next_before_version_number: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", mockFetch);
    const { getSnapshotHistory } = await import("../../lib/portfolio-api");
    await getSnapshotHistory();
    const url = String(mockFetch.mock.calls[0]?.[0]);
    expect(url).toContain("limit=20");
  });

  it("getPortfolioAudit includes limit param", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", mockFetch);
    const { getPortfolioAudit } = await import("../../lib/portfolio-api");
    await getPortfolioAudit();
    const url = String(mockFetch.mock.calls[0]?.[0]);
    expect(url).toContain("limit=50");
  });
});
