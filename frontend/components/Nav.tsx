import Link from "next/link";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/library", label: "Library" },
  { href: "/recipes/new", label: "Add Recipe" },
  { href: "/finder", label: "Finder" },
  { href: "/shopping-list", label: "Shopping List" },
  { href: "/calendar", label: "Calendar" },
];

export function Nav() {
  return (
    <nav className="flex gap-4 border-b border-neutral-200 px-6 py-4">
      {links.map((link) => (
        <Link key={link.href} href={link.href} className="text-sm font-medium hover:underline">
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
