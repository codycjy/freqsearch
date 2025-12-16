/**
 * Refine DataProvider for FreqSearch REST API
 *
 * Implements the Refine data provider interface to communicate with the FreqSearch backend.
 * Handles strategies, backtests, and optimization runs with full type safety.
 *
 * API Endpoints:
 * - Strategies: GET/POST/DELETE /api/v1/strategies
 * - Backtests: GET/POST/DELETE /api/v1/backtests
 * - Optimizations: GET/POST /api/v1/optimizations, POST /api/v1/optimizations/:id/control
 *
 * @see https://refine.dev/docs/core/providers/data-provider/
 */

import type { DataProvider } from "@refinedev/core";
import { axiosInstance } from "@api/axios";
import type {
  BacktestJob,
  BacktestResult,
  OptimizationRun,
  OptimizationIteration,
  ControlOptimizationPayload,
} from "./types";

/**
 * Type guard to check if a resource is a known resource type
 */
type ResourceType = "strategies" | "backtests" | "optimizations" | "backtest-results";

const isValidResource = (resource: string): resource is ResourceType => {
  return ["strategies", "backtests", "optimizations", "backtest-results"].includes(resource);
};

/**
 * Map resource names to API endpoints
 */
const getResourceEndpoint = (resource: string): string => {
  // Note: baseURL already includes /api/v1, so endpoints should NOT include it
  const endpoints: Record<ResourceType, string> = {
    strategies: "/strategies",
    backtests: "/backtests",
    optimizations: "/optimizations",
    "backtest-results": "/backtest-results",
  };

  if (!isValidResource(resource)) {
    throw new Error(`Unknown resource: ${resource}`);
  }

  return endpoints[resource];
};

/**
 * Map Refine filter operators to API query parameters
 */
const mapFiltersToParams = (filters?: any[]): Record<string, any> => {
  if (!filters || filters.length === 0) {
    return {};
  }

  const params: Record<string, any> = {};

  filters.forEach((filter) => {
    const { field, operator, value } = filter;

    // Handle different operator types
    switch (operator) {
      case "eq":
        params[field] = value;
        break;
      case "ne":
        params[`${field}_ne`] = value;
        break;
      case "lt":
        params[`max_${field}`] = value;
        break;
      case "lte":
        params[`max_${field}`] = value;
        break;
      case "gt":
        params[`min_${field}`] = value;
        break;
      case "gte":
        params[`min_${field}`] = value;
        break;
      case "contains":
        params[`${field}_pattern`] = `%${value}%`;
        break;
      case "containss":
        params[`${field}_pattern`] = `%${value}%`;
        break;
      case "startswith":
        params[`${field}_pattern`] = `${value}%`;
        break;
      case "endswith":
        params[`${field}_pattern`] = `%${value}`;
        break;
      case "in":
        // For array values, join with comma
        params[field] = Array.isArray(value) ? value.join(",") : value;
        break;
      default:
        // Default to direct field assignment
        params[field] = value;
    }
  });

  return params;
};

/**
 * Map Refine sort parameters to API query parameters
 */
const mapSortToParams = (sorters?: any[]): Record<string, any> => {
  if (!sorters || sorters.length === 0) {
    return {};
  }

  // Use the first sorter (API typically supports single column sorting)
  const { field, order } = sorters[0];

  return {
    order_by: field,
    ascending: order === "asc",
  };
};

/**
 * Extract the resource name from list response based on resource type
 */
const getListKey = (resource: string): string => {
  const keys: Record<string, string> = {
    strategies: "strategies",
    backtests: "backtests",
    optimizations: "runs",
    "backtest-results": "results",
  };

  return keys[resource] || resource;
};

/**
 * Refine DataProvider implementation
 */
export const dataProvider: DataProvider = {
  /**
   * Get a list of resources with filters, sorting, and pagination
   *
   * API Response Format:
   * {
   *   "strategies/backtests/runs": [...],
   *   "pagination": { total_count, page, page_size, total_pages }
   * }
   */
  getList: async ({ resource, pagination, sorters, filters, meta }) => {
    const endpoint = getResourceEndpoint(resource);
    const listKey = getListKey(resource);

    // Build query parameters
    const params: Record<string, any> = {
      // Pagination (Refine uses 1-indexed pages, which matches the API)
      page: pagination?.current || 1,
      page_size: pagination?.pageSize || 10,
      ...mapSortToParams(sorters),
      ...mapFiltersToParams(filters),
      ...meta,
    };

    const { data } = await axiosInstance.get(endpoint, { params });

    return {
      data: data[listKey] || [],
      total: data.pagination?.total_count || 0,
    };
  },

  /**
   * Get a single resource by ID
   *
   * API returns the item directly (not wrapped)
   */
  getOne: async ({ resource, id, meta }) => {
    const endpoint = getResourceEndpoint(resource);
    const { data } = await axiosInstance.get(`${endpoint}/${id}`, {
      params: meta,
    });

    return { data };
  },

  /**
   * Get multiple resources by IDs
   */
  getMany: async ({ resource, ids, meta }) => {
    const endpoint = getResourceEndpoint(resource);

    // Fetch all resources in parallel
    const responses = await Promise.all(
      ids.map((id) =>
        axiosInstance.get(`${endpoint}/${id}`, { params: meta })
      )
    );

    return {
      data: responses.map((response) => response.data),
    };
  },

  /**
   * Create a new resource
   *
   * Examples:
   * - POST /api/v1/strategies { name, code, description, parent_id }
   * - POST /api/v1/backtests { strategy_id, config, priority }
   * - POST /api/v1/optimizations { name, base_strategy_id, config }
   */
  create: async ({ resource, variables, meta }) => {
    const endpoint = getResourceEndpoint(resource);
    const { data } = await axiosInstance.post(endpoint, variables, {
      params: meta,
    });

    return { data };
  },

  /**
   * Update an existing resource
   *
   * Note: Most resources are immutable in this API.
   * For optimizations, use control endpoint (pause/resume/cancel).
   */
  update: async ({ resource, id, variables, meta }) => {
    const endpoint = getResourceEndpoint(resource);

    // For optimizations with action, use the control endpoint
    if (resource === "optimizations" && (variables as any).action) {
      const { data } = await axiosInstance.post(
        `${endpoint}/${id}/control`,
        variables,
        { params: meta }
      );
      return { data: data.run || data };
    }

    // For other resources, use PUT/PATCH
    const { data } = await axiosInstance.put(`${endpoint}/${id}`, variables, {
      params: meta,
    });

    return { data };
  },

  /**
   * Update multiple resources
   */
  updateMany: async ({ resource, ids, variables, meta }) => {
    const endpoint = getResourceEndpoint(resource);

    // Update all resources in parallel
    const responses = await Promise.all(
      ids.map((id) =>
        axiosInstance.put(`${endpoint}/${id}`, variables, { params: meta })
      )
    );

    return {
      data: responses.map((response) => response.data),
    };
  },

  /**
   * Delete a resource
   *
   * Examples:
   * - DELETE /api/v1/strategies/:id - delete strategy
   * - DELETE /api/v1/backtests/:id - cancel backtest
   */
  deleteOne: async ({ resource, id, meta }) => {
    const endpoint = getResourceEndpoint(resource);
    const { data } = await axiosInstance.delete(`${endpoint}/${id}`, {
      params: meta,
    });

    return { data };
  },

  /**
   * Delete multiple resources
   */
  deleteMany: async ({ resource, ids, meta }) => {
    const endpoint = getResourceEndpoint(resource);

    // Delete all resources in parallel
    await Promise.all(
      ids.map((id) => axiosInstance.delete(`${endpoint}/${id}`, { params: meta }))
    );

    return {
      data: ids.map((id) => ({ id } as any)),
    };
  },

  /**
   * Get API URL
   */
  getApiUrl: () => axiosInstance.defaults.baseURL || "",

  /**
   * Custom method for special operations
   *
   * Examples:
   * - Control optimization: POST /api/v1/optimizations/:id/control
   * - Get optimization iterations: GET /api/v1/optimizations/:id
   * - Get backtest result: GET /api/v1/backtests/:id
   * - Get strategy lineage: GET /api/v1/strategies/:id/lineage
   * - Get queue stats: GET /api/v1/backtests/queue/stats
   */
  custom: async ({ url, method, payload, query, headers }) => {
    let requestUrl = url;

    // If URL doesn't start with /, prepend it
    if (!url.startsWith("/") && !url.startsWith("http")) {
      requestUrl = `/${url}`;
    }

    const { data } = await axiosInstance.request({
      url: requestUrl,
      method: method || "GET",
      data: payload,
      params: query,
      headers: headers || {},
    });

    return { data };
  },
};

// ============================================================================
// Typed Helper Functions
// ============================================================================

/**
 * Type-safe wrappers for common operations
 */

/**
 * Get optimization run with iterations
 */
export const getOptimizationWithIterations = async (
  runId: string
): Promise<{ run: OptimizationRun; iterations: OptimizationIteration[] }> => {
  const { data } = await dataProvider.custom!({
    url: `/optimizations/${runId}`,
    method: "get",
  });

  return data as { run: OptimizationRun; iterations: OptimizationIteration[] };
};

/**
 * Control optimization run
 */
export const controlOptimization = async (
  runId: string,
  action: ControlOptimizationPayload["action"]
): Promise<OptimizationRun> => {
  const { data } = await dataProvider.custom!({
    url: `/optimizations/${runId}/control`,
    method: "post",
    payload: { action },
  });

  return data.run || data;
};

/**
 * Get backtest job with result
 */
export const getBacktestWithResult = async (
  jobId: string
): Promise<{ job: BacktestJob; result?: BacktestResult }> => {
  const { data } = await dataProvider.custom!({
    url: `/backtests/${jobId}`,
    method: "get",
  });

  return data as { job: BacktestJob; result?: BacktestResult };
};

/**
 * Get strategy lineage
 */
export const getStrategyLineage = async (
  strategyId: string,
  depth: number = 10
): Promise<any> => {
  const { data } = await dataProvider.custom!({
    url: `/strategies/${strategyId}/lineage`,
    method: "get",
    query: { depth },
  });

  return data;
};

/**
 * Get queue statistics
 */
export const getQueueStats = async (): Promise<{
  pending_jobs: number;
  running_jobs: number;
  completed_today: number;
  failed_today: number;
  max_concurrent: number;
}> => {
  const { data } = await dataProvider.custom!({
    url: "/backtests/queue/stats",
    method: "get",
  });

  return data as {
    pending_jobs: number;
    running_jobs: number;
    completed_today: number;
    failed_today: number;
    max_concurrent: number;
  };
};

export default dataProvider;
