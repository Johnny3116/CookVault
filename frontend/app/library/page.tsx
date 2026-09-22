"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { RecipeCard } from "@/components/RecipeCard";
import { apiFetch } from "@/lib/api";
import type { RecipeFacets, RecipeSummary } from "@/types";

const TIME_OPTIONS = [
  { value: "", label: "Any time" },
  { value: "20", label: "Under 20 min" },
  { value: "30", label: "Under 30 min" },
  { value: "45", label: "Under 45 min" },
  { value: "60", label: "Under 1 hour" },
];

const control = "rounded border border-neutral-300 px-3 py-2 text-sm";

function LibraryContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // The URL is the source of truth, so a filtered view is shareable and the
  // back button steps through filter changes.
  const favoriteOnly = searchParams.get("favorite") === "true";
  const tag = searchParams.get("tag") ?? "";
  const cookMethod = searchParams.get("cook_method") ?? "";
  const maxTime = searchParams.get("max_total_time") ?? "";
  const search = searchParams.get("search") ?? "";
  const sort = searchParams.get("sort") ?? "";

  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [facets, setFacets] = useState<RecipeFacets>({ tags: [], cook_methods: [] });
  const [searchDraft, setSearchDraft] = useState(search);
  const [loading, setLoading] = useState(true);

  const setFilter = useCallback(
    (key: string, value: string) => {
      const next = new URLSearchParams(searchParams.toString());
      if (value) next.set(key, value);
      else next.delete(key);
      router.replace(next.toString() ? `/library?${next}` : "/library");
    },
    [router, searchParams],
  );

  useEffect(() => {
    setSearchDraft(search);
  }, [search]);

  useEffect(() => {
    const query = new URLSearchParams();
    if (favoriteOnly) query.set("favorite", "true");
    if (tag) query.set("tag", tag);
    if (cookMethod) query.set("cook_method", cookMethod);
    if (maxTime) query.set("max_total_time", maxTime);
    if (search) query.set("search", search);
    if (sort) query.set("sort", sort);

    setLoading(true);
    apiFetch<RecipeSummary[]>(`/recipes${query.toString() ? `?${query}` : ""}`)
      .then(setRecipes)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [favoriteOnly, tag, cookMethod, maxTime, search, sort]);

  useEffect(() => {
    apiFetch<RecipeFacets>("/recipes/facets").then(setFacets).catch(() => {});
  }, []);

  const hasFilters = favoriteOnly || tag || cookMethod || maxTime || search;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Recipe Library</h1>

      <div className="flex flex-wrap items-center gap-2">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setFilter("search", searchDraft.trim());
          }}
          className="flex gap-2"
        >
          <input
            placeholder="Search titles"
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
            className={control}
          />
          <button type="submit" className="rounded border border-neutral-300 px-3 py-2 text-sm">
            Search
          </button>
        </form>

        <select
          aria-label="Filter by tag"
          value={tag}
          onChange={(e) => setFilter("tag", e.target.value)}
          className={control}
        >
          <option value="">All tags</option>
          {facets.tags.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        <select
          aria-label="Filter by cook method"
          value={cookMethod}
          onChange={(e) => setFilter("cook_method", e.target.value)}
          className={control}
        >
          <option value="">Any method</option>
          {facets.cook_methods.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>

        <select
          aria-label="Filter by total time"
          value={maxTime}
          onChange={(e) => setFilter("max_total_time", e.target.value)}
          className={control}
        >
          {TIME_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        <select
          aria-label="Sort"
          value={sort}
          onChange={(e) => setFilter("sort", e.target.value)}
          className={control}
        >
          <option value="">Recently updated</option>
          {/* The question cooking history exists to answer. */}
          <option value="last_cooked">Not made in ages</option>
          <option value="most_cooked">Made most often</option>
        </select>

        <button
          onClick={() => setFilter("favorite", favoriteOnly ? "" : "true")}
          aria-pressed={favoriteOnly}
          className={`rounded border px-3 py-2 text-sm ${
            favoriteOnly ? "border-neutral-800 bg-neutral-800 text-white" : "border-neutral-300"
          }`}
        >
          ★ Favorites
        </button>

        {hasFilters && (
          <button onClick={() => router.replace("/library")} className="text-sm underline">
            Clear filters
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
        {recipes.map((recipe) => (
          <RecipeCard key={recipe.id} recipe={recipe} />
        ))}
      </div>
      {!loading && recipes.length === 0 && (
        <p className="text-neutral-500">
          {hasFilters ? "No recipes match these filters." : "No recipes yet — add your first one."}
        </p>
      )}
    </div>
  );
}

export default function LibraryPage() {
  return (
    <Suspense fallback={<p className="text-neutral-500">Loading…</p>}>
      <LibraryContent />
    </Suspense>
  );
}
