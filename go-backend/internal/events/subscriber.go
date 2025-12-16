// Package events provides RabbitMQ event subscription for FreqSearch.
package events

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/config"
)

// EventHandler is a function that processes received events.
type EventHandler func(routingKey string, body []byte) error

// Subscriber provides event subscription from RabbitMQ.
type Subscriber interface {
	// Subscribe starts consuming messages from RabbitMQ.
	Subscribe(ctx context.Context, routingKeys []string, handler EventHandler) error

	// Close closes the subscriber connection.
	Close() error
}

// RabbitMQSubscriber implements Subscriber using RabbitMQ.
type RabbitMQSubscriber struct {
	config   *config.RabbitMQConfig
	conn     *amqp.Connection
	channel  *amqp.Channel
	exchange string
	queue    string
	logger   *zap.Logger

	mu           sync.RWMutex
	closed       bool
	reconnecting bool
	handler      EventHandler
	routingKeys  []string
	ctx          context.Context
	cancel       context.CancelFunc
}

// NewRabbitMQSubscriber creates a new RabbitMQ subscriber.
func NewRabbitMQSubscriber(cfg *config.RabbitMQConfig, queueName string, logger *zap.Logger) (*RabbitMQSubscriber, error) {
	s := &RabbitMQSubscriber{
		config:   cfg,
		exchange: cfg.Exchange,
		queue:    queueName,
		logger:   logger,
	}

	if err := s.connect(); err != nil {
		return nil, err
	}

	return s, nil
}

// connect establishes connection to RabbitMQ.
func (s *RabbitMQSubscriber) connect() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.closed {
		return fmt.Errorf("subscriber is closed")
	}

	var err error

	// Connect to RabbitMQ
	s.conn, err = amqp.Dial(s.config.URL)
	if err != nil {
		return fmt.Errorf("failed to connect to RabbitMQ: %w", err)
	}

	// Create channel
	s.channel, err = s.conn.Channel()
	if err != nil {
		s.conn.Close()
		return fmt.Errorf("failed to create channel: %w", err)
	}

	// Declare exchange (idempotent)
	err = s.channel.ExchangeDeclare(
		s.exchange, // name
		"topic",    // type
		true,       // durable
		false,      // auto-deleted
		false,      // internal
		false,      // no-wait
		nil,        // arguments
	)
	if err != nil {
		s.channel.Close()
		s.conn.Close()
		return fmt.Errorf("failed to declare exchange: %w", err)
	}

	// Declare queue
	_, err = s.channel.QueueDeclare(
		s.queue, // name
		false,   // durable (use false for temporary queues)
		true,    // auto-delete when no consumers
		false,   // exclusive
		false,   // no-wait
		nil,     // arguments
	)
	if err != nil {
		s.channel.Close()
		s.conn.Close()
		return fmt.Errorf("failed to declare queue: %w", err)
	}

	// Bind queue to routing keys if already subscribed
	if len(s.routingKeys) > 0 {
		for _, routingKey := range s.routingKeys {
			err = s.channel.QueueBind(
				s.queue,    // queue name
				routingKey, // routing key
				s.exchange, // exchange
				false,      // no-wait
				nil,        // arguments
			)
			if err != nil {
				s.channel.Close()
				s.conn.Close()
				return fmt.Errorf("failed to bind queue to routing key %s: %w", routingKey, err)
			}
		}
	}

	// Set QoS (prefetch count)
	err = s.channel.Qos(
		10,    // prefetch count
		0,     // prefetch size
		false, // global
	)
	if err != nil {
		s.channel.Close()
		s.conn.Close()
		return fmt.Errorf("failed to set QoS: %w", err)
	}

	// Set up connection close notification
	closeChan := make(chan *amqp.Error)
	s.conn.NotifyClose(closeChan)

	go s.handleClose(closeChan)

	s.logger.Info("Connected to RabbitMQ for subscription",
		zap.String("exchange", s.exchange),
		zap.String("queue", s.queue),
	)

	return nil
}

// handleClose handles connection close events and triggers reconnection.
func (s *RabbitMQSubscriber) handleClose(closeChan chan *amqp.Error) {
	err := <-closeChan
	if err == nil {
		return // Graceful close
	}

	s.logger.Warn("RabbitMQ subscriber connection closed", zap.Error(err))
	s.reconnect()
}

// reconnect attempts to reconnect to RabbitMQ with exponential backoff.
func (s *RabbitMQSubscriber) reconnect() {
	s.mu.Lock()
	if s.closed || s.reconnecting {
		s.mu.Unlock()
		return
	}
	s.reconnecting = true
	s.mu.Unlock()

	defer func() {
		s.mu.Lock()
		s.reconnecting = false
		s.mu.Unlock()
	}()

	// Parse reconnect delays
	reconnectDelay := 5 * time.Second
	maxReconnectWait := 30 * time.Second

	if d, err := time.ParseDuration(s.config.ReconnectDelay); err == nil {
		reconnectDelay = d
	}
	if d, err := time.ParseDuration(s.config.MaxReconnectWait); err == nil {
		maxReconnectWait = d
	}

	delay := reconnectDelay

	for {
		s.mu.RLock()
		if s.closed {
			s.mu.RUnlock()
			return
		}
		s.mu.RUnlock()

		s.logger.Info("Attempting to reconnect subscriber to RabbitMQ",
			zap.Duration("delay", delay),
		)

		time.Sleep(delay)

		if err := s.connect(); err != nil {
			s.logger.Warn("Subscriber reconnection failed",
				zap.Error(err),
				zap.Duration("next_attempt", delay*2),
			)
			delay *= 2
			if delay > maxReconnectWait {
				delay = maxReconnectWait
			}
			continue
		}

		// Restart consumption if handler is set
		s.mu.RLock()
		handler := s.handler
		ctx := s.ctx
		s.mu.RUnlock()

		if handler != nil && ctx != nil {
			go s.consume(ctx, handler)
		}

		s.logger.Info("Subscriber reconnected to RabbitMQ")
		return
	}
}

// Subscribe starts consuming messages from RabbitMQ.
func (s *RabbitMQSubscriber) Subscribe(ctx context.Context, routingKeys []string, handler EventHandler) error {
	s.mu.Lock()
	if s.closed {
		s.mu.Unlock()
		return fmt.Errorf("subscriber is closed")
	}

	// Store handler and context for reconnection
	s.ctx, s.cancel = context.WithCancel(ctx)
	s.handler = handler
	s.routingKeys = routingKeys

	// Bind queue to routing keys
	for _, routingKey := range routingKeys {
		err := s.channel.QueueBind(
			s.queue,    // queue name
			routingKey, // routing key
			s.exchange, // exchange
			false,      // no-wait
			nil,        // arguments
		)
		if err != nil {
			s.mu.Unlock()
			return fmt.Errorf("failed to bind queue to routing key %s: %w", routingKey, err)
		}
	}
	s.mu.Unlock()

	s.logger.Info("Subscribed to routing keys",
		zap.Strings("routing_keys", routingKeys),
		zap.String("queue", s.queue),
	)

	// Start consuming in a goroutine
	go s.consume(s.ctx, handler)

	return nil
}

// consume consumes messages from the queue.
func (s *RabbitMQSubscriber) consume(ctx context.Context, handler EventHandler) {
	s.mu.RLock()
	if s.closed || s.channel == nil {
		s.mu.RUnlock()
		return
	}
	channel := s.channel
	s.mu.RUnlock()

	// Start consuming
	msgs, err := channel.Consume(
		s.queue, // queue
		"",      // consumer tag
		false,   // auto-ack (we'll manually ack)
		false,   // exclusive
		false,   // no-local
		false,   // no-wait
		nil,     // args
	)
	if err != nil {
		s.logger.Error("Failed to start consuming", zap.Error(err))
		return
	}

	s.logger.Info("Started consuming messages from queue", zap.String("queue", s.queue))

	for {
		select {
		case msg, ok := <-msgs:
			if !ok {
				// Channel closed
				s.logger.Info("Message channel closed")
				return
			}

			// Process message
			if err := s.processMessage(msg, handler); err != nil {
				s.logger.Error("Failed to process message",
					zap.Error(err),
					zap.String("routing_key", msg.RoutingKey),
				)
				// Reject and requeue the message
				msg.Nack(false, true)
			} else {
				// Acknowledge successful processing
				msg.Ack(false)
			}

		case <-ctx.Done():
			s.logger.Info("Subscriber context cancelled, stopping consumption")
			return
		}
	}
}

// processMessage processes a single message.
func (s *RabbitMQSubscriber) processMessage(msg amqp.Delivery, handler EventHandler) error {
	s.logger.Debug("Received message",
		zap.String("routing_key", msg.RoutingKey),
		zap.Int("body_size", len(msg.Body)),
	)

	// Validate message
	if !json.Valid(msg.Body) {
		return fmt.Errorf("invalid JSON in message body")
	}

	// Call the handler
	if err := handler(msg.RoutingKey, msg.Body); err != nil {
		return fmt.Errorf("handler error: %w", err)
	}

	return nil
}

// Close closes the subscriber connection.
func (s *RabbitMQSubscriber) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.closed {
		return nil
	}
	s.closed = true

	// Cancel context to stop consumption
	if s.cancel != nil {
		s.cancel()
	}

	var errs []error

	if s.channel != nil {
		if err := s.channel.Close(); err != nil {
			errs = append(errs, err)
		}
	}

	if s.conn != nil {
		if err := s.conn.Close(); err != nil {
			errs = append(errs, err)
		}
	}

	s.logger.Info("RabbitMQ subscriber closed")

	if len(errs) > 0 {
		return fmt.Errorf("errors closing subscriber: %v", errs)
	}
	return nil
}

// NoOpSubscriber is a subscriber that does nothing (for testing or when events disabled).
type NoOpSubscriber struct{}

// NewNoOpSubscriber creates a new no-op subscriber.
func NewNoOpSubscriber() *NoOpSubscriber {
	return &NoOpSubscriber{}
}

func (s *NoOpSubscriber) Subscribe(ctx context.Context, routingKeys []string, handler EventHandler) error {
	return nil
}

func (s *NoOpSubscriber) Close() error {
	return nil
}

// Ensure interface compliance
var _ Subscriber = (*RabbitMQSubscriber)(nil)
var _ Subscriber = (*NoOpSubscriber)(nil)
