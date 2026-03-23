"use client";

import { useEffect, useMemo, useCallback } from "react";
import { useIntent } from "@/lib/use-intent";
import { MetricCard } from "@/components/metric-card";
import { BudgetBar } from "@/components/budget-bar";
import { RefreshCw } from "lucide-react";
import type { StateSnapshotEvent } from "@/lib/event-types";

interface BudgetEntry {
  label: string;
  used: number;
  limit: number;
}

interface WorkerBreakdown {
  slot: string;
  tokens: number;
  calls: number;
  avg_latency_ms: number;
}

interface MetricsData {
  total_tokens?: number;
  total_cost?: number;
  avg_latency_ms?: number;
  cache_hit_rate?: number;
  budgets?: BudgetEntry[];
  worker_breakdown?: WorkerBreakdown[];
}

export default function MetricsPage() {
  const { events, isStreaming, error, send } = useIntent();

  const fetch = useCallback(() => {
    send({
      capability: "metrics.usage",
      input: "show 24h stats",
      stream: true,
    });
  }, [send]);

  useEffect(() => {
    fetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const data = useMemo<MetricsData>(() => {
    const snapshots = events.filter((e) => e.type === "state_snapshot");
    if (snapshots.length === 0) return {};
    const last = snapshots[snapshots.length - 1] as StateSnapshotEvent;
    return last.state as unknown as MetricsData;
  }, [events]);

  const fmt = (n: number | undefined) =>
    n !== undefined ? n.toLocaleString() : "--";

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-lg font-semibold text-text-primary">Metrics</h1>
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

      {/* Top metric cards */}
      {isStreaming && events.length === 0 ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="bg-surface border border-border rounded-lg h-20 animate-pulse"
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <MetricCard label="Total Tokens (24h)" value={fmt(data.total_tokens)} />
          <MetricCard
            label="Total Cost"
            value={
              data.total_cost !== undefined
                ? `$${data.total_cost.toFixed(2)}`
                : "--"
            }
          />
          <MetricCard
            label="Avg Latency"
            value={
              data.avg_latency_ms !== undefined
                ? `${data.avg_latency_ms.toFixed(0)} ms`
                : "--"
            }
          />
          <MetricCard
            label="Cache Hit Rate"
            value={
              data.cache_hit_rate !== undefined
                ? `${(data.cache_hit_rate * 100).toFixed(1)}%`
                : "--"
            }
          />
        </div>
      )}

      {/* Budget bars */}
      {data.budgets && data.budgets.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-medium text-text-primary mb-3">
            Budgets
          </h2>
          <div className="space-y-3">
            {data.budgets.map((b, i) => (
              <BudgetBar key={i} label={b.label} used={b.used} limit={b.limit} />
            ))}
          </div>
        </div>
      )}

      {/* Worker breakdown table */}
      {data.worker_breakdown && data.worker_breakdown.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-text-primary mb-3">
            Worker Breakdown
          </h2>
          <div className="bg-surface border border-border rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-text-muted">
                  <th className="text-left px-4 py-2 font-medium">Worker</th>
                  <th className="text-right px-4 py-2 font-medium">Tokens</th>
                  <th className="text-right px-4 py-2 font-medium">Calls</th>
                  <th className="text-right px-4 py-2 font-medium">
                    Avg Latency
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.worker_breakdown.map((w) => (
                  <tr
                    key={w.slot}
                    className="border-b border-border last:border-b-0"
                  >
                    <td className="px-4 py-2 font-mono text-text-primary">
                      {w.slot}
                    </td>
                    <td className="px-4 py-2 text-right text-text-secondary">
                      {w.tokens.toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-right text-text-secondary">
                      {w.calls}
                    </td>
                    <td className="px-4 py-2 text-right text-text-secondary">
                      {w.avg_latency_ms.toFixed(0)} ms
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
