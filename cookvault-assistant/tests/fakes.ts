import type { CookVaultClient } from "../src/cookvault.ts";
import { CookVaultError } from "../src/cookvault.ts";
import type { ChatProvider, ChatRequest, ProviderEvent, ToolCall } from "../src/provider/types.ts";
import { ProviderError } from "../src/provider/types.ts";

/** A model that says what it is told to, in order. Each scripted turn is
 *  either text, or tool calls, or a thrown failure. */
export type ScriptedTurn = { text?: string; calls?: ToolCall[] } | { fail: string };

export class FakeProvider implements ChatProvider {
  readonly name = "fake";
  readonly model = "fake-model";
  readonly requests: ChatRequest[] = [];
  reachable = true;

  constructor(private readonly script: ScriptedTurn[]) {}

  async ping() {
    return this.reachable ? { ok: true } : { ok: false, detail: "fake model is down" };
  }

  async *chat(request: ChatRequest): AsyncIterable<ProviderEvent> {
    this.requests.push(request);
    const turn = this.script.shift();
    if (!turn) throw new Error("FakeProvider: script ran out of turns");
    if ("fail" in turn) throw new ProviderError(turn.fail);
    if (turn.text) {
      // Stream in two halves so the loop's concatenation is exercised.
      const half = Math.ceil(turn.text.length / 2);
      yield { type: "text", delta: turn.text.slice(0, half) };
      yield { type: "text", delta: turn.text.slice(half) };
    }
    if (turn.calls?.length) yield { type: "tool_calls", calls: turn.calls };
    yield { type: "done" };
  }
}

/** CookVault's /agent surface, as a table of canned answers keyed by
 *  "METHOD path". Records every call so a test can assert what was sent. */
export class FakeCookVault implements CookVaultClient {
  readonly calls: { method: string; path: string; body?: unknown; query?: unknown }[] = [];
  reachable = true;

  constructor(private readonly answers: Record<string, unknown | ((body: unknown) => unknown)> = {}) {}

  private answer(method: string, path: string, body?: unknown) {
    const key = `${method} ${path}`;
    if (!(key in this.answers)) throw new CookVaultError(404, `no fake answer for ${key}`);
    const value = this.answers[key];
    const result = typeof value === "function" ? (value as (b: unknown) => unknown)(body) : value;
    if (result instanceof CookVaultError) throw result;
    return result;
  }

  async get<T>(path: string, query?: Record<string, string | number | undefined>): Promise<T> {
    this.calls.push({ method: "GET", path, query });
    return this.answer("GET", path) as T;
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    this.calls.push({ method: "POST", path, body });
    return this.answer("POST", path, body) as T;
  }

  async ping() {
    return this.reachable ? { ok: true } : { ok: false, detail: "fake cookvault is down" };
  }
}

export const RECIPE_ID = "11111111-1111-4111-8111-111111111111";
export const DRAFT_ID = "22222222-2222-4222-8222-222222222222";

export const summary = {
  id: RECIPE_ID,
  title: "Quick Pasta",
  tags: ["italian"],
  cook_methods: ["stovetop"],
  total_time: 15,
  servings: 4,
  estimated_cost: "6.00",
  is_favorite: false,
  times_cooked: 2,
  last_cooked_on: "2026-09-01",
};
