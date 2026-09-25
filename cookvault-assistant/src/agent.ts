import { readFileSync } from "node:fs";

import type { AuditLog } from "./audit.ts";
import { CookVaultError } from "./cookvault.ts";
import { log } from "./log.ts";
import { type ChatMessage, type ChatProvider, ProviderError, type ToolCall } from "./provider/types.ts";
import type { SseEvent, ToolEvent } from "./sse.ts";
import type { ToolContext, ToolRegistry } from "./tools/registry.ts";

/** The bounded loop: model → tool request? → validate → execute → model.
 *
 * Every tool result goes back to the model in one controlled shape, success
 * or failure, so the model explains a failure instead of hallucinating past
 * it. Unknown tools are refused. The same call twice in a row is refused. And
 * after MAX_TOOL_ROUNDS the model is asked once more, without tools, so the
 * person gets an answer rather than a spinner.
 */

export interface AgentOptions {
  provider: ChatProvider;
  tools: ToolRegistry;
  audit: AuditLog;
  toolContext: Omit<ToolContext, "today">;
  systemPrompt: string;
  maxToolRounds: number;
  contextMessages: number;
}

export interface ConversationTurn {
  role: "user" | "assistant";
  content: string;
}

export interface RunInput {
  conversationId: string;
  messages: ConversationTurn[];
  signal?: AbortSignal;
  /** Overridable for tests; defaults to the wall clock. */
  today?: string;
}

export type Emit = (event: SseEvent) => void;

export function loadSystemPrompt(path: string): string {
  return readFileSync(path, "utf8");
}

function renderPrompt(template: string, values: Record<string, string>): string {
  return template.replace(/\{\{(\w+)\}\}/g, (_, key: string) => values[key] ?? "");
}

function localDate(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export class Agent {
  constructor(private readonly options: AgentOptions) {}

  /** One assistant turn. Emits events as they happen; resolves when done. */
  async run(input: RunInput, emit: Emit): Promise<void> {
    const { provider, tools, options } = { provider: this.options.provider, tools: this.options.tools, options: this.options };
    const today = input.today ?? localDate();
    const ctx: ToolContext = { ...options.toolContext, today };
    const started = Date.now();

    const system: ChatMessage = {
      role: "system",
      content: renderPrompt(options.systemPrompt, { today, model: provider.model }),
    };
    // Older turns are dropped, not summarised. A summary is a place for a
    // model to quietly invent a recipe the person never described.
    const history = input.messages.slice(-options.contextMessages);
    const messages: ChatMessage[] = [system, ...history.map((m) => ({ role: m.role, content: m.content }))];
    const specs = tools.specs();

    let toolCallsMade = 0;
    let lastCallKey: string | null = null;

    try {
      for (let round = 0; round <= options.maxToolRounds; round++) {
        const exhausted = round === options.maxToolRounds;
        const { text, calls } = await this.ask(messages, exhausted ? [] : specs, input.signal, emit);
        messages.push({ role: "assistant", content: text, ...(calls.length ? { toolCalls: calls } : {}) });

        if (calls.length === 0) break;

        for (const call of calls) {
          const key = `${call.name}:${JSON.stringify(call.arguments)}`;
          const repeated = key === lastCallKey;
          lastCallKey = key;
          toolCallsMade++;
          const result = await this.execute(call, ctx, input.conversationId, repeated, emit);
          messages.push({ role: "tool", toolCallId: call.id, toolName: call.name, content: JSON.stringify(result) });
        }
      }
    } catch (err) {
      if (input.signal?.aborted) {
        log("info", "orchestrator", "turn cancelled", { conversation: input.conversationId });
        return;
      }
      const message = err instanceof ProviderError ? `Sage couldn't reach its model: ${err.message}` : "Sage hit a problem answering that.";
      log("error", "orchestrator", "turn failed", { conversation: input.conversationId, error: String(err) });
      emit({ event: "error", data: { message } });
    } finally {
      log("info", "orchestrator", "turn finished", {
        conversation: input.conversationId,
        model: provider.model,
        tool_calls: toolCallsMade,
        ms: Date.now() - started,
      });
      emit({ event: "done", data: {} });
    }
  }

  private async ask(messages: ChatMessage[], specs: ReturnType<ToolRegistry["specs"]>, signal: AbortSignal | undefined, emit: Emit) {
    let text = "";
    let calls: ToolCall[] = [];
    const started = Date.now();
    // A copy: the provider gets a snapshot of the conversation as it stood,
    // not a reference the loop keeps appending to while it streams.
    for await (const event of this.options.provider.chat({ messages: [...messages], tools: specs, signal })) {
      if (event.type === "text") {
        text += event.delta;
        emit({ event: "text", data: { delta: event.delta } });
      } else if (event.type === "tool_calls") {
        calls = event.calls;
      } else if (event.type === "done") {
        log("debug", "model", "model turn", { ms: Date.now() - started, calls: calls.length, ...event.usage });
      }
    }
    return { text, calls };
  }

  private async execute(call: ToolCall, ctx: ToolContext, conversationId: string, repeated: boolean, emit: Emit) {
    const tool = this.options.tools.get(call.name);
    const id = call.id;
    const started = Date.now();

    const chip = (patch: Partial<ToolEvent>): ToolEvent => ({
      id,
      name: call.name,
      label: tool ? tool.label(call.arguments as never) : call.name,
      status: "running",
      ...patch,
    });

    if (!tool) {
      log("warn", "tool", "unknown tool requested", { tool: call.name });
      emit({ event: "tool", data: chip({ label: `Unknown tool ${call.name}`, status: "error" }) });
      return { error: `There is no tool called ${call.name}. Available: ${this.options.tools.names().join(", ")}.` };
    }

    const parsed = tool.schema.safeParse(call.arguments);
    if (!parsed.success) {
      const problems = parsed.error.issues.map((i) => `${i.path.join(".") || "arguments"}: ${i.message}`).join("; ");
      log("warn", "tool", "invalid arguments", { tool: call.name, problems });
      emit({ event: "tool", data: chip({ status: "error", summary: "invalid arguments" }) });
      return { error: `Invalid arguments for ${call.name}: ${problems}. Fix them and try once more, or ask the person.` };
    }

    if (repeated) {
      emit({ event: "tool", data: chip({ status: "error", summary: "already called" }) });
      return { error: `You already called ${call.name} with exactly these arguments. Use the result you have; do not call it again.` };
    }

    emit({ event: "tool", data: chip({}) });

    try {
      const result = await tool.execute(parsed.data, ctx);
      await this.options.audit.record({
        conversation_id: conversationId,
        model: ctx.model,
        tool: tool.name,
        kind: tool.kind,
        arguments: parsed.data,
        ok: true,
        duration_ms: Date.now() - started,
        ...(result.affectedId ? { affected_record_id: result.affectedId } : {}),
      });
      emit({
        event: "tool",
        data: chip({ status: "done", ...(result.summary ? { summary: result.summary } : {}), ...(result.links ? { links: result.links } : {}) }),
      });
      return { ok: true, result: result.content };
    } catch (err) {
      const detail = err instanceof CookVaultError ? err.detail : err instanceof Error ? err.message : String(err);
      log("warn", "tool", "tool failed", { tool: tool.name, error: detail });
      await this.options.audit.record({
        conversation_id: conversationId,
        model: ctx.model,
        tool: tool.name,
        kind: tool.kind,
        arguments: parsed.data,
        ok: false,
        duration_ms: Date.now() - started,
        error: detail,
      });
      emit({ event: "tool", data: chip({ status: "error", summary: detail.slice(0, 80) }) });
      return { error: `${tool.name} failed: ${detail}. Tell the person plainly; do not claim it worked.` };
    }
  }
}
