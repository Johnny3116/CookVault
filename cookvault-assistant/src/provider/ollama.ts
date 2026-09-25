import type { Config } from "../config.ts";
import { log } from "../log.ts";
import { type ChatMessage, type ChatProvider, type ChatRequest, type ProviderEvent, ProviderError, type ToolCall } from "./types.ts";

/** Ollama's native /api/chat, streamed as NDJSON.
 *
 * Native rather than the OpenAI-compatible endpoint because two things this
 * service relies on only exist here: `think` (to switch Qwen3's reasoning
 * off for a shared GPU) and `num_ctx` (Ollama's default context truncates
 * silently, and a truncated prompt looks like a stupid model, not an error).
 */
export class OllamaProvider implements ChatProvider {
  readonly name = "ollama";
  readonly model: string;

  constructor(private readonly config: Pick<Config, "AI_BASE_URL" | "AI_MODEL" | "AI_NUM_CTX" | "AI_TEMPERATURE" | "AI_THINK" | "AI_TIMEOUT_MS">) {
    this.model = config.AI_MODEL;
  }

  async ping(): Promise<{ ok: boolean; detail?: string }> {
    try {
      const res = await fetch(`${this.config.AI_BASE_URL}/api/tags`, { signal: AbortSignal.timeout(5_000) });
      if (!res.ok) return { ok: false, detail: `Ollama answered ${res.status}` };
      const body = (await res.json()) as { models?: { name: string }[] };
      const names = (body.models ?? []).map((m) => m.name);
      const have = names.includes(this.model) || names.includes(`${this.model}:latest`);
      return have ? { ok: true } : { ok: false, detail: `model ${this.model} is not pulled on ${this.config.AI_BASE_URL}` };
    } catch (err) {
      return { ok: false, detail: `Ollama unreachable at ${this.config.AI_BASE_URL}: ${describe(err)}` };
    }
  }

  async *chat(request: ChatRequest): AsyncIterable<ProviderEvent> {
    const body = {
      model: this.model,
      stream: true,
      think: this.config.AI_THINK,
      messages: request.messages.map(toOllama),
      tools: request.tools.map((tool) => ({
        type: "function",
        function: { name: tool.name, description: tool.description, parameters: tool.parameters },
      })),
      options: { num_ctx: this.config.AI_NUM_CTX, temperature: this.config.AI_TEMPERATURE },
    };

    const timeout = AbortSignal.timeout(this.config.AI_TIMEOUT_MS);
    const signal = request.signal ? AbortSignal.any([request.signal, timeout]) : timeout;
    const started = Date.now();

    let res: Response;
    try {
      res = await fetch(`${this.config.AI_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
        signal,
      });
    } catch (err) {
      throw new ProviderError(`Ollama unreachable at ${this.config.AI_BASE_URL}: ${describe(err)}`, err);
    }
    if (!res.ok || !res.body) {
      const text = await res.text().catch(() => "");
      throw new ProviderError(`Ollama answered ${res.status}: ${text.slice(0, 300)}`);
    }

    // Tool calls can arrive spread across chunks; collect until the final one.
    const calls: ToolCall[] = [];
    let usage: { promptTokens?: number; completionTokens?: number } = {};
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let callIndex = 0;

    const handle = function* (line: string): Generator<ProviderEvent> {
      if (!line.trim()) return;
      let chunk: OllamaChunk;
      try {
        chunk = JSON.parse(line) as OllamaChunk;
      } catch {
        log("warn", "model", "unparseable chunk from Ollama", { line: line.slice(0, 200) });
        return;
      }
      if (chunk.error) throw new ProviderError(`Ollama: ${chunk.error}`);
      const message = chunk.message;
      if (message?.content) yield { type: "text", delta: message.content };
      for (const call of message?.tool_calls ?? []) {
        calls.push({
          id: call.id ?? `call_${callIndex++}`,
          name: call.function.name,
          arguments: call.function.arguments,
        });
      }
      if (chunk.done) {
        usage = { promptTokens: chunk.prompt_eval_count, completionTokens: chunk.eval_count };
      }
    };

    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let newline = buffer.indexOf("\n");
        while (newline !== -1) {
          const line = buffer.slice(0, newline);
          buffer = buffer.slice(newline + 1);
          yield* handle(line);
          newline = buffer.indexOf("\n");
        }
      }
      if (buffer.trim()) yield* handle(buffer);
    } catch (err) {
      if (err instanceof ProviderError) throw err;
      if (request.signal?.aborted) throw new ProviderError("cancelled", err);
      throw new ProviderError(timeout.aborted ? "the model took too long to answer" : `stream failed: ${describe(err)}`, err);
    }

    if (calls.length > 0) yield { type: "tool_calls", calls };
    yield { type: "done", usage: { ...usage, totalMs: Date.now() - started } };
  }
}

interface OllamaChunk {
  message?: {
    role: string;
    content?: string;
    thinking?: string;
    tool_calls?: { id?: string; function: { name: string; arguments: unknown } }[];
  };
  done?: boolean;
  error?: string;
  prompt_eval_count?: number;
  eval_count?: number;
}

function toOllama(message: ChatMessage) {
  if (message.role === "assistant" && message.toolCalls?.length) {
    return {
      role: "assistant",
      content: message.content,
      tool_calls: message.toolCalls.map((call) => ({
        id: call.id,
        type: "function",
        function: { name: call.name, arguments: call.arguments },
      })),
    };
  }
  if (message.role === "tool") {
    return { role: "tool", content: message.content, tool_name: message.toolName, tool_call_id: message.toolCallId };
  }
  return { role: message.role, content: message.content };
}

function describe(err: unknown): string {
  if (err instanceof Error) return err.cause instanceof Error ? `${err.message} (${err.cause.message})` : err.message;
  return String(err);
}
