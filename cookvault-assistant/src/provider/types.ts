/** The model, from the orchestrator's point of view.
 *
 * Deliberately small: a chat with tools, streamed. Anything Ollama-shaped
 * stays in provider/ollama.ts so that swapping the model, or the thing that
 * serves it, is one file.
 */

export type ChatRole = "system" | "user" | "assistant" | "tool";

export interface ToolCall {
  id: string;
  name: string;
  /** Parsed by the provider; validated by the tool registry, never here. */
  arguments: unknown;
}

export interface ChatMessage {
  role: ChatRole;
  content: string;
  /** Present on an assistant turn that asked for tools. */
  toolCalls?: ToolCall[];
  /** Present on a tool turn: which call this answers. */
  toolCallId?: string;
  toolName?: string;
}

/** The OpenAI function shape, which is what Ollama's `tools` takes. */
export interface ToolSpec {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

export type ProviderEvent =
  | { type: "text"; delta: string }
  | { type: "tool_calls"; calls: ToolCall[] }
  | { type: "done"; usage?: { promptTokens?: number; completionTokens?: number; totalMs?: number } };

export interface ChatRequest {
  messages: ChatMessage[];
  tools: ToolSpec[];
  signal?: AbortSignal;
}

export interface ChatProvider {
  readonly name: string;
  readonly model: string;
  chat(request: ChatRequest): AsyncIterable<ProviderEvent>;
  /** Can the model be reached right now? Used by /health and to fail fast. */
  ping(): Promise<{ ok: boolean; detail?: string }>;
}

export class ProviderError extends Error {
  constructor(message: string, cause?: unknown) {
    super(message, cause === undefined ? undefined : { cause });
    this.name = "ProviderError";
  }
}
