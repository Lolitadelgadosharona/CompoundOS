"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  AuditEvent,
  createHousehold,
  getAuditEvents,
  getCurrentHousehold,
  HouseholdApiError,
  HouseholdInput,
  HouseholdProfile,
  updateHousehold,
} from "../../lib/household-api";

const LOCAL_ONLY_NOTICE =
  "This Sprint 002 build is for local, single-user development only. It has no authentication and must not be exposed to the public internet.";

const NON_ADVISORY_NOTICE =
  "CompoundOS records information you enter. It does not evaluate whether an investment policy or decision is suitable, appropriate, or likely to succeed. Policy links and validations are for recordkeeping only and do not constitute investment, tax, or legal advice.";

const EMPTY_FORM: HouseholdInput = {
  household_name: "",
  base_currency: "USD",
  investment_horizon: "",
  liquidity_needs: "",
  risk_statement: "",
  notes: "",
};

async function fetchHouseholdData() {
  const [profile, auditEvents] = await Promise.all([
    getCurrentHousehold(),
    getAuditEvents(),
  ]);
  return { profile, auditEvents };
}

type HouseholdFormProps = {
  initialValue: HouseholdInput;
  submitLabel: string;
  onCancel?: () => void;
  onSubmit: (value: HouseholdInput) => Promise<void>;
};

function HouseholdForm({ initialValue, submitLabel, onCancel, onSubmit }: HouseholdFormProps) {
  const [form, setForm] = useState<HouseholdInput>(initialValue);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function updateField(field: keyof HouseholdInput, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const householdName = form.household_name.trim();
    if (!householdName) {
      setError("Household name is required.");
      return;
    }
    if (!/^[A-Z]{3}$/.test(form.base_currency)) {
      setError("Base currency must be a three-letter uppercase code.");
      return;
    }

    setError(null);
    setSubmitting(true);
    try {
      await onSubmit({ ...form, household_name: householdName });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The household request failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="household-form" onSubmit={handleSubmit} noValidate>
      <label>
        Household name
        <input
          maxLength={200}
          onChange={(event) => updateField("household_name", event.target.value)}
          required
          value={form.household_name}
        />
      </label>
      <label>
        Base currency
        <input
          aria-describedby="currency-hint"
          maxLength={3}
          onChange={(event) => updateField("base_currency", event.target.value)}
          pattern="[A-Z]{3}"
          required
          value={form.base_currency}
        />
        <span className="hint" id="currency-hint">
          Three uppercase letters, such as USD, CNY, or HKD. No conversion is performed.
        </span>
      </label>
      <label>
        Investment horizon
        <textarea
          maxLength={2000}
          onChange={(event) => updateField("investment_horizon", event.target.value)}
          value={form.investment_horizon}
        />
      </label>
      <label>
        Liquidity needs
        <textarea
          maxLength={4000}
          onChange={(event) => updateField("liquidity_needs", event.target.value)}
          value={form.liquidity_needs}
        />
      </label>
      <label>
        Risk statement
        <textarea
          maxLength={4000}
          onChange={(event) => updateField("risk_statement", event.target.value)}
          value={form.risk_statement}
        />
        <span className="hint">Saved as your text without interpretation.</span>
      </label>
      <label>
        Notes
        <textarea
          maxLength={8000}
          onChange={(event) => updateField("notes", event.target.value)}
          value={form.notes}
        />
      </label>
      {error ? <p className="error" role="alert">{error}</p> : null}
      <div className="actions">
        <button className="primary-button" disabled={submitting} type="submit">
          {submitting ? "Saving…" : submitLabel}
        </button>
        {onCancel ? (
          <button disabled={submitting} onClick={onCancel} type="button">
            Cancel
          </button>
        ) : null}
      </div>
    </form>
  );
}

function HouseholdSummary({ profile }: { profile: HouseholdProfile }) {
  const fields: Array<[string, string]> = [
    ["Base currency", profile.base_currency],
    ["Investment horizon", profile.investment_horizon],
    ["Liquidity needs", profile.liquidity_needs],
    ["Risk statement", profile.risk_statement],
    ["Notes", profile.notes],
  ];

  return (
    <dl className="summary-grid">
      {fields.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value || "Not provided"}</dd>
        </div>
      ))}
    </dl>
  );
}

function AuditTimeline({ events }: { events: AuditEvent[] }) {
  return (
    <section className="panel" aria-labelledby="audit-heading">
      <div className="section-heading">
        <p className="eyebrow">Read-only history</p>
        <h2 id="audit-heading">Audit timeline</h2>
      </div>
      {events.length === 0 ? (
        <p>No audit events yet.</p>
      ) : (
        <ol className="timeline">
          {events.map((event) => (
            <li key={event.id}>
              <strong>{event.action === "household.created" ? "Profile created" : "Profile updated"}</strong>
              <span>{new Date(event.occurred_at).toLocaleString()}</span>
              <span>Actor: {event.actor}</span>
              <span>Fields: {event.metadata.changed_fields?.join(", ") ?? "None"}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export function HouseholdClient() {
  const [profile, setProfile] = useState<HouseholdProfile | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  async function reload() {
    setLoading(true);
    setLoadError(null);
    try {
      const result = await fetchHouseholdData();
      setProfile(result.profile);
      setAuditEvents(result.auditEvents);
    } catch (caught) {
      setLoadError(
        caught instanceof HouseholdApiError ? caught.message : "Unable to load household data.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    void fetchHouseholdData()
      .then((result) => {
        if (!active) return;
        setProfile(result.profile);
        setAuditEvents(result.auditEvents);
      })
      .catch((caught: unknown) => {
        if (!active) return;
        setLoadError(
          caught instanceof HouseholdApiError ? caught.message : "Unable to load household data.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleCreate(value: HouseholdInput) {
    const created = await createHousehold(value);
    setProfile(created);
    setAuditEvents(await getAuditEvents());
  }

  async function handleUpdate(value: HouseholdInput) {
    const updated = await updateHousehold(value);
    setProfile(updated);
    setAuditEvents(await getAuditEvents());
    setEditing(false);
  }

  return (
    <main className="household-shell">
      <header className="page-header">
        <p className="eyebrow">CompoundOS · Sprint 002 Slice 1</p>
        <h1>Household profile</h1>
        <p className="lede">Record the household context that you provide, with an immutable audit trail.</p>
      </header>

      <aside className="notice notice-warning" aria-label="Local-only limitation">
        <strong>Local-only limitation</strong>
        <p>{LOCAL_ONLY_NOTICE}</p>
      </aside>
      <aside className="notice" aria-label="Non-advisory notice">
        <strong>Recordkeeping only</strong>
        <p>{NON_ADVISORY_NOTICE}</p>
      </aside>

      {loading ? <p role="status">Loading household profile…</p> : null}
      {loadError ? (
        <div className="error-panel" role="alert">
          <p>{loadError}</p>
          <button onClick={() => void reload()} type="button">Try again</button>
        </div>
      ) : null}

      {!loading && !loadError && !profile ? (
        <section className="panel" aria-labelledby="create-heading">
          <div className="section-heading">
            <p className="eyebrow">Empty household workspace</p>
            <h2 id="create-heading">Create the household profile</h2>
          </div>
          <HouseholdForm initialValue={EMPTY_FORM} onSubmit={handleCreate} submitLabel="Create profile" />
        </section>
      ) : null}

      {!loading && !loadError && profile ? (
        <>
          <section className="panel" aria-labelledby="summary-heading">
            <div className="section-heading section-heading-row">
              <div>
                <p className="eyebrow">Current profile</p>
                <h2 id="summary-heading">{profile.household_name}</h2>
              </div>
              {!editing ? <button onClick={() => setEditing(true)} type="button">Edit profile</button> : null}
            </div>
            {editing ? (
              <HouseholdForm
                initialValue={profile}
                onCancel={() => setEditing(false)}
                onSubmit={handleUpdate}
                submitLabel="Save changes"
              />
            ) : (
              <HouseholdSummary profile={profile} />
            )}
          </section>
          <AuditTimeline events={auditEvents} />
        </>
      ) : null}
    </main>
  );
}
