package http

// Example WebSocket client usage (JavaScript/TypeScript)
//
// Connection:
//   const ws = new WebSocket('ws://localhost:8080/api/v1/ws/events');
//
//   ws.onopen = () => {
//     console.log('Connected to WebSocket');
//
//     // Subscribe to specific event types
//     ws.send(JSON.stringify({
//       action: 'subscribe',
//       event_types: [
//         'optimization.iteration.completed',
//         'backtest.completed',
//         'backtest.failed'
//       ]
//     }));
//   };
//
//   ws.onmessage = (event) => {
//     const message = JSON.parse(event.data);
//     console.log('Received event:', message);
//
//     // Message format:
//     // {
//     //   "type": "optimization.iteration.completed",
//     //   "data": {
//     //     "event_id": "uuid",
//     //     "event_type": "optimization.iteration",
//     //     "timestamp": "2025-12-15T10:30:00Z",
//     //     "run_id": "uuid",
//     //     "iteration_number": 42,
//     //     "strategy_id": "uuid",
//     //     "profit_pct": 15.5,
//     //     "sharpe_ratio": 1.8,
//     //     "is_best": true
//     //   },
//     //   "timestamp": "2025-12-15T10:30:00Z"
//     // }
//
//     // Handle different event types
//     switch (message.type) {
//       case 'optimization.iteration.completed':
//         handleOptimizationIteration(message.data);
//         break;
//       case 'backtest.completed':
//         handleBacktestCompleted(message.data);
//         break;
//       case 'backtest.failed':
//         handleBacktestFailed(message.data);
//         break;
//     }
//   };
//
//   ws.onerror = (error) => {
//     console.error('WebSocket error:', error);
//   };
//
//   ws.onclose = () => {
//     console.log('WebSocket connection closed');
//     // Implement reconnection logic here
//   };
//
// Unsubscribe from events:
//   ws.send(JSON.stringify({
//     action: 'unsubscribe',
//     event_types: ['backtest.failed']
//   }));
//
// Event Types:
//   - optimization.iteration.started
//   - optimization.iteration.completed
//   - optimization.new_best
//   - optimization.completed
//   - optimization.failed
//   - backtest.submitted
//   - backtest.completed
//   - backtest.failed
//   - agent.status.changed
//   - task.running
//   - task.failed
//   - task.cancelled
//   - strategy.discovered
//   - strategy.needs_processing
//   - strategy.ready_for_backtest
//   - strategy.approved
//   - strategy.evolve
//   - strategy.archived
