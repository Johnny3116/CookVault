/** Server-sent events, the frame the browser's useChefNexusChat reads.
 *
 * The event names are the contract with frontend/src/components/chef-nexus/useChefNexusChat.ts:
 *   text   {delta}
 *   tool   {id, name, label, status, summary?, links?}
 *   error  {message}
 *   done   {}
 */

export type ToolLink = { kind: "draft" | "recipe" | "proposal"; id: string; title: string };

export type ToolEvent = {
  id: string;
  name: string;
  label: string;
  status: "running" | "done" | "error";
  summary?: string;
  links?: ToolLink[];
};

export type SseEvent =
  | { event: "text"; data: { delta: string } }
  | { event: "tool"; data: ToolEvent }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: Record<string, never> };

export function encodeSse(event: SseEvent): string {
  return `event: ${event.event}\ndata: ${JSON.stringify(event.data)}\n\n`;
}

export const SSE_HEADERS = {
  "content-type": "text/event-stream; charset=utf-8",
  "cache-control": "no-cache, no-transform",
  connection: "keep-alive",
  // Tells any proxy in the way not to buffer the stream.
  "x-accel-buffering": "no",
};
