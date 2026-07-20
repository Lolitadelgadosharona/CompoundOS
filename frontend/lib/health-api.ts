/** Sprint 007 Slice B — Health API client (3 endpoints). */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export interface ComponentHealth {
  component: string;
  status: string;
  reason: string;
  last_checked: string | null;
  details: Record<string, unknown>;
}

export interface HealthResult {
  overall: string;
  components: ComponentHealth[];
  checked_at: string;
}

export interface LivenessResult {
  alive: boolean;
  checked_at: string;
}

export interface ReadinessResult {
  ready: boolean;
  reason: string;
  checked_at: string;
}

class HealthError extends Error {
  constructor(message: string) { super(message); this.name = "HealthError"; }
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const url = new URL(path, BASE);
  const resp = await fetch(url.toString(), { signal });
  if (!resp.ok) throw new HealthError(`Health API error: ${resp.status}`);
  return resp.json();
}

export function getLiveness(signal?: AbortSignal): Promise<LivenessResult> {
  return request<LivenessResult>("/api/health/live", signal);
}

export function getReadiness(signal?: AbortSignal): Promise<ReadinessResult> {
  return request<ReadinessResult>("/api/health/ready", signal);
}

export function getFullHealth(signal?: AbortSignal): Promise<HealthResult> {
  return request<HealthResult>("/api/health/full", signal);
}
