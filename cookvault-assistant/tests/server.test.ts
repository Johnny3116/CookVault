import { describe, expect, test } from "bun:test";

import { Agent } from "../src/agent.ts";
import { createMemoryAuditLog } from "../src/audit.ts";
import { createApp } from "../src/server.ts";
import { defaultRegistry } from "../src/tools/index.ts";
import { FakeCookVault, FakeProvider, type ScriptedTurn, summary } from "./fakes.ts";

function app(script: ScriptedTurn[], opts: { modelDown?: boolean; cookvaultDown?: boolean } = {}) {
  const provider = new FakeProvider(script);
  provider.reachable = !opts.modelDown;
  const cookvault = new FakeCookVault({ "POST /agent/search-recipes": { total_matched: 1, results: [summary] } });
  cookvault.reachable = !opts.cookvaultDown;
  const agent = new Agent({
    provider,
    tools: defaultRegistry(),
    audit: createMemoryAuditLog(),
    toolContext: { cookvault, model: provider.model, version: "test" },
    systemPrompt: "system",
    maxToolRounds: 3,
    contextMessages: 10,
  });
  return createApp({ agent, provider, cookvault, version: "test" });
}

const post = (body: unknown) =>
  new Request("http://assistant/chat", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

describe("GET /health", () => {
  test("is 200 when the model and CookVault both answer", async () => {
    const res = await app([]).fetch(new Request("http://assistant/health"));
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ ok: true, provider: "fake", model: "fake-model", cookvault: { ok: true } });
  });

  test("is 503 with the reason when the model is down", async () => {
    const res = await app([], { modelDown: true }).fetch(new Request("http://assistant/health"));
    expect(res.status).toBe(503);
    expect(await res.json()).toMatchObject({ ok: false, detail: "fake model is down" });
  });

  test("is 503 when CookVault's agent door is shut", async () => {
    const res = await app([], { cookvaultDown: true }).fetch(new Request("http://assistant/health"));
    expect(res.status).toBe(503);
    expect(await res.json()).toMatchObject({ ok: false, cookvault: { ok: false } });
  });
});

describe("POST /chat", () => {
  test("rejects a body that is not a conversation", async () => {
    const service = app([]);
    expect((await service.fetch(post({}))).status).toBe(400);
    expect((await service.fetch(post({ conversation_id: "c", messages: [] }))).status).toBe(400);
    expect((await service.fetch(post({ conversation_id: "c", messages: [{ role: "assistant", content: "hi" }] }))).status).toBe(400);
    expect((await service.fetch(post({ conversation_id: "c", messages: [{ role: "user", content: "   " }] }))).status).toBe(400);
  });

  test("refuses to start a turn the model cannot answer", async () => {
    const res = await app([{ text: "never" }], { modelDown: true }).fetch(post({ conversation_id: "c", messages: [{ role: "user", content: "hi" }] }));
    expect(res.status).toBe(503);
    expect(((await res.json()) as { detail: string }).detail).toContain("unavailable");
  });

  test("streams the turn as server-sent events", async () => {
    const service = app([{ calls: [{ id: "1", name: "search_recipes", arguments: {} }] }, { text: "One recipe: **Quick Pasta**." }]);
    const res = await service.fetch(post({ conversation_id: "c", messages: [{ role: "user", content: "what do I have?" }] }));

    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("text/event-stream");
    const body = await res.text();
    const events = body
      .split("\n\n")
      .filter(Boolean)
      .map((frame) => frame.split("\n")[0]!.replace("event: ", ""));
    expect(events).toEqual(["tool", "tool", "text", "text", "done"]);
    expect(body).toContain('"delta":"One recipe: **Quick Pasta**."'.slice(0, 20));
  });

  test("anything else is 404", async () => {
    expect((await app([]).fetch(new Request("http://assistant/nope"))).status).toBe(404);
  });
});
