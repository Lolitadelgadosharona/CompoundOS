"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { getFullHealth, type HealthResult, type ComponentHealth } from "../../lib/health-api";

// ═══════════════════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════════════════

const STATUS_LABELS: Record<string, string> = {
  healthy: "Healthy", degraded: "Degraded", unavailable: "Unavailable", stale: "Stale", unknown: "Unknown",
};
const STATUS_COLORS: Record<string, string> = {
  healthy: "green", degraded: "orange", unavailable: "red", stale: "yellow", unknown: "gray",
};

const NOTE = "Health dashboard is read-only. No repair, restart, or restore actions are available here.";

// ═══════════════════════════════════════════════════════════════════════════

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString();
}

export default function HealthClient() {
  const [health, setHealth] = useState<HealthResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    const ac = new AbortController();
    abortRef.current?.abort();
    abortRef.current = ac;
    setLoading(true);
    try {
      const result = await getFullHealth(ac.signal);
      setHealth(result);
      setError(null);
    } catch (err) {
      if (!ac.signal.aborted) setError("Health service unavailable.");
    } finally {
      if (!ac.signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    return () => abortRef.current?.abort();
  }, [load]);

  if (loading && !health) {
    return (
      <main className="shell" role="status" aria-label="Loading health">
        <h1>Health Dashboard</h1><p>Loading…</p>
      </main>
    );
  }

  const components = health?.components ?? [];

  return (
    <main className="shell" role="region" aria-label="Health dashboard">
      <h1>Health Dashboard</h1>
      <p role="note">{NOTE}</p>
      {error && <div role="alert"><p>{error}</p></div>}

      <section aria-label="Overall status">
        <h2>Overall: <span aria-label={`Status ${health?.overall ?? "unknown"}`}>
          {STATUS_LABELS[health?.overall ?? "unknown"] ?? health?.overall}
        </span></h2>
        <p>Checked: {fmtTime(health?.checked_at ?? null)}</p>
        <button onClick={load} aria-label="Refresh health status">Refresh</button>
      </section>

      <section aria-label="Component details">
        <h2>Components</h2>
        {components.length === 0 && <p>No component data.</p>}
        <ul role="list">
          {components.map((c: ComponentHealth) => (
            <li key={c.component} aria-label={`${c.component}: ${STATUS_LABELS[c.status] ?? c.status}`}>
              <strong>{c.component}</strong>
              {" — "}
              <span aria-label={STATUS_LABELS[c.status] ?? c.status}>{STATUS_LABELS[c.status] ?? c.status}</span>
              {c.reason && <span> — {c.reason}</span>}
              {c.last_checked && <span> ({fmtTime(c.last_checked)})</span>}
            </li>
          ))}
        </ul>
      </section>

      <nav><Link href="/">← Home</Link></nav>
    </main>
  );
}
