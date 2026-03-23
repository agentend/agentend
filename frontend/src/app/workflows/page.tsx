"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import { useIntent } from "@/lib/use-intent";
import { DagView } from "@/components/dag-view";
import type { StateSnapshotEvent } from "@/lib/event-types";

interface WorkflowRun {
  id: string;
  name: string;
  status: "completed" | "running" | "failed" | "pending";
  started_at?: string;
  steps?: Array<{
    name: string;
    status: "completed" | "running" | "failed" | "pending";
    depends_on?: string[];
  }>;
}

const STATUS_BADGE: Record<string, string> = {
  completed: "bg-success/20 text-success",
  running: "bg-warning/20 text-warning",
  failed: "bg-error/20 text-error",
  pending: "bg-border text-text-muted",
};

export default function WorkflowsPage() {
  const { events, isStreaming, error, send } = useIntent();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const fetch = useCallback(() => {
    send({
      capability: "workflow.status",
      input: "list runs",
      stream: true,
    });
  }, [send]);

  useEffect(() => {
    fetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runs = useMemo<WorkflowRun[]>(() => {
    const snapshots = events.filter((e) => e.type === "state_snapshot");
    if (snapshots.length === 0) return [];
    const last = snapshots[snapshots.length - 1] as StateSnapshotEvent;
    const data = last.state;
    if (Array.isArray(data.runs)) return data.runs as WorkflowRun[];
    if (Array.isArray(data)) return data as WorkflowRun[];
    return [];
  }, [events]);

  const selected = useMemo(
    () => runs.find((r) => r.id === selectedId) ?? runs[0] ?? null,
    [runs, selectedId]
  );

  return (
    <div className="flex h-full">
      {/* Left panel: run list */}
      <div className="w-64 shrink-0 border-r border-border overflow-y-auto">
        <div className="p-4 border-b border-border">
          <h1 className="text-sm font-semibold text-text-primary">
            Workflows
          </h1>
        </div>

        {isStreaming && runs.length === 0 ? (
          <div className="p-4 space-y-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-14 bg-surface border border-border rounded-md animate-pulse"
              />
            ))}
          </div>
        ) : runs.length === 0 ? (
          <div className="p-4 text-sm text-text-muted">No workflow runs.</div>
        ) : (
          <div className="p-2 space-y-1">
            {runs.map((run) => (
              <button
                key={run.id}
                onClick={() => setSelectedId(run.id)}
                className={`w-full text-left px-3 py-2 rounded-md text-xs transition-colors ${
                  (selected?.id ?? runs[0]?.id) === run.id
                    ? "bg-hover"
                    : "hover:bg-hover"
                }`}
              >
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-text-primary font-medium truncate">
                    {run.name}
                  </span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] shrink-0 ${
                      STATUS_BADGE[run.status] ?? STATUS_BADGE.pending
                    }`}
                  >
                    {run.status}
                  </span>
                </div>
                {run.started_at && (
                  <span className="text-text-muted text-[10px]">
                    {run.started_at}
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Right panel: DAG detail */}
      <div className="flex-1 p-6 overflow-auto">
        {error && (
          <div className="mb-4 px-3 py-2 text-sm text-error bg-error/10 border border-error/30 rounded-md">
            {error}
          </div>
        )}

        {selected ? (
          <div>
            <div className="flex items-center gap-3 mb-4">
              <h2 className="text-sm font-semibold text-text-primary">
                {selected.name}
              </h2>
              <span
                className={`px-2 py-0.5 rounded text-xs ${
                  STATUS_BADGE[selected.status] ?? STATUS_BADGE.pending
                }`}
              >
                {selected.status}
              </span>
            </div>
            <DagView steps={selected.steps ?? []} />
          </div>
        ) : (
          <div className="text-sm text-text-muted py-8 text-center">
            Select a workflow run to view its DAG.
          </div>
        )}
      </div>
    </div>
  );
}
