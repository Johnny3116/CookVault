/**
 * The API serializes Postgres NUMERIC columns as JSON strings with their full
 * scale -- "1.500", "2.000". Rendering those raw gives "1.500 cup flour", so
 * trim the trailing zeros without doing float arithmetic on the value.
 */
export function formatQuantity(quantity: string | null): string {
  if (quantity === null || quantity.trim() === "") return "";
  if (!quantity.includes(".")) return quantity;
  const trimmed = quantity.replace(/0+$/, "").replace(/\.$/, "");
  return trimmed === "" || trimmed === "-" ? "0" : trimmed;
}

/** "9.99" -> "$9.99". Returns null when there's nothing to show. */
export function formatCost(cost: string | null): string | null {
  if (cost === null || cost.trim() === "") return null;
  const value = Number(cost);
  return Number.isFinite(value) ? `$${value.toFixed(2)}` : `$${cost}`;
}

/** Renders "2 cup flour" / "flour" without stray spaces when parts are missing. */
export function ingredientLabel(parts: {
  quantity: string | null;
  unit: string | null;
  name: string;
}): string {
  return [formatQuantity(parts.quantity), parts.unit ?? "", parts.name]
    .filter((piece) => piece !== "")
    .join(" ");
}
