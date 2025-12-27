# FreqSearch REST API

This package provides a REST API for the FreqSearch backend, wrapping the existing gRPC service methods.

## Features

- **RESTful endpoints** for strategies, backtests, and optimization runs
- **CORS support** for frontend integration
- **JSON request/response** encoding
- **Proper error handling** with HTTP status codes
- **Query parameter parsing** for filters and pagination

## API Endpoints

### Strategy Endpoints

#### Search Strategies
```
GET /api/v1/strategies
```
Query parameters:
- `name_pattern` - Filter by name pattern
- `min_sharpe` - Minimum Sharpe ratio
- `min_profit_pct` - Minimum profit percentage
- `max_drawdown_pct` - Maximum drawdown percentage
- `min_trades` - Minimum number of trades
- `order_by` - Sort field (sharpe, profit, created_at)
- `ascending` - Sort order (true/false)
- `page` - Page number (default: 1)
- `page_size` - Page size (default: 20, max: 100)

Response:
```json
{
  "strategies": [
    {
      "strategy": {
        "id": "uuid",
        "name": "Strategy Name",
        "code": "...",
        "generation": 1
      },
      "best_result": {
        "profit_pct": 15.5,
        "max_drawdown_pct": 10.2,
        "sharpe_ratio": 1.8
      }
    }
  ],
  "pagination": {
    "total_count": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5
  }
}
```

#### Get Strategy by ID
```
GET /api/v1/strategies/:id
```

Response:
```json
{
  "strategy": {
    "id": "uuid",
    "name": "Strategy Name",
    "code": "...",
    "description": "..."
  }
}
```

#### Create Strategy
```
POST /api/v1/strategies
```

Request body:
```json
{
  "name": "Strategy Name",
  "code": "strategy code here",
  "description": "Optional description",
  "parent_id": "optional-parent-uuid"
}
```

Response: `201 Created`
```json
{
  "strategy": {
    "id": "newly-created-uuid",
    "name": "Strategy Name",
    ...
  }
}
```

#### Delete Strategy
```
DELETE /api/v1/strategies/:id
```

Response: `204 No Content` on success

#### Get Strategy Lineage
```
GET /api/v1/strategies/:id/lineage?depth=2
```

Response:
```json
{
  "lineage": {
    "id": "uuid",
    "name": "Strategy Name",
    "generation": 1,
    "children": [...]
  }
}
```

### Backtest Endpoints

#### Query Backtest Results
```
GET /api/v1/backtests
```

Query parameters:
- `strategy_id` - Filter by strategy UUID
- `optimization_run_id` - Filter by optimization run UUID
- `min_sharpe` - Minimum Sharpe ratio
- `min_profit_pct` - Minimum profit percentage
- `max_drawdown_pct` - Maximum drawdown percentage
- `min_trades` - Minimum number of trades
- `start_time` - Start time (RFC3339 format)
- `end_time` - End time (RFC3339 format)
- `order_by` - Sort field
- `ascending` - Sort order
- `page` - Page number
- `page_size` - Page size

Response:
```json
{
  "results": [
    {
      "id": "uuid",
      "job_id": "uuid",
      "strategy_id": "uuid",
      "total_trades": 100,
      "profit_pct": 15.5,
      "sharpe_ratio": 1.8
    }
  ],
  "pagination": {...}
}
```

#### Submit Backtest
```
POST /api/v1/backtests
```

Request body:
```json
{
  "strategy_id": "uuid",
  "config": {
    "exchange": "binance",
    "pairs": ["BTC/USDT"],
    "timeframe": "5m",
    "timerange_start": "20230101",
    "timerange_end": "20231231",
    "dry_run_wallet": 1000,
    "max_open_trades": 3,
    "stake_amount": "100"
  },
  "priority": 5,
  "optimization_run_id": "optional-uuid"
}
```

Response: `201 Created`
```json
{
  "job": {
    "id": "uuid",
    "strategy_id": "uuid",
    "status": "pending",
    "priority": 5
  }
}
```

#### Get Backtest Job
```
GET /api/v1/backtests/:id
```

Response:
```json
{
  "job": {
    "id": "uuid",
    "strategy_id": "uuid",
    "status": "running",
    "priority": 5,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

#### Cancel Backtest
```
DELETE /api/v1/backtests/:id
```

Response: `204 No Content` on success

#### Get Queue Statistics
```
GET /api/v1/backtests/queue/stats
```

Response:
```json
{
  "stats": {
    "pending_jobs": 5,
    "running_jobs": 2,
    "completed_today": 100,
    "failed_today": 3,
    "avg_wait_time_ms": 5000,
    "avg_run_time_ms": 30000
  }
}
```

### Optimization Endpoints

#### List Optimization Runs
```
GET /api/v1/optimizations
```

Query parameters:
- `status` - Filter by status (pending, running, paused, completed, failed, cancelled)
- `start_time` - Start time (RFC3339 format)
- `end_time` - End time (RFC3339 format)
- `order_by` - Sort field
- `ascending` - Sort order
- `page` - Page number
- `page_size` - Page size

Response:
```json
{
  "runs": [
    {
      "id": "uuid",
      "name": "Optimization Run 1",
      "base_strategy_id": "uuid",
      "status": "running",
      "current_iteration": 5,
      "max_iterations": 10
    }
  ],
  "pagination": {...}
}
```

#### Start Optimization
```
POST /api/v1/optimizations
```

Request body:
```json
{
  "name": "Optimization Run Name",
  "base_strategy_id": "uuid",
  "config": {
    "backtest_config": {
      "exchange": "binance",
      "pairs": ["BTC/USDT"],
      "timeframe": "5m",
      "timerange_start": "20230101",
      "timerange_end": "20231231",
      "dry_run_wallet": 1000,
      "max_open_trades": 3,
      "stake_amount": "100"
    },
    "max_iterations": 10,
    "criteria": {
      "min_sharpe": 1.5,
      "min_profit_pct": 10.0,
      "max_drawdown_pct": 20.0,
      "min_trades": 50,
      "min_win_rate": 0.5
    },
    "mode": "maximize_sharpe"
  }
}
```

Response: `201 Created`
```json
{
  "run": {
    "id": "uuid",
    "name": "Optimization Run Name",
    "status": "pending",
    ...
  }
}
```

#### Get Optimization Run
```
GET /api/v1/optimizations/:id
```

Response:
```json
{
  "run": {
    "id": "uuid",
    "name": "Optimization Run Name",
    "status": "running",
    "current_iteration": 5,
    "max_iterations": 10
  },
  "iterations": [
    {
      "iteration_number": 1,
      "strategy_id": "uuid",
      "backtest_job_id": "uuid",
      "approval": "approved"
    }
  ]
}
```

#### Control Optimization
```
POST /api/v1/optimizations/:id/control
```

Request body:
```json
{
  "action": "pause"  // or "resume", "cancel"
}
```

Response:
```json
{
  "success": true,
  "run": {
    "id": "uuid",
    "status": "paused"
  }
}
```

## Error Responses

All endpoints return JSON error responses with appropriate HTTP status codes:

```json
{
  "error": "resource not found",
  "message": "strategy not found"
}
```

Status codes:
- `400 Bad Request` - Invalid input
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict (e.g., duplicate, in use)
- `500 Internal Server Error` - Server error

## CORS

The API includes CORS middleware that allows requests from any origin. In production, you should configure this to only allow requests from your frontend domain.

## Integration

The REST API is integrated into the main HTTP server alongside health checks and metrics endpoints. It uses the same repository layer as the gRPC service, ensuring consistency across all API interfaces.
