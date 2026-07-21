"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

interface NotificationEvent { id: string; source: string; severity: string; title: string; delivery_status: string; suppressed_reason?: string; occurred_at: string; }
interface Preferences { quiet_hours_start: string; quiet_hours_end: string; timezone: string; enabled: boolean; enabled_sources: string[]; enabled_severities: string[]; }

async function getJSON<T>(path: string, s?: AbortSignal): Promise<T> {
  const r = await fetch(new URL(path, BASE).toString(), { signal: s });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

export default function NotificationsClient() {
  const [events, setEvents] = useState<NotificationEvent[]>([]);
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    const ac = new AbortController(); abortRef.current?.abort(); abortRef.current = ac;
    setLoading(true);
    try {
      const [e, p] = await Promise.all([
        getJSON<NotificationEvent[]>("/api/notifications/events", ac.signal),
        getJSON<Preferences>("/api/notifications/preferences", ac.signal),
      ]);
      setEvents(e); setPrefs(p);
    } catch { /* silent */ } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load(); return () => abortRef.current?.abort(); }, [load]);

  const toggleEnabled = useCallback(async () => {
    if (!prefs) return;
    setToggling(true);
    try {
      const r = await fetch(new URL("/api/notifications/preferences", BASE).toString(), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !prefs.enabled }),
      });
      if (r.ok) {
        const updated = await r.json() as Preferences;
        setPrefs(updated);
      }
    } catch { /* silent */ } finally { setToggling(false); }
  }, [prefs]);

  if (loading) return <main className="shell" role="status"><h1>Notifications</h1><p>Loading…</p></main>;

  return (
    <main className="shell" aria-label="Notifications">
      <h1>Notifications</h1>
      <p>Local notification history. No external notification services.</p>
      <nav><Link href="/">← Home</Link></nav>
      {prefs && <section aria-label="Preferences">
        <h2>Preferences</h2>
        <p>
          Status:{" "}
          <button onClick={toggleEnabled} disabled={toggling} aria-label={prefs.enabled ? "Disable notifications" : "Enable notifications"}>
            {prefs.enabled ? "Enabled" : "Disabled"}
          </button>
        </p>
        <p>Quiet hours: {prefs.quiet_hours_start}–{prefs.quiet_hours_end} ({prefs.timezone})</p>
        {prefs.enabled && (
          <>
            <p>Enabled sources: {prefs.enabled_sources.length > 0 ? prefs.enabled_sources.join(", ") : "none"}</p>
            <p>Enabled severities: {prefs.enabled_severities.length > 0 ? prefs.enabled_severities.join(", ") : "none"}</p>
          </>
        )}
      </section>}
      <section aria-label="History">
        <h2>History ({events.length})</h2>
        {events.length === 0 && <p>No notifications.</p>}
        <ul role="list">{events.map(e => (
          <li key={e.id}>
            <strong>{e.severity}</strong> · {e.source} · {e.title} · <em>{e.delivery_status}</em>
            {e.suppressed_reason && <> · <small>({e.suppressed_reason})</small></>}
            {" · "}{new Date(e.occurred_at).toLocaleString()}
          </li>
        ))}</ul>
        <button onClick={load} aria-label="Refresh">Refresh</button>
      </section>
    </main>
  );
}
