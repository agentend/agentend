"use client";

import { useEffect, useMemo, useCallback } from "react";
import { useIntent } from "@/lib/use-intent";
import { WorkerCard } from "@/components/worker-card";
import { RefreshCw } from "lucide-react";
import type { StateSnapshotEvent } from "@/lib/event-types";

const WORKER_SLOTS = [
  "classify",
  "extract",
  "verify",
  "summarize",
  "generate",
  "tool_call",
];

interface WorkerInfo {
  slot: string;
  model?: string;
  backend?: string;
  temperature?: number;
  max_tokens?: number;
  fallback?: string;
  routing?: string;
}

export default function FleetPage() {
  const { events, isStreaming, error, send } = useIntent();

  const fetch = useCallback(() => {
    send({ capability: "fleet.status", input: "show workers", stream: true });
  }, [send]);

  useEffect(() => {
    fetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const workers = useMemo<WorkerInfo[]>(() => {
    const snapshots = events.filter((e) => e.type === "state_snapshot");
    if (snapshots.length === 0) {
      return WORKER_SLOTS.map((s) => ({ slot: s }));
    }
    const last = snapshots[snapshots.length - 1] as StateSnapshotEvent;
    const data = last.state;

    // Accept snapshot.workers as array or keyed object
    if (Array.isArray(data.workers)) {
      return data.workers as WorkerInfo[];
    }
    if (data.workers && typeof data.workers === "object") {
      return Object.entries(data.workers as Record<string, unknown>).map(
        ([slot, cfg]) => ({
          slot,
          ...(typeof cfg === "object" && cfg !== null
            ? (cfg as Omit<WorkerInfo, "slot">)
            : {}),
        })
      );
    }

    // Fallback: try top-level keys matching slots
    return WORKER_SLOTS.map((slot) => {
      const cfg = data[slot];
      return {
        slot,
        ...(typeof cfg === "object" && cfg !== null
          ? (cfg as Omit<WorkerInfo, "slot">)
          : {}),
      };
    });
  }, [events]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-lg font-semibold text-text-primary">Fleet</h1>
        <button
          onClick={fetch}
          disabled={isStreaming}
          className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-primary disabled:opacity-40 transition-colors"
        >
          <RefreshCw
            size={14}
            className={isStreaming ? "animate-spin" : ""}
          />
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 px-3 py-2 text-sm text-error bg-error/10 border border-error/30 rounded-md">
          {error}
        </div>
      )}

      {isStreaming && events.length === 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {WORKER_SLOTS.map((s) => (
            <div
              key={s}
              className="bg-surface border border-border rounded-lg p-4 animate-pulse h-36"
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {workers.map((w) => (
            <WorkerCard key={w.slot} {...w} />
          ))}
        </div>
      )}
    </div>
  );
}
