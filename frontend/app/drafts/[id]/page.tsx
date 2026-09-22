"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { ProvenanceCard } from "@/components/ProvenanceCard";
import { RecipeForm, type RecipeFormInitial, type RecipePayload } from "@/components/RecipeForm";
import { ApiError, apiFetch } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { DraftValidation, RecipeDetail, RecipeDraftDetail } from "@/types";

/** A refusal-to-promote body, or null if this 422 is some other shape. */
function parseValidation(err: ApiError): DraftValidation | null {
  try {
    const detail = JSON.parse(err.body).detail;
    return detail && Array.isArray(detail.issues) ? (detail as DraftValidation) : null;
  } catch {
    return null;
  }
}

export default function DraftDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [draft, setDraft] = useState<RecipeDraftDetail | null>(null);
  const [validation, setValidation] = useState<DraftValidation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    apiFetch<RecipeDraftDetail>(`/drafts/${params.id}`)
      .then(setDraft)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load draft"));
  }, [params.id]);

  async function run<T>(action: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setError(null);
    try {
      return await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      return undefined;
    } finally {
      setBusy(false);
    }
  }

  async function handleSave(payload: RecipePayload) {
    const updated = await apiFetch<RecipeDraftDetail>(`/drafts/${params.id}`, {
      method: "PATCH",
      body: JSON.stringify({ title: payload.title, payload }),
    });
    setDraft(updated);
    // The saved payload has not been checked, so any previous verdict is about
    // a payload that no longer exists. Showing it would be a lie.
    setValidation(null);
    setSaved(true);
  }

  async function handleValidate() {
    const result = await run(() =>
      apiFetch<DraftValidation>(`/drafts/${params.id}/validate`, { method: "POST" }),
    );
    if (result) {
      setValidation(result);
      const refreshed = await apiFetch<RecipeDraftDetail>(`/drafts/${params.id}`);
      setDraft(refreshed);
    }
  }

  async function handlePromote() {
    setBusy(true);
    setError(null);
    try {
      const recipe = await apiFetch<RecipeDetail>(`/drafts/${params.id}/promote`, {
        method: "POST",
      });
      router.push(`/recipes/${recipe.id}`);
      return;
    } catch (err) {
      // A refused promotion is the system doing its job, so show the reasons
      // rather than a wall of JSON. It carries a DraftValidation. Anything else with a
      // 422 -- request validation, say -- carries FastAPI's list of field
      // errors, which is a different shape and must not be handed to the
      // issues renderer.
      const detail = err instanceof ApiError && err.status === 422 ? parseValidation(err) : null;
      if (detail) {
        setValidation(detail);
        setError("This draft isn't ready yet — see below.");
      } else {
        setError(describeApiError(err, "Failed to promote"));
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleDiscard() {
    const updated = await run(() =>
      apiFetch<RecipeDraftDetail>(`/drafts/${params.id}/discard`, { method: "POST" }),
    );
    if (updated) setDraft(updated);
  }

  async function handleDelete() {
    if (!window.confirm("Delete this draft outright? Discard keeps the record instead.")) return;
    const done = await run(async () => {
      await apiFetch(`/drafts/${params.id}`, { method: "DELETE" });
      return true;
    });
    if (done) router.push("/drafts");
  }

  if (error && !draft) return <p className="text-sm text-red-600">{error}</p>;
  if (!draft) return <p className="text-neutral-500">Loading…</p>;

  const settled = draft.status === "promoted" || draft.status === "discarded";
  const errors = validation?.issues.filter((i) => i.severity === "error") ?? [];
  const warnings = validation?.issues.filter((i) => i.severity === "warning") ?? [];

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{draft.title?.trim() || "Untitled draft"}</h1>
          <p className="mt-1 text-sm text-neutral-500">
            status: <span className="font-medium">{draft.status}</span>
            {draft.status === "ready" && " — validated, waiting on you"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link href="/drafts" className="rounded border border-neutral-300 px-3 py-1 text-sm">
            All drafts
          </Link>
          {!settled && (
            <>
              <button
                onClick={handleValidate}
                disabled={busy}
                className="rounded border border-neutral-300 px-3 py-1 text-sm disabled:opacity-50"
              >
                Validate
              </button>
              <button
                onClick={handlePromote}
                disabled={busy}
                className="rounded bg-neutral-800 px-3 py-1 text-sm text-white disabled:opacity-50"
              >
                Promote to recipe
              </button>
              <button
                onClick={handleDiscard}
                disabled={busy}
                className="rounded border border-neutral-300 px-3 py-1 text-sm disabled:opacity-50"
              >
                Discard
              </button>
              <button
                onClick={handleDelete}
                disabled={busy}
                className="rounded border border-red-300 px-3 py-1 text-sm text-red-600 disabled:opacity-50"
              >
                Delete
              </button>
            </>
          )}
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {saved && !validation && (
        <p className="text-sm text-neutral-500">
          Saved. Validate again when you want to know whether it is promotable.
        </p>
      )}

      {validation && (
        <section className="space-y-3 rounded border border-neutral-200 p-4">
          <p className="text-sm font-medium">
            {validation.ok
              ? warnings.length > 0
                ? "No blocking problems, but worth a look:"
                : "No problems found. This draft can be promoted."
              : "Not promotable yet:"}
          </p>
          {errors.length > 0 && (
            <ul className="space-y-1 text-sm text-red-700">
              {errors.map((issue, index) => (
                <li key={`e${index}`}>
                  <span className="font-mono text-xs text-red-500">{issue.field}</span>{" "}
                  {issue.message}
                </li>
              ))}
            </ul>
          )}
          {warnings.length > 0 && (
            <ul className="space-y-1 text-sm text-amber-700">
              {warnings.map((issue, index) => (
                <li key={`w${index}`}>
                  <span className="font-mono text-xs text-amber-600">{issue.field}</span>{" "}
                  {issue.message}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {draft.provenance && <ProvenanceCard provenance={draft.provenance} />}

      {settled ? (
        <section className="rounded border border-neutral-200 p-4">
          <p className="text-sm text-neutral-600">
            {draft.status === "promoted" ? (
              <>
                Promoted{draft.promoted_at ? ` on ${new Date(draft.promoted_at).toLocaleString()}` : ""}.
                This draft is kept as the record of what was approved.{" "}
                {draft.promoted_recipe_id && (
                  <Link href={`/recipes/${draft.promoted_recipe_id}`} className="underline">
                    Open the recipe
                  </Link>
                )}
              </>
            ) : (
              "Discarded. Kept as the record of having rejected it."
            )}
          </p>
          <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap rounded bg-neutral-50 p-3 text-xs">
            {JSON.stringify(draft.payload, null, 2)}
          </pre>
        </section>
      ) : (
        <RecipeForm
          initial={draft.payload as RecipeFormInitial}
          submitLabel="Save draft"
          onSubmit={handleSave}
        />
      )}
    </div>
  );
}
