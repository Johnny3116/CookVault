import Link from "next/link";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/library", label: "Library" },
  { href: "/recipes/new", label: "Add Recipe" },
  { href: "/drafts", label: "Drafts" },
  { href: "/finder", label: "Finder" },
  { href: "/shopping-list", label: "Shopping List" },
  { href: "/pantry", label: "Pantry" },
  { href: "/calendar", label: "Calendar" },
];

export function Nav() {
  return (
    // Six links do not fit on a phone in one row, and pushing the page
    // sideways is worse than a second line of nav.
    <nav className="flex flex-wrap gap-x-4 gap-y-2 border-b border-neutral-200 px-6 py-4">
      {links.map((link) => (
        <Link key={link.href} href={link.href} className="text-sm font-medium hover:underline">
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
