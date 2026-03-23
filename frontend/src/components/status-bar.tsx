"use client";

interface ServiceDot {
  label: string;
  status: "green" | "yellow" | "red" | "gray";
}

const COLOR_MAP: Record<ServiceDot["status"], string> = {
  green: "bg-success",
  yellow: "bg-warning",
  red: "bg-error",
  gray: "bg-text-muted",
};

export function StatusBar() {
  // Initially all gray (unknown). Will be wired to health check later.
  const services: ServiceDot[] = [
    { label: "PostgreSQL", status: "gray" },
    { label: "Redis", status: "gray" },
    { label: "Ollama", status: "gray" },
  ];

  return (
    <div className="flex items-center justify-between h-6 px-3 bg-sidebar border-t border-border text-xs text-text-muted shrink-0">
      <div className="flex items-center gap-3">
        {services.map((s) => (
          <span key={s.label} className="flex items-center gap-1">
            <span
              className={`inline-block w-2 h-2 rounded-full ${COLOR_MAP[s.status]}`}
            />
            {s.label}
          </span>
        ))}
      </div>
      <span>dev-tenant / dev-user</span>
    </div>
  );
}
