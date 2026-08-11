import { afterEach, describe, expect, it, vi } from "vitest";
import { connectRealtimeEvents } from "./realtime-events";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  listeners = new Map<string, Array<(event: any) => void>>();
  sent: string[] = [];
  constructor(public url: string) { FakeWebSocket.instances.push(this); }
  addEventListener(type: string, listener: (event: any) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }
  emit(type: string, event: any = {}) { this.listeners.get(type)?.forEach((listener) => listener(event)); }
  send(value: string) { this.sent.push(value); }
  close(code = 1000) { this.emit("close", { code }); }
}

afterEach(() => {
  FakeWebSocket.instances = [];
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("realtime event client", () => {
  it("authenticates after connection and accepts only valid envelopes", () => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    const received = vi.fn();
    const disconnect = connectRealtimeEvents({ apiUrl: "https://api.example.com", accessToken: "secret", onEvents: received });
    const socket = FakeWebSocket.instances[0];
    expect(socket.url).toBe("wss://api.example.com/api/v1/ws/events");
    socket.emit("open");
    expect(JSON.parse(socket.sent[0])).toEqual({ type: "authenticate", access_token: "secret" });
    socket.emit("message", { data: JSON.stringify({ cursor: "2-0", events: [{ id: "one", type: "trip.started", occurred_at: "now", payload: {} }] }) });
    socket.emit("message", { data: "not-json" });
    expect(received).toHaveBeenCalledTimes(1);
    disconnect();
  });

  it("reconnects with the last cursor and stops on unauthorized closure", () => {
    vi.useFakeTimers();
    vi.stubGlobal("WebSocket", FakeWebSocket);
    const status = vi.fn();
    connectRealtimeEvents({ apiUrl: "http://localhost:8000", onEvents: () => undefined, onStatus: status });
    FakeWebSocket.instances[0].emit("message", { data: JSON.stringify({ cursor: "9-0", events: [] }) });
    FakeWebSocket.instances[0].emit("close", { code: 1006 });
    vi.advanceTimersByTime(500);
    expect(FakeWebSocket.instances[1].url).toContain("cursor=9-0");
    FakeWebSocket.instances[1].emit("close", { code: 4401 });
    expect(status).toHaveBeenLastCalledWith("unauthorized");
  });
});
