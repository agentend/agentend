"use client";

import { useState, useCallback, useRef } from "react";
import { IntentRequest } from "./api";
import { ensureToken } from "./auth";
import { AgentEvent } from "./event-types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useIntent() {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(async (params: IntentRequest) => {
    setError(null);
    setEvents([]);
    setIsStreaming(true);

    try {
      const token = await ensureToken();
      const controller = new AbortController();
      abortRef.current = controller;

      const res = await fetch(`${API_URL}/intent`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ ...params, stream: true }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text);
      }

      const contentType = res.headers.get("content-type") || "";

      if (contentType.includes("text/event-stream") && res.body) {
        // SSE stream returned directly from POST /intent
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const event: AgentEvent = JSON.parse(line.slice(6));
                setEvents((prev) => [...prev, event]);
                if (
                  event.type === "run_finished" ||
                  event.type === "run_error"
                ) {
                  setIsStreaming(false);
                }
              } catch {
                // skip malformed events
              }
            }
          }
        }
        setIsStreaming(false);
      } else {
        // JSON response (non-streaming)
        const data = await res.json();
        setIsStreaming(false);
        return data;
      }

      return { session_id: "", stream_url: null, status: "completed" };
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        setIsStreaming(false);
        return { session_id: "", stream_url: null, status: "aborted" };
      }
      setError(err instanceof Error ? err.message : "Unknown error");
      setIsStreaming(false);
      throw err;
    }
  }, []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
  }, []);

  return { events, isStreaming, error, send, stop };
}
