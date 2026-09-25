import { Link, useRouterState } from "@tanstack/react-router";
import { BookOpen, Plus } from "lucide-react";
import type { ReactNode } from "react";

const NAV = [
  { to: "/", label: "Home", exact: true },
  { to: "/library", label: "Recipes" },
  { to: "/drafts", label: "Drafts" },
  { to: "/calendar", label: "Meal Plan" },
  { to: "/shopping-list", label: "Shopping" },
  { to: "/pantry", label: "Pantry" },
  { to: "/finder", label: "Finder" },
] as const;

/** The frame every page sits in: brand, the glass nav, and the one button
 *  that is always worth having in reach. */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const isLogin = pathname === "/login";

  return (
    <main className="cookvault-shell min-h-screen text-foreground">
      <div className="mx-auto max-w-[1440px] px-4 py-5 sm:px-6 lg:px-8 lg:py-7">
        {!isLogin && (
          <header className="flex flex-wrap items-center justify-between gap-4">
            <Link to="/" className="brand-lockup" aria-label="CookVault home">
              <span className="brand-mark">
                <BookOpen aria-hidden="true" />
              </span>
              <span>
                <strong>CookVault</strong>
                <small>your kitchen</small>
              </span>
            </Link>

            <nav
              className="glass-nav order-3 flex w-full items-center gap-0.5 overflow-x-auto md:order-none md:w-auto"
              aria-label="CookVault sections"
            >
              {NAV.map((item) => {
                const active = "exact" in item ? pathname === item.to : pathname.startsWith(item.to);
                return (
                  <Link key={item.to} to={item.to} className={active ? "nav-active" : ""}>
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            <Link to="/recipes/new" className="glass-button inline-flex h-9 items-center gap-2 rounded-xl px-4 text-sm font-semibold">
              <Plus className="size-4" /> New Recipe
            </Link>
          </header>
        )}

        <div className={isLogin ? "" : "mt-8 pb-28"}>{children}</div>
      </div>
    </main>
  );
}
