"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

interface NotificationEvent { id: string; source: string; severity: string; title: string; delivery_status: string; occurred_at: string; }
interface Preferences { quiet_hours_start: string; quiet_hours_end: string; timezone: string; }

async function getJSON<T>(path: string, s?: AbortSignal): Promise<T> {
  const r = await fetch(new URL(path, BASE).toString(), { signal: s });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

export default function NotificationsClient() {
  const [events, setEvents] = useState<NotificationEvent[]>([]);
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [loading, setLoading] = useState(true);
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

  if (loading) return <main className="shell" role="status"><h1>Notifications</h1><p>Loading…</p></main>;

  return (
    <main className="shell" aria-label="Notifications">
      <h1>Notifications</h1>
      <p>Local notification history. No external notification services.</p>
      <nav><Link href="/">← Home</Link></nav>
      {prefs && <section aria-label="Preferences">
        <h2>Preferences</h2>
        <p>Quiet hours: {prefs.quiet_hours_start}–{prefs.quiet_hours_end} ({prefs.timezone})</p>
      </section>}
      <section aria-label="History">
        <h2>History ({events.length})</h2>
        {events.length === 0 && <p>No notifications.</p>}
        <ul role="list">{events.map(e => (
          <li key={e.id}>{e.severity} · {e.source} · {e.title} · {e.delivery_status} · {new Date(e.occurred_at).toLocaleString()}</li>
        ))}</ul>
        <button onClick={load} aria-label="Refresh">Refresh</button>
      </section>
    </main>
  );
}
