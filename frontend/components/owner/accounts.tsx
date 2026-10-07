"use client";
import { useEffect, useState } from "react";
import { Connections, ownerApi } from "../../lib/owner-data";
import { Loading } from "./shared";
import IBKRInventory from "./ibkr-inventory";
export default function OwnerAccounts() {
  const [data, setData] = useState<Connections | null>(null), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  useEffect(() => {
    let alive = true;
    ownerApi<Connections>("investment/connections").then((d) => { if (alive) setData(d); }).catch(() => { if (alive) setError("Account information is unavailable. Please refresh."); });
    return () => { alive = false; };
  }, []);
  async function action(kind: "sync" | "disconnect") {
    setBusy(true); setError("");
    try {
      const b = await ownerApi<Connections["brokers"][number]>(`investment/ibkr/${kind}`, {});
      setData((previous) => previous ? { ...previous, brokers: previous.brokers.map((row) => row.name === "Interactive Brokers" ? b : row) } : previous);
    } catch (e) { setError(e instanceof Error ? e.message : "Read-only sync unavailable."); }
    finally { setBusy(false); }
  }
  return <main className="owner-shell">
    <header className="owner-page-header"><div><p className="eyebrow">YOUR ACCOUNTS</p><h1>Broker connections</h1><p>Read-only inventory. Your assets stay with your broker.</p></div></header>
    <section className="notice notice-warning"><strong>Owner setup required before any broker read.</strong><p>Authenticate directly with IBKR in its official local gateway. No credentials are requested here. No orders can be placed. Paper first; LIVE reads require separate explicit authorization.</p></section>
    {error && data && <p role="alert">{error}</p>}
    {!data ? <Loading error={error} /> : <>
      <div className="owner-connection-grid">{data.brokers.map((b) => <article className="panel owner-card" key={b.name}>
        <h2>{b.name}</h2><p className="owner-value">{b.status === "NOT_CONNECTED" ? "Not Connected" : b.status}</p>
        <p className="owner-badge">READ ONLY · {b.connection_type && b.connection_type !== "NONE" ? b.connection_type : "PLANNED"}</p>
        <dl><dt>Last sync</dt><dd>{b.last_sync ?? "Never synced"}</dd><dt>Accounts discovered</dt><dd>{b.accounts_discovered ?? "Unknown"}</dd><dt>Cash / positions</dt><dd>{b.cash ?? "Unknown"} / {b.positions ?? "Unknown"}</dd><dt>Data quality</dt><dd>{b.data_quality ?? "UNKNOWN"}</dd><dt>Read capabilities</dt><dd>{b.capabilities.join(", ")}</dd></dl>
        {b.name === "Interactive Brokers" ? <>
          <button disabled={!b.available || busy} onClick={() => void action("sync")}>{busy ? "Reading…" : b.available ? "SYNC NOW" : "Complete local Owner setup"}</button>
          {b.connection_type && b.connection_type !== "NONE" && <button disabled={busy} onClick={() => void action("disconnect")}>Disconnect local reads</button>}
        </> : <button disabled>Connection unavailable in Preview</button>}
      </article>)}</div>
      {data.brokers.filter((b) => b.name === "Interactive Brokers" && b.connection_type && b.connection_type !== "NONE").map((b) => <IBKRInventory key={b.name} broker={b} />)}
      <section className="panel"><h2>Manual Portfolio</h2><p>{data.manual.status === "CONNECTED" ? "Connected — your local portfolio records are available." : "Not connected — add manual records in portfolio setup."}</p><p>No external brokerage connection.</p></section>
    </>}
    <section className="panel"><h2>Read-only safety</h2><p><strong>Order execution is not supported.</strong></p><p>Only account, position, cash and available cost information may be read. Imported holdings never create strategic targets. No order preview, execution, transfers or withdrawals.</p><p>Disconnect stops CompoundOS reads and retains last-known data. Log out or stop the official gateway separately to end the IBKR session.</p></section>
  </main>;
}
