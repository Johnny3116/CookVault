import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { Clock3, ExternalLink, Heart, Pencil, Trash2, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { CookLog } from "@/components/CookLog";
import { IngredientColumn } from "@/components/IngredientColumn";
import { ErrorText } from "@/components/PageHeader";
import { ProvenanceCard } from "@/components/ProvenanceCard";
import { StepList } from "@/components/StepList";
import { Button } from "@/components/ui/button";
import { apiFetch, json } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import { formatCost } from "@/lib/format";
import { COLUMNS, artFor, formatMinutes, totalMinutes } from "@/lib/recipes";
import type { IngredientCategory, RecipeDetail } from "@/types";

const PRESETS = [0.5, 1, 1.5, 2];

export const Route = createFileRoute("/recipes/$id/")({
  // The scaling target lives in the URL, not component state, so a planned
  // meal can link straight to the servings it was planned for and a scaled
  // view survives the back button.
  validateSearch: (raw: Record<string, unknown>): { servings?: number } => {
    const n = Number(raw["servings"]);
    return Number.isFinite(n) && n > 0 ? { servings: n } : {};
  },
  component: RecipePage,
});

function formatScale(value: number) {
  return Number(value.toFixed(2)).toString();
}

function RecipePage() {
  const { id } = Route.useParams();
  const { servings } = Route.useSearch();
  const navigate = useNavigate({ from: "/recipes/$id/" });
  const queryClient = useQueryClient();

  const recipeQuery = useQuery({
    queryKey: ["recipe", id, servings ?? null],
    queryFn: () => apiFetch<RecipeDetail>(`/recipes/${id}${servings ? `?servings=${servings}` : ""}`),
  });
  const recipe = recipeQuery.data;

  const currentTarget = recipe?.scaled_to_servings ?? recipe?.servings ?? null;
  const [servingsDraft, setServingsDraft] = useState("");
  useEffect(() => setServingsDraft(currentTarget === null ? "" : String(currentTarget)), [currentTarget]);

  const setServings = (next: number | null) => {
    const search: { servings?: number } = next === null ? {} : { servings: next };
    navigate({ search, replace: true, resetScroll: false });
  };

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["recipe", id] });
    queryClient.invalidateQueries({ queryKey: ["recipes"] });
  };

  const favorite = useMutation({
    mutationFn: () => apiFetch(`/recipes/${id}`, json("PATCH", { is_favorite: !recipe?.is_favorite })),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: () => apiFetch(`/recipes/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success(`${recipe?.title ?? "Recipe"} was removed.`);
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
      navigate({ to: "/library" });
    },
  });

  if (recipeQuery.error) return <ErrorText>{describeApiError(recipeQuery.error, "Failed to load recipe")}</ErrorText>;
  if (!recipe) return <div className="glass-panel p-10 text-center text-muted-foreground">Opening the recipe…</div>;

  const byCategory = (category: IngredientCategory) => recipe.ingredients.filter((i) => i.category === category);
  const canScale = (recipe.scaled_to_servings ?? recipe.servings ?? 0) > 0;
  const baseServings = recipe.scaled_to_servings
    ? Math.round(recipe.scaled_to_servings / Number(recipe.applied_scale ?? 1))
    : recipe.servings;
  const isScaled = recipe.scaled_to_servings !== null;
  const presetTarget = (multiplier: number) => Math.round((baseServings ?? 0) * multiplier);
  const matchedPresetTarget = PRESETS.map(presetTarget).find((t) => t === currentTarget) ?? null;
  const customScale = baseServings && currentTarget ? currentTarget / baseServings : null;

  function commitServings() {
    const value = Number(servingsDraft);
    if (servingsDraft.trim() === "" || !Number.isFinite(value) || value <= 0) {
      setServingsDraft(currentTarget === null ? "" : String(currentTarget));
      return;
    }
    setServings(value === baseServings ? null : Math.round(value));
  }

  const art = artFor(recipe.title);
  const minutes = formatMinutes(totalMinutes(recipe));
  const error = favorite.error ?? remove.error;

  return (
    <div className="space-y-6">
      <section className="glass-panel recipe-hero">
        <div className="recipe-art" style={{ ["--art-hue" as string]: art.hue }} aria-hidden="true">
          <span>{art.glyph}</span>
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {recipe.tags.map((tag) => (
              <Link key={tag} to="/library" search={{ tag }} className="category-chip">
                {tag}
              </Link>
            ))}
            {recipe.cook_methods.map((method) => (
              <span key={method} className="pill pill-sky">
                {method}
              </span>
            ))}
          </div>
          <h1 className="mt-3 font-display text-3xl font-semibold leading-tight sm:text-4xl">{recipe.title}</h1>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground">
            {minutes && (
              <span className="flex items-center gap-1.5">
                <Clock3 className="size-4" />
                {recipe.prep_time ? `${recipe.prep_time}m prep` : null}
                {recipe.prep_time && recipe.cook_time ? " · " : null}
                {recipe.cook_time ? `${recipe.cook_time}m cook` : null}
              </span>
            )}
            {baseServings && (
              <span className="flex items-center gap-1.5">
                <Users className="size-4" /> serves {baseServings}
              </span>
            )}
            {formatCost(recipe.estimated_cost) && <span>~{formatCost(recipe.estimated_cost)}</span>}
            {recipe.last_cooked_on && (
              <span>
                last cooked {recipe.last_cooked_on}
                {recipe.times_cooked > 1 ? ` · ${recipe.times_cooked}×` : ""}
              </span>
            )}
            {recipe.source_url && (
              <a href={recipe.source_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-primary underline">
                Source <ExternalLink className="size-3.5" />
              </a>
            )}
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <Button variant="secondary" className="glass-button" onClick={() => favorite.mutate()} disabled={favorite.isPending} aria-pressed={recipe.is_favorite}>
              <Heart className={recipe.is_favorite ? "fill-current text-honey" : ""} /> {recipe.is_favorite ? "Favorite" : "Add to favorites"}
            </Button>
            <Button asChild variant="secondary" className="glass-button">
              <Link to="/recipes/$id/edit" params={{ id }}>
                <Pencil /> Edit
              </Link>
            </Button>
            <Button
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => {
                if (window.confirm(`Delete “${recipe.title}”? This can't be undone.`)) remove.mutate();
              }}
            >
              <Trash2 /> Delete
            </Button>
          </div>
          {error && <div className="mt-3"><ErrorText>{describeApiError(error)}</ErrorText></div>}
        </div>
      </section>

      <section className="glass-panel flex flex-wrap items-center gap-2 p-4">
        <span className="mr-1 text-sm font-semibold">Make for</span>
        {canScale ? (
          <>
            {PRESETS.map((multiplier) => {
              const target = presetTarget(multiplier);
              return (
                <button key={multiplier} className="chip" aria-pressed={target === matchedPresetTarget} onClick={() => setServings(multiplier === 1 ? null : target)}>
                  {formatScale(multiplier)}×
                </button>
              );
            })}
            {matchedPresetTarget === null && customScale !== null && (
              <span className="chip is-active" aria-current="true" title="Custom scale">
                {formatScale(customScale)}×
              </span>
            )}
            <input
              type="number"
              min={1}
              aria-label="Servings"
              value={servingsDraft}
              onChange={(e) => setServingsDraft(e.target.value)}
              onBlur={commitServings}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitServings();
                if (e.key === "Escape") setServingsDraft(currentTarget === null ? "" : String(currentTarget));
              }}
              className="field field-sm w-20"
            />
            <span className="text-sm text-muted-foreground">servings</span>
            {isScaled && (
              <span className="basis-full text-xs text-muted-foreground sm:basis-auto">
                scaled {recipe.applied_scale}× from {baseServings} — the saved recipe is unchanged
              </span>
            )}
          </>
        ) : (
          <span className="text-sm text-muted-foreground">Set a servings count on this recipe to scale it.</span>
        )}
      </section>

      <section className="glass-panel p-6">
        <div className="columns-4">
          {COLUMNS.map((column) => (
            <IngredientColumn key={column.category} title={column.label} ingredients={byCategory(column.category)} />
          ))}
        </div>
        <hr className="my-6 border-border" />
        <h2 className="mb-4 font-display text-2xl font-semibold">Method</h2>
        <StepList steps={recipe.steps} />
      </section>

      <section className="glass-panel p-6">
        <h2 className="mb-3 font-display text-2xl font-semibold">Alternates</h2>
        {recipe.alternates.length === 0 ? (
          <p className="text-sm text-muted-foreground">No alternates recorded.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {recipe.alternates.map((alt) => (
              <li key={alt.id} className="flex flex-wrap items-baseline gap-2">
                <span className="pill pill-muted">{alt.type === "cook_method" ? "method" : "ingredient"}</span>
                <span className="font-semibold">{alt.original_value}</span> → {alt.alternate_value}
                {alt.notes && <span className="text-muted-foreground">({alt.notes})</span>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <CookLog recipeId={recipe.id} onChange={invalidate} />

      {recipe.provenance && <ProvenanceCard provenance={recipe.provenance} />}
    </div>
  );
}
