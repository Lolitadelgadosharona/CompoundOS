"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
export const ownerLinks = [
  ["Dashboard", "/"],
  ["Portfolio", "/portfolio"],
  ["Investment Plan", "/investment-plan"],
  ["Committee", "/committee"],
  ["Policy", "/policy"],
  ["Accounts", "/accounts"],
  ["Decisions", "/decisions"],
  ["Settings", "/settings"],
];
export default function OwnerNavigation() {
  const path = usePathname();
  return (
    <header className="owner-navigation">
      <div className="owner-nav-inner">
        <Link href="/" className="owner-brand">
          <strong>COMPOUNDOS</strong>
          <span>AI FAMILY OFFICE</span>
        </Link>
        <nav aria-label="Family office navigation">
          {ownerLinks.map(([label, href]) => (
            <Link
              key={href}
              href={href}
              aria-current={
                (href === "/" ? path === "/" : path?.startsWith(href))
                  ? "page"
                  : undefined
              }
            >
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
