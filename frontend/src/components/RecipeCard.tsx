import { Link } from "@tanstack/react-router";
import { Clock3, Heart, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { artFor, formatMinutes, primaryTag, totalMinutes } from "@/lib/recipes";
import type { RecipeSummary } from "@/types";

/** A recipe in a grid. The whole card opens the recipe; the heart is the one
 *  thing you can do without leaving the page. */
export function RecipeCard({
  recipe,
  onFavorite,
}: {
  recipe: RecipeSummary;
  onFavorite?: (recipe: RecipeSummary) => void;
}) {
  const art = artFor(recipe.title);
  const minutes = formatMinutes(totalMinutes(recipe));
  const tag = primaryTag(recipe);

  return (
    <article className="recipe-card glass-panel flex flex-col overflow-hidden">
      <Link to="/recipes/$id" params={{ id: recipe.id }} className="block flex-1 text-left">
        <div className="recipe-art" style={{ ["--art-hue" as string]: art.hue }} aria-hidden="true">
          <span>{art.glyph}</span>
        </div>
        <div className="p-5">
          <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock3 /> {minutes ?? "untimed"}
            </span>
            <span className="flex items-center gap-1">
              <Users /> {recipe.servings ? `${recipe.servings} servings` : "any"}
            </span>
          </div>
          <h3 className="mt-2 font-display text-xl font-semibold leading-snug">{recipe.title}</h3>
          <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-muted-foreground">
            {recipe.last_cooked_on
              ? `Last cooked ${recipe.last_cooked_on}${recipe.times_cooked > 1 ? ` · ${recipe.times_cooked}×` : ""}`
              : "Never cooked yet"}
            {recipe.cook_methods.length > 0 && ` · ${recipe.cook_methods.join(", ")}`}
          </p>
        </div>
      </Link>
      <div className="flex items-center justify-between px-5 pb-5">
        {tag ? <span className="category-chip">{tag}</span> : <span />}
        {onFavorite ? (
          <Button
            size="icon-sm"
            variant="ghost"
            onClick={() => onFavorite(recipe)}
            aria-pressed={recipe.is_favorite}
            aria-label={`${recipe.is_favorite ? "Remove" : "Add"} ${recipe.title} ${recipe.is_favorite ? "from" : "to"} favorites`}
          >
            <Heart className={recipe.is_favorite ? "fill-current text-honey" : "text-muted-foreground"} />
          </Button>
        ) : (
          recipe.is_favorite && <Heart className="size-4 fill-current text-honey" aria-label="Favorite" />
        )}
      </div>
    </article>
  );
}
