import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import Accounts from "./accounts";
import IBKRInventory from "./ibkr-inventory";
import { Connections } from "../../lib/owner-data";
const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("../../lib/owner-data", () => ({ ownerApi: api }));
const broker: Connections["brokers"][number] = {
  name: "Interactive Brokers", status: "CONNECTED", mode: "READ_ONLY", available: true,
  capabilities: ["ACCOUNT_READ", "POSITIONS_READ", "CASH_READ", "COST_BASIS_READ"],
  connection_type: "PAPER", last_sync: "2026-10-06", positions: 1, accounts_discovered: 1,
  data_quality: "UNKNOWN", unresolved: 0,
  holdings: [{ account: "…4567", symbol: "BRK.B", conid: "4", quantity: "2.5", currency: "USD", average_cost: "100", canonical_id: "asset", identity_status: "CURRENT", target: "0", non_target: true, quality: "UNKNOWN", source: "PAPER" }],
};
afterEach(() => { cleanup(); api.mockReset(); });
it("shows Paper inventory and zero strategic target without live valuation or trading controls", () => {
  render(<IBKRInventory broker={broker} />);
  expect(screen.getByText("IBKR inventory · PAPER")).toBeTruthy();
  expect(screen.getByText("MIXED DATA MODE · READ ONLY · VALUATION NOT LIVE")).toBeTruthy();
  expect(screen.getByText("0% · Non-target holding")).toBeTruthy();
  expect(screen.getByText("BRK.B · conid 4")).toBeTruthy();
  expect(screen.queryByRole("button")).toBeNull();
});
it("syncs only on Owner click, never accepts credentials and preserves Paper display", async () => {
  const disconnected = { ...broker, status: "NOT_CONNECTED", connection_type: "NONE" as const };
  api.mockResolvedValueOnce({ brokers: [disconnected], manual: { status: "CONNECTED" } }).mockResolvedValueOnce(broker);
  render(<Accounts />);
  await screen.findByRole("button", { name: "SYNC NOW" });
  expect(api.mock.calls.length).toBe(1);
  fireEvent.click(screen.getByRole("button", { name: "SYNC NOW" }));
  await screen.findByText("IBKR inventory · PAPER");
  expect(api.mock.calls[1]).toEqual(["investment/ibkr/sync", {}]);
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(document.querySelector('input[type="password"]')).toBeNull();
});
it("labels failures and last-known observations explicitly", () => {
  render(<IBKRInventory broker={{ ...broker, status: "SYNC_FAILED", data_quality: "STALE", error_code: "IBKR_OWNER_REAUTHENTICATION_REQUIRED" }} />);
  expect(screen.getByRole("alert").textContent).toContain("Previous data is retained");
  expect(screen.getByText("BRK.B · conid 4")).toBeTruthy();
});
it("shows LIVE read inventory separately from not-live mixed valuation", () => {
  render(<IBKRInventory broker={{ ...broker, connection_type: "LIVE" }} />);
  expect(screen.getByText("IBKR inventory · LIVE")).toBeTruthy();
  expect(screen.getByText("MIXED DATA MODE · READ ONLY · VALUATION NOT LIVE")).toBeTruthy();
});
