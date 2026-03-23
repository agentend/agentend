const TOKEN_KEY = "agentend_token";
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function decodePayload(
  token: string
): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    // Handle URL-safe base64
    let b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    while (b64.length % 4) b64 += "=";
    const payload = JSON.parse(atob(b64));
    return payload;
  } catch {
    return null;
  }
}

export async function ensureToken(): Promise<string> {
  // Always fetch a fresh token from the backend on startup
  // This guarantees the signature matches the backend's current secret
  clearToken();

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(`${API_URL}/dev/token`, {
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (res.ok) {
      const data = await res.json();
      setToken(data.token);
      return data.token;
    }
  } catch (err) {
    console.warn("[agentend] Could not fetch dev token:", err);
  }

  return "";
}
