"use client";

interface DagStep {
  name: string;
  status: "completed" | "running" | "failed" | "pending";
  depends_on?: string[];
}

interface DagViewProps {
  steps: DagStep[];
}

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-success/20 border-success text-success",
  running: "bg-warning/20 border-warning text-warning",
  failed: "bg-error/20 border-error text-error",
  pending: "bg-border border-border text-text-muted",
};

const STATUS_DOTS: Record<string, string> = {
  completed: "bg-success",
  running: "bg-warning animate-pulse",
  failed: "bg-error",
  pending: "bg-text-muted",
};

export function DagView({ steps }: DagViewProps) {
  if (!steps || steps.length === 0) {
    return (
      <div className="text-sm text-text-muted py-8 text-center">
        No steps in this workflow.
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 overflow-x-auto py-4 px-2">
      {steps.map((step, i) => (
        <div key={step.name} className="flex items-center gap-2 shrink-0">
          <div
            className={`border rounded-lg px-4 py-3 min-w-[120px] text-center ${
              STATUS_COLORS[step.status] ?? STATUS_COLORS.pending
            }`}
          >
            <div className="flex items-center justify-center gap-2 mb-1">
              <span
                className={`inline-block w-2 h-2 rounded-full ${
                  STATUS_DOTS[step.status] ?? STATUS_DOTS.pending
                }`}
              />
              <span className="text-xs font-mono">{step.name}</span>
            </div>
            <span className="text-[10px] opacity-70">{step.status}</span>
          </div>
          {i < steps.length - 1 && (
            <span className="text-text-muted text-lg select-none">&rarr;</span>
          )}
        </div>
      ))}
    </div>
  );
}
