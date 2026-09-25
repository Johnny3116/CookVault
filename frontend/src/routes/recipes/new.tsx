import { useQueryClient } from "@tanstack/react-query";
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";

import { PageHeader } from "@/components/PageHeader";
import { RecipeForm, type RecipePayload } from "@/components/RecipeForm";
import { Button } from "@/components/ui/button";
import { apiFetch, json } from "@/lib/api";

export const Route = createFileRoute("/recipes/new")({
  head: () => ({ meta: [{ title: "New recipe — CookVault" }] }),
  component: NewRecipePage,
});

function NewRecipePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  async function handleSubmit(payload: RecipePayload) {
    const created = await apiFetch<{ id: string }>("/recipes", json("POST", payload));
    queryClient.invalidateQueries({ queryKey: ["recipes"] });
    toast.success("Recipe saved to CookVault.");
    navigate({ to: "/recipes/$id", params: { id: created.id } });
  }

  return (
    <div>
      <PageHeader
        eyebrow="Recipe vault"
        title="Add a favorite"
        intro="Typing it in saves straight to the cookbook. Have a link, a video or a block of text instead? Import it and review the draft first."
        actions={
          <Button asChild variant="secondary" className="glass-button">
            <Link to="/drafts/import">Import from a link or text</Link>
          </Button>
        }
      />
      <RecipeForm submitLabel="Save recipe" onSubmit={handleSubmit} />
    </div>
  );
}
