"use client";

import { useSession } from "@/providers/session-provider";
import { Plus } from "lucide-react";

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function SessionList() {
  const { sessions, activeId, setActiveId } = useSession();

  return (
    <div className="flex flex-col w-[220px] bg-sidebar border-r border-border h-full">
      <div className="p-2">
        <button
          onClick={() => setActiveId(null)}
          className="flex items-center gap-1.5 w-full px-2.5 py-1.5 text-xs font-medium text-text-primary bg-surface border border-border rounded-md hover:bg-hover transition-colors"
        >
          <Plus size={14} />
          New Session
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-1 pb-2">
        {sessions.length === 0 && (
          <p className="text-text-muted text-xs px-2 py-4 text-center">
            No sessions yet
          </p>
        )}
        {sessions.map((s) => (
          <button
            key={s.id}
            onClick={() => setActiveId(s.id)}
            className={`flex flex-col w-full text-left px-2.5 py-2 rounded-md mb-0.5 transition-colors ${
              activeId === s.id
                ? "bg-surface text-text-primary"
                : "text-text-secondary hover:bg-hover hover:text-text-primary"
            }`}
          >
            <span className="inline-block text-[10px] font-mono px-1.5 py-0.5 rounded bg-border text-text-muted mb-1 w-fit">
              {s.capability}
            </span>
            <span className="text-xs truncate w-full">{s.firstInput}</span>
            <span className="text-[10px] text-text-muted mt-0.5">
              {relativeTime(s.createdAt)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
