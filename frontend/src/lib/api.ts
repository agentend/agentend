const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface IntentRequest {
  capability: string;
  input: string;
  stream?: boolean;
}

export interface IntentResponse {
  session_id: string;
  stream_url: string | null;
  status: string;
}

export async function sendIntent(
  params: IntentRequest
): Promise<IntentResponse> {
  const { ensureToken } = await import("./auth");
  const token = await ensureToken();
  const res = await fetch(`${API_URL}/intent`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text);
  }
  return res.json();
}

export async function checkHealth(): Promise<{
  status: string;
  version: string;
}> {
  const res = await fetch(`${API_URL}/health`);
  return res.json();
}

export async function checkReady(): Promise<{
  ready: boolean;
  checks: Record<string, boolean>;
}> {
  const res = await fetch(`${API_URL}/ready`);
  return res.json();
}

export function createEventSource(streamUrl: string): EventSource {
  return new EventSource(`${API_URL}${streamUrl}`);
}
