"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useIntent } from "@/lib/use-intent";
import { useSessions, type SessionEntry } from "@/lib/use-sessions";
import { ensureToken } from "@/lib/auth";
import type { AgentEvent } from "@/lib/event-types";
import type { IntentRequest, IntentResponse } from "@/lib/api";

interface SessionContextValue {
  // Sessions
  sessions: SessionEntry[];
  activeId: string | null;
  setActiveId: (id: string | null) => void;
  addSession: (id: string, capability: string, input: string) => void;
  // Intent / streaming
  events: AgentEvent[];
  isStreaming: boolean;
  error: string | null;
  send: (params: IntentRequest) => Promise<IntentResponse>;
  stop: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const { sessions, activeId, setActiveId, addSession } = useSessions();
  const { events, isStreaming, error, send, stop } = useIntent();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    ensureToken()
      .then((token) => {
        console.log("[agentend] Token acquired:", token ? "yes" : "no (backend unreachable)");
        setReady(true);
      })
      .catch((err) => {
        console.error("[agentend] Token error:", err);
        setReady(true); // Still render UI, auth errors will show in the views
      });
  }, []);

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg text-text-muted text-sm">
        Connecting...
      </div>
    );
  }

  return (
    <SessionContext.Provider
      value={{
        sessions,
        activeId,
        setActiveId,
        addSession,
        events,
        isStreaming,
        error,
        send,
        stop,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useSession must be used within a SessionProvider");
  }
  return ctx;
}
