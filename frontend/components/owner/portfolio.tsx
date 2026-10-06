"use client";
import Link from "next/link";
import { amount } from "../../lib/owner-data";
import { useOverview, Loading, AllocationTable, RiskCard } from "./shared";
export default function OwnerPortfolio() {
  const { data, error } = useOverview();
  if (!data)
    return (
      <main className="owner-shell">
        <Loading error={error} />
      </main>
    );
  return (
    <main className="owner-shell">
      <header className="owner-page-header">
        <div>
          <p className="eyebrow">YOUR PORTFOLIO</p>
          <h1>Where your wealth is invested</h1>
          <p>
            {amount(
              data.snapshot.valuation.total_value,
              data.snapshot.valuation.base_currency,
            )}{" "}
            · DEMO portfolio
          </p>
        </div>
        <Link href="/investment-plan">Review Investment Plan →</Link>
      </header>
      <section className="panel">
        <h2>Current allocation</h2>
        <AllocationTable data={data} />
        <p className="hint">
          Current percentages include cash. Missing data is never treated as
          zero.
        </p>
      </section>
      <RiskCard data={data} />
      <details className="panel">
        <summary>Manage accounts, holdings and target settings</summary>
        <p>
          Use your existing local portfolio workspace to record quantities, cash
          and contribution settings.
        </p>
        <Link href="/investment">Open advanced portfolio setup →</Link>
      </details>
    </main>
  );
}
