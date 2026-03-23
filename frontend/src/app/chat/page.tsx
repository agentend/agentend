"use client";

import {
  useState,
  useRef,
  useEffect,
  useCallback,
  useMemo,
  type FormEvent,
} from "react";
import { useSession } from "@/providers/session-provider";
import { SessionList } from "@/components/session-list";
import { ContextPanel } from "@/components/context-panel";
import type { AgentEvent } from "@/lib/event-types";
import type {
  TextMessageContentEvent,
  ToolCallStartEvent,
  ToolCallArgsEvent,
  ToolCallEndEvent,
  ThinkingStepEvent,
  StateSnapshotEvent,
  RunErrorEvent,
} from "@/lib/event-types";
import {
  Send,
  Square,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  Bot,
  User,
  Wrench,
} from "lucide-react";

const CAPABILITIES = [
  "fleet.status",
  "system.health",
  "memory.inspect",
  "metrics.usage",
  "sessions.list",
  "workflow.status",
] as const;

// ---------------------------------------------------------------------------
// Sub-components for rendering different event types
// ---------------------------------------------------------------------------

function TextBubble({ content }: { content: string }) {
  return (
    <div className="flex gap-2.5 items-start">
      <span className="shrink-0 mt-0.5 w-6 h-6 rounded-full bg-surface border border-border flex items-center justify-center">
        <Bot size={14} className="text-text-secondary" />
      </span>
      <div className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed max-w-[600px]">
        {content}
      </div>
    </div>
  );
}

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex gap-2.5 items-start justify-end">
      <div className="text-sm text-text-primary bg-surface border border-border rounded-lg px-3 py-2 max-w-[600px] whitespace-pre-wrap">
        {content}
      </div>
      <span className="shrink-0 mt-0.5 w-6 h-6 rounded-full bg-border flex items-center justify-center">
        <User size={14} className="text-text-secondary" />
      </span>
    </div>
  );
}

function ToolCallCard({
  name,
  args,
  done,
}: {
  name: string;
  args: string;
  done: boolean;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="ml-8 border border-border rounded-md bg-surface text-xs max-w-[520px]">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-hover transition-colors"
      >
        <Wrench size={12} className="text-text-muted shrink-0" />
        <span className="font-mono text-text-primary">{name}</span>
        <span
          className={`ml-auto inline-block w-2 h-2 rounded-full shrink-0 ${
            done ? "bg-success" : "bg-warning animate-pulse"
          }`}
        />
        {open ? (
          <ChevronDown size={12} className="text-text-muted" />
        ) : (
          <ChevronRight size={12} className="text-text-muted" />
        )}
      </button>
      {open && args && (
        <pre className="px-3 py-2 border-t border-border text-text-secondary overflow-x-auto whitespace-pre-wrap break-all">
          {args}
        </pre>
      )}
    </div>
  );
}

function ThinkingStepBubble({ content }: { content: string }) {
  return (
    <div className="ml-8 text-xs italic text-text-muted leading-relaxed">
      {content}
    </div>
  );
}

function StateViewer({ state }: { state: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="ml-8 border border-border rounded-md bg-surface text-xs max-w-[520px]">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-hover transition-colors"
      >
        <span className="text-text-muted">State Snapshot</span>
        {open ? (
          <ChevronDown size={12} className="text-text-muted ml-auto" />
        ) : (
          <ChevronRight size={12} className="text-text-muted ml-auto" />
        )}
      </button>
      {open && (
        <pre className="px-3 py-2 border-t border-border text-text-secondary overflow-x-auto whitespace-pre-wrap break-all max-h-64 overflow-y-auto">
          {JSON.stringify(state, null, 2)}
        </pre>
      )}
    </div>
  );
}

function ErrorAlert({ message }: { message: string }) {
  return (
    <div className="ml-8 flex items-center gap-2 px-3 py-2 border border-error/30 bg-error/10 rounded-md text-sm text-error max-w-[520px]">
      <AlertTriangle size={14} className="shrink-0" />
      {message}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Aggregate text deltas and tool call data from raw events
// ---------------------------------------------------------------------------

interface RenderedItem {
  key: string;
  type:
    | "user"
    | "text"
    | "tool_call"
    | "thinking"
    | "state"
    | "error";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any;
}

function buildRenderItems(
  events: AgentEvent[],
  userInputs: { text: string; capability: string }[]
): RenderedItem[] {
  const items: RenderedItem[] = [];
  let currentText = "";
  let currentMsgId: string | null = null;
  const toolCalls = new Map<
    string,
    { name: string; args: string; done: boolean }
  >();
  let userIdx = 0;

  // Insert user message at the start
  if (userInputs.length > 0) {
    items.push({
      key: `user-${userIdx}`,
      type: "user",
      data: { text: userInputs[userIdx]?.text ?? "" },
    });
  }

  for (const e of events) {
    switch (e.type) {
      case "text_message_start": {
        currentMsgId = e.run_id ?? `msg-${items.length}`;
        currentText = "";
        break;
      }
      case "text_message_content": {
        const ev = e as TextMessageContentEvent;
        currentText += ev.content;
        break;
      }
      case "text_message_end": {
        if (currentText) {
          items.push({
            key: `text-${currentMsgId ?? items.length}`,
            type: "text",
            data: { content: currentText },
          });
        }
        currentText = "";
        currentMsgId = null;
        break;
      }
      case "tool_call_start": {
        const ev = e as ToolCallStartEvent;
        toolCalls.set(ev.tool_use_id, {
          name: ev.tool_name,
          args: "",
          done: false,
        });
        items.push({
          key: `tool-${ev.tool_use_id}`,
          type: "tool_call",
          data: toolCalls.get(ev.tool_use_id)!,
        });
        break;
      }
      case "tool_call_args": {
        const ev = e as ToolCallArgsEvent;
        const tc = toolCalls.get(ev.tool_use_id);
        if (tc) tc.args += ev.args;
        break;
      }
      case "tool_call_end": {
        const ev = e as ToolCallEndEvent;
        const tc = toolCalls.get(ev.tool_use_id);
        if (tc) tc.done = true;
        break;
      }
      case "thinking_step": {
        const ev = e as ThinkingStepEvent;
        items.push({
          key: `think-${items.length}`,
          type: "thinking",
          data: { content: ev.content },
        });
        break;
      }
      case "state_snapshot": {
        const ev = e as StateSnapshotEvent;
        items.push({
          key: `state-${items.length}`,
          type: "state",
          data: { snapshot: ev.state },
        });
        break;
      }
      case "run_error": {
        const ev = e as RunErrorEvent;
        items.push({
          key: `err-${items.length}`,
          type: "error",
          data: { message: ev.message },
        });
        break;
      }
    }
  }

  // If there's still buffered text (stream didn't send text_message_end yet)
  if (currentText) {
    items.push({
      key: `text-streaming-${currentMsgId ?? "last"}`,
      type: "text",
      data: { content: currentText },
    });
  }

  return items;
}

// ---------------------------------------------------------------------------
// Main chat page
// ---------------------------------------------------------------------------

export default function ChatPage() {
  const {
    events,
    isStreaming,
    error,
    send,
    stop,
    addSession,
  } = useSession();

  const [input, setInput] = useState("");
  const [capability, setCapability] = useState<string>(CAPABILITIES[0]);
  const [userInputs, setUserInputs] = useState<
    { text: string; capability: string }[]
  >([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new events
  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [events]);

  const handleSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      const text = input.trim();
      if (!text || isStreaming) return;

      setUserInputs((prev) => [...prev, { text, capability }]);
      setInput("");

      try {
        const res = await send({
          capability,
          input: text,
          stream: true,
        });
        addSession(res.session_id, capability, text);
      } catch {
        // error is available via context
      }
    },
    [input, capability, isStreaming, send, addSession]
  );

  const renderItems = useMemo(
    () => buildRenderItems(events, userInputs),
    [events, userInputs]
  );

  const isEmpty = renderItems.length === 0 && !isStreaming && !error;

  return (
    <div className="flex h-full">
      <SessionList />

      {/* Chat thread */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Messages area */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4">
          {isEmpty ? (
            <div className="flex flex-col items-center justify-center h-full text-text-muted">
              <Bot size={32} className="mb-3 opacity-40" />
              <p className="text-sm">Send a message to get started</p>
              <p className="text-xs mt-1">
                Choose a capability and describe your intent
              </p>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-4">
              {renderItems.map((item) => {
                switch (item.type) {
                  case "user":
                    return (
                      <UserBubble key={item.key} content={item.data.text} />
                    );
                  case "text":
                    return (
                      <TextBubble
                        key={item.key}
                        content={item.data.content}
                      />
                    );
                  case "tool_call":
                    return (
                      <ToolCallCard
                        key={item.key}
                        name={item.data.name}
                        args={item.data.args}
                        done={item.data.done}
                      />
                    );
                  case "thinking":
                    return (
                      <ThinkingStepBubble
                        key={item.key}
                        content={item.data.content}
                      />
                    );
                  case "state":
                    return (
                      <StateViewer
                        key={item.key}
                        state={item.data.snapshot}
                      />
                    );
                  case "error":
                    return (
                      <ErrorAlert
                        key={item.key}
                        message={item.data.message}
                      />
                    );
                  default:
                    return null;
                }
              })}

              {isStreaming && (
                <div className="ml-8 flex items-center gap-1.5 text-text-muted text-xs">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                  Streaming...
                </div>
              )}
            </div>
          )}

          {error && !events.some((e) => e.type === "run_error") && (
            <div className="max-w-3xl mx-auto mt-4">
              <ErrorAlert message={error} />
            </div>
          )}
        </div>

        {/* Input bar */}
        <form
          onSubmit={handleSubmit}
          className="shrink-0 border-t border-border bg-sidebar px-4 py-3"
        >
          <div className="max-w-3xl mx-auto flex items-center gap-2">
            <select
              value={capability}
              onChange={(e) => setCapability(e.target.value)}
              className="bg-surface border border-border rounded-md px-2 py-1.5 text-xs text-text-primary focus:outline-none focus:border-text-muted"
            >
              {CAPABILITIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>

            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Describe your intent..."
              disabled={isStreaming}
              className="flex-1 bg-surface border border-border rounded-md px-3 py-1.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-text-muted disabled:opacity-50"
            />

            {isStreaming ? (
              <button
                type="button"
                onClick={stop}
                className="shrink-0 w-8 h-8 flex items-center justify-center rounded-md bg-error/20 text-error hover:bg-error/30 transition-colors"
                title="Stop"
              >
                <Square size={14} />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="shrink-0 w-8 h-8 flex items-center justify-center rounded-md bg-surface border border-border text-text-secondary hover:text-text-primary hover:bg-hover transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                title="Send"
              >
                <Send size={14} />
              </button>
            )}
          </div>
        </form>
      </div>

      <ContextPanel events={events} />
    </div>
  );
}
