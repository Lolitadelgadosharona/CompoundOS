"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

type Instrument = {
  asset_id?: string;
  symbol: string;
  name: string;
  currency: string;
  exchange: string;
  provider_id: string;
  asset_type: string;
};
type Target = Instrument & {
  asset_id: string;
  weight: string;
  leverage_status?: "unleveraged" | "leveraged" | "unknown";
  equity_exposure_pct?: string | null;
};
type Allocation = {
  asset_id: string;
  symbol: string;
  target_weight: string;
  current_weight: string;
  absolute_drift: string;
  buy_amount: string;
  post_weight: string;
};
type Candidate = {
  id: string;
  content_hash: string;
  expires_at: string;
  decision_status: string;
  committee_status: string;
  committee_report?: {
    recommended_direction: string;
    confidence?: string;
    supporting_arguments: string[];
    opposing_arguments: string[];
    risks: string[];
  };
  evidence: {
    as_of: string;
    recommendation_ready: boolean;
    plan: {
      new_capital: string;
      retained_cash: string;
      rows: Allocation[];
      reason: string;
    };
    policy: { status: string; findings: string[] };
    guardian: { status: string; findings: { detail: string }[] };
    market_data: {
      symbol: string;
      price: string;
      currency: string;
      as_of: string;
      provider: string;
    }[];
  };
};
type Snapshot = {
  valuation: {
    total_value: string | null;
    base_currency: string;
    status: string;
    as_of: string;
    reasons: string[];
  };
  cash_value: string | null;
  positions: {
    id: string;
    symbol: string;
    value: string | null;
    weight: string | null;
    currency: string;
    quality: string;
    gain_loss_native: string | null;
  }[];
  configuration: {
    monthly_amount: string;
    monthly_currency: string;
    initial_capital: string;
    targets: Target[];
  } | null;
  accounts: { id: string; name: string }[];
  candidates: Candidate[];
};

async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  key?: string,
): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    method,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(key ? { "X-API-Key": key } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : `Request failed (${response.status})`,
    );
  return result as T;
}
const money = (v: string | null | undefined) =>
  v == null
    ? "Unavailable"
    : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });

export default function InvestmentClient() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [key, setKey] = useState(""),
    [query, setQuery] = useState(""),
    [matches, setMatches] = useState<Instrument[]>([]),
    [selected, setSelected] = useState<Target[]>([]);
  const [monthly, setMonthly] = useState("10000"),
    [monthlyCurrency, setMonthlyCurrency] = useState("CNY"),
    [initial, setInitial] = useState("100000");
  const [account, setAccount] = useState(""),
    [quantity, setQuantity] = useState(""),
    [cost, setCost] = useState(""),
    [cash, setCash] = useState(""),
    [cashCurrency, setCashCurrency] = useState("USD");
  const [accountName, setAccountName] = useState(""),
    [consent, setConsent] = useState(false),
    [preview, setPreview] = useState<Candidate | null>(null);
  const [message, setMessage] = useState(""),
    [version, setVersion] = useState<{
      git_sha: string;
      application_version: string;
      status: string;
    } | null>(null);
  const reload = useCallback(async () => {
    setSnapshot(await api<Snapshot>("investment/dashboard"));
  }, []);
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    void api<Snapshot>("investment/dashboard")
      .then((data) => {
        setSnapshot(data);
        if (data.configuration) {
          setSelected(data.configuration.targets);
          setMonthly(data.configuration.monthly_amount);
          setMonthlyCurrency(data.configuration.monthly_currency);
          setInitial(data.configuration.initial_capital);
        }
      })
      .catch((e) => setError(e.message));
    void api<{ git_sha: string; application_version: string; status: string }>(
      "version",
    ).then(setVersion);
  }, [reload]);
  return (
    <main className="shell">
      <h1>Investment workspace</h1>
      <p>
        Real ledger · deterministic evidence · Owner approval · manual execution
      </p>
      <nav>
        <Link href="/">Home</Link> · <Link href="/household">Household</Link> ·{" "}
        <Link href="/policy">Published Policy</Link> ·{" "}
        <Link href="/guardian">Guardian</Link> ·{" "}
        <Link href="/decisions">Decision Journal</Link>
      </nav>
      <details>
        <summary>Owner sign in</summary>
        <label>
          API key{" "}
          <input
            aria-label="API key"
            type="password"
            autoComplete="off"
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
        </label>
        <button
          disabled={busy || !key}
          onClick={() =>
            void act(async () => {
              await api("auth/session", "POST", {}, key);
              setKey("");
            })
          }
        >
          Sign in securely
        </button>
        <button onClick={() => void act(() => api("auth/session", "DELETE"))}>
          Sign out
        </button>
        <p>
          Key is sent once; browser session expires after eight hours.
          Production requires HTTPS.
        </p>
      </details>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <section>
        <h2>Portfolio</h2>
        <p>
          Value: {money(snapshot?.valuation.total_value)}{" "}
          {snapshot?.valuation.base_currency} · Cash:{" "}
          {money(snapshot?.cash_value)}
        </p>
        <p>
          Data: {snapshot?.valuation.status ?? "Not loaded"} · As of{" "}
          {snapshot?.valuation.as_of ?? "Unknown"}
        </p>
        {snapshot?.valuation.reasons.map((r) => (
          <p key={r}>{r}</p>
        ))}
        <button
          disabled={busy}
          onClick={() => void act(() => api("investment/refresh", "POST"))}
        >
          Refresh observed prices and FX
        </button>
        <table>
          <thead>
            <tr>
              <th>Instrument</th>
              <th>Base value</th>
              <th>Weight</th>
              <th>Native gain/loss</th>
              <th>Quality</th>
            </tr>
          </thead>
          <tbody>
            {snapshot?.positions.map((p) => (
              <tr key={p.id}>
                <td>
                  {p.symbol} ({p.currency})
                </td>
                <td>{money(p.value)}</td>
                <td>{money(p.weight)}%</td>
                <td>{money(p.gain_loss_native)}</td>
                <td>{p.quality}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p>
          Missing data blocks recommendations. Manual cost estimates are not
          market quotes.
        </p>
      </section>
      <section>
        <h2>Instrument search</h2>
        <label>
          Symbol, company or ETF description{" "}
          <input value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        <button
          disabled={busy || !query}
          onClick={() =>
            void act(async () =>
              setMatches(
                (
                  await api<{ candidates: Instrument[] }>(
                    `investment/instruments?q=${encodeURIComponent(query)}`,
                  )
                ).candidates,
              ),
            )
          }
        >
          Search
        </button>
        {matches.map((i) => (
          <p key={i.provider_id}>
            {i.symbol} · {i.name} · {i.exchange} · {i.currency}{" "}
            <button
              disabled={busy}
              onClick={() =>
                void act(async () => {
                  const a = await api<Target>(
                    "investment/instruments",
                    "POST",
                    { provider_id: i.provider_id },
                  );
                  setSelected((old) =>
                    old.some((t) => t.asset_id === a.asset_id)
                      ? old
                      : [...old, { ...a, weight: "" }],
                  );
                })
              }
            >
              Select instrument
            </button>
          </p>
        ))}
      </section>
      <section>
        <h2>Accounts, holdings and cash</h2>
        <label>
          New account name{" "}
          <input
            value={accountName}
            onChange={(e) => setAccountName(e.target.value)}
          />
        </label>
        <button
          disabled={busy || !accountName}
          onClick={() =>
            void act(() =>
              api("portfolio/accounts", "POST", {
                name: accountName,
                account_type: "brokerage",
                capital_bucket: "CORE",
                currency: snapshot?.valuation.base_currency ?? "USD",
              }),
            )
          }
        >
          Create account
        </button>
        <label>
          Account{" "}
          <select value={account} onChange={(e) => setAccount(e.target.value)}>
            <option value="">Select account</option>
            {snapshot?.accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Quantity{" "}
          <input
            type="number"
            min="0"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
        </label>
        <label>
          Average cost if known (instrument currency){" "}
          <input
            type="number"
            min="0"
            value={cost}
            onChange={(e) => setCost(e.target.value)}
          />
        </label>
        {selected.map((i) => (
          <button
            key={i.asset_id}
            disabled={busy || !account || !quantity}
            onClick={() =>
              void act(() =>
                api("investment/holdings", "POST", {
                  account_id: account,
                  asset_id: i.asset_id,
                  quantity,
                  avg_cost: cost || null,
                  cost_currency: i.currency,
                }),
              )
            }
          >
            Record {i.symbol} holding
          </button>
        ))}
        <label>
          Cash balance{" "}
          <input
            type="number"
            min="0"
            value={cash}
            onChange={(e) => setCash(e.target.value)}
          />
        </label>
        <label>
          Cash currency{" "}
          <input
            value={cashCurrency}
            onChange={(e) => setCashCurrency(e.target.value.toUpperCase())}
          />
        </label>
        <button
          disabled={busy || !account || !cash}
          onClick={() =>
            void act(() =>
              api("portfolio/cash", "POST", {
                account_id: account,
                currency: cashCurrency,
                amount: cash,
              }),
            )
          }
        >
          Record actual cash
        </button>
        <p>
          Recording holdings/cash updates the native ledger; configuration and
          recommendations never deposit or trade funds.
        </p>
      </section>
      <section>
        <h2>Targets and monthly contribution</h2>
        <p>
          Configured contribution:{" "}
          {snapshot?.configuration
            ? `${snapshot.configuration.monthly_currency} ${money(snapshot.configuration.monthly_amount)}`
            : "Not configured"}
        </p>
        <label>
          Initial investable capital (configuration only){" "}
          <input value={initial} onChange={(e) => setInitial(e.target.value)} />
        </label>
        <label>
          Monthly amount{" "}
          <input value={monthly} onChange={(e) => setMonthly(e.target.value)} />
        </label>
        <label>
          Monthly currency{" "}
          <input
            value={monthlyCurrency}
            onChange={(e) => setMonthlyCurrency(e.target.value.toUpperCase())}
          />
        </label>
        {selected.map((t) => (
          <fieldset key={t.asset_id}><legend>{t.symbol} target</legend><label>
            {t.symbol} target %{" "}
            <input
              type="number"
              min="0"
              max="100"
              value={t.weight}
              onChange={(e) =>
                setSelected((old) =>
                  old.map((x) =>
                    x.asset_id === t.asset_id
                      ? { ...x, weight: e.target.value }
                      : x,
                  ),
                )
              }
            />
            </label>
            {t.asset_type !== "STOCK" && (
              <label>
                <input type="checkbox" checked={t.leverage_status === "unleveraged"}
                  onChange={e => setSelected(old => old.map(x =>
                    x.asset_id === t.asset_id ? {
                      ...x, leverage_status: e.target.checked ? "unleveraged" : "unknown",
                    } : x)))} />
                Owner confirms non-leveraged product from fund documentation (Owner attestation)
              </label>
            )}
            <label>
              Equity look-through % if verified
              <input type="number" min="0" max="100" value={t.equity_exposure_pct ?? ""}
                onChange={e => setSelected(old => old.map(x =>
                  x.asset_id === t.asset_id ? { ...x, equity_exposure_pct: e.target.value } : x)))} />
            </label>
            <button
              onClick={() =>
                setSelected((old) =>
                  old.filter((x) => x.asset_id !== t.asset_id),
                )
              }
            >
              Remove
            </button>
          </fieldset>
        ))}
        <button
          disabled={busy || !selected.length}
          onClick={() =>
            void act(() =>
              api("investment/configuration", "POST", {
                base_currency: snapshot?.valuation.base_currency,
                initial_capital: initial,
                monthly_currency: monthlyCurrency,
                monthly_amount: monthly,
                targets: selected.map((t) => ({
                  asset_id: t.asset_id,
                  weight: t.weight,
                  leverage_status:t.leverage_status??"unknown",
                  equity_exposure_pct:t.equity_exposure_pct||null,
                })),
              }),
            )
          }
        >
          Save targets against published Policy
        </button>
        <button
          disabled={busy || !snapshot?.configuration}
          onClick={() => void act(() => api("investment/candidates", "POST"))}
        >
          Generate contribution candidate
        </button>
        <button
          disabled={busy || !snapshot?.configuration}
          onClick={() =>
            void act(() =>
              api("investment/candidates", "POST", { funding: "initial" }),
            )
          }
        >
          Plan initial capital from recorded cash
        </button>
        <p>
          Targets are Owner configuration, not permanent investment advice.
          Existing Policy and Guardian constraints apply.
        </p>
      </section>
      <section>
        <h2>Owner review and decision history</h2>
        {snapshot?.candidates.map((c) => (
          <article key={c.id}>
            <h3>Contribution · {c.decision_status}</h3>
            <p>
              New capital {money(c.evidence.plan.new_capital)}{" "}
              {snapshot.valuation.base_currency} · Retained cash{" "}
              {money(c.evidence.plan.retained_cash)}
            </p>
            <p>{c.evidence.plan.reason}</p>
            <table>
              <thead>
                <tr>
                  <th>Instrument</th>
                  <th>Current %</th>
                  <th>Target %</th>
                  <th>Drift pp</th>
                  <th>Candidate purchase amount</th>
                </tr>
              </thead>
              <tbody>
                {c.evidence.plan.rows.map((r) => (
                  <tr key={r.asset_id}>
                    <td>{r.symbol}</td>
                    <td>{money(r.current_weight)}</td>
                    <td>{money(r.target_weight)}</td>
                    <td>{money(r.absolute_drift)}</td>
                    <td>{money(r.buy_amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p>
              Policy: {c.evidence.policy.status} · Guardian:{" "}
              {c.evidence.guardian.status} · Committee: {c.committee_status}
            </p>
            {c.evidence.policy.findings.map((f) => (
              <p key={f}>{f}</p>
            ))}
            {c.evidence.guardian.findings.map((f, i) => (
              <p key={i}>
                {typeof f.detail === "string"
                  ? f.detail
                  : "Guardian constraint exceeded"}
              </p>
            ))}
            <p>
              FACT evidence time: {c.evidence.as_of} · Expires: {c.expires_at}
            </p>
            <details>
              <summary>Price provenance (FACT)</summary>
              {c.evidence.market_data.map((q) => (
                <p key={q.symbol}>
                  {q.symbol}: {q.price} {q.currency} · {q.provider} · {q.as_of}
                </p>
              ))}
            </details>
            {c.committee_report && (
              <div>
                <p>
                  Committee direction (RECOMMENDATION):{" "}
                  {c.committee_report.recommended_direction} · Confidence:{" "}
                  {c.committee_report.confidence ?? "Not provided"}
                </p>
                <p>
                  INFERENCE — supporting reasons:{" "}
                  {c.committee_report.supporting_arguments.join("; ")}
                </p>
                <p>
                  INFERENCE — opposing reasons:{" "}
                  {c.committee_report.opposing_arguments.join("; ")}
                </p>
                <p>
                  INFERENCE — risk considerations:{" "}
                  {c.committee_report.risks.join("; ")}
                </p>
              </div>
            )}
            <button
              disabled={
                busy ||
                !c.evidence.recommendation_ready ||
                c.decision_status === "rejected" ||
                c.committee_status !== "not_requested"
              }
              onClick={() =>
                void act(async () => {
                  setPreview(
                    await api<Candidate>(
                      `investment/candidates/${c.id}/committee-preview`,
                      "POST",
                    ),
                  );
                  setConsent(false);
                })
              }
            >
              Ask Committee — preview disclosure
            </button>
            <button
              disabled={
                busy ||
                c.committee_report?.recommended_direction !==
                  "aligned_with_policy" ||
                c.decision_status !== "draft"
              }
              onClick={() =>
                void act(async () => {
                  await api(`investment/candidates/${c.id}/approve`, "POST");
                  setMessage(
                    "Approved for manual execution only. No trade was placed. Exact plan is stored in the Decision Journal.",
                  );
                })
              }
            >
              Approve manual plan
            </button>
            <button
              disabled={
                busy ||
                ["confirmed", "archived", "rejected"].includes(
                  c.decision_status,
                )
              }
              onClick={() =>
                void act(() =>
                  api(`investment/candidates/${c.id}/reject`, "POST"),
                )
              }
            >
              Reject
            </button>
          </article>
        ))}
      </section>
      {preview && (
        <section>
          <h2>Committee privacy preview</h2>
          <p>
            The configured DeepSeek provider will receive this candidate’s
            portfolio value, holdings, targets, contribution, observed prices/FX
            and Policy/Guardian evaluations. No account credentials are
            included.
          </p>
          <p>Evidence hash: {preview.content_hash}</p>
          <label>
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            I confirm disclosure of this evidence to the configured provider.
          </label>
          <button
            disabled={busy || !consent}
            onClick={() =>
              void act(async () => {
                await api(
                  `investment/candidates/${preview.id}/committee`,
                  "POST",
                  { confirmation: true, content_hash: preview.content_hash },
                );
                setPreview(null);
              })
            }
          >
            Confirm and run existing Committee
          </button>
        </section>
      )}
      <p>
        Application {version?.application_version} · Build {version?.git_sha} ·{" "}
        {version?.status}
      </p>
      <p>
        Backtesting, Monte Carlo and optimizer are deferred. No broker
        connection or automatic execution exists in this flow.
      </p>
    </main>
  );
}
