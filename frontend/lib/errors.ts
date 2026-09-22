import { ApiError } from "@/lib/api";

/** A sentence to show the user for a failed request.
 *
 * FastAPI's `detail` is a plain string when the app raises HTTPException, but
 * a *list* of per-field objects when request validation fails — which is what
 * a PATCH carrying an explicit null now produces. Rendering that list straight
 * into JSX throws "Objects are not valid as a React child" and takes the page
 * with it, so every shape gets flattened to text here instead.
 */
export function describeApiError(err: unknown, fallback = "Something went wrong"): string {
  if (!(err instanceof ApiError)) {
    return err instanceof Error ? err.message : fallback;
  }

  let detail: unknown;
  try {
    detail = JSON.parse(err.body).detail;
  } catch {
    return err.message;
  }

  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (typeof item === "string" ? item : item?.msg))
      .filter((msg): msg is string => typeof msg === "string" && msg.length > 0);
    if (messages.length > 0) return messages.join("; ");
  }

  return err.message;
}
