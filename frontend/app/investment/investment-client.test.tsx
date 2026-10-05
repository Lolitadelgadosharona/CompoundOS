// Synthetic UI regression; no credentials, external providers or real ledger writes.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InvestmentClient from "./investment-client";

const snapshot = {
  valuation: {
    total_value: "100000",
    base_currency: "USD",
    status: "COMPLETE",
    as_of: "synthetic-time",
    reasons: [],
  },
  cash_value: "100000",
  positions: [],
  configuration: null,
  accounts: [],
  candidates: [],
};
function mockAPI(data: unknown = snapshot) {
  const calls = vi.fn(async (url: RequestInfo | URL) =>
    Response.json(
      String(url).endsWith("version")
        ? {
            git_sha: "test-sha",
            application_version: "0.2.0",
            status: "UNKNOWN",
          }
        : data,
    ),
  );
  vi.stubGlobal("fetch", calls);
  return calls;
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("Investment launch workspace", () => {
  it("shows shared valuation and manual boundary", async () => {
    mockAPI();
    render(<InvestmentClient />);
    await screen.findByText(/Value: 100,000 USD/);
    expect(screen.getByText(/manual execution/i)).toBeTruthy();
    expect(screen.getByText(/No broker connection/)).toBeTruthy();
  });
  it("shows missing data without a zero portfolio", async () => {
    mockAPI({
      ...snapshot,
      valuation: {
        ...snapshot.valuation,
        total_value: null,
        status: "INCOMPLETE",
        reasons: ["missing FX"],
      },
      cash_value: null,
    });
    render(<InvestmentClient />);
    await screen.findByText("missing FX");
    expect(screen.getByText(/Value: Unavailable/)).toBeTruthy();
  });
  it("has no configured target or silent default recommendation", async () => {
    mockAPI();
    render(<InvestmentClient />);
    await screen.findByText(/Configured contribution: Not configured/);
    expect(
      (
        screen.getByRole("button", {
          name: "Generate contribution candidate",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
  });
  it("displays search candidates and requires explicit selection", async () => {
    const user = userEvent.setup();
    const calls = mockAPI();
    calls.mockImplementation(async (url) =>
      Response.json(
        String(url).includes("instruments?")
          ? {
              candidates: [
                {
                  symbol: "BRK.B",
                  name: "Synthetic class B",
                  exchange: "TEST",
                  currency: "USD",
                  provider_id: "BRK-B",
                  asset_type: "STOCK",
                },
              ],
            }
          : String(url).endsWith("version")
            ? {}
            : snapshot,
      ),
    );
    render(<InvestmentClient />);
    await user.type(
      screen.getByRole("textbox", { name: /Symbol, company/ }),
      "BRK.B",
    );
    await user.click(screen.getByRole("button", { name: "Search" }));
    await screen.findByText(/Synthetic class B/);
    expect(
      screen.getByRole("button", { name: "Select instrument" }),
    ).toBeTruthy();
    expect(calls.mock.calls.some(([u]) => String(u).includes("q=BRK.B"))).toBe(
      true,
    );
  });
  it("does not enable approval before Committee validation", async () => {
    mockAPI({
      ...snapshot,
      candidates: [
        {
          id: "c",
          content_hash: "hash",
          expires_at: "future",
          decision_status: "draft",
          committee_status: "not_requested",
          evidence: {
            as_of: "now",
            recommendation_ready: false,
            plan: {
              new_capital: "1400",
              retained_cash: "0",
              rows: [],
              reason: "Fill deficits",
            },
            policy: { status: "BLOCKED", findings: ["Prohibited asset"] },
            guardian: { status: "PASS", findings: [] },
            market_data: [],
          },
        },
      ],
    });
    render(<InvestmentClient />);
    await screen.findByText("Prohibited asset");
    expect(
      (
        screen.getByRole("button", {
          name: "Approve manual plan",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(
      (
        screen.getByRole("button", {
          name: /Ask Committee/,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
  });
  it("never stores an API key in browser local storage", async () => {
    const user = userEvent.setup();
    mockAPI();
    const spy = vi.spyOn(Storage.prototype, "setItem");
    render(<InvestmentClient />);
    await user.click(screen.getByText("Owner sign in"));
    await user.type(screen.getByLabelText("API key"), "synthetic-key");
    await user.click(screen.getByRole("button", { name: "Sign in securely" }));
    await waitFor(() =>
      expect((screen.getByLabelText("API key") as HTMLInputElement).value).toBe(
        "",
      ),
    );
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});
