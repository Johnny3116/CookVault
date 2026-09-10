import type { Step } from "@/types";

export function StepList({ steps }: { steps: Step[] }) {
  return (
    <ol className="space-y-4">
      {steps
        .slice()
        .sort((a, b) => a.order - b.order)
        .map((step) => (
          <li key={step.id} className="border-l-2 border-neutral-200 pl-4">
            <p>{step.instruction_text}</p>
            <p className="mt-1 text-xs text-neutral-400">
              {step.temperature && `${step.temperature} `}
              {step.duration && `· ${step.duration} `}
              {step.notes && `· ${step.notes}`}
            </p>
          </li>
        ))}
      {steps.length === 0 && <p className="text-sm text-neutral-400">No steps recorded.</p>}
    </ol>
  );
}
