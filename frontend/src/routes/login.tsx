import { createFileRoute } from "@tanstack/react-router";
import { BookOpen } from "lucide-react";
import { useState } from "react";

import { ErrorText } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { apiFetch, json } from "@/lib/api";

export const Route = createFileRoute("/login")({
  validateSearch: (search: Record<string, unknown>) => ({
    next: typeof search["next"] === "string" ? search["next"] : "/",
  }),
  component: LoginPage,
});

function LoginPage() {
  const { next } = Route.useSearch();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await apiFetch("/auth/login", json("POST", { password }));
      // Full navigation so every page refetches with the new session cookie.
      window.location.href = next.startsWith("/") ? next : "/";
    } catch {
      setError("Incorrect password.");
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-[80vh] items-center justify-center">
      <form onSubmit={handleSubmit} className="glass-panel w-full max-w-sm space-y-4 p-8">
        <div className="brand-lockup">
          <span className="brand-mark">
            <BookOpen aria-hidden="true" />
          </span>
          <span>
            <strong>CookVault</strong>
            <small>your kitchen</small>
          </span>
        </div>
        <p className="text-sm text-muted-foreground">This vault is password protected.</p>
        <input
          type="password"
          autoFocus
          placeholder="Password"
          aria-label="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="field"
        />
        <ErrorText>{error}</ErrorText>
        <Button type="submit" className="w-full rounded-xl" disabled={submitting || !password}>
          {submitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </div>
  );
}
