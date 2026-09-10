"use client";

import { useState } from "react";
import Link from "next/link";

import { apiFetch } from "@/lib/api";
import type { RecipeSummary } from "@/types";

interface FinderResults {
  from_collection: RecipeSummary[];
  new_finds: RecipeSummary[];
  new_finds_note: string;
}

export default function FinderPage() {
  const [query, setQuery] = useState("");
  const [fromCollection, setFromCollection] = useState<RecipeSummary[]>([]);
  const [newFindsNote, setNewFindsNote] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await apiFetch<FinderResults>("/finder/search", {
        method: "POST",
        body: JSON.stringify({ query }),
      });
      setFromCollection(data.from_collection ?? []);
      setNewFindsNote(data.new_finds_note ?? null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Recipe Finder</h1>
      <form onSubmit={handleSearch} className="flex gap-2">
        <input
          placeholder="e.g. cheap chicken dinner under 30 minutes"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm"
        />
        <button type="submit" className="rounded bg-neutral-800 px-4 py-2 text-sm text-white">
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-neutral-500">
            From your collection
          </h2>
          <ul className="space-y-2">
            {fromCollection.map((recipe) => (
              <li key={recipe.id}>
                <Link href={`/recipes/${recipe.id}`} className="text-sm underline">
                  {recipe.title}
                </Link>
              </li>
            ))}
            {fromCollection.length === 0 && <p className="text-sm text-neutral-400">No matches yet.</p>}
          </ul>
        </div>
        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-neutral-500">New finds</h2>
          <p className="text-sm text-neutral-400">{newFindsNote ?? "Search to see results."}</p>
        </div>
      </div>
    </div>
  );
}
