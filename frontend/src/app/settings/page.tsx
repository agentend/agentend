"use client";

import { useEffect, useMemo, useCallback } from "react";
import { useIntent } from "@/lib/use-intent";
import { getToken, decodePayload } from "@/lib/auth";
import type { StateSnapshotEvent } from "@/lib/event-types";

export default function SettingsPage() {
  const fleet = useIntent();
  const health = useIntent();

  const fetchFleet = useCallback(() => {
    fleet.send({
      capability: "fleet.status",
      input: "show workers",
      stream: true,
    });
  }, [fleet.send]);

  const fetchHealth = useCallback(() => {
    health.send({
      capability: "system.health",
      input: "check connections",
      stream: true,
    });
  }, [health.send]);

  useEffect(() => {
    fetchFleet();
    fetchHealth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fleet config from state snapshot
  const fleetConfig = useMemo(() => {
    const snapshots = fleet.events.filter((e) => e.type === "state_snapshot");
    if (snapshots.length === 0) return null;
    const last = snapshots[snapshots.length - 1] as StateSnapshotEvent;
    return last.state;
  }, [fleet.events]);

  // Auth info from JWT
  const authInfo = useMemo(() => {
    const token = getToken();
    if (!token) return null;
    return decodePayload(token);
  }, []);

  // Connection statuses from health check
  const connections = useMemo<
    Record<string, string | boolean> | null
  >(() => {
    const snapshots = health.events.filter((e) => e.type === "state_snapshot");
    if (snapshots.length === 0) return null;
    const last = snapshots[snapshots.length - 1] as StateSnapshotEvent;
    const data = last.state;
    if (data.connections && typeof data.connections === "object") {
      return data.connections as Record<string, string | boolean>;
    }
    return data as Record<string, string | boolean>;
  }, [health.events]);

  return (
    <div className="p-6 max-w-3xl space-y-6">
      <h1 className="text-lg font-semibold text-text-primary">Settings</h1>

      {/* Fleet Config */}
      <section>
        <h2 className="text-sm font-medium text-text-primary mb-2">
          Fleet Config
        </h2>
        <div className="bg-surface border border-border rounded-lg p-4 overflow-auto max-h-80">
          {fleet.isStreaming && !fleetConfig ? (
            <div className="h-32 animate-pulse bg-border/30 rounded" />
          ) : fleetConfig ? (
            <pre className="text-xs font-mono text-text-secondary whitespace-pre-wrap">
              {JSON.stringify(fleetConfig, null, 2)}
            </pre>
          ) : (
            <p className="text-sm text-text-muted">
              Unable to load fleet config.
            </p>
          )}
        </div>
        {fleet.error && (
          <p className="mt-1 text-xs text-error">{fleet.error}</p>
        )}
      </section>

      {/* Auth Info */}
      <section>
        <h2 className="text-sm font-medium text-text-primary mb-2">
          Auth Info
        </h2>
        <div className="bg-surface border border-border rounded-lg p-4">
          {authInfo ? (
            <dl className="space-y-2 text-xs">
              <InfoRow label="Tenant" value={String(authInfo.tenant_id ?? "--")} />
              <InfoRow label="User" value={String(authInfo.user_id ?? authInfo.sub ?? "--")} />
              <InfoRow
                label="Roles"
                value={
                  Array.isArray(authInfo.roles)
                    ? (authInfo.roles as string[]).join(", ")
                    : "--"
                }
              />
              <InfoRow
                label="Capabilities"
                value={
                  Array.isArray(authInfo.capabilities)
                    ? (authInfo.capabilities as string[]).join(", ")
                    : "--"
                }
              />
            </dl>
          ) : (
            <p className="text-sm text-text-muted">No token found.</p>
          )}
        </div>
      </section>

      {/* Connections */}
      <section>
        <h2 className="text-sm font-medium text-text-primary mb-2">
          Connections
        </h2>
        <div className="bg-surface border border-border rounded-lg p-4">
          {health.isStreaming && !connections ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-6 bg-border/30 rounded animate-pulse"
                />
              ))}
            </div>
          ) : connections ? (
            <dl className="space-y-2 text-xs">
              {Object.entries(connections).map(([key, val]) => {
                const ok =
                  val === true ||
                  val === "ok" ||
                  val === "connected" ||
                  val === "healthy";
                return (
                  <div key={key} className="flex items-center gap-2">
                    <span
                      className={`inline-block w-2 h-2 rounded-full shrink-0 ${
                        ok ? "bg-success" : "bg-error"
                      }`}
                    />
                    <dt className="text-text-muted w-24 shrink-0">{key}</dt>
                    <dd className="text-text-secondary">{String(val)}</dd>
                  </div>
                );
              })}
            </dl>
          ) : (
            <p className="text-sm text-text-muted">
              Unable to load connection status.
            </p>
          )}
        </div>
        {health.error && (
          <p className="mt-1 text-xs text-error">{health.error}</p>
        )}
      </section>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex">
      <dt className="text-text-muted w-24 shrink-0">{label}</dt>
      <dd className="text-text-secondary">{value}</dd>
    </div>
  );
}
