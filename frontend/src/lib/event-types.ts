export type EventType =
  | "run_started"
  | "text_message_start"
  | "text_message_content"
  | "text_message_end"
  | "tool_call_start"
  | "tool_call_args"
  | "tool_call_end"
  | "state_snapshot"
  | "state_delta"
  | "thinking_step"
  | "interrupt"
  | "run_finished"
  | "run_error";

export interface AgentEvent {
  type: EventType;
  timestamp: string;
  run_id?: string;
}

export interface RunStartedEvent extends AgentEvent {
  type: "run_started";
  session_id?: string;
  input?: string;
}

export interface TextMessageStartEvent extends AgentEvent {
  type: "text_message_start";
  content_type?: string;
}

export interface TextMessageContentEvent extends AgentEvent {
  type: "text_message_content";
  content: string;
  delta: boolean;
}

export interface TextMessageEndEvent extends AgentEvent {
  type: "text_message_end";
  stop_reason?: string;
}

export interface ToolCallStartEvent extends AgentEvent {
  type: "tool_call_start";
  tool_name: string;
  tool_use_id: string;
}

export interface ToolCallArgsEvent extends AgentEvent {
  type: "tool_call_args";
  tool_use_id: string;
  args: string;
  delta: boolean;
}

export interface ToolCallEndEvent extends AgentEvent {
  type: "tool_call_end";
  tool_name: string;
  tool_use_id: string;
  result?: unknown;
  is_error?: boolean;
}

export interface StateSnapshotEvent extends AgentEvent {
  type: "state_snapshot";
  state: Record<string, unknown>;
  memory: Record<string, unknown>;
}

export interface StateDeltaEvent extends AgentEvent {
  type: "state_delta";
  path: string;
  value?: unknown;
  operation: string;
}

export interface ThinkingStepEvent extends AgentEvent {
  type: "thinking_step";
  content: string;
  thinking_type?: string;
}

export interface InterruptEvent extends AgentEvent {
  type: "interrupt";
  reason: string;
  action_required: string;
  options?: string[];
  context?: Record<string, unknown>;
}

export interface RunFinishedEvent extends AgentEvent {
  type: "run_finished";
  result?: unknown;
  stop_reason?: string;
  messages_sent?: number;
  tools_used?: string[];
}

export interface RunErrorEvent extends AgentEvent {
  type: "run_error";
  error_type: string;
  message: string;
  traceback?: string;
  recoverable: boolean;
}

export type TypedAgentEvent =
  | RunStartedEvent
  | TextMessageStartEvent
  | TextMessageContentEvent
  | TextMessageEndEvent
  | ToolCallStartEvent
  | ToolCallArgsEvent
  | ToolCallEndEvent
  | StateSnapshotEvent
  | StateDeltaEvent
  | ThinkingStepEvent
  | InterruptEvent
  | RunFinishedEvent
  | RunErrorEvent;
