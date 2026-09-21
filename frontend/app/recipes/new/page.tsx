"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { RecipeForm, type RecipePayload } from "@/components/RecipeForm";
import { apiFetch } from "@/lib/api";

export default function NewRecipePage() {
  const router = useRouter();
  const [importUrl, setImportUrl] = useState("");
  const [importMessage, setImportMessage] = useState<string | null>(null);

  async function handleImport(e: React.FormEvent) {
    e.preventDefault();
    setImportMessage(null);
    try {
      await apiFetch("/import", { method: "POST", body: JSON.stringify({ url: importUrl }) });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Import failed";
      if (message.includes("501")) {
        setImportMessage(
          "Import from a link isn't built yet — that's a Phase 2 feature. Enter the recipe manually below for now.",
        );
      } else {
        setImportMessage(message);
      }
    }
  }

  async function handleSubmit(payload: RecipePayload) {
    const created = await apiFetch<{ id: string }>("/recipes", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    router.push(`/recipes/${created.id}`);
  }

  return (
    <div className="space-y-10">
      <section>
        <h1 className="mb-4 text-xl font-semibold">Import from a link</h1>
        <form onSubmit={handleImport} className="flex gap-2">
          <input
            type="url"
            placeholder="YouTube, TikTok, Instagram, or web URL"
            value={importUrl}
            onChange={(e) => setImportUrl(e.target.value)}
            className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm"
          />
          <button type="submit" className="rounded bg-neutral-800 px-4 py-2 text-sm text-white">
            Import
          </button>
        </form>
        {importMessage && <p className="mt-2 text-sm text-amber-600">{importMessage}</p>}
      </section>

      <hr className="border-neutral-200" />

      <section className="space-y-6">
        <h1 className="text-xl font-semibold">Add Recipe Manually</h1>
        <RecipeForm submitLabel="Save Recipe" onSubmit={handleSubmit} />
      </section>
    </div>
  );
}
