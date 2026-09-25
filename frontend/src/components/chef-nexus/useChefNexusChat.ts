import { useCallback, useEffect, useRef, useState } from "react";

/** The wire protocol with the assistant service, mirrored in
 *  cookvault-assistant/src/sse.ts. Server-sent events over a POST, because
 *  EventSource cannot send a body and the conversation is the body. */
export type ToolLink = { kind: "draft" | "recipe" | "proposal"; id: string; title: string };

export type ToolActivity = {
  id: string;
  name: string;
  label: string;
  status: "running" | "done" | "error";
  summary?: string;
  links?: ToolLink[];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  activity: ToolActivity[];
  error?: string;
};

export type ChefNexusHealth = { ok: boolean; model?: string; provider?: string; detail?: string };

type Status = "idle" | "streaming" | "error";

const STORAGE_KEY = "cookvault.chefnexus.conversation";

function newId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : String(Date.now() + Math.random());
}

/** Parses `event:`/`data:` frames out of a byte stream. Frames end at a blank line. */
function parseSse(buffer: string): { frames: { event: string; data: string }[]; rest: string } {
  const frames: { event: string; data: string }[] = [];
  let rest = buffer;
  for (;;) {
    const end = rest.indexOf("\n\n");
    if (end === -1) break;
    const block = rest.slice(0, end);
    rest = rest.slice(end + 2);
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    frames.push({ event, data: data.join("\n") });
  }
  return { frames, rest };
}

export function useChefNexusChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [health, setHealth] = useState<ChefNexusHealth | null>(null);
  const conversationId = useRef(newId());
  const abort = useRef<AbortController | null>(null);

  // The conversation is kept in this browser only, so a page reload does not
  // lose a half-finished exchange. Nothing about it is stored server-side.
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (raw) {
        const saved = JSON.parse(raw) as { id: string; messages: ChatMessage[] };
        conversationId.current = saved.id;
        setMessages(saved.messages);
      }
    } catch {
      /* private mode or blocked storage: start fresh */
    }
  }, []);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ id: conversationId.current, messages }));
    } catch {
      /* ignore */
    }
  }, [messages]);

  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch("/api/assistant/health", { cache: "no-store" });
      const body = (await res.json()) as ChefNexusHealth;
      setHealth(res.ok ? body : { ok: false, detail: body.detail ?? `ChefNexus answered ${res.status}` });
    } catch {
      setHealth({ ok: false, detail: "ChefNexus is unreachable" });
    }
  }, []);

  const patchAssistant = (id: string, patch: (m: ChatMessage) => ChatMessage) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? patch(m) : m)));

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || status === "streaming") return;

      const user: ChatMessage = { id: newId(), role: "user", content: trimmed, activity: [] };
      const assistant: ChatMessage = { id: newId(), role: "assistant", content: "", activity: [] };
      const history = [...messages, user];
      setMessages([...history, assistant]);
      setStatus("streaming");

      const controller = new AbortController();
      abort.current = controller;

      try {
        const res = await fetch("/api/assistant/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            conversation_id: conversationId.current,
            messages: history.map((m) => ({ role: m.role, content: m.content })),
          }),
          signal: controller.signal,
        });
        if (!res.ok || !res.body) {
          const detail = await res.text().catch(() => "");
          throw new Error(res.status === 401 ? "You need to sign in first." : detail || `ChefNexus answered ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parsed = parseSse(buffer);
          buffer = parsed.rest;
          for (const frame of parsed.frames) {
            const data = frame.data ? (JSON.parse(frame.data) as Record<string, unknown>) : {};
            if (frame.event === "text") {
              patchAssistant(assistant.id, (m) => ({ ...m, content: m.content + String(data["delta"] ?? "") }));
            } else if (frame.event === "tool") {
              const activity = data as unknown as ToolActivity;
              patchAssistant(assistant.id, (m) => {
                const existing = m.activity.findIndex((a) => a.id === activity.id);
                const next = [...m.activity];
                if (existing === -1) next.push(activity);
                else next[existing] = activity;
                return { ...m, activity: next };
              });
            } else if (frame.event === "error") {
              patchAssistant(assistant.id, (m) => ({ ...m, error: String(data["message"] ?? "Something went wrong") }));
            }
          }
        }
        setStatus("idle");
      } catch (err) {
        if (controller.signal.aborted) {
          setStatus("idle");
          return;
        }
        const message = err instanceof Error ? err.message : "ChefNexus couldn't answer.";
        patchAssistant(assistant.id, (m) => ({ ...m, error: message }));
        setStatus("error");
      } finally {
        abort.current = null;
      }
    },
    [messages, status],
  );

  const stop = useCallback(() => abort.current?.abort(), []);

  const reset = useCallback(() => {
    abort.current?.abort();
    conversationId.current = newId();
    setMessages([]);
    setStatus("idle");
  }, []);

  return { messages, status, health, checkHealth, send, stop, reset };
}
