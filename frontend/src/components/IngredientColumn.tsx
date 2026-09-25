import { ingredientLabel } from "@/lib/format";
import type { Ingredient } from "@/types";

export function IngredientColumn({ title, ingredients }: { title: string; ingredients: Ingredient[] }) {
  return (
    <div className="column">
      <h3>{title}</h3>
      {ingredients.length === 0 ? (
        <p className="text-sm text-muted-foreground/70">—</p>
      ) : (
        <ul>
          {ingredients.map((ingredient) => (
            <li key={ingredient.id}>{ingredientLabel(ingredient)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
