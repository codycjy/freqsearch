package http

import (
	"encoding/json"
	"testing"
	"time"

	"go.uber.org/zap"
)

func TestHub_ClientRegistration(t *testing.T) {
	logger := zap.NewNop()
	hub := NewHub(logger)

	// Start hub
	go hub.Run()
	defer hub.Shutdown()

	// Create a mock client
	client := &Client{
		hub:           hub,
		send:          make(chan []byte, sendBufferSize),
		subscriptions: make(map[string]bool),
		logger:        logger,
	}

	// Register client
	hub.register <- client

	// Give it time to process
	time.Sleep(10 * time.Millisecond)

	// Check client count
	if count := hub.GetClientCount(); count != 1 {
		t.Errorf("Expected 1 client, got %d", count)
	}

	// Unregister client
	hub.unregister <- client

	// Give it time to process
	time.Sleep(10 * time.Millisecond)

	// Check client count
	if count := hub.GetClientCount(); count != 0 {
		t.Errorf("Expected 0 clients, got %d", count)
	}
}

func TestHub_BroadcastEvent(t *testing.T) {
	logger := zap.NewNop()
	hub := NewHub(logger)

	// Start hub
	go hub.Run()
	defer hub.Shutdown()

	// Create a mock client
	client := &Client{
		hub:           hub,
		send:          make(chan []byte, sendBufferSize),
		subscriptions: make(map[string]bool),
		logger:        logger,
	}

	// Register client
	hub.register <- client

	// Give it time to process
	time.Sleep(10 * time.Millisecond)

	// Broadcast an event
	testData := map[string]interface{}{
		"test": "data",
		"num":  42,
	}
	hub.BroadcastEvent(EventTypeBacktestCompleted, testData)

	// Receive the message
	select {
	case msg := <-client.send:
		var wsMsg WSMessage
		if err := json.Unmarshal(msg, &wsMsg); err != nil {
			t.Fatalf("Failed to unmarshal message: %v", err)
		}

		if wsMsg.Type != EventTypeBacktestCompleted {
			t.Errorf("Expected event type %s, got %s", EventTypeBacktestCompleted, wsMsg.Type)
		}

		data, ok := wsMsg.Data.(map[string]interface{})
		if !ok {
			t.Fatal("Data is not a map")
		}

		if data["test"] != "data" {
			t.Errorf("Expected test=data, got %v", data["test"])
		}

		if data["num"] != float64(42) {
			t.Errorf("Expected num=42, got %v", data["num"])
		}

	case <-time.After(1 * time.Second):
		t.Fatal("Timeout waiting for message")
	}
}

func TestClient_Subscriptions(t *testing.T) {
	logger := zap.NewNop()
	hub := NewHub(logger)

	// Start hub
	go hub.Run()
	defer hub.Shutdown()

	// Create a client with specific subscriptions
	client := &Client{
		hub:           hub,
		send:          make(chan []byte, sendBufferSize),
		subscriptions: make(map[string]bool),
		logger:        logger,
	}

	// Subscribe to specific event types
	client.subscribe([]string{EventTypeBacktestCompleted, EventTypeOptIterationCompleted})

	// Register client
	hub.register <- client

	// Give it time to process
	time.Sleep(10 * time.Millisecond)

	// Test subscribed event
	if !client.isSubscribed(EventTypeBacktestCompleted) {
		t.Error("Client should be subscribed to backtest.completed")
	}

	// Test unsubscribed event
	if client.isSubscribed(EventTypeBacktestFailed) {
		t.Error("Client should not be subscribed to backtest.failed")
	}

	// Broadcast subscribed event - should receive
	hub.BroadcastEvent(EventTypeBacktestCompleted, map[string]string{"status": "success"})

	select {
	case msg := <-client.send:
		var wsMsg WSMessage
		if err := json.Unmarshal(msg, &wsMsg); err != nil {
			t.Fatalf("Failed to unmarshal message: %v", err)
		}
		if wsMsg.Type != EventTypeBacktestCompleted {
			t.Errorf("Expected event type %s, got %s", EventTypeBacktestCompleted, wsMsg.Type)
		}
	case <-time.After(100 * time.Millisecond):
		t.Fatal("Should have received subscribed event")
	}

	// Broadcast unsubscribed event - should not receive
	hub.BroadcastEvent(EventTypeBacktestFailed, map[string]string{"status": "failed"})

	select {
	case <-client.send:
		t.Fatal("Should not have received unsubscribed event")
	case <-time.After(100 * time.Millisecond):
		// Expected - no message received
	}

	// Unsubscribe from an event
	client.unsubscribe([]string{EventTypeBacktestCompleted})

	if client.isSubscribed(EventTypeBacktestCompleted) {
		t.Error("Client should be unsubscribed from backtest.completed")
	}
}

func TestClient_NoSubscriptionReceivesAll(t *testing.T) {
	logger := zap.NewNop()
	hub := NewHub(logger)

	// Start hub
	go hub.Run()
	defer hub.Shutdown()

	// Create a client with no specific subscriptions
	client := &Client{
		hub:           hub,
		send:          make(chan []byte, sendBufferSize),
		subscriptions: make(map[string]bool),
		logger:        logger,
	}

	// Register client
	hub.register <- client

	// Give it time to process
	time.Sleep(10 * time.Millisecond)

	// Client with no subscriptions should receive all events
	if !client.isSubscribed(EventTypeBacktestCompleted) {
		t.Error("Client with no subscriptions should receive all events")
	}

	if !client.isSubscribed(EventTypeBacktestFailed) {
		t.Error("Client with no subscriptions should receive all events")
	}

	if !client.isSubscribed("any.event.type") {
		t.Error("Client with no subscriptions should receive all events")
	}
}

func TestMapRoutingKeyToEventType(t *testing.T) {
	tests := []struct {
		routingKey string
		expected   string
	}{
		{"task.running", EventTypeBacktestSubmitted},
		{"task.completed", EventTypeBacktestCompleted},
		{"task.failed", EventTypeBacktestFailed},
		{"optimization.iteration", EventTypeOptIterationCompleted},
		{"backtest.completed", EventTypeBacktestCompleted},
		{"backtest.failed", EventTypeBacktestFailed},
		{"strategy.discovered", "strategy.discovered"}, // Pass through
		{"unknown.event", "unknown.event"},             // Pass through
	}

	for _, tt := range tests {
		t.Run(tt.routingKey, func(t *testing.T) {
			result := mapRoutingKeyToEventType(tt.routingKey)
			if result != tt.expected {
				t.Errorf("Expected %s, got %s", tt.expected, result)
			}
		})
	}
}
