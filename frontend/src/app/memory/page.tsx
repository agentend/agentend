"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useIntent } from "@/lib/use-intent";
import { MemoryTier } from "@/components/memory-tier";
import type { StateSnapshotEvent } from "@/lib/event-types";

const TIERS = [
  { key: "working", label: "Working" },
  { key: "session", label: "Session" },
  { key: "semantic", label: "Semantic" },
  { key: "core_blocks", label: "Core Blocks" },
  { key: "consolidation", label: "Consolidation" },
] as const;

type TierKey = (typeof TIERS)[number]["key"];

export default function MemoryPage() {
  const [activeTier, setActiveTier] = useState<TierKey>("working");
  const { events, isStreaming, error, send } = useIntent();

  const fetch = useCallback(
    (tier: TierKey) => {
      send({
        capability: "memory.inspect",
        input: `show ${tier} memory`,
        stream: true,
      });
    },
    [send]
  );

  useEffect(() => {
    fetch(activeTier);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTier]);

  const tierData = useMemo(() => {
    const snapshots = events.filter((e) => e.type === "state_snapshot");
    if (snapshots.length === 0) return null;
    const last = snapshots[snapshots.length - 1] as StateSnapshotEvent;
    const data = last.state;
    // Accept tier-keyed data or top-level
    return (data[activeTier] as Record<string, unknown> | unknown[]) ?? data;
  }, [events, activeTier]);

  return (
    <div className="p-6">
      <h1 className="text-lg font-semibold text-text-primary mb-4">Memory</h1>

      {/* Tab bar */}
      <div className="flex gap-0 border-b border-border mb-6">
        {TIERS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTier(key)}
            className={`px-4 py-2 text-sm transition-colors -mb-px ${
              activeTier === key
                ? "text-text-primary border-b-2 border-text-primary"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 px-3 py-2 text-sm text-error bg-error/10 border border-error/30 rounded-md">
          {error}
        </div>
      )}

      {isStreaming && !tierData ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-surface border border-border rounded-md h-10 animate-pulse"
            />
          ))}
        </div>
      ) : (
        <MemoryTier
          tier={activeTier}
          data={tierData as Record<string, unknown> | unknown[] | null}
        />
      )}
    </div>
  );
}
