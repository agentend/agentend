"use client";

interface BudgetBarProps {
  label: string;
  used: number;
  limit: number;
}

export function BudgetBar({ label, used, limit }: BudgetBarProps) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
  const barColor =
    pct > 90 ? "bg-error" : pct > 70 ? "bg-warning" : "bg-success";

  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-text-primary">{label}</span>
        <span className="text-xs text-text-muted">
          {pct.toFixed(0)}% &middot; {used.toLocaleString()} /{" "}
          {limit.toLocaleString()}
        </span>
      </div>
      <div className="w-full h-2 bg-border rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
