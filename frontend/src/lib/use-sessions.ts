"use client";

import { useState, useCallback, useEffect } from "react";

export interface SessionEntry {
  id: string;
  capability: string;
  firstInput: string;
  createdAt: string;
}

const STORAGE_KEY = "agentend_sessions";

export function useSessions() {
  const [sessions, setSessions] = useState<SessionEntry[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        setSessions(JSON.parse(stored));
      } catch {
        // Ignore corrupt storage
      }
    }
  }, []);

  const addSession = useCallback(
    (id: string, capability: string, input: string) => {
      const entry: SessionEntry = {
        id,
        capability,
        firstInput: input.slice(0, 80),
        createdAt: new Date().toISOString(),
      };
      setSessions((prev) => {
        const next = [entry, ...prev].slice(0, 50);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        return next;
      });
      setActiveId(id);
    },
    []
  );

  return { sessions, activeId, setActiveId, addSession };
}
