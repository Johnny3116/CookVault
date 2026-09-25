import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { RecipeForm, type RecipePayload } from "@/components/RecipeForm";
import { apiFetch, json } from "@/lib/api";
import type { ImportMethod, RecipeDraftDetail, SourceType } from "@/types";

const SOURCE_TYPES: SourceType[] = ["manual", "web", "youtube", "tiktok", "instagram"];
// video_fetch is deliberately absent: only the video importer sets it.
const IMPORT_METHODS: ImportMethod[] = ["manual", "paste", "url_fetch", "agent"];

export const Route = createFileRoute("/drafts/new")({
  head: () => ({ meta: [{ title: "New draft — CookVault" }] }),
  component: NewDraftPage,
});

function NewDraftPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [sourceType, setSourceType] = useState<SourceType>("manual");
  const [importMethod, setImportMethod] = useState<ImportMethod>("manual");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceTitle, setSourceTitle] = useState("");
  const [originalText, setOriginalText] = useState("");

  async function handleSubmit(payload: RecipePayload) {
    const draft = await apiFetch<RecipeDraftDetail>(
      "/drafts",
      json("POST", {
        title: payload.title,
        payload,
        // Provenance is recorded at creation and not edited afterwards: it
        // describes where this came from, which does not change later.
        provenance: {
          source_type: sourceType,
          import_method: importMethod,
          source_url: sourceUrl.trim() || null,
          source_title: sourceTitle.trim() || null,
          original_text: originalText.trim() || null,
        },
      }),
    );
    queryClient.invalidateQueries({ queryKey: ["drafts"] });
    navigate({ to: "/drafts/$id", params: { id: draft.id } });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Draft"
        title="New draft"
        intro="A draft can be saved half-finished and wrong — that is what it is for. Validate it when you want to know what is missing, and promote it when you are happy."
      />

      <section className="glass-panel editor-form">
        <h2 className="font-display text-xl font-semibold">Where it came from</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <label>
            Source
            <select value={sourceType} onChange={(e) => setSourceType(e.target.value as SourceType)} className="field">
              {SOURCE_TYPES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label>
            How it arrived
            <select value={importMethod} onChange={(e) => setImportMethod(e.target.value as ImportMethod)} className="field">
              {IMPORT_METHODS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label>
            Source title
            <input value={sourceTitle} onChange={(e) => setSourceTitle(e.target.value)} placeholder="Nonna's book, p.42" className="field" />
          </label>
          <label>
            Source URL
            <input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} className="field" />
          </label>
        </div>
        <label>
          Original text
          <span className="field-hint">
            Paste the recipe as written, or the transcript. Kept apart from the structured draft so the two can be compared later.
          </span>
          <textarea value={originalText} onChange={(e) => setOriginalText(e.target.value)} rows={6} className="field font-mono !text-xs" />
        </label>
      </section>

      <RecipeForm submitLabel="Save draft" onSubmit={handleSubmit} />
    </div>
  );
}
