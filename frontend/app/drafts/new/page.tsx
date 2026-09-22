"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { RecipeForm, type RecipePayload } from "@/components/RecipeForm";
import { apiFetch } from "@/lib/api";
import type { ImportMethod, RecipeDraftDetail, SourceType } from "@/types";

const SOURCE_TYPES: SourceType[] = ["manual", "web", "youtube", "tiktok", "instagram"];
const IMPORT_METHODS: ImportMethod[] = ["manual", "paste", "url_fetch", "agent"];

export default function NewDraftPage() {
  const router = useRouter();
  const [sourceType, setSourceType] = useState<SourceType>("manual");
  const [importMethod, setImportMethod] = useState<ImportMethod>("manual");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceTitle, setSourceTitle] = useState("");
  const [originalText, setOriginalText] = useState("");

  async function handleSubmit(payload: RecipePayload) {
    const draft = await apiFetch<RecipeDraftDetail>("/drafts", {
      method: "POST",
      body: JSON.stringify({
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
    });
    router.push(`/drafts/${draft.id}`);
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">New draft</h1>
        <p className="mt-1 max-w-2xl text-sm text-neutral-500">
          A draft can be saved half-finished and wrong — that is what it is for. Validate it when
          you want to know what is missing, and promote it when you are happy.
        </p>
      </div>

      <section className="space-y-4 rounded border border-neutral-200 p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Where it came from
        </h2>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Source</span>
            <select
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value as SourceType)}
              className="w-full rounded border border-neutral-300 px-2 py-1"
            >
              {SOURCE_TYPES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm">
            <span className="mb-1 block font-medium">How it arrived</span>
            <select
              value={importMethod}
              onChange={(e) => setImportMethod(e.target.value as ImportMethod)}
              className="w-full rounded border border-neutral-300 px-2 py-1"
            >
              {IMPORT_METHODS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm">
            <span className="mb-1 block font-medium">Source title</span>
            <input
              value={sourceTitle}
              onChange={(e) => setSourceTitle(e.target.value)}
              placeholder="Nonna's book, p.42"
              className="w-full rounded border border-neutral-300 px-2 py-1"
            />
          </label>

          <label className="block text-sm">
            <span className="mb-1 block font-medium">Source URL</span>
            <input
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              className="w-full rounded border border-neutral-300 px-2 py-1"
            />
          </label>
        </div>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">Original text</span>
          <span className="mb-1 block text-xs text-neutral-500">
            Paste the recipe as written, or the transcript. Kept apart from the structured draft so
            the two can be compared later.
          </span>
          <textarea
            value={originalText}
            onChange={(e) => setOriginalText(e.target.value)}
            rows={6}
            className="w-full rounded border border-neutral-300 px-2 py-1 font-mono text-xs"
          />
        </label>
      </section>

      <RecipeForm submitLabel="Save draft" onSubmit={handleSubmit} />
    </div>
  );
}
