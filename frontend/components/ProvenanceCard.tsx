import type { ImportMethod, Provenance } from "@/types";

// How it arrived, in words rather than as a column value.
const ARRIVAL: Record<ImportMethod, string> = {
  manual: "typed in by hand",
  paste: "pasted text, parsed",
  url_fetch: "fetched from a page",
  video_fetch: "read from a video",
  agent: "proposed by an agent",
};

/** Where a draft or recipe came from, shown read-only.
 *
 * The raw source and the extracted structure are displayed as two separate
 * things because they are stored as two separate things -- "did the transcript
 * actually say two teaspoons, or did the model decide that?" is the question
 * this card exists to let you answer.
 */
export function ProvenanceCard({ provenance }: { provenance: Provenance }) {
  const extracted = provenance.extracted_payload;
  const byAgent = provenance.import_method === "agent";
  // For a video the original text is the transcript, and checking a quantity
  // against what was actually said is the main thing you are here to do -- so
  // it starts open rather than one click away.
  const fromVideo = provenance.import_method === "video_fetch";

  return (
    <section className="rounded border border-neutral-200 p-4">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">Provenance</h2>

      <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs uppercase tracking-wide text-neutral-400">Source</dt>
          <dd>
            {provenance.source_title?.trim() || provenance.source_type}
            {provenance.source_url && (
              <>
                {" "}
                <a
                  href={provenance.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-neutral-500 underline"
                >
                  link
                </a>
              </>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-neutral-400">How it arrived</dt>
          <dd>
            {ARRIVAL[provenance.import_method] ?? provenance.import_method}
            {byAgent && provenance.agent_model && (
              <span className="text-neutral-500">
                {" "}
                — {provenance.agent_model}
                {provenance.agent_version ? ` ${provenance.agent_version}` : ""}
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-neutral-400">Imported</dt>
          <dd>{new Date(provenance.imported_at).toLocaleString()}</dd>
        </div>
      </dl>

      {provenance.original_text && (
        <details className="mt-4" open={fromVideo}>
          <summary className="cursor-pointer text-sm font-medium">
            {fromVideo ? "Description and transcript" : "Original text"}
          </summary>
          <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-neutral-50 p-3 text-xs">
            {provenance.original_text}
          </pre>
        </details>
      )}

      {extracted && (
        <details className="mt-2">
          <summary className="cursor-pointer text-sm font-medium">
            What was extracted from it
          </summary>
          <p className="mt-1 text-xs text-neutral-500">
            As first proposed, before any edit. Compare it against the draft to see what you
            changed.
          </p>
          <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-neutral-50 p-3 text-xs">
            {JSON.stringify(extracted, null, 2)}
          </pre>
        </details>
      )}
    </section>
  );
}
