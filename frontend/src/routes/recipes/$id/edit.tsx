import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";

import { ErrorText, PageHeader } from "@/components/PageHeader";
import { RecipeForm, type RecipePayload } from "@/components/RecipeForm";
import { apiFetch, json } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { RecipeDetail } from "@/types";

export const Route = createFileRoute("/recipes/$id/edit")({
  component: EditRecipePage,
});

function EditRecipePage() {
  const { id } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const recipe = useQuery({ queryKey: ["recipe", id, null], queryFn: () => apiFetch<RecipeDetail>(`/recipes/${id}`) });

  async function handleSubmit(payload: RecipePayload) {
    // PUT replaces the recipe and all its children in one call, so the form
    // doesn't have to diff ingredients and steps against per-child endpoints.
    await apiFetch(`/recipes/${id}`, json("PUT", { ...payload, source_type: recipe.data?.source_type ?? "manual" }));
    queryClient.invalidateQueries({ queryKey: ["recipe", id] });
    queryClient.invalidateQueries({ queryKey: ["recipes"] });
    toast.success("Recipe saved.");
    navigate({ to: "/recipes/$id", params: { id } });
  }

  if (recipe.error) return <ErrorText>{describeApiError(recipe.error, "Failed to load recipe")}</ErrorText>;
  if (!recipe.data) return <div className="glass-panel p-10 text-center text-muted-foreground">Loading…</div>;

  return (
    <div>
      <PageHeader eyebrow="Edit" title={recipe.data.title} />
      <RecipeForm initial={recipe.data} submitLabel="Save changes" onSubmit={handleSubmit} />
    </div>
  );
}
