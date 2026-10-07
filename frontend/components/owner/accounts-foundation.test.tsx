import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import Accounts from "./accounts";
vi.mock("../../lib/owner-data", () => ({
  ownerApi: vi.fn().mockResolvedValue({
    brokers: [{ name: "Synthetic broker", status: "NOT_CONNECTED", mode: "READ_ONLY", available: false, capabilities: ["ACCOUNT_READ"], last_sync: null, accounts_discovered: 0, cash: null, positions: null, data_quality: "UNKNOWN" }],
    manual: { status: "CONNECTED" }, credentials_accepted: false, order_execution_supported: false,
  }),
}));
afterEach(cleanup);
it("keeps unknown broker balances explicit and prevents connection or credential collection", async () => {
  render(<Accounts />);
  await screen.findByText("Synthetic broker");
  expect(screen.getByText("Never synced")).toBeTruthy();
  expect(screen.getByText("UNKNOWN")).toBeTruthy();
  expect(screen.getByText("Unknown / Unknown")).toBeTruthy();
  expect(screen.getByText("READ ONLY · PLANNED")).toBeTruthy();
  expect(screen.getByRole("button").hasAttribute("disabled")).toBe(true);
  expect(document.querySelector('input[type="password"]')).toBeNull();
});
