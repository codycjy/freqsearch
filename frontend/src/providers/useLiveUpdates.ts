import { useEffect, useCallback, useRef } from "react";
import { useInvalidate, useSubscription } from "@refinedev/core";
import type { BaseKey } from "@refinedev/core";

/**
 * Hook options for live updates
 */
interface UseLiveUpdatesOptions {
  /**
   * Resource name to subscribe to
   */
  resource: string;

  /**
   * Event types to listen for
   * @default ["*"]
   */
  types?: Array<"created" | "updated" | "deleted" | "*">;

  /**
   * Specific IDs to watch for updates
   */
  ids?: BaseKey[];

  /**
   * Custom callback when event is received
   */
  onEvent?: (event: {
    type: "created" | "updated" | "deleted";
    payload: Record<string, unknown>;
  }) => void;

  /**
   * Whether to automatically invalidate queries
   * @default true
   */
  autoInvalidate?: boolean;

  /**
   * Whether to enable the subscription
   * @default true
   */
  enabled?: boolean;

  /**
   * Debounce time for invalidations (ms)
   * @default 300
   */
  debounceMs?: number;
}

/**
 * Custom hook for subscribing to live updates with automatic query invalidation
 *
 * @param options - Configuration options
 *
 * @example
 * ```tsx
 * // Basic usage - auto-invalidate on any change
 * useLiveUpdates({
 *   resource: "optimizations"
 * });
 *
 * // Watch specific items
 * useLiveUpdates({
 *   resource: "backtests",
 *   ids: [backtestId],
 *   types: ["updated"]
 * });
 *
 * // Custom event handler
 * useLiveUpdates({
 *   resource: "agents",
 *   onEvent: (event) => {
 *     if (event.type === "updated") {
 *       notification.info({
 *         message: "Agent status changed",
 *         description: event.payload.status
 *       });
 *     }
 *   }
 * });
 * ```
 */
export const useLiveUpdates = (options: UseLiveUpdatesOptions): void => {
  const {
    resource,
    types = ["*"],
    ids,
    onEvent,
    autoInvalidate = true,
    enabled = true,
    debounceMs = 300,
  } = options;

  const invalidate = useInvalidate();
  const invalidationTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /**
   * Debounced invalidation to prevent excessive query updates
   */
  const debouncedInvalidate = useCallback(
    (invalidateResource: string, invalidateIds?: BaseKey[]) => {
      if (invalidationTimeoutRef.current) {
        clearTimeout(invalidationTimeoutRef.current);
      }

      invalidationTimeoutRef.current = setTimeout(() => {
        if (invalidateIds && invalidateIds.length > 0) {
          // Invalidate specific items
          invalidateIds.forEach((id) => {
            invalidate({
              resource: invalidateResource,
              invalidates: ["detail"],
              id,
            });
          });
        } else {
          // Invalidate list
          invalidate({
            resource: invalidateResource,
            invalidates: ["list"],
          });
        }
      }, debounceMs);
    },
    [invalidate, debounceMs]
  );

  /**
   * Clean up timeout on unmount
   */
  useEffect(() => {
    return () => {
      if (invalidationTimeoutRef.current) {
        clearTimeout(invalidationTimeoutRef.current);
      }
    };
  }, []);

  /**
   * Subscribe to live updates
   */
  useSubscription({
    channel: resource,
    types,
    enabled,
    onLiveEvent: (event) => {
      const eventType = event.type as "created" | "updated" | "deleted";
      const payload = event.payload as Record<string, unknown>;

      // Call custom event handler if provided
      if (onEvent) {
        onEvent({ type: eventType, payload });
      }

      // Auto-invalidate queries if enabled
      if (autoInvalidate) {
        const eventIds = event.payload?.ids as BaseKey[] | undefined;

        // If we're watching specific IDs, only invalidate if event matches
        if (ids && ids.length > 0) {
          if (eventIds && eventIds.some((id) => ids.includes(id))) {
            debouncedInvalidate(resource, ids);
          }
        } else {
          // Otherwise invalidate based on event IDs or entire list
          debouncedInvalidate(resource, eventIds);
        }
      }
    },
  });
};

/**
 * Hook for subscribing to optimization updates
 *
 * @example
 * ```tsx
 * useOptimizationUpdates({
 *   ids: [optimizationId],
 *   onIterationComplete: (data) => {
 *     console.log(`Iteration ${data.iteration} completed`);
 *   }
 * });
 * ```
 */
export const useOptimizationUpdates = (options: {
  ids?: BaseKey[];
  enabled?: boolean;
  onIterationStart?: (data: Record<string, unknown>) => void;
  onIterationComplete?: (data: Record<string, unknown>) => void;
  onNewBest?: (data: Record<string, unknown>) => void;
  onComplete?: (data: Record<string, unknown>) => void;
  onFailed?: (data: Record<string, unknown>) => void;
}): void => {
  const {
    ids,
    enabled = true,
    onIterationStart,
    onIterationComplete,
    onNewBest,
    onComplete,
    onFailed,
  } = options;

  useLiveUpdates({
    resource: "optimizations",
    ids,
    enabled,
    onEvent: (event) => {
      const eventType = (event.payload as Record<string, unknown>).type as string;

      switch (eventType) {
        case "optimization.iteration.started":
          onIterationStart?.(event.payload);
          break;
        case "optimization.iteration.completed":
          onIterationComplete?.(event.payload);
          break;
        case "optimization.new_best":
          onNewBest?.(event.payload);
          break;
        case "optimization.completed":
          onComplete?.(event.payload);
          break;
        case "optimization.failed":
          onFailed?.(event.payload);
          break;
      }
    },
  });
};

/**
 * Hook for subscribing to backtest updates
 *
 * @example
 * ```tsx
 * useBacktestUpdates({
 *   ids: [backtestId],
 *   onComplete: (data) => {
 *     notification.success({
 *       message: "Backtest completed",
 *       description: `Sharpe Ratio: ${data.sharpe_ratio}`
 *     });
 *   }
 * });
 * ```
 */
export const useBacktestUpdates = (options: {
  ids?: BaseKey[];
  enabled?: boolean;
  onSubmitted?: (data: Record<string, unknown>) => void;
  onComplete?: (data: Record<string, unknown>) => void;
}): void => {
  const { ids, enabled = true, onSubmitted, onComplete } = options;

  useLiveUpdates({
    resource: "backtests",
    ids,
    enabled,
    onEvent: (event) => {
      const eventType = (event.payload as Record<string, unknown>).type as string;

      switch (eventType) {
        case "backtest.submitted":
          onSubmitted?.(event.payload);
          break;
        case "backtest.completed":
          onComplete?.(event.payload);
          break;
      }
    },
  });
};

/**
 * Hook for subscribing to agent status updates
 *
 * @example
 * ```tsx
 * useAgentUpdates({
 *   onStatusChange: (data) => {
 *     console.log(`Agent ${data.agent_id} is now ${data.status}`);
 *   }
 * });
 * ```
 */
export const useAgentUpdates = (options: {
  ids?: BaseKey[];
  enabled?: boolean;
  onStatusChange?: (data: Record<string, unknown>) => void;
}): void => {
  const { ids, enabled = true, onStatusChange } = options;

  useLiveUpdates({
    resource: "agents",
    ids,
    enabled,
    onEvent: (event) => {
      const eventType = (event.payload as Record<string, unknown>).type as string;

      if (eventType === "agent.status.changed") {
        onStatusChange?.(event.payload);
      }
    },
  });
};
