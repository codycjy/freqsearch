/**
 * Live Provider Tests
 *
 * Note: These tests require a WebSocket mock library like 'mock-socket' or 'jest-websocket-mock'
 * Install with: npm install --save-dev mock-socket @types/mock-socket
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { createLiveProvider } from "./liveProvider";
import type { WebSocketMessage, LiveEvent } from "./liveProvider";

/**
 * Mock WebSocket for testing
 */
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  url: string;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;

  private messageQueue: string[] = [];

  constructor(url: string) {
    this.url = url;
    // Simulate async connection
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event("open"));
      }
    }, 0);
  }

  send(data: string): void {
    this.messageQueue.push(data);
  }

  close(code?: number, reason?: string): void {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent("close", { code, reason }));
    }
  }

  // Test helpers
  simulateMessage(data: string | WebSocketMessage): void {
    if (this.onmessage && this.readyState === MockWebSocket.OPEN) {
      const message = typeof data === "string" ? data : JSON.stringify(data);
      this.onmessage(new MessageEvent("message", { data: message }));
    }
  }

  simulateError(): void {
    if (this.onerror) {
      this.onerror(new Event("error"));
    }
  }

  getSentMessages(): string[] {
    return [...this.messageQueue];
  }
}

describe("WebSocket Live Provider", () => {
  let originalWebSocket: typeof WebSocket;
  let mockWsInstance: MockWebSocket | null;

  beforeEach(() => {
    // Save original WebSocket
    originalWebSocket = global.WebSocket;

    // Replace with mock
    global.WebSocket = vi.fn((url: string) => {
      mockWsInstance = new MockWebSocket(url);
      return mockWsInstance as unknown as WebSocket;
    }) as unknown as typeof WebSocket;

    // Add static properties
    Object.defineProperty(global.WebSocket, "CONNECTING", { value: 0 });
    Object.defineProperty(global.WebSocket, "OPEN", { value: 1 });
    Object.defineProperty(global.WebSocket, "CLOSING", { value: 2 });
    Object.defineProperty(global.WebSocket, "CLOSED", { value: 3 });
  });

  afterEach(() => {
    // Restore original WebSocket
    global.WebSocket = originalWebSocket;
    mockWsInstance = null;
  });

  describe("Connection Management", () => {
    it("should connect on first subscription", async () => {
      const provider = createLiveProvider({
        wsUrl: "ws://localhost:8080/test",
        debug: false,
      });

      const callback = vi.fn();

      provider.subscribe({
        channel: "optimizations",
        types: ["*"],
        callback,
      });

      // Wait for connection
      await new Promise((resolve) => setTimeout(resolve, 10));

      expect(global.WebSocket).toHaveBeenCalledWith("ws://localhost:8080/test");
    });

    it("should disconnect when no subscriptions remain", async () => {
      const provider = createLiveProvider({
        wsUrl: "ws://localhost:8080/test",
        debug: false,
      });

      const callback = vi.fn();

      const unsubscribe = provider.subscribe({
        channel: "optimizations",
        types: ["*"],
        callback,
      });

      await new Promise((resolve) => setTimeout(resolve, 10));

      // Unsubscribe
      unsubscribe();

      await new Promise((resolve) => setTimeout(resolve, 10));

      expect(mockWsInstance?.readyState).toBe(MockWebSocket.CLOSED);
    });

    it("should maintain connection with multiple subscriptions", async () => {
      const provider = createLiveProvider({
        wsUrl: "ws://localhost:8080/test",
        debug: false,
      });

      const callback1 = vi.fn();
      const callback2 = vi.fn();

      const unsubscribe1 = provider.subscribe({
        channel: "optimizations",
        types: ["*"],
        callback: callback1,
      });

      provider.subscribe({
        channel: "backtests",
        types: ["*"],
        callback: callback2,
      });

      await new Promise((resolve) => setTimeout(resolve, 10));

      // Unsubscribe first
      unsubscribe1();

      await new Promise((resolve) => setTimeout(resolve, 10));

      // Connection should remain (second subscription still active)
      expect(mockWsInstance?.readyState).toBe(MockWebSocket.OPEN);
    });
  });

  describe("Event Routing", () => {
    it("should route optimization events to correct subscriptions", async () => {
      const provider = createLiveProvider({
        wsUrl: "ws://localhost:8080/test",
        debug: false,
      });

      const callback = vi.fn();

      provider.subscribe({
        channel: "optimizations",
        types: ["updated"],
        callback,
      });

      await new Promise((resolve) => setTimeout(resolve, 10));

      // Simulate optimization event
      const message: WebSocketMessage = {
        type: "optimization.iteration.completed",
        data: {
          optimization_run_id: "opt_123",
          iteration: 5,
          sharpe_ratio: 1.85,
        },
        timestamp: new Date().toISOString(),
      };

      mockWsInstance?.simulateMessage(message);

      expect(callback).toHaveBeenCalledTimes(1);
      expect(callback).toHaveBeenCalledWith(
        expect.objectContaining({
          channel: "optimizations",
          type: "updated",
          payload: expect.objectContaining({
            ids: ["opt_123"],
            optimization_run_id: "opt_123",
            iteration: 5,
            sharpe_ratio: 1.85,
          }),
        })
      );
    });

    it("should route backtest events to correct subscriptions", async () => {
      const provider = createLiveProvider({
        wsUrl: "ws://localhost:8080/test",
        debug: false,
      });

      const callback = vi.fn();

      provider.subscribe({
        channel: "backtests",
        types: ["created"],
        callback,
      });

      await new Promise((resolve) => setTimeout(resolve, 10));

      const message: WebSocketMessage = {
        type: "backtest.submitted",
        data: {
          backtest_id: "bt_456",
          strategy: "MACDStrategy",
        },
        timestamp: new Date().toISOString(),
      };

      mockWsInstance?.simulateMessage(message);

      expect(callback).toHaveBeenCalledTimes(1);
      expect(callback).toHaveBeenCalledWith(
        expect.objectContaining({
          channel: "backtests",
          type: "created",
        })
      );
    });

    it("should not call callback for non-matching event types", async () => {
      const provider = createLiveProvider({
        wsUrl: "ws://localhost:8080/test",
        debug: false,
      });

      const callback = vi.fn();

      provider.subscribe({
        channel: "optimizations",
        types: ["created"], // Only subscribe to created events
        callback,
      });

      await new Promise((resolve) => setTimeout(resolve, 10));

      const message: WebSocketMessage = {
        type: "optimization.iteration.completed", // This is an "updated" event
        data: {
          optimization_run_id: "opt_123",
        },
        timestamp: new Date().toISOString(),
      };

      mockWsInstance?.simulateMessage(message);

      expect(callback).not.toHaveBeenCalled();
    });

    it("should call callback for wildcard subscriptions", async () => {
      const provider = createLiveProvider({
        wsUrl: "ws://localhost:8080/test",
        debug: false,
      });

      const callback = vi.fn();

      provider.subscribe({
        channel: "optimizations",
        types: ["*"], // Subscribe to all events
        callback,
      });

      await new Promise((resolve) => setTimeout(resolve, 10));

      const message: WebSocketMessage = {
        type: "optimization.iteration.completed",
        data: {
          optimization_run_id: "opt_123",
        },
        timestamp: new Date().toISOString(),
      };

      mockWsInstance?.simulateMessage(message);

      expect(callback).toHaveBeenCalledTimes(1);
    });
  });

  describe("Keep-Alive", () => {
    it("should send ping messages", async () => {
      vi.useFakeTimers();

      const provider = createLiveProvider({
        wsUrl: "ws://localhost:8080/test",
        pingInterval: 1000,
        debug: false,
      });

      const callback = vi.fn();

      provider.subscribe({
        channel: "optimizations",
        types: ["*"],
        callback,
      });

      await vi.runAllTimersAsync();

      // Advance time past ping interval
      vi.advanceTimersByTime(1100);

      await vi.runAllTimersAsync();

      const sentMessages = mockWsInstance?.getSentMessages() || [];
      expect(sentMessages).toContain("ping");

      vi.useRealTimers();
    });

    it("should handle pong responses", async () => {
      vi.useFakeTimers();

      const provider = createLiveProvider({
        wsUrl: "ws://localhost:8080/test",
        pingInterval: 1000,
        pongTimeout: 500,
        debug: false,
      });

      const callback = vi.fn();

      provider.subscribe({
        channel: "optimizations",
        types: ["*"],
        callback,
      });

      await vi.runAllTimersAsync();

      // Advance time past ping interval
      vi.advanceTimersByTime(1100);

      await vi.runAllTimersAsync();

      // Simulate pong response
      mockWsInstance?.simulateMessage("pong");

      // Connection should remain open
      expect(mockWsInstance?.readyState).toBe(MockWebSocket.OPEN);

      vi.useRealTimers();
    });
  });

  describe("Error Handling", () => {
    it("should handle invalid JSON messages gracefully", async () => {
      const provider = createLiveProvider({
        wsUrl: "ws://localhost:8080/test",
        debug: false,
      });

      const callback = vi.fn();

      provider.subscribe({
        channel: "optimizations",
        types: ["*"],
        callback,
      });

      await new Promise((resolve) => setTimeout(resolve, 10));

      // Simulate invalid JSON
      mockWsInstance?.simulateMessage("invalid json{{{");

      // Callback should not be called
      expect(callback).not.toHaveBeenCalled();

      // Connection should remain open
      expect(mockWsInstance?.readyState).toBe(MockWebSocket.OPEN);
    });

    it("should handle unknown event types gracefully", async () => {
      const provider = createLiveProvider({
        wsUrl: "ws://localhost:8080/test",
        debug: false,
      });

      const callback = vi.fn();

      provider.subscribe({
        channel: "optimizations",
        types: ["*"],
        callback,
      });

      await new Promise((resolve) => setTimeout(resolve, 10));

      const message: WebSocketMessage = {
        type: "unknown.event.type" as any,
        data: {},
        timestamp: new Date().toISOString(),
      };

      mockWsInstance?.simulateMessage(message);

      // Callback should not be called for unknown events
      expect(callback).not.toHaveBeenCalled();
    });

    it("should handle callback errors gracefully", async () => {
      const provider = createLiveProvider({
        wsUrl: "ws://localhost:8080/test",
        debug: false,
      });

      const errorCallback = vi.fn(() => {
        throw new Error("Callback error");
      });

      const normalCallback = vi.fn();

      provider.subscribe({
        channel: "optimizations",
        types: ["*"],
        callback: errorCallback,
      });

      provider.subscribe({
        channel: "optimizations",
        types: ["*"],
        callback: normalCallback,
      });

      await new Promise((resolve) => setTimeout(resolve, 10));

      const message: WebSocketMessage = {
        type: "optimization.iteration.completed",
        data: {
          optimization_run_id: "opt_123",
        },
        timestamp: new Date().toISOString(),
      };

      mockWsInstance?.simulateMessage(message);

      // Both callbacks should be called despite error in first
      expect(errorCallback).toHaveBeenCalledTimes(1);
      expect(normalCallback).toHaveBeenCalledTimes(1);
    });
  });

  describe("Subscription Management", () => {
    it("should support multiple subscriptions to same resource", async () => {
      const provider = createLiveProvider({
        wsUrl: "ws://localhost:8080/test",
        debug: false,
      });

      const callback1 = vi.fn();
      const callback2 = vi.fn();

      provider.subscribe({
        channel: "optimizations",
        types: ["*"],
        callback: callback1,
      });

      provider.subscribe({
        channel: "optimizations",
        types: ["updated"],
        callback: callback2,
      });

      await new Promise((resolve) => setTimeout(resolve, 10));

      const message: WebSocketMessage = {
        type: "optimization.iteration.completed",
        data: {
          optimization_run_id: "opt_123",
        },
        timestamp: new Date().toISOString(),
      };

      mockWsInstance?.simulateMessage(message);

      // Both callbacks should be called
      expect(callback1).toHaveBeenCalledTimes(1);
      expect(callback2).toHaveBeenCalledTimes(1);
    });

    it("should unsubscribe correctly", async () => {
      const provider = createLiveProvider({
        wsUrl: "ws://localhost:8080/test",
        debug: false,
      });

      const callback = vi.fn();

      const unsubscribe = provider.subscribe({
        channel: "optimizations",
        types: ["*"],
        callback,
      });

      await new Promise((resolve) => setTimeout(resolve, 10));

      // Unsubscribe
      unsubscribe();

      const message: WebSocketMessage = {
        type: "optimization.iteration.completed",
        data: {
          optimization_run_id: "opt_123",
        },
        timestamp: new Date().toISOString(),
      };

      mockWsInstance?.simulateMessage(message);

      // Callback should not be called after unsubscribe
      expect(callback).not.toHaveBeenCalled();
    });
  });
});
