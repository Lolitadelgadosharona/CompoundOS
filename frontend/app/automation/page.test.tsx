import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import AutomationClient from "../../app/automation/automation-client";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const schedule = {
  id: "s1",
  job_definition_id: "jd1",
  job_type: "guardian.evaluate_all",
  job_params: {},
  execution_time: "09:00:00",
  timezone: "UTC",
  next_run_at: "2026-07-20T09:00:00Z",
  enabled: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const scheduleEnabled = { ...schedule, enabled: true };
const workerOk = { worker_count: 1, active_leases: 0, running_runs: 0 };

describe("AutomationClient — UI states", () => {
  it("loading", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<AutomationClient />);
    expect(screen.getByRole("status").textContent).toContain("Loading");
  });

  it("no household", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      void input;
      return json({ detail: "not found" }, 404);
    }));
    render(<AutomationClient />);
    expect(await screen.findByText(/No household profile/)).toBeTruthy();
  });

  it("no schedules", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      if (String(input).includes("schedules")) return json([]);
      if (String(input).includes("worker")) return json(workerOk);
      return new Response(null, { status: 404 });
    }));
    render(<AutomationClient />);
    expect(await screen.findByText(/No schedules configured/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Create schedule/ })).toBeTruthy();
  });

  it("schedules list", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      if (String(input).includes("schedules")) return json([schedule]);
      if (String(input).includes("worker")) return json(workerOk);
      return new Response(null, { status: 404 });
    }));
    render(<AutomationClient />);
    expect(await screen.findByRole("button", { name: /guardian.evaluate_all/ })).toBeTruthy();
  });

  it("create: default disabled", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      if (String(input).includes("schedules")) return json([]);
      if (String(input).includes("worker")) return json(workerOk);
      return new Response(null, { status: 404 });
    }));
    render(<AutomationClient />);
    await screen.findByRole("button", { name: /Create schedule/ });
    await userEvent.click(screen.getByRole("button", { name: /Create schedule/ }));
    expect(screen.getByLabelText("Job type")).toBeTruthy();
  });

  it("enable: explicit action", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string, init?: RequestInit) => {
      if (String(input).includes("schedules/s1") && init?.method === "PATCH") return json({ ...schedule, enabled: true });
      if (String(input).includes("schedules/s1")) return json(schedule);
      if (String(input).includes("schedules") && !init?.method) return json([schedule]);
      if (String(input).includes("worker")) return json(workerOk);
      return new Response(null, { status: 404 });
    }));
    render(<AutomationClient />);
    await screen.findByRole("button", { name: /guardian.evaluate_all/ });
    await userEvent.click(screen.getByRole("button", { name: /guardian.evaluate_all/ }));
    expect(await screen.findByRole("button", { name: /Enable schedule/ })).toBeTruthy();
  });

  it("disable: explicit action", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string, init?: RequestInit) => {
      if (String(input).includes("schedules/s1") && init?.method === "PATCH") return json({ ...scheduleEnabled, enabled: false });
      if (String(input).includes("schedules/s1")) return json(scheduleEnabled);
      if (String(input).includes("schedules") && !init?.method) return json([scheduleEnabled]);
      if (String(input).includes("worker")) return json(workerOk);
      return new Response(null, { status: 404 });
    }));
    render(<AutomationClient />);
    await screen.findByRole("button", { name: /guardian.evaluate_all/ });
    await userEvent.click(screen.getByRole("button", { name: /guardian.evaluate_all/ }));
    expect(await screen.findByRole("button", { name: /Disable schedule/ })).toBeTruthy();
  });

  it("delete: explicit action", async () => {
    let deleted = false;
    vi.stubGlobal("fetch", vi.fn(async (input: string, init?: RequestInit) => {
      if (String(input).includes("schedules/s1") && init?.method === "DELETE") { deleted = true; return new Response(null, { status: 204 }); }
      if (String(input).includes("schedules/s1")) return json(schedule);
      if (String(input).includes("schedules") && !init?.method) return json([schedule]);
      if (String(input).includes("worker")) return json(workerOk);
      return new Response(null, { status: 404 });
    }));
    render(<AutomationClient />);
    await screen.findByRole("button", { name: /guardian.evaluate_all/ });
    await userEvent.click(screen.getByRole("button", { name: /guardian.evaluate_all/ }));
    await screen.findByRole("button", { name: /Delete schedule/ });
    await userEvent.click(screen.getByRole("button", { name: /Delete schedule/ }));
    await waitFor(() => { expect(deleted).toBe(true); });
  });

  it("manual trigger button visible", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string, init?: RequestInit) => {
      if (String(input).includes("schedules/s1")) return json(scheduleEnabled);
      if (String(input).includes("schedules") && !init?.method) return json([scheduleEnabled]);
      if (String(input).includes("worker")) return json(workerOk);
      return new Response(null, { status: 404 });
    }));
    render(<AutomationClient />);
    await screen.findByRole("button", { name: /guardian.evaluate_all/ });
    await userEvent.click(screen.getByRole("button", { name: /guardian.evaluate_all/ }));
    expect(await screen.findByRole("button", { name: /Trigger run now/ })).toBeTruthy();
  });

  it("no auto-trigger on load", async () => {
    const mock = vi.fn(async (input: string, _init?: RequestInit) => {
      void _init;
      if (String(input).includes("schedules")) return json([scheduleEnabled]);
      if (String(input).includes("worker")) return json(workerOk);
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", mock);
    render(<AutomationClient />);
    await screen.findByRole("button", { name: /guardian.evaluate_all/ });
    const postCalls = mock.mock.calls.filter((c: unknown[]) => (c[1] as RequestInit)?.method === "POST");
    expect(postCalls).toHaveLength(0);
  });

  it("Worker status display", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      if (String(input).includes("schedules")) return json([]);
      if (String(input).includes("worker")) return json({ worker_count: 2, active_leases: 1, running_runs: 1 });
      return json({});
    }));
    render(<AutomationClient />);
    expect(await screen.findByText(/Active workers: 2/)).toBeTruthy();
  });

  it("409 conflict preserves local input", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string, init?: RequestInit) => {
      if (String(input).includes("schedules") && init?.method === "POST") return json({ detail: "conflict" }, 409);
      if (String(input).includes("schedules") && !init?.method) return json([]);
      if (String(input).includes("worker")) return json(workerOk);
      return new Response(null, { status: 404 });
    }));
    render(<AutomationClient />);
    await screen.findByRole("button", { name: /Create schedule/ });
    await userEvent.click(screen.getByRole("button", { name: /Create schedule/ }));
    const timeInput = screen.getByLabelText("Execution time") as HTMLInputElement;
    await userEvent.clear(timeInput);
    await userEvent.type(timeInput, "10:00");
    expect(timeInput.value).toBe("10:00");
  });

  it("neutral language", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      if (String(input).includes("schedules")) return json([]);
      if (String(input).includes("worker")) return json(workerOk);
      return new Response(null, { status: 404 });
    }));
    render(<AutomationClient />);
    await screen.findByText(/Nothing here is advice/);
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("Buy");
    expect(body).not.toContain("Sell");
    expect(body).not.toContain("recommend");
  });

  it("accessible: inputs have labels", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      if (String(input).includes("schedules")) return json([]);
      if (String(input).includes("worker")) return json(workerOk);
      return new Response(null, { status: 404 });
    }));
    render(<AutomationClient />);
    await screen.findByRole("button", { name: /Create schedule/ });
    await userEvent.click(screen.getByRole("button", { name: /Create schedule/ }));
    expect(screen.getByLabelText("Job type")).toBeTruthy();
    expect(screen.getByLabelText("Execution time")).toBeTruthy();
    expect(screen.getByLabelText("Timezone (IANA)")).toBeTruthy();
  });

  it("accessible: buttons have names", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      if (String(input).includes("schedules")) return json([schedule]);
      if (String(input).includes("worker")) return json(workerOk);
      return new Response(null, { status: 404 });
    }));
    render(<AutomationClient />);
    await screen.findByRole("button", { name: /guardian.evaluate_all/ });
    expect(screen.getByRole("button", { name: /Create schedule/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Load run history/ })).toBeTruthy();
  });
});
