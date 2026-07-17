import Link from "next/link";

export default function HomePage() {
  return (
    <main className="shell">
      <h1>CompoundOS</h1>
      <p>Local household discipline workspace.</p>
      <nav className="home-actions" aria-label="CompoundOS workspaces">
        <Link className="primary-link" href="/household">
          Open household profile
        </Link>
        <Link href="/policy">Open Investment Policy</Link>
        <Link href="/portfolio">Open Portfolio</Link>
        <Link href="/decisions">Open Decision Journal</Link>
        <Link href="/guardian">Open Guardian Monitoring</Link>
      </nav>
    </main>
  );
}
