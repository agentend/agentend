"use client";

import { useMemo } from "react";
import type { AgentEvent } from "@/lib/event-types";
import { Activity, Brain, Cpu } from "lucide-react";

interface ContextPanelProps {
  events: AgentEvent[];
}

interface WorkerInfo {
  id: string;
  name: string;
  status: "running" | "done";
}

export function ContextPanel({ events }: ContextPanelProps) {
  const stats = useMemo(() => {
    const finished = events.find((e) => e.type === "run_finished") as
      | (AgentEvent & { tokens_in?: number; tokens_out?: number; cost?: number; latency_ms?: number })
      | undefined;

    return {
      tokensIn: finished?.tokens_in ?? 0,
      tokensOut: finished?.tokens_out ?? 0,
      cost: finished?.cost ?? 0,
      latencyMs: finished?.latency_ms ?? 0,
    };
  }, [events]);

  const memory = useMemo(() => {
    const snapshots = events.filter((e) => e.type === "state_snapshot") as Array<
      AgentEvent & { state: Record<string, unknown>; memory: Record<string, unknown> }
    >;
    if (snapshots.length === 0) return null;
    const last = snapshots[snapshots.length - 1];
    const mem = last.memory as Record<string, number> | undefined;
    return mem ?? null;
  }, [events]);

  const workers = useMemo(() => {
    const map = new Map<string, WorkerInfo>();
    for (const e of events) {
      if (e.type === "tool_call_start") {
        const ev = e as AgentEvent & { tool_use_id: string; tool_name: string };
        map.set(ev.tool_use_id, {
          id: ev.tool_use_id,
          name: ev.tool_name,
          status: "running",
        });
      } else if (e.type === "tool_call_end") {
        const ev = e as AgentEvent & { tool_use_id: string };
        const w = map.get(ev.tool_use_id);
        if (w) w.status = "done";
      }
    }
    return Array.from(map.values());
  }, [events]);

  return (
    <div className="flex flex-col w-[260px] bg-sidebar border-l border-border h-full overflow-y-auto">
      {/* Stats */}
      <section className="p-3 border-b border-border">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
          <Activity size={12} />
          Stats
        </h3>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <StatItem label="Tokens In" value={stats.tokensIn.toLocaleString()} />
          <StatItem label="Tokens Out" value={stats.tokensOut.toLocaleString()} />
          <StatItem
            label="Cost"
            value={stats.cost > 0 ? `$${stats.cost.toFixed(4)}` : "--"}
          />
          <StatItem
            label="Latency"
            value={stats.latencyMs > 0 ? `${stats.latencyMs}ms` : "--"}
          />
        </div>
      </section>

      {/* Memory */}
      <section className="p-3 border-b border-border">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
          <Brain size={12} />
          Memory
        </h3>
        {memory ? (
          <div className="space-y-1">
            {Object.entries(memory).map(([tier, count]) => (
              <div
                key={tier}
                className="flex items-center justify-between text-xs"
              >
                <span className="text-text-secondary capitalize">{tier}</span>
                <span className="text-text-primary font-mono">{String(count)}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-text-muted text-xs">No memory data</p>
        )}
      </section>

      {/* Workers */}
      <section className="p-3">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
          <Cpu size={12} />
          Workers
        </h3>
        {workers.length > 0 ? (
          <div className="space-y-1.5">
            {workers.map((w) => (
              <div
                key={w.id}
                className="flex items-center gap-2 text-xs"
              >
                <span
                  className={`inline-block w-2 h-2 rounded-full shrink-0 ${
                    w.status === "done" ? "bg-success" : "bg-warning animate-pulse"
                  }`}
                />
                <span className="text-text-primary font-mono truncate">
                  {w.name}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-text-muted text-xs">No workers called</p>
        )}
      </section>
    </div>
  );
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-text-muted text-[10px]">{label}</span>
      <span className="text-text-primary font-mono">{value}</span>
    </div>
  );
}
