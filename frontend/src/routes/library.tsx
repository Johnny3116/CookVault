import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Heart, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState, PageHeader } from "@/components/PageHeader";
import { RecipeCard } from "@/components/RecipeCard";
import { apiFetch, json } from "@/lib/api";
import type { RecipeFacets, RecipeSummary } from "@/types";

type LibrarySearch = {
  favorite?: boolean;
  tag?: string;
  cook_method?: string;
  max_total_time?: number;
  search?: string;
  sort?: string;
};

const TIME_OPTIONS = [
  { value: "", label: "Any time" },
  { value: "20", label: "Under 20 min" },
  { value: "30", label: "Under 30 min" },
  { value: "45", label: "Under 45 min" },
  { value: "60", label: "Under 1 hour" },
];

const str = (v: unknown) => (typeof v === "string" && v ? v : undefined);

export const Route = createFileRoute("/library")({
  // The URL is the source of truth, so a filtered view is shareable and the
  // back button steps through filter changes.
  validateSearch: (raw: Record<string, unknown>): LibrarySearch => ({
    ...(raw["favorite"] === true || raw["favorite"] === "true" ? { favorite: true } : {}),
    ...(str(raw["tag"]) ? { tag: str(raw["tag"]) } : {}),
    ...(str(raw["cook_method"]) ? { cook_method: str(raw["cook_method"]) } : {}),
    ...(Number(raw["max_total_time"]) > 0 ? { max_total_time: Number(raw["max_total_time"]) } : {}),
    ...(str(raw["search"]) ? { search: str(raw["search"]) } : {}),
    ...(str(raw["sort"]) ? { sort: str(raw["sort"]) } : {}),
  }),
  head: () => ({ meta: [{ title: "Recipes — CookVault" }] }),
  component: LibraryPage,
});

function LibraryPage() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: "/library" });
  const queryClient = useQueryClient();
  const [searchDraft, setSearchDraft] = useState(search.search ?? "");

  useEffect(() => setSearchDraft(search.search ?? ""), [search.search]);

  const setFilter = (patch: LibrarySearch) =>
    navigate({ search: (prev) => cleanSearch({ ...prev, ...patch }), replace: true });

  const query = new URLSearchParams();
  if (search.favorite) query.set("favorite", "true");
  if (search.tag) query.set("tag", search.tag);
  if (search.cook_method) query.set("cook_method", search.cook_method);
  if (search.max_total_time) query.set("max_total_time", String(search.max_total_time));
  if (search.search) query.set("search", search.search);
  if (search.sort) query.set("sort", search.sort);
  const qs = query.toString();

  const recipes = useQuery({
    queryKey: ["recipes", qs],
    queryFn: () => apiFetch<RecipeSummary[]>(`/recipes${qs ? `?${qs}` : ""}`),
  });
  const facets = useQuery({ queryKey: ["recipe-facets"], queryFn: () => apiFetch<RecipeFacets>("/recipes/facets") });
  const toggleFavorite = useMutation({
    mutationFn: (recipe: RecipeSummary) =>
      apiFetch(`/recipes/${recipe.id}`, json("PATCH", { is_favorite: !recipe.is_favorite })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["recipes"] }),
  });

  const hasFilters = Boolean(search.favorite || search.tag || search.cook_method || search.max_total_time || search.search);
  const list = recipes.data ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Library"
        title="Your recipes"
        intro={`${list.length} shown${hasFilters ? " with filters" : ""}.`}
      />

      <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center">
        <form
          className="search-field flex-1"
          onSubmit={(e) => {
            e.preventDefault();
            setFilter({ search: searchDraft.trim() || undefined });
          }}
        >
          <Search aria-hidden="true" />
          <span className="sr-only">Search recipes</span>
          <input value={searchDraft} onChange={(e) => setSearchDraft(e.target.value)} placeholder="Search titles…" />
        </form>
        <div className="flex flex-wrap gap-2">
          <select aria-label="Filter by tag" value={search.tag ?? ""} onChange={(e) => setFilter({ tag: e.target.value || undefined })} className="field field-sm w-auto">
            <option value="">All tags</option>
            {(facets.data?.tags ?? []).map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <select aria-label="Filter by cook method" value={search.cook_method ?? ""} onChange={(e) => setFilter({ cook_method: e.target.value || undefined })} className="field field-sm w-auto">
            <option value="">Any method</option>
            {(facets.data?.cook_methods ?? []).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <select aria-label="Filter by total time" value={search.max_total_time ?? ""} onChange={(e) => setFilter({ max_total_time: e.target.value ? Number(e.target.value) : undefined })} className="field field-sm w-auto">
            {TIME_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select aria-label="Sort" value={search.sort ?? ""} onChange={(e) => setFilter({ sort: e.target.value || undefined })} className="field field-sm w-auto">
            <option value="">Recently updated</option>
            <option value="last_cooked">Not made in ages</option>
            <option value="most_cooked">Made most often</option>
            <option value="title">A to Z</option>
            <option value="cost">Cheapest first</option>
          </select>
          <button className="chip inline-flex items-center gap-1" aria-pressed={Boolean(search.favorite)} onClick={() => setFilter({ favorite: search.favorite ? undefined : true })}>
            <Heart className="size-3.5" /> Favorites
          </button>
          {hasFilters && (
            <button className="text-sm font-semibold text-primary underline" onClick={() => navigate({ search: {}, replace: true })}>
              Clear
            </button>
          )}
        </div>
      </div>

      {recipes.isLoading ? (
        <div className="glass-panel p-10 text-center text-muted-foreground">Opening your recipe vault…</div>
      ) : list.length === 0 ? (
        <EmptyState title={hasFilters ? "No recipes match" : "No recipes yet"}>
          {hasFilters ? "Try another search or clear the filters." : "Add your first one, or import from a link."}
        </EmptyState>
      ) : (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {list.map((recipe) => (
            <RecipeCard key={recipe.id} recipe={recipe} onFavorite={(r) => toggleFavorite.mutate(r)} />
          ))}
        </div>
      )}
    </div>
  );
}

function cleanSearch(value: LibrarySearch): LibrarySearch {
  const out: LibrarySearch = {};
  if (value.favorite) out.favorite = true;
  if (value.tag) out.tag = value.tag;
  if (value.cook_method) out.cook_method = value.cook_method;
  if (value.max_total_time) out.max_total_time = value.max_total_time;
  if (value.search) out.search = value.search;
  if (value.sort) out.sort = value.sort;
  return out;
}
