"use client";

interface MemoryTierProps {
  tier: string;
  data: Record<string, unknown> | unknown[] | null;
}

export function MemoryTier({ tier, data }: MemoryTierProps) {
  if (!data) {
    return (
      <div className="text-sm text-text-muted py-8 text-center">
        No data available for {tier} tier.
      </div>
    );
  }

  switch (tier) {
    case "working":
      return <WorkingView data={data as Record<string, unknown>} />;
    case "session":
      return <SessionView data={data as unknown[]} />;
    case "semantic":
      return <SemanticView data={data as unknown[]} />;
    case "core_blocks":
      return <CoreBlocksView data={data as unknown[]} />;
    case "consolidation":
      return <ConsolidationView data={data as unknown[]} />;
    default:
      return (
        <pre className="text-xs text-text-secondary font-mono whitespace-pre-wrap">
          {JSON.stringify(data, null, 2)}
        </pre>
      );
  }
}

function WorkingView({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data);
  if (entries.length === 0) {
    return (
      <p className="text-sm text-text-muted py-4 text-center">
        Working memory is empty.
      </p>
    );
  }
  return (
    <div className="space-y-1">
      {entries.map(([key, value]) => (
        <div
          key={key}
          className="flex gap-3 px-3 py-2 rounded-md bg-surface border border-border text-xs"
        >
          <span className="font-mono text-text-primary shrink-0">{key}</span>
          <span className="text-text-secondary truncate">
            {typeof value === "string" ? value : JSON.stringify(value)}
          </span>
        </div>
      ))}
    </div>
  );
}

interface SessionMessage {
  role?: string;
  content?: string;
  timestamp?: string;
}

function SessionView({ data }: { data: unknown[] }) {
  const messages = data as SessionMessage[];
  if (messages.length === 0) {
    return (
      <p className="text-sm text-text-muted py-4 text-center">
        No session messages.
      </p>
    );
  }
  return (
    <div className="space-y-1">
      {messages.map((msg, i) => (
        <div
          key={i}
          className="px-3 py-2 rounded-md bg-surface border border-border text-xs"
        >
          <span className="font-mono text-text-muted mr-2">
            {msg.role ?? "unknown"}
          </span>
          <span className="text-text-secondary">
            {msg.content ?? JSON.stringify(msg)}
          </span>
        </div>
      ))}
    </div>
  );
}

interface SemanticFact {
  fact?: string;
  content?: string;
  score?: number;
}

function SemanticView({ data }: { data: unknown[] }) {
  const facts = data as SemanticFact[];
  if (facts.length === 0) {
    return (
      <p className="text-sm text-text-muted py-4 text-center">
        No semantic facts.
      </p>
    );
  }
  return (
    <div className="space-y-1">
      {facts.map((item, i) => (
        <div
          key={i}
          className="flex items-start gap-3 px-3 py-2 rounded-md bg-surface border border-border text-xs"
        >
          <span className="text-text-secondary flex-1">
            {item.fact ?? item.content ?? JSON.stringify(item)}
          </span>
          {item.score !== undefined && (
            <span className="font-mono text-text-muted shrink-0">
              {item.score.toFixed(3)}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

interface CoreBlock {
  name?: string;
  priority?: number;
  content?: string;
}

function CoreBlocksView({ data }: { data: unknown[] }) {
  const blocks = data as CoreBlock[];
  if (blocks.length === 0) {
    return (
      <p className="text-sm text-text-muted py-4 text-center">
        No core blocks.
      </p>
    );
  }
  return (
    <div className="space-y-1">
      {blocks.map((block, i) => (
        <div
          key={i}
          className="px-3 py-2 rounded-md bg-surface border border-border text-xs"
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-text-primary">
              {block.name ?? `Block ${i}`}
            </span>
            {block.priority !== undefined && (
              <span className="text-text-muted">
                priority: {block.priority}
              </span>
            )}
          </div>
          {block.content && (
            <p className="text-text-secondary">{block.content}</p>
          )}
        </div>
      ))}
    </div>
  );
}

interface ConsolidationOp {
  operation?: string;
  timestamp?: string;
  details?: string;
}

function ConsolidationView({ data }: { data: unknown[] }) {
  const ops = data as ConsolidationOp[];
  if (ops.length === 0) {
    return (
      <p className="text-sm text-text-muted py-4 text-center">
        No consolidation operations.
      </p>
    );
  }
  return (
    <div className="space-y-1">
      {ops.map((op, i) => (
        <div
          key={i}
          className="flex items-center gap-3 px-3 py-2 rounded-md bg-surface border border-border text-xs"
        >
          <span className="font-mono text-text-primary">
            {op.operation ?? "op"}
          </span>
          {op.timestamp && (
            <span className="text-text-muted">{op.timestamp}</span>
          )}
          {op.details && (
            <span className="text-text-secondary">{op.details}</span>
          )}
        </div>
      ))}
    </div>
  );
}
