import Link from "next/link";
export default function SettingsPage() {
  return (
    <main className="owner-shell">
      <header className="owner-page-header">
        <div>
          <p className="eyebrow">YOUR FAMILY OFFICE</p>
          <h1>Settings</h1>
          <p>Your household context and preferences, one place.</p>
        </div>
      </header>
      <section className="panel">
        <h2>Household</h2>
        <p>Your family’s currency, planning horizon and liquidity needs.</p>
        <Link className="primary-link" href="/settings/household">
          Manage Household →
        </Link>
      </section>
      <details className="panel">
        <summary>Advanced workspace</summary>
        <p>Portfolio setup, calculation records and operational details.</p>
        <Link href="/investment">Portfolio setup</Link> ·{" "}
        <Link href="/governance/journal">Journal & audit</Link>
      </details>
    </main>
  );
}
