import type { Step } from "@/types";

export function StepList({ steps }: { steps: Step[] }) {
  if (steps.length === 0) return <p className="text-sm text-muted-foreground">No steps recorded.</p>;
  const detail = (step: Step) => [step.temperature, step.duration, step.notes].filter(Boolean).join(" · ");
  return (
    <ol className="step-list">
      {steps
        .slice()
        .sort((a, b) => a.order - b.order)
        .map((step) => (
          <li key={step.id}>
            <span className="step-number">{step.order}</span>
            <div>
              <p>{step.instruction_text}</p>
              {detail(step) && <p className="mt-1 text-xs text-muted-foreground">{detail(step)}</p>}
            </div>
          </li>
        ))}
    </ol>
  );
}
