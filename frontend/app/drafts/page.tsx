"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiFetch } from "@/lib/api";
import type { DraftStatus, RecipeDraftSummary } from "@/types";

const FILTERS: { value: DraftStatus | "all"; label: string }[] = [
  { value: "draft", label: "In progress" },
  { value: "ready", label: "Ready to review" },
  { value: "promoted", label: "Promoted" },
  { value: "discarded", label: "Discarded" },
  { value: "all", label: "All" },
];

const BADGE: Record<DraftStatus, string> = {
  draft: "bg-neutral-100 text-neutral-700",
  ready: "bg-emerald-100 text-emerald-800",
  promoted: "bg-blue-100 text-blue-800",
  discarded: "bg-neutral-100 text-neutral-400",
};

export default function DraftsPage() {
  // The default view is the work queue, not the archive: promoted and
  // discarded drafts are finished business.
  const [filter, setFilter] = useState<DraftStatus | "all">("draft");
  const [drafts, setDrafts] = useState<RecipeDraftSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const query = filter === "all" ? "" : `?status_filter=${filter}`;
    apiFetch<RecipeDraftSummary[]>(`/drafts${query}`)
      .then(setDrafts)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load drafts"));
  }, [filter]);

  useEffect(load, [load]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Drafts</h1>
          <p className="mt-1 max-w-2xl text-sm text-neutral-500">
            Proposed recipes waiting on you. Nothing here is in the cookbook until it passes
            validation and you promote it.
          </p>
        </div>
        <Link href="/drafts/new" className="rounded bg-neutral-800 px-3 py-2 text-sm text-white">
          New draft
        </Link>
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((option) => (
          <button
            key={option.value}
            onClick={() => setFilter(option.value)}
            aria-pressed={filter === option.value}
            className={`rounded border px-3 py-1 text-sm ${
              filter === option.value
                ? "border-neutral-800 bg-neutral-800 text-white"
                : "border-neutral-300"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {drafts.length === 0 ? (
        <p className="text-neutral-500">Nothing here.</p>
      ) : (
        <ul className="divide-y divide-neutral-200 rounded border border-neutral-200">
          {drafts.map((draft) => (
            <li key={draft.id} className="flex flex-wrap items-center justify-between gap-3 p-3">
              <div>
                <Link href={`/drafts/${draft.id}`} className="font-medium hover:underline">
                  {draft.title?.trim() || "Untitled draft"}
                </Link>
                <p className="text-xs text-neutral-400">
                  updated {new Date(draft.updated_at).toLocaleString()}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className={`rounded px-2 py-0.5 text-xs ${BADGE[draft.status]}`}>
                  {draft.status}
                </span>
                {draft.promoted_recipe_id && (
                  <Link
                    href={`/recipes/${draft.promoted_recipe_id}`}
                    className="text-xs text-neutral-500 underline"
                  >
                    view recipe
                  </Link>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
