"use client";

interface MetricCardProps {
  label: string;
  value: string;
}

export function MetricCard({ label, value }: MetricCardProps) {
  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      <p className="text-xs text-text-muted mb-1">{label}</p>
      <p className="text-xl font-semibold text-text-primary">{value}</p>
    </div>
  );
}
