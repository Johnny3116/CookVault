import type { Ingredient } from "@/types";

export function IngredientColumn({ title, ingredients }: { title: string; ingredients: Ingredient[] }) {
  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">{title}</h4>
      <ul className="space-y-1 text-sm">
        {ingredients.map((ingredient) => (
          <li key={ingredient.id}>
            {ingredient.quantity ? `${ingredient.quantity} ` : ""}
            {ingredient.unit ? `${ingredient.unit} ` : ""}
            {ingredient.name}
          </li>
        ))}
        {ingredients.length === 0 && <li className="text-neutral-400">—</li>}
      </ul>
    </div>
  );
}
