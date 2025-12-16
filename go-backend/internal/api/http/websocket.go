// Package http provides WebSocket hub for real-time event broadcasting.
package http

import (
	"encoding/json"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"go.uber.org/zap"
)

const (
	// Time allowed to write a message to the peer.
	writeWait = 10 * time.Second

	// Time allowed to read the next pong message from the peer.
	pongWait = 60 * time.Second

	// Send pings to peer with this period. Must be less than pongWait.
	pingPeriod = (pongWait * 9) / 10

	// Maximum message size allowed from peer.
	maxMessageSize = 512

	// Size of the send buffer for each client.
	sendBufferSize = 256
)

// Event types that can be broadcasted to WebSocket clients.
const (
	// Optimization events
	EventTypeOptIterationStarted   = "optimization.iteration.started"
	EventTypeOptIterationCompleted = "optimization.iteration.completed"
	EventTypeOptNewBest            = "optimization.new_best"
	EventTypeOptCompleted          = "optimization.completed"
	EventTypeOptFailed             = "optimization.failed"

	// Backtest events
	EventTypeBacktestSubmitted = "backtest.submitted"
	EventTypeBacktestCompleted = "backtest.completed"
	EventTypeBacktestFailed    = "backtest.failed"

	// Agent events
	EventTypeAgentStatusChanged = "agent.status.changed"
	EventTypeAgentStatusUpdate  = "agent.status.update"

	// Task events (from RabbitMQ)
	EventTypeTaskRunning   = "task.running"
	EventTypeTaskFailed    = "task.failed"
	EventTypeTaskCancelled = "task.cancelled"
)

// WSMessage represents a WebSocket message sent to clients.
type WSMessage struct {
	Type      string      `json:"type"`
	Data      interface{} `json:"data"`
	Timestamp time.Time   `json:"timestamp"`
}

// SubscriptionMessage represents a subscription request from a client.
type SubscriptionMessage struct {
	Action     string   `json:"action"` // "subscribe" or "unsubscribe"
	EventTypes []string `json:"event_types"`
}

// Client represents a WebSocket client connection.
type Client struct {
	hub *Hub

	// The websocket connection.
	conn *websocket.Conn

	// Buffered channel of outbound messages.
	send chan []byte

	// Subscribed event types (if empty, receives all events).
	subscriptions map[string]bool
	mu            sync.RWMutex

	// Logger for this client.
	logger *zap.Logger
}

// Hub maintains the set of active clients and broadcasts messages to them.
type Hub struct {
	// Registered clients.
	clients map[*Client]bool

	// Inbound messages from clients.
	broadcast chan []byte

	// Register requests from clients.
	register chan *Client

	// Unregister requests from clients.
	unregister chan *Client

	// Mutex to protect clients map.
	mu sync.RWMutex

	// Logger.
	logger *zap.Logger

	// Shutdown channel.
	done chan struct{}
}

// NewHub creates a new Hub instance.
func NewHub(logger *zap.Logger) *Hub {
	return &Hub{
		clients:    make(map[*Client]bool),
		broadcast:  make(chan []byte, 256),
		register:   make(chan *Client),
		unregister: make(chan *Client),
		logger:     logger,
		done:       make(chan struct{}),
	}
}

// Run starts the hub's main loop.
func (h *Hub) Run() {
	h.logger.Info("WebSocket hub started")
	defer h.logger.Info("WebSocket hub stopped")

	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = true
			h.mu.Unlock()
			h.logger.Info("Client registered", zap.Int("total_clients", len(h.clients)))

		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
				h.logger.Info("Client unregistered", zap.Int("total_clients", len(h.clients)))
			}
			h.mu.Unlock()

		case message := <-h.broadcast:
			h.broadcastMessage(message)

		case <-h.done:
			h.shutdown()
			return
		}
	}
}

// broadcastMessage sends a message to all subscribed clients.
func (h *Hub) broadcastMessage(message []byte) {
	// Parse message to get event type
	var wsMsg WSMessage
	if err := json.Unmarshal(message, &wsMsg); err != nil {
		h.logger.Error("Failed to unmarshal message for broadcasting", zap.Error(err))
		return
	}

	h.mu.RLock()
	defer h.mu.RUnlock()

	for client := range h.clients {
		if client.isSubscribed(wsMsg.Type) {
			select {
			case client.send <- message:
			default:
				// Client's send buffer is full, remove it
				go func(c *Client) {
					h.unregister <- c
				}(client)
			}
		}
	}
}

// BroadcastEvent broadcasts an event to all connected clients.
func (h *Hub) BroadcastEvent(eventType string, data interface{}) {
	msg := WSMessage{
		Type:      eventType,
		Data:      data,
		Timestamp: time.Now(),
	}

	msgBytes, err := json.Marshal(msg)
	if err != nil {
		h.logger.Error("Failed to marshal event", zap.Error(err), zap.String("event_type", eventType))
		return
	}

	select {
	case h.broadcast <- msgBytes:
	default:
		h.logger.Warn("Broadcast channel full, dropping message", zap.String("event_type", eventType))
	}
}

// GetClientCount returns the number of connected clients.
func (h *Hub) GetClientCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.clients)
}

// Shutdown gracefully shuts down the hub.
func (h *Hub) Shutdown() {
	close(h.done)
}

// shutdown closes all client connections.
func (h *Hub) shutdown() {
	h.mu.Lock()
	defer h.mu.Unlock()

	for client := range h.clients {
		close(client.send)
		if client.conn != nil {
			client.conn.Close()
		}
	}
	h.clients = make(map[*Client]bool)
}

// isSubscribed checks if the client is subscribed to the given event type.
func (c *Client) isSubscribed(eventType string) bool {
	c.mu.RLock()
	defer c.mu.RUnlock()

	// If no specific subscriptions, receive all events
	if len(c.subscriptions) == 0 {
		return true
	}

	return c.subscriptions[eventType]
}

// subscribe adds event types to the client's subscriptions.
func (c *Client) subscribe(eventTypes []string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.subscriptions == nil {
		c.subscriptions = make(map[string]bool)
	}

	for _, eventType := range eventTypes {
		c.subscriptions[eventType] = true
	}

	c.logger.Info("Client subscribed to events", zap.Strings("event_types", eventTypes))
}

// unsubscribe removes event types from the client's subscriptions.
func (c *Client) unsubscribe(eventTypes []string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	for _, eventType := range eventTypes {
		delete(c.subscriptions, eventType)
	}

	c.logger.Info("Client unsubscribed from events", zap.Strings("event_types", eventTypes))
}

// readPump pumps messages from the websocket connection to the hub.
func (c *Client) readPump() {
	defer func() {
		c.hub.unregister <- c
		c.conn.Close()
	}()

	c.conn.SetReadDeadline(time.Now().Add(pongWait))
	c.conn.SetReadLimit(maxMessageSize)
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	// Also handle text ping messages from clients that don't use WebSocket ping frames
	c.conn.SetPingHandler(func(appData string) error {
		c.conn.SetReadDeadline(time.Now().Add(pongWait))
		return c.conn.WriteControl(websocket.PongMessage, []byte(appData), time.Now().Add(writeWait))
	})

	for {
		_, message, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure, websocket.CloseNormalClosure) {
				c.logger.Error("WebSocket read error", zap.Error(err))
			}
			break
		}

		// Handle text "ping" messages from frontend (some clients send text ping instead of WS ping frames)
		msgStr := string(message)
		if msgStr == "ping" {
			c.conn.SetReadDeadline(time.Now().Add(pongWait))
			if err := c.conn.WriteMessage(websocket.TextMessage, []byte("pong")); err != nil {
				c.logger.Debug("Failed to send pong response", zap.Error(err))
			}
			continue
		}

		// Handle subscription messages (must be valid JSON)
		var subMsg SubscriptionMessage
		if err := json.Unmarshal(message, &subMsg); err != nil {
			// Silently ignore non-JSON messages (debug level)
			c.logger.Debug("Ignoring non-JSON message", zap.String("message", msgStr))
			continue
		}

		switch subMsg.Action {
		case "subscribe":
			c.subscribe(subMsg.EventTypes)
		case "unsubscribe":
			c.unsubscribe(subMsg.EventTypes)
		default:
			c.logger.Debug("Unknown subscription action", zap.String("action", subMsg.Action))
		}
	}
}

// writePump pumps messages from the hub to the websocket connection.
func (c *Client) writePump() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()

	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if !ok {
				// The hub closed the channel.
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			w, err := c.conn.NextWriter(websocket.TextMessage)
			if err != nil {
				return
			}
			w.Write(message)

			// Add queued messages to the current websocket message.
			n := len(c.send)
			for i := 0; i < n; i++ {
				w.Write([]byte{'\n'})
				w.Write(<-c.send)
			}

			if err := w.Close(); err != nil {
				return
			}

		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

// upgrader is used to upgrade HTTP connections to WebSocket.
var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		// TODO: Implement proper origin checking in production
		return true
	},
}

// ServeWS handles websocket requests from the peer.
func (h *Hub) ServeWS(w http.ResponseWriter, r *http.Request, logger *zap.Logger) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		logger.Error("Failed to upgrade connection", zap.Error(err))
		return
	}

	client := &Client{
		hub:           h,
		conn:          conn,
		send:          make(chan []byte, sendBufferSize),
		subscriptions: make(map[string]bool),
		logger:        logger.With(zap.String("remote_addr", r.RemoteAddr)),
	}

	h.register <- client

	// Start goroutines for reading and writing
	go client.writePump()
	go client.readPump()
}
