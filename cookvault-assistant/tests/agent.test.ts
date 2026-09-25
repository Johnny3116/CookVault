import { describe, expect, test } from "bun:test";

import { Agent } from "../src/agent.ts";
import { createMemoryAuditLog } from "../src/audit.ts";
import { CookVaultError } from "../src/cookvault.ts";
import type { SseEvent } from "../src/sse.ts";
import { defaultRegistry } from "../src/tools/index.ts";
import { DRAFT_ID, FakeCookVault, FakeProvider, RECIPE_ID, type ScriptedTurn, summary } from "./fakes.ts";

function build(script: ScriptedTurn[], cookvault = new FakeCookVault(), maxToolRounds = 4) {
  const provider = new FakeProvider(script);
  const audit = createMemoryAuditLog();
  const agent = new Agent({
    provider,
    tools: defaultRegistry(),
    audit,
    toolContext: { cookvault, model: provider.model, version: "test" },
    systemPrompt: "Today is {{today}}. Model {{model}}.",
    maxToolRounds,
    contextMessages: 6,
  });
  return { agent, provider, audit, cookvault };
}

async function runTurn(agent: Agent, text = "hi", history: { role: "user" | "assistant"; content: string }[] = []) {
  const events: SseEvent[] = [];
  await agent.run({ conversationId: "c1", messages: [...history, { role: "user", content: text }], today: "2026-09-24" }, (e) => events.push(e));
  return events;
}

const textOf = (events: SseEvent[]) =>
  events
    .filter((e) => e.event === "text")
    .map((e) => (e.data as { delta: string }).delta)
    .join("");
const toolEvents = (events: SseEvent[]) => events.filter((e) => e.event === "tool").map((e) => e.data as { name: string; status: string; summary?: string; links?: unknown[] });

describe("a plain answer", () => {
  test("streams text and finishes with done, calling no tools", async () => {
    const { agent, cookvault } = build([{ text: "Rest the steak for five minutes." }]);
    const events = await runTurn(agent, "how long do I rest a steak?");

    expect(textOf(events)).toBe("Rest the steak for five minutes.");
    expect(events.at(-1)?.event).toBe("done");
    expect(toolEvents(events)).toHaveLength(0);
    expect(cookvault.calls).toHaveLength(0);
  });

  test("the system prompt carries today's date and the model name", async () => {
    const { agent, provider } = build([{ text: "ok" }]);
    await runTurn(agent);

    expect(provider.requests[0]?.messages[0]).toEqual({ role: "system", content: "Today is 2026-09-24. Model fake-model." });
  });

  test("older turns are dropped past the context window", async () => {
    const { agent, provider } = build([{ text: "ok" }]);
    const history = Array.from({ length: 10 }, (_, i) => ({ role: (i % 2 ? "assistant" : "user") as "user" | "assistant", content: `turn ${i}` }));
    await runTurn(agent, "latest", history);

    const sent = provider.requests[0]!.messages;
    // system + the last 6 of (10 history + 1 new)
    expect(sent).toHaveLength(7);
    expect(sent.at(-1)?.content).toBe("latest");
    expect(sent[1]?.content).toBe("turn 5");
  });
});

describe("a tool call", () => {
  test("executes the tool, hands the result back to the model, then answers", async () => {
    const cookvault = new FakeCookVault({ "POST /agent/search-recipes": { total_matched: 1, results: [summary] } });
    const { agent, provider, audit } = build(
      [{ calls: [{ id: "call_1", name: "search_recipes", arguments: { text: "pasta" } }] }, { text: "You have **Quick Pasta**." }],
      cookvault,
    );
    const events = await runTurn(agent, "any pasta?");

    expect(textOf(events)).toBe("You have **Quick Pasta**.");
    const chips = toolEvents(events);
    expect(chips.map((c) => c.status)).toEqual(["running", "done"]);
    expect(chips[1]?.summary).toBe("1 recipe");

    // The model saw the tool result on its second turn, in the controlled shape.
    const second = provider.requests[1]!.messages;
    const toolMessage = second.find((m) => m.role === "tool")!;
    expect(toolMessage.toolCallId).toBe("call_1");
    expect(JSON.parse(toolMessage.content)).toMatchObject({ ok: true, result: { total_matched: 1 } });
    // And the assistant's request turn was kept, tool calls attached.
    expect(second.find((m) => m.role === "assistant")?.toolCalls?.[0]?.name).toBe("search_recipes");

    expect(audit.entries).toHaveLength(1);
    expect(audit.entries[0]).toMatchObject({ tool: "search_recipes", kind: "READ", ok: true, conversation_id: "c1" });
  });

  test("an unknown tool is refused and the model is told what exists", async () => {
    const { agent, provider, cookvault } = build([{ calls: [{ id: "x", name: "delete_recipe", arguments: {} }] }, { text: "I can't do that." }]);
    const events = await runTurn(agent);

    expect(toolEvents(events)[0]?.status).toBe("error");
    const reply = JSON.parse(provider.requests[1]!.messages.find((m) => m.role === "tool")!.content);
    expect(reply.error).toContain("no tool called delete_recipe");
    expect(reply.error).toContain("search_recipes");
    expect(cookvault.calls).toHaveLength(0);
  });

  test("invalid arguments never reach CookVault", async () => {
    const cookvault = new FakeCookVault({ "GET /agent/recipes/not-a-uuid": summary });
    const { agent, provider } = build([{ calls: [{ id: "x", name: "get_recipe", arguments: { recipe_id: "not-a-uuid" } }] }, { text: "hm" }], cookvault);
    const events = await runTurn(agent);

    expect(toolEvents(events)[0]).toMatchObject({ status: "error", summary: "invalid arguments" });
    expect(JSON.parse(provider.requests[1]!.messages.find((m) => m.role === "tool")!.content).error).toContain("recipe_id");
    expect(cookvault.calls).toHaveLength(0);
  });

  test("a CookVault failure is reported as a failure, not a success", async () => {
    const cookvault = new FakeCookVault({ [`GET /agent/recipes/${RECIPE_ID}`]: new CookVaultError(404, "Recipe not found") });
    const { agent, provider, audit } = build([{ calls: [{ id: "x", name: "get_recipe", arguments: { recipe_id: RECIPE_ID } }] }, { text: "That recipe isn't there." }], cookvault);
    const events = await runTurn(agent);

    const chips = toolEvents(events);
    expect(chips.at(-1)).toMatchObject({ status: "error", summary: "Recipe not found" });
    const reply = JSON.parse(provider.requests[1]!.messages.find((m) => m.role === "tool")!.content);
    expect(reply).not.toHaveProperty("ok");
    expect(reply.error).toContain("do not claim it worked");
    expect(audit.entries[0]).toMatchObject({ ok: false, error: "Recipe not found" });
  });

  test("the same call twice in a row is refused", async () => {
    const cookvault = new FakeCookVault({ "POST /agent/search-recipes": { total_matched: 0, results: [] } });
    const call = { id: "x", name: "search_recipes", arguments: { text: "tacos" } };
    const { agent, provider } = build([{ calls: [call] }, { calls: [{ ...call, id: "y" }] }, { text: "Nothing with tacos." }], cookvault);
    await runTurn(agent);

    expect(cookvault.calls).toHaveLength(1);
    const reply = JSON.parse(provider.requests[2]!.messages.filter((m) => m.role === "tool").at(-1)!.content);
    expect(reply.error).toContain("already called");
  });

  test("after the round limit the model is asked once more without tools", async () => {
    const cookvault = new FakeCookVault({ "POST /agent/search-recipes": { total_matched: 0, results: [] } });
    const script: ScriptedTurn[] = [0, 1, 2].map((i) => ({ calls: [{ id: `c${i}`, name: "search_recipes", arguments: { text: `try ${i}` } }] }));
    script.push({ text: "I couldn't find it." });
    const { agent, provider } = build(script, cookvault, 3);
    const events = await runTurn(agent);

    expect(textOf(events)).toBe("I couldn't find it.");
    expect(provider.requests).toHaveLength(4);
    expect(provider.requests[3]!.tools).toEqual([]);
    expect(provider.requests[2]!.tools.length).toBeGreaterThan(0);
  });
});

describe("proposing", () => {
  test("a recipe draft goes through /agent with provenance and comes back as a link", async () => {
    const cookvault = new FakeCookVault({
      "POST /agent/recipe-drafts": (body: unknown) => ({ id: DRAFT_ID, status: "ready", title: (body as { title: string }).title, valid: true, issues: [] }),
    });
    const { agent, audit } = build(
      [
        {
          calls: [
            {
              id: "d",
              name: "create_recipe_draft",
              arguments: {
                title: "Mom's Chili",
                ingredients: [{ name: "ground beef", quantity: 2, unit: "lb", category: "raw_ingredient" }, { name: "chili powder" }],
                steps: ["Brown the beef.", "Add everything else and simmer for an hour."],
                source_text: "two pounds of ground beef... simmer for about an hour",
              },
            },
          ],
        },
        { text: "Drafted **Mom's Chili** for you to review." },
      ],
      cookvault,
    );
    const events = await runTurn(agent, "add my mom's chili");

    const sent = cookvault.calls[0]!.body as Record<string, any>;
    expect(sent.payload.steps).toEqual([
      { order: 1, instruction_text: "Brown the beef." },
      { order: 2, instruction_text: "Add everything else and simmer for an hour." },
    ]);
    expect(sent.payload.ingredients[1]).toEqual({ name: "chili powder", quantity: null, unit: null, category: "misc" });
    expect(sent.provenance).toEqual({
      source_type: "manual",
      original_text: "two pounds of ground beef... simmer for about an hour",
      agent_model: "fake-model",
      agent_version: "test",
    });
    // import_method is CookVault's to set, never the model's.
    expect(sent.provenance).not.toHaveProperty("import_method");

    const done = toolEvents(events).find((c) => c.status === "done")!;
    expect(done.links).toEqual([{ kind: "draft", id: DRAFT_ID, title: "Mom's Chili" }]);
    expect(audit.entries[0]).toMatchObject({ kind: "WRITE_DRAFT", affected_record_id: DRAFT_ID });
  });

  test("a draft with no ingredients or steps is refused at the schema, before CookVault", async () => {
    const cookvault = new FakeCookVault({ "POST /agent/recipe-drafts": { id: DRAFT_ID, status: "draft", title: "x", valid: false, issues: [] } });
    const { agent } = build([{ calls: [{ id: "d", name: "create_recipe_draft", arguments: { title: "Chicken tacos", ingredients: [], steps: [] } }] }, { text: "What goes in them?" }], cookvault);
    const events = await runTurn(agent, "add chicken tacos");

    expect(toolEvents(events)[0]?.status).toBe("error");
    expect(cookvault.calls).toHaveLength(0);
    expect(textOf(events)).toBe("What goes in them?");
  });
});

describe("failure of the model itself", () => {
  test("becomes an error event and still ends with done", async () => {
    const { agent } = build([{ fail: "Ollama unreachable at http://nowhere" }]);
    const events = await runTurn(agent);

    expect(events.map((e) => e.event)).toEqual(["error", "done"]);
    expect((events[0]!.data as { message: string }).message).toContain("Ollama unreachable");
  });
});
