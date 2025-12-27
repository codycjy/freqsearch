# WebSocket Hub for Real-time Event Broadcasting

This package implements a WebSocket hub for broadcasting real-time events from the FreqSearch backend to frontend clients. Events are consumed from RabbitMQ and pushed to all connected WebSocket clients.

## Features

- **Thread-safe client management**: Concurrent-safe registration/unregistration of clients
- **Event subscription filtering**: Clients can subscribe to specific event types
- **Ping/pong health checks**: Automatic connection health monitoring
- **RabbitMQ integration**: Subscribes to RabbitMQ events and broadcasts to WebSocket clients
- **Automatic reconnection**: RabbitMQ subscriber automatically reconnects on connection loss
- **Graceful shutdown**: Properly closes all connections and cleans up resources

## Architecture

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   RabbitMQ   │────────>│  Subscriber  │────────>│  WS Hub      │
│   Events     │         │              │         │              │
└──────────────┘         └──────────────┘         └──────────────┘
                                                         │
                                                         │ Broadcast
                                                         │
                         ┌───────────────────────────────┴────────────┐
                         │                │                           │
                         ▼                ▼                           ▼
                   ┌──────────┐    ┌──────────┐              ┌──────────┐
                   │ Client 1 │    │ Client 2 │    ...       │ Client N │
                   └──────────┘    └──────────┘              └──────────┘
```

## WebSocket Endpoint

**URL**: `ws://localhost:8080/api/v1/ws/events`

## Event Types

The following event types are broadcasted:

### Optimization Events
- `optimization.iteration.started` - Optimization iteration has started
- `optimization.iteration.completed` - Optimization iteration completed
- `optimization.new_best` - New best result found
- `optimization.completed` - Optimization run completed
- `optimization.failed` - Optimization run failed

### Backtest Events
- `backtest.submitted` - Backtest job submitted
- `backtest.completed` - Backtest job completed successfully
- `backtest.failed` - Backtest job failed

### Task Events
- `task.running` - Task is now running
- `task.failed` - Task failed
- `task.cancelled` - Task was cancelled

### Strategy Events (from Python Agents)
- `strategy.discovered` - New strategy discovered by Scout Agent
- `strategy.needs_processing` - Strategy needs processing by Engineer Agent
- `strategy.ready_for_backtest` - Strategy ready for backtesting
- `strategy.approved` - Strategy approved for live trading
- `strategy.evolve` - Strategy needs modification
- `strategy.archived` - Strategy archived/discarded

### Agent Events
- `agent.status.changed` - Agent status changed

## Message Format

All WebSocket messages follow this JSON structure:

```json
{
  "type": "event.type.name",
  "data": {
    // Event-specific data
  },
  "timestamp": "2025-12-15T10:30:00Z"
}
```

### Example Messages

#### Backtest Completed
```json
{
  "type": "backtest.completed",
  "data": {
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "event_type": "task.completed",
    "timestamp": "2025-12-15T10:30:00Z",
    "job_id": "123e4567-e89b-12d3-a456-426614174000",
    "strategy_id": "987e6543-e21b-43d2-b987-123456789abc",
    "result_id": "456e7890-e12b-34d5-c678-234567890def",
    "duration_ms": 45000,
    "sharpe_ratio": 1.85,
    "profit_pct": 15.5,
    "total_trades": 142
  },
  "timestamp": "2025-12-15T10:30:00Z"
}
```

#### Optimization Iteration
```json
{
  "type": "optimization.iteration.completed",
  "data": {
    "event_id": "660f9500-f39c-51e5-b827-557766551111",
    "event_type": "optimization.iteration",
    "timestamp": "2025-12-15T10:35:00Z",
    "run_id": "789e0123-f45b-67d8-e901-345678901234",
    "iteration_number": 42,
    "strategy_id": "987e6543-e21b-43d2-b987-123456789abc",
    "result_id": "234e5678-f90b-12d3-a456-567890123456",
    "sharpe_ratio": 2.1,
    "profit_pct": 18.3,
    "is_best": true
  },
  "timestamp": "2025-12-15T10:35:00Z"
}
```

## Client Usage

### JavaScript/TypeScript Example

```javascript
// Establish WebSocket connection
const ws = new WebSocket('ws://localhost:8080/api/v1/ws/events');

ws.onopen = () => {
  console.log('Connected to WebSocket');

  // Subscribe to specific event types
  ws.send(JSON.stringify({
    action: 'subscribe',
    event_types: [
      'optimization.iteration.completed',
      'backtest.completed',
      'backtest.failed'
    ]
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Received event:', message);

  // Handle different event types
  switch (message.type) {
    case 'optimization.iteration.completed':
      handleOptimizationIteration(message.data);
      break;
    case 'backtest.completed':
      handleBacktestCompleted(message.data);
      break;
    case 'backtest.failed':
      handleBacktestFailed(message.data);
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket connection closed');
  // Implement reconnection logic
  setTimeout(() => connectWebSocket(), 5000);
};

// Unsubscribe from events
ws.send(JSON.stringify({
  action: 'unsubscribe',
  event_types: ['backtest.failed']
}));
```

### React Hook Example

```typescript
import { useEffect, useState, useRef } from 'react';

interface WSMessage {
  type: string;
  data: any;
  timestamp: string;
}

export function useWebSocket(url: string, eventTypes?: string[]) {
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Connect to WebSocket
    ws.current = new WebSocket(url);

    ws.current.onopen = () => {
      setIsConnected(true);

      // Subscribe to specific events if provided
      if (eventTypes && eventTypes.length > 0) {
        ws.current?.send(JSON.stringify({
          action: 'subscribe',
          event_types: eventTypes
        }));
      }
    };

    ws.current.onmessage = (event) => {
      const message: WSMessage = JSON.parse(event.data);
      setLastMessage(message);
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.current.onclose = () => {
      setIsConnected(false);
    };

    // Cleanup on unmount
    return () => {
      ws.current?.close();
    };
  }, [url]);

  return { lastMessage, isConnected };
}

// Usage in component
function OptimizationDashboard() {
  const { lastMessage, isConnected } = useWebSocket(
    'ws://localhost:8080/api/v1/ws/events',
    ['optimization.iteration.completed', 'optimization.new_best']
  );

  useEffect(() => {
    if (lastMessage?.type === 'optimization.iteration.completed') {
      console.log('New iteration:', lastMessage.data);
      // Update UI with new iteration data
    }
  }, [lastMessage]);

  return (
    <div>
      <div>Status: {isConnected ? 'Connected' : 'Disconnected'}</div>
      {/* Your dashboard UI */}
    </div>
  );
}
```

## Subscription Management

### Subscribe to Events

Send a subscription message to receive only specific event types:

```json
{
  "action": "subscribe",
  "event_types": [
    "backtest.completed",
    "optimization.iteration.completed"
  ]
}
```

### Unsubscribe from Events

```json
{
  "action": "unsubscribe",
  "event_types": ["backtest.completed"]
}
```

### Receive All Events

If you don't send any subscription message, the client will receive **all** event types by default.

## Server-Side Integration

### Setting up the HTTP Server with WebSocket

```go
import (
    "github.com/saltfish/freqsearch/go-backend/internal/api/http"
    "github.com/saltfish/freqsearch/go-backend/internal/config"
    "github.com/saltfish/freqsearch/go-backend/internal/events"
)

// Create HTTP server with WebSocket hub
server := http.NewServer(
    ":8080",
    pool,
    repos,
    scheduler,
    logger,
)

// Create and set RabbitMQ subscriber (optional)
subscriber, err := events.NewRabbitMQSubscriber(
    &config.RabbitMQConfig{
        URL:              "amqp://guest:guest@localhost:5672/",
        Exchange:         "freqsearch_events",
        ReconnectDelay:   "5s",
        MaxReconnectWait: "30s",
    },
    "websocket_events_queue", // Queue name
    logger,
)
if err == nil {
    server.SetSubscriber(subscriber)
}

// Start server (automatically starts WebSocket hub and RabbitMQ subscriber)
server.Start()
```

### Broadcasting Events Programmatically

You can also broadcast events directly from your Go code:

```go
// Get the WebSocket hub
hub := server.GetHub()

// Broadcast a custom event
hub.BroadcastEvent("custom.event", map[string]interface{}{
    "message": "Something happened",
    "value": 42,
})
```

## Configuration

### Connection Settings

The WebSocket implementation uses the following timeouts:

- **Write timeout**: 10 seconds
- **Pong timeout**: 60 seconds
- **Ping period**: 54 seconds (90% of pong timeout)
- **Max message size**: 512 bytes (for client-to-server messages)
- **Send buffer size**: 256 messages per client

### RabbitMQ Subscriber Settings

Configure via the `RabbitMQConfig`:

- `URL`: RabbitMQ connection URL (e.g., `amqp://guest:guest@localhost:5672/`)
- `Exchange`: Exchange name (e.g., `freqsearch_events`)
- `ReconnectDelay`: Initial reconnection delay (e.g., `5s`)
- `MaxReconnectWait`: Maximum reconnection delay (e.g., `30s`)

## Monitoring

### WebSocket Metrics

WebSocket metrics are included in the `/metrics` endpoint:

```bash
curl http://localhost:8080/metrics
```

Response includes:

```json
{
  "scheduler": { ... },
  "database": { ... },
  "websocket": {
    "connected_clients": 5
  }
}
```

### Health Check

The `/health` endpoint includes WebSocket hub status indirectly through service availability.

## Error Handling

### Client-Side

- **Connection errors**: Implement exponential backoff for reconnection
- **Message parsing errors**: Validate JSON before processing
- **Unexpected disconnections**: Subscribe to `onclose` event and reconnect

### Server-Side

- **Buffer full**: If a client's send buffer is full, the client is automatically disconnected
- **Invalid messages**: Non-JSON messages are logged and ignored
- **RabbitMQ disconnection**: Automatic reconnection with exponential backoff

## Security Considerations

### CORS Configuration

The current implementation allows all origins (`*`). In production:

```go
// Update corsMiddleware in server.go
w.Header().Set("Access-Control-Allow-Origin", "https://your-frontend-domain.com")
```

### Origin Checking

Update the `upgrader` in `websocket.go`:

```go
var upgrader = websocket.Upgrader{
    ReadBufferSize:  1024,
    WriteBufferSize: 1024,
    CheckOrigin: func(r *http.Request) bool {
        origin := r.Header.Get("Origin")
        // Add your origin validation logic
        return origin == "https://your-frontend-domain.com"
    },
}
```

### Authentication

For authenticated WebSocket connections, add authentication middleware:

```go
mux.HandleFunc("/api/v1/ws/events", func(w http.ResponseWriter, r *http.Request) {
    // Verify authentication token
    token := r.Header.Get("Authorization")
    if !validateToken(token) {
        http.Error(w, "Unauthorized", http.StatusUnauthorized)
        return
    }

    s.wsHub.ServeWS(w, r, logger)
})
```

## Testing

Run the WebSocket tests:

```bash
cd go-backend
go test -v ./internal/api/http -run TestHub
go test -v ./internal/events -run TestSubscriber
```

## Performance

- **Concurrent clients**: Supports thousands of concurrent WebSocket connections
- **Message throughput**: Can handle high-frequency events (100+ events/second)
- **Memory usage**: ~10KB per client connection
- **CPU usage**: Minimal overhead for message broadcasting

## Troubleshooting

### WebSocket connection fails

1. Check if the HTTP server is running
2. Verify the WebSocket URL is correct
3. Check CORS configuration
4. Verify firewall/proxy settings allow WebSocket connections

### No events received

1. Verify RabbitMQ subscriber is connected
2. Check RabbitMQ exchange and routing key bindings
3. Verify events are being published to RabbitMQ
4. Check subscription filters on the client

### Client disconnected unexpectedly

1. Check network stability
2. Verify ping/pong timeouts are appropriate
3. Check server logs for errors
4. Ensure client send buffer isn't full

## Future Enhancements

- [ ] Authentication and authorization
- [ ] Rate limiting per client
- [ ] Message compression for large payloads
- [ ] Event replay/history for new clients
- [ ] Client-to-server messaging (commands)
- [ ] Multi-room/namespace support
- [ ] Metrics per event type
