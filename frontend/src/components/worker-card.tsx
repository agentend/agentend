"use client";

interface WorkerCardProps {
  slot: string;
  model?: string;
  backend?: string;
  temperature?: number;
  max_tokens?: number;
  fallback?: string;
  routing?: string;
}

export function WorkerCard({
  slot,
  model,
  backend,
  temperature,
  max_tokens,
  fallback,
  routing,
}: WorkerCardProps) {
  const configured = !!model;

  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <span
          className={`inline-block w-2 h-2 rounded-full shrink-0 ${
            configured ? "bg-success" : "bg-text-muted"
          }`}
        />
        <span className="font-mono text-sm text-text-primary font-medium">
          {slot}
        </span>
      </div>
      <dl className="space-y-1.5 text-xs">
        <Row label="Model" value={model ?? "not set"} muted={!model} />
        <Row label="Backend" value={backend ?? "litellm"} />
        <Row
          label="Temp"
          value={temperature !== undefined ? String(temperature) : "--"}
          inline
        />
        <Row
          label="Max"
          value={max_tokens !== undefined ? String(max_tokens) : "--"}
          inline
        />
        {fallback && <Row label="Fallback" value={fallback} />}
        {routing && <Row label="Routing" value={routing} />}
      </dl>
    </div>
  );
}

function Row({
  label,
  value,
  muted,
  inline: _inline,
}: {
  label: string;
  value: string;
  muted?: boolean;
  inline?: boolean;
}) {
  return (
    <div className={`flex ${_inline ? "inline-flex mr-4" : ""}`}>
      <dt className="text-text-muted w-16 shrink-0">{label}</dt>
      <dd className={muted ? "text-text-muted italic" : "text-text-secondary"}>
        {value}
      </dd>
    </div>
  );
}
