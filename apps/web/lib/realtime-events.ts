export type RealtimeEvent = {
  id: string;
  type: string;
  occurred_at: string;
  payload: Record<string, unknown>;
};

type EventEnvelope = {
  cursor: string | null;
  events: RealtimeEvent[];
  type?: "heartbeat";
};

type RealtimeOptions = {
  apiUrl: string;
  accessToken?: string;
  initialCursor?: string;
  onEvents: (events: RealtimeEvent[], cursor: string | null) => void;
  onStatus?: (status: "connecting" | "connected" | "disconnected" | "unauthorized") => void;
};

function websocketUrl(apiUrl: string, cursor?: string) {
  const url = new URL("/api/v1/ws/events", apiUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  if (cursor) url.searchParams.set("cursor", cursor);
  return url.toString();
}

function validEnvelope(value: unknown): value is EventEnvelope {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<EventEnvelope>;
  return (candidate.cursor === null || typeof candidate.cursor === "string") &&
    Array.isArray(candidate.events) &&
    candidate.events.every((event) => event && typeof event.id === "string" && typeof event.type === "string");
}

export function connectRealtimeEvents(options: RealtimeOptions) {
  let active = true;
  let socket: WebSocket | null = null;
  let cursor = options.initialCursor;
  let attempts = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const connect = () => {
    if (!active) return;
    options.onStatus?.("connecting");
    socket = new WebSocket(websocketUrl(options.apiUrl, cursor));
    socket.addEventListener("open", () => {
      attempts = 0;
      options.onStatus?.("connected");
      if (options.accessToken) {
        socket?.send(JSON.stringify({ type: "authenticate", access_token: options.accessToken }));
      }
    });
    socket.addEventListener("message", (message) => {
      try {
        const envelope: unknown = JSON.parse(String(message.data));
        if (!validEnvelope(envelope)) return;
        cursor = envelope.cursor ?? cursor;
        if (envelope.events.length) options.onEvents(envelope.events, envelope.cursor);
      } catch {
        // Malformed server messages are ignored without terminating the stream.
      }
    });
    socket.addEventListener("close", (event) => {
      socket = null;
      if (!active) return;
      if (event.code === 4401) {
        options.onStatus?.("unauthorized");
        active = false;
        return;
      }
      options.onStatus?.("disconnected");
      const delay = Math.min(30_000, 500 * 2 ** Math.min(attempts++, 6));
      reconnectTimer = setTimeout(connect, delay);
    });
  };

  connect();
  return () => {
    active = false;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    socket?.close(1000, "Client disconnected");
  };
}
