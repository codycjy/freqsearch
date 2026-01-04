import type { LiveProvider, LiveEvent } from "@refinedev/core";

/**
 * WebSocket event types from backend
 */
export type WebSocketEventType =
  | "optimization.iteration.started"
  | "optimization.iteration.completed"
  | "optimization.new_best"
  | "optimization.completed"
  | "optimization.failed"
  | "backtest.submitted"
  | "backtest.completed"
  | "agent.status.changed";

/**
 * WebSocket message structure from backend
 */
export interface WebSocketMessage<T = unknown> {
  type: WebSocketEventType;
  data: T;
  timestamp: string;
}

/**
 * Optimization event data structures
 */
export interface OptimizationIterationData {
  optimization_run_id: string;
  iteration: number;
  sharpe_ratio: number;
  parameters: Record<string, unknown>;
}

export interface OptimizationCompletedData {
  optimization_run_id: string;
  total_iterations: number;
  best_sharpe_ratio: number;
  best_parameters: Record<string, unknown>;
  duration_seconds: number;
}

export interface OptimizationFailedData {
  optimization_run_id: string;
  error: string;
  iteration?: number;
}

/**
 * Backtest event data structures
 */
export interface BacktestSubmittedData {
  backtest_id: string;
  strategy: string;
  parameters: Record<string, unknown>;
}

export interface BacktestCompletedData {
  backtest_id: string;
  sharpe_ratio: number;
  total_return: number;
  max_drawdown: number;
  trades_count: number;
}

/**
 * Agent event data structures
 */
export interface AgentStatusChangedData {
  agent_id: string;
  status: "idle" | "running" | "stopped" | "error";
  message?: string;
}

/**
 * Subscription callback function type
 */
type SubscriptionCallback = (event: LiveEvent) => void;

/**
 * Subscription entry
 */
interface Subscription {
  channel: string;
  types: string[];
  callback: SubscriptionCallback;
  params?: Record<string, unknown>;
}

/**
 * WebSocket connection states
 */
enum ConnectionState {
  DISCONNECTED = "DISCONNECTED",
  CONNECTING = "CONNECTING",
  CONNECTED = "CONNECTED",
  RECONNECTING = "RECONNECTING",
}

/**
 * Configuration options for the live provider
 */
interface LiveProviderConfig {
  wsUrl?: string;
  reconnectInterval?: number;
  maxReconnectInterval?: number;
  reconnectDecay?: number;
  pingInterval?: number;
  pongTimeout?: number;
  debug?: boolean;
}

/**
 * Default configuration values
 */
// 自动检测 WebSocket URL：根据当前页面协议和域名构建
const getDefaultWsUrl = (): string => {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }
  // 自动检测：http->ws, https->wss
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/api/v1/ws/events`;
};

const DEFAULT_CONFIG: Required<LiveProviderConfig> = {
  wsUrl: getDefaultWsUrl(),
  reconnectInterval: 1000,
  maxReconnectInterval: 30000,
  reconnectDecay: 1.5,
  pingInterval: 30000,
  pongTimeout: 5000,
  debug: import.meta.env.DEV,
};

/**
 * Maps WebSocket event types to Refine resources and event types
 */
const EVENT_MAPPING: Record<
  string,
  { resource: string; type: "created" | "updated" | "deleted" }
> = {
  "optimization.iteration.started": { resource: "optimizations", type: "updated" },
  "optimization.iteration.completed": { resource: "optimizations", type: "updated" },
  "optimization.new_best": { resource: "optimizations", type: "updated" },
  "optimization.completed": { resource: "optimizations", type: "updated" },
  "optimization.failed": { resource: "optimizations", type: "updated" },
  "backtest.submitted": { resource: "backtests", type: "created" },
  "backtest.completed": { resource: "backtests", type: "updated" },
  "agent.status.changed": { resource: "agents", type: "updated" },
};

/**
 * WebSocket Live Provider for Refine
 *
 * Provides real-time updates via WebSocket connection with:
 * - Auto-reconnection with exponential backoff
 * - Keep-alive ping/pong mechanism
 * - Event routing to appropriate Refine resources
 * - Subscription management
 *
 * @example
 * ```ts
 * const liveProvider = createLiveProvider({
 *   wsUrl: "ws://localhost:8080/api/v1/ws/events",
 *   debug: true
 * });
 * ```
 */
class WebSocketLiveProvider implements LiveProvider {
  private ws: WebSocket | null = null;
  private config: Required<LiveProviderConfig>;
  private subscriptions: Map<string, Subscription> = new Map();
  private state: ConnectionState = ConnectionState.DISCONNECTED;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setTimeout> | null = null;
  private pongTimer: ReturnType<typeof setTimeout> | null = null;
  private messageQueue: Array<unknown> = [];

  constructor(config: LiveProviderConfig = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.log("LiveProvider initialized with config:", this.config);
  }

  /**
   * Subscribe to real-time events
   */
  subscribe = (params: {
    channel: string;
    types: string[];
    callback: SubscriptionCallback;
    params?: Record<string, unknown>;
  }): (() => void) => {
    const { channel, types, callback, params: subscriptionParams } = params;
    const subscriptionKey = this.getSubscriptionKey(channel, types);

    this.log(`Subscribing to channel: ${channel}, types:`, types);

    // Store subscription
    this.subscriptions.set(subscriptionKey, {
      channel,
      types,
      callback,
      params: subscriptionParams,
    });

    // Connect WebSocket if not already connected
    if (this.state === ConnectionState.DISCONNECTED) {
      this.connect();
    }

    // Return unsubscribe function
    return () => {
      this.unsubscribe({ channel, types });
    };
  };

  /**
   * Unsubscribe from real-time events
   */
  unsubscribe = (params: {
    channel: string;
    types: string[];
  }): void => {
    const { channel, types } = params;
    const subscriptionKey = this.getSubscriptionKey(channel, types);

    this.log(`Unsubscribing from channel: ${channel}, types:`, types);

    this.subscriptions.delete(subscriptionKey);

    // Disconnect if no more subscriptions
    if (this.subscriptions.size === 0) {
      this.disconnect();
    }
  };

  /**
   * Publish events (optional - not implemented for this use case)
   */
  publish?: (event: LiveEvent) => void;

  /**
   * Connect to WebSocket server
   */
  private connect = (): void => {
    if (this.state === ConnectionState.CONNECTING || this.state === ConnectionState.CONNECTED) {
      return;
    }

    this.state = ConnectionState.CONNECTING;
    this.log(`Connecting to WebSocket: ${this.config.wsUrl}`);

    try {
      this.ws = new WebSocket(this.config.wsUrl);

      this.ws.onopen = this.handleOpen;
      this.ws.onmessage = this.handleMessage;
      this.ws.onerror = this.handleError;
      this.ws.onclose = this.handleClose;
    } catch (error) {
      this.logError("Failed to create WebSocket connection:", error);
      this.scheduleReconnect();
    }
  };

  /**
   * Disconnect from WebSocket server
   */
  private disconnect = (): void => {
    this.log("Disconnecting from WebSocket");

    this.clearTimers();

    if (this.ws) {
      // Remove event listeners to prevent reconnection
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;
      this.ws.onopen = null;

      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.close(1000, "Normal closure");
      }

      this.ws = null;
    }

    this.state = ConnectionState.DISCONNECTED;
    this.reconnectAttempts = 0;
  };

  /**
   * Handle WebSocket connection open
   */
  private handleOpen = (): void => {
    this.log("WebSocket connected");

    this.state = ConnectionState.CONNECTED;
    this.reconnectAttempts = 0;

    // Start ping/pong keep-alive
    this.startPingPong();

    // Send any queued messages
    this.flushMessageQueue();
  };

  /**
   * Handle incoming WebSocket messages
   */
  private handleMessage = (event: MessageEvent): void => {
    try {
      // Handle pong responses
      if (event.data === "pong") {
        this.handlePong();
        return;
      }

      // Handle multiple JSON messages that might be concatenated (split by newlines)
      const rawData = event.data as string;
      const lines = rawData.split('\n').filter((line: string) => line.trim());

      for (const line of lines) {
        try {
          const message = JSON.parse(line) as WebSocketMessage;
          this.log("Received message:", message);
          // Route message to appropriate subscriptions
          this.routeMessage(message);
        } catch (parseError) {
          this.logError("Failed to parse WebSocket message line:", parseError, line);
        }
      }
    } catch (error) {
      this.logError("Failed to handle WebSocket message:", error);
    }
  };

  /**
   * Handle WebSocket errors
   */
  private handleError = (event: Event): void => {
    this.logError("WebSocket error:", event);
  };

  /**
   * Handle WebSocket connection close
   */
  private handleClose = (event: CloseEvent): void => {
    this.log(`WebSocket closed: ${event.code} - ${event.reason}`);

    this.clearTimers();
    this.state = ConnectionState.DISCONNECTED;

    // Attempt reconnection if we have active subscriptions
    if (this.subscriptions.size > 0) {
      this.scheduleReconnect();
    }
  };

  /**
   * Route WebSocket messages to appropriate subscriptions
   */
  private routeMessage = (message: WebSocketMessage): void => {
    const mapping = EVENT_MAPPING[message.type];

    if (!mapping) {
      this.log(`Unknown event type: ${message.type}`);
      return;
    }

    const { resource, type } = mapping;

    // Find matching subscriptions
    this.subscriptions.forEach((subscription) => {
      const { channel, types, callback } = subscription;

      // Check if subscription matches the resource and event type
      if (
        channel === resource &&
        (types.includes("*") || types.includes(type))
      ) {
        const liveEvent: LiveEvent = {
          channel: resource,
          type,
          payload: {
            ids: this.extractIds(message),
            ...(typeof message.data === 'object' && message.data !== null ? message.data : {}),
          },
          date: new Date(message.timestamp),
        };

        this.log(`Dispatching event to subscription:`, liveEvent);

        try {
          callback(liveEvent);
        } catch (error) {
          this.logError("Error in subscription callback:", error);
        }
      }
    });
  };

  /**
   * Extract IDs from message data for Refine event
   */
  private extractIds = (message: WebSocketMessage): string[] | undefined => {
    const data = message.data as Record<string, unknown>;

    // Extract relevant ID based on event type
    if (message.type.startsWith("optimization.")) {
      const id = data.optimization_run_id as string;
      return id ? [id] : undefined;
    } else if (message.type.startsWith("backtest.")) {
      const id = data.backtest_id as string;
      return id ? [id] : undefined;
    } else if (message.type.startsWith("agent.")) {
      const id = data.agent_id as string;
      return id ? [id] : undefined;
    }

    return undefined;
  };

  /**
   * Schedule reconnection with exponential backoff
   */
  private scheduleReconnect = (): void => {
    if (this.reconnectTimer) {
      return;
    }

    this.state = ConnectionState.RECONNECTING;

    const delay = Math.min(
      this.config.reconnectInterval * Math.pow(this.config.reconnectDecay, this.reconnectAttempts),
      this.config.maxReconnectInterval
    );

    this.log(`Scheduling reconnect in ${delay}ms (attempt ${this.reconnectAttempts + 1})`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  };

  /**
   * Start ping/pong keep-alive mechanism
   */
  private startPingPong = (): void => {
    this.clearTimers();

    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.log("Sending ping");
        this.ws.send("ping");

        // Set pong timeout
        this.pongTimer = setTimeout(() => {
          this.logError("Pong timeout - closing connection");
          this.ws?.close(1000, "Pong timeout");
        }, this.config.pongTimeout);
      }
    }, this.config.pingInterval);
  };

  /**
   * Handle pong response
   */
  private handlePong = (): void => {
    this.log("Received pong");

    if (this.pongTimer) {
      clearTimeout(this.pongTimer);
      this.pongTimer = null;
    }
  };

  /**
   * Clear all timers
   */
  private clearTimers = (): void => {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }

    if (this.pongTimer) {
      clearTimeout(this.pongTimer);
      this.pongTimer = null;
    }
  };

  /**
   * Flush message queue
   */
  private flushMessageQueue = (): void => {
    if (this.messageQueue.length === 0) {
      return;
    }

    this.log(`Flushing ${this.messageQueue.length} queued messages`);

    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify(message));
      }
    }
  };

  /**
   * Generate subscription key
   */
  private getSubscriptionKey = (
    channel: string,
    types?: string[]
  ): string => {
    const sortedTypes = types && types.length > 0 ? types.sort().join(",") : "*";
    return `${channel}:${sortedTypes}`;
  };

  /**
   * Log debug message
   */
  private log = (message: string, ...args: unknown[]): void => {
    if (this.config.debug) {
      console.log(`[LiveProvider] ${message}`, ...args);
    }
  };

  /**
   * Log error message
   */
  private logError = (message: string, ...args: unknown[]): void => {
    console.error(`[LiveProvider] ${message}`, ...args);
  };

  /**
   * Get current connection state (for debugging)
   */
  public getState = (): ConnectionState => {
    return this.state;
  };

  /**
   * Get active subscriptions count (for debugging)
   */
  public getSubscriptionsCount = (): number => {
    return this.subscriptions.size;
  };
}

/**
 * Factory function to create a live provider instance
 *
 * @param config - Configuration options
 * @returns LiveProvider instance
 *
 * @example
 * ```ts
 * const liveProvider = createLiveProvider({
 *   wsUrl: "ws://localhost:8080/api/v1/ws/events",
 *   reconnectInterval: 2000,
 *   debug: true
 * });
 * ```
 */
export const createLiveProvider = (config?: LiveProviderConfig): LiveProvider => {
  return new WebSocketLiveProvider(config);
};

/**
 * Default live provider instance using environment variables
 */
export const liveProvider = createLiveProvider();
