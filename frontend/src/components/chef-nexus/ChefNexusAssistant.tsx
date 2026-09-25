import { Link, useRouterState } from "@tanstack/react-router";
import { AlertCircle, Check, CornerDownLeft, Loader2, MessageCircle, RotateCcw, Square, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";

import chefImage from "@/assets/chef-nexus.png";
import { Button } from "@/components/ui/button";
import { type ChatMessage, type ToolActivity, useChefNexusChat } from "@/components/chef-nexus/useChefNexusChat";

const STARTERS = [
  "What can I cook with chicken tonight?",
  "What am I cooking this week?",
  "Something under 30 minutes, please",
];

/** ChefNexus, the floating cooking companion. Reads the cookbook through the
 *  assistant service and proposes drafts; it never writes a recipe itself. */
export function ChefNexusAssistant() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const { messages, status, health, checkHealth, send, stop, reset } = useChefNexusChat();

  useEffect(() => {
    if (open) {
      checkHealth();
      inputRef.current?.focus();
    }
  }, [open, checkHealth]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  if (pathname === "/login") return null;

  const streaming = status === "streaming";
  const down = health !== null && !health.ok;

  async function submit() {
    const text = draft;
    setDraft("");
    await send(text);
  }

  return (
    <div className="assistant-wrap">
      {open && (
        <div className="assistant-panel glass-panel" role="dialog" aria-label="ChefNexus assistant">
          <div className="assistant-head">
            <img src={chefImage} alt="" width={816} height={816} />
            <div className="min-w-0 flex-1">
              <h2 className="font-display text-lg font-semibold">ChefNexus</h2>
              <p>{health?.model ? `${health.model} · proposes, never saves` : "Cooking companion · proposes, never saves"}</p>
            </div>
            {messages.length > 0 && (
              <Button size="icon-sm" variant="ghost" onClick={reset} aria-label="New conversation" title="New conversation">
                <RotateCcw />
              </Button>
            )}
            <Button size="icon-sm" variant="ghost" onClick={() => setOpen(false)} aria-label="Close ChefNexus">
              <X />
            </Button>
          </div>

          {down && (
            <div className="assistant-status is-down flex items-center gap-1.5">
              <AlertCircle className="size-3.5" /> ChefNexus is currently unavailable{health?.detail ? ` — ${health.detail}` : ""}. Everything else still works.
            </div>
          )}

          <div ref={logRef} className="assistant-log">
            {messages.length === 0 && (
              <div className="assistant-greeting">
                <p className="font-medium">Hi! I'm ChefNexus, your cooking companion.</p>
                <p>I can search your recipes, tell you what's planned, help with a substitution, or draft a recipe from what you tell me. Drafts wait for your approval.</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {STARTERS.map((starter) => (
                    <button key={starter} className="chip !text-xs" onClick={() => send(starter)} disabled={streaming || down}>
                      {starter}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((message) => (
              <MessageView key={message.id} message={message} streaming={streaming && message === messages[messages.length - 1]} />
            ))}
          </div>

          <form
            className="assistant-compose"
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
          >
            <textarea
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              placeholder={down ? "ChefNexus is offline" : "Ask ChefNexus about dinner…"}
              aria-label="Message ChefNexus"
              disabled={down}
              className="field"
            />
            <div className="flex items-center justify-between">
              <span className="text-[.68rem] text-muted-foreground">Enter to send · Shift+Enter for a new line</span>
              {streaming ? (
                <Button type="button" size="icon-sm" variant="secondary" onClick={stop} aria-label="Stop">
                  <Square />
                </Button>
              ) : (
                <Button type="submit" size="icon-sm" disabled={!draft.trim() || down} aria-label="Send">
                  <CornerDownLeft />
                </Button>
              )}
            </div>
          </form>
        </div>
      )}
      <Button className="assistant-toggle" onClick={() => setOpen((v) => !v)} aria-label={open ? "Close ChefNexus assistant" : "Open ChefNexus assistant"}>
        {open ? <X /> : <MessageCircle />}
        <span>{open ? "Close" : "Ask ChefNexus"}</span>
      </Button>
    </div>
  );
}

function MessageView({ message, streaming }: { message: ChatMessage; streaming: boolean }) {
  if (message.role === "user") return <div className="msg msg-user">{message.content}</div>;
  const waiting = streaming && !message.content && !message.error;
  return (
    <div className="msg msg-assistant flex flex-col gap-2">
      {message.activity.map((activity) => (
        <ActivityChip key={activity.id} activity={activity} />
      ))}
      {message.content && <Markdown>{message.content}</Markdown>}
      {waiting && message.activity.every((a) => a.status !== "running") && (
        <span className="typing-dots text-muted-foreground" aria-label="ChefNexus is thinking">
          <span />
          <span />
          <span />
        </span>
      )}
      {message.error && (
        <p className="flex items-center gap-1.5 text-xs text-destructive">
          <AlertCircle className="size-3.5" /> {message.error}
        </p>
      )}
      {message.activity.flatMap((a) => a.links ?? []).map((link) => (
        <div key={`${link.kind}-${link.id}`} className="draft-card">
          <p className="font-semibold">
            {link.kind === "draft" ? "Draft proposed: " : link.kind === "proposal" ? "Week proposed: " : ""}
            {link.title}
          </p>
          <p className="text-muted-foreground">
            {link.kind === "draft" && "Nothing is saved until you review and promote it."}
            {link.kind === "proposal" && "Nothing is planned until you approve it."}
          </p>
          {link.kind === "draft" && (
            <Link to="/drafts/$id" params={{ id: link.id }}>
              Review the draft
            </Link>
          )}
          {link.kind === "proposal" && (
            <Link to="/calendar/proposals" hash={link.id}>
              Review the week
            </Link>
          )}
          {link.kind === "recipe" && (
            <Link to="/recipes/$id" params={{ id: link.id }}>
              Open recipe
            </Link>
          )}
        </div>
      ))}
    </div>
  );
}

function ActivityChip({ activity }: { activity: ToolActivity }) {
  const icon =
    activity.status === "running" ? <Loader2 className="animate-spin" /> : activity.status === "done" ? <Check /> : <AlertCircle />;
  return (
    <span className={`tool-chip ${activity.status === "done" ? "is-done" : activity.status === "error" ? "is-error" : ""}`} title={activity.summary}>
      {icon} {activity.label}
      {activity.status === "done" && activity.summary ? ` · ${activity.summary}` : ""}
    </span>
  );
}
