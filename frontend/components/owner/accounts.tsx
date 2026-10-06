"use client";
import { useEffect, useState } from "react";
import { Connections, ownerApi } from "../../lib/owner-data";
import { Loading } from "./shared";
export default function OwnerAccounts() {
  const [data, setData] = useState<Connections | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    ownerApi<Connections>("investment/connections")
      .then((d) => {
        if (alive) setData(d);
      })
      .catch(() => {
        if (alive)
          setError("Account information is unavailable. Please refresh.");
      });
    return () => {
      alive = false;
    };
  }, []);
  return (
    <main className="owner-shell">
      <header className="owner-page-header">
        <div>
          <p className="eyebrow">YOUR ACCOUNTS</p>
          <h1>Broker connections</h1>
          <p>
            A future read-only view of your accounts. Your assets stay with your
            broker.
          </p>
        </div>
      </header>
      <section className="notice notice-warning">
        <strong>Preview does not connect to real brokers.</strong>
        <p>No credentials are requested. No orders can be placed.</p>
      </section>
      {!data ? (
        <Loading error={error} />
      ) : (
        <>
          <div className="owner-connection-grid">
            {data.brokers.map((b) => (
              <article className="panel owner-card" key={b.name}>
                <h2>{b.name}</h2>
                <p className="owner-value">Not Connected</p>
                <p className="owner-badge">READ ONLY · PLANNED</p>
                <p>
                  Future imports may include accounts, positions, cash, cost
                  basis and transaction history, subject to provider permission.
                </p>
                <button disabled>Connection unavailable in Preview</button>
              </article>
            ))}
          </div>
          <section className="panel">
            <h2>Manual Portfolio</h2>
            <p>
              {data.manual.status === "CONNECTED"
                ? "Connected — your local portfolio records are available."
                : "Not connected — add manual records in portfolio setup."}
            </p>
            <p>No external brokerage connection.</p>
          </section>
        </>
      )}
      <section className="panel">
        <h2>How future connections would work</h2>
        <p>
          Manual statements and approved read-only APIs are separate connection
          modes. Availability depends on the broker and applicable agreements;
          no broker API is implemented here.
        </p>
        <ul>
          <li>Read account details and cash balances</li>
          <li>Read positions, cost basis and transaction history</li>
          <li>Reconcile imports with your existing ledger</li>
        </ul>
        <p>
          <strong>Order execution is not supported.</strong> Future order
          preview or execution would need a separate architecture and explicit
          authorization. A read-only connection cannot grant either.
        </p>
      </section>
    </main>
  );
}
