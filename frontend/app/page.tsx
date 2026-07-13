import Link from "next/link";

export default function HomePage() {
  return (
    <main className="shell">
      <h1>CompoundOS</h1>
      <p>Local household discipline workspace.</p>
      <Link className="primary-link" href="/household">
        Open household profile
      </Link>
    </main>
  );
}
