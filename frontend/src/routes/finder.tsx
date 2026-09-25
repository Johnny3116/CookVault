import { useMutation } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { useState } from "react";

import { ErrorText, PageHeader } from "@/components/PageHeader";
import { RecipeCard } from "@/components/RecipeCard";
import { Button } from "@/components/ui/button";
import { apiFetch, json } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { RecipeSummary } from "@/types";

interface FinderResults {
  from_collection: RecipeSummary[];
  new_finds: RecipeSummary[];
  new_finds_note: string;
}

export const Route = createFileRoute("/finder")({
  head: () => ({ meta: [{ title: "Finder — CookVault" }] }),
  component: FinderPage,
});

function FinderPage() {
  const [query, setQuery] = useState("");
  const search = useMutation({
    mutationFn: (q: string) => apiFetch<FinderResults>("/finder/search", json("POST", { query: q })),
  });

  return (
    <div>
      <PageHeader
        eyebrow="Finder"
        title="What are you in the mood for?"
        intro="Searches your own collection by title and tag. For the conversational version — budget, time, what's in the fridge — ask Sage."
      />
      <form
        className="search-field mb-6 max-w-2xl"
        onSubmit={(e) => {
          e.preventDefault();
          if (query.trim()) search.mutate(query.trim());
        }}
      >
        <Search aria-hidden="true" />
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. cheap chicken dinner" aria-label="Search" />
        <Button type="submit" size="sm" disabled={search.isPending}>
          {search.isPending ? "Searching…" : "Search"}
        </Button>
      </form>

      {search.error && <ErrorText>{describeApiError(search.error)}</ErrorText>}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
        <section>
          <h2 className="mb-3 font-display text-2xl font-semibold">From your collection</h2>
          {!search.data ? (
            <p className="text-sm text-muted-foreground">Search to see results.</p>
          ) : search.data.from_collection.length === 0 ? (
            <p className="text-sm text-muted-foreground">No matches. Try a tag, or a word from the title.</p>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {search.data.from_collection.map((recipe) => (
                <RecipeCard key={recipe.id} recipe={recipe} />
              ))}
            </div>
          )}
        </section>
        <section className="glass-panel h-fit p-5">
          <h2 className="font-display text-xl font-semibold">New finds</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {search.data?.new_finds_note ?? "Web search for new recipes isn't built yet."}
          </p>
          <p className="mt-3 text-sm text-muted-foreground">
            In the meantime, paste any recipe you find and it lands in a draft:{" "}
            <Link to="/drafts/import" className="text-primary underline">
              import a link or text
            </Link>
            .
          </p>
        </section>
      </div>
    </div>
  );
}
