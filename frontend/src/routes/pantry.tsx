import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { X } from "lucide-react";
import { useState } from "react";

import { BackupPanel } from "@/components/BackupPanel";
import { ErrorText, PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { apiFetch, json } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { PantryItem } from "@/types";

export const Route = createFileRoute("/pantry")({
  head: () => ({ meta: [{ title: "Pantry — CookVault" }] }),
  component: PantryPage,
});

function PantryPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [note, setNote] = useState("");

  const items = useQuery({ queryKey: ["pantry"], queryFn: () => apiFetch<PantryItem[]>("/pantry") });
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["pantry"] });
    queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
  };
  const add = useMutation({
    mutationFn: () => apiFetch("/pantry", json("POST", { name: name.trim(), note: note.trim() || null })),
    onSuccess: () => {
      setName("");
      setNote("");
      invalidate();
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiFetch(`/pantry/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });

  const error = add.error ?? remove.error ?? items.error;

  return (
    <div>
      <PageHeader
        eyebrow="Pantry"
        title="The things you keep in"
        intro="No quantities and no expiry dates on purpose — this is not inventory software. Its one job is to mark a shopping line as something you probably already have. It never takes anything off the list."
      />

      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <section className="space-y-4">
          <form
            className="glass-panel flex flex-wrap gap-2 p-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim()) add.mutate();
            }}
          >
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="olive oil" aria-label="Pantry item" className="field min-w-40 flex-1" />
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="note (optional)" aria-label="Note" className="field min-w-40 flex-1" />
            <Button type="submit" disabled={add.isPending}>
              Add
            </Button>
          </form>

          {error && <ErrorText>{describeApiError(error)}</ErrorText>}

          <div className="glass-panel p-4">
            {(items.data ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">Nothing in the pantry yet.</p>
            ) : (
              <ul className="list-rows">
                {items.data!.map((item) => (
                  <li key={item.id} className="group flex items-center gap-3 text-sm">
                    <span className="font-semibold">{item.name}</span>
                    {item.note && <span className="text-muted-foreground">{item.note}</span>}
                    <button onClick={() => remove.mutate(item.id)} aria-label={`Remove ${item.name}`} className="ml-auto text-muted-foreground/50 hover:text-destructive">
                      <X className="size-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <BackupPanel />
      </div>
    </div>
  );
}
