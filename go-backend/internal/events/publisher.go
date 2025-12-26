package events

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	amqp "github.com/rabbitmq/amqp091-go"
	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/config"
	"github.com/saltfish/freqsearch/go-backend/internal/domain"
)

// Publisher provides event publishing to RabbitMQ.
type Publisher interface {
	// Publish publishes an event with the given routing key.
	Publish(ctx context.Context, routingKey string, event interface{}) error

	// PublishTaskCreated publishes a task created event.
	PublishTaskCreated(job *domain.BacktestJob) error

	// PublishTaskRunning publishes a task running event.
	PublishTaskRunning(job *domain.BacktestJob) error

	// PublishTaskCompleted publishes a task completed event.
	PublishTaskCompleted(job *domain.BacktestJob, result *domain.BacktestResult) error

	// PublishTaskFailed publishes a task failed event.
	PublishTaskFailed(job *domain.BacktestJob, errMsg string) error

	// PublishTaskCancelled publishes a task cancelled event.
	PublishTaskCancelled(job *domain.BacktestJob) error

	// PublishOptimizationStarted publishes an optimization started event.
	PublishOptimizationStarted(run *domain.OptimizationRun) error

	// PublishOptimizationIteration publishes an optimization iteration event.
	PublishOptimizationIteration(event *OptimizationIterationEvent) error

	// PublishOptimizationCompleted publishes an optimization completed event.
	PublishOptimizationCompleted(run *domain.OptimizationRun) error

	// PublishOptimizationFailed publishes an optimization failed event.
	PublishOptimizationFailed(run *domain.OptimizationRun, reason string) error

	// PublishOptimizationStatusChanged publishes an optimization status changed event.
	PublishOptimizationStatusChanged(run *domain.OptimizationRun, oldStatus, newStatus string) error

	// PublishScoutTrigger publishes a scout trigger event.
	PublishScoutTrigger(event *ScoutTriggerEvent) error

	// PublishScoutCancelled publishes a scout cancelled event.
	PublishScoutCancelled(runID uuid.UUID) error

	// Close closes the publisher connection.
	Close() error
}

// RabbitMQPublisher implements Publisher using RabbitMQ.
type RabbitMQPublisher struct {
	config   *config.RabbitMQConfig
	conn     *amqp.Connection
	channel  *amqp.Channel
	exchange string
	logger   *zap.Logger

	mu           sync.RWMutex
	closed       bool
	reconnecting bool
}

// NewRabbitMQPublisher creates a new RabbitMQ publisher.
func NewRabbitMQPublisher(cfg *config.RabbitMQConfig, logger *zap.Logger) (*RabbitMQPublisher, error) {
	p := &RabbitMQPublisher{
		config:   cfg,
		exchange: cfg.Exchange,
		logger:   logger,
	}

	if err := p.connect(); err != nil {
		return nil, err
	}

	return p, nil
}

// connect establishes connection to RabbitMQ.
func (p *RabbitMQPublisher) connect() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	if p.closed {
		return fmt.Errorf("publisher is closed")
	}

	var err error

	// Connect to RabbitMQ
	p.conn, err = amqp.Dial(p.config.URL)
	if err != nil {
		return fmt.Errorf("failed to connect to RabbitMQ: %w", err)
	}

	// Create channel
	p.channel, err = p.conn.Channel()
	if err != nil {
		p.conn.Close()
		return fmt.Errorf("failed to create channel: %w", err)
	}

	// Declare exchange
	err = p.channel.ExchangeDeclare(
		p.exchange, // name
		"topic",    // type
		true,       // durable
		false,      // auto-deleted
		false,      // internal
		false,      // no-wait
		nil,        // arguments
	)
	if err != nil {
		p.channel.Close()
		p.conn.Close()
		return fmt.Errorf("failed to declare exchange: %w", err)
	}

	// Set up connection close notification
	closeChan := make(chan *amqp.Error)
	p.conn.NotifyClose(closeChan)

	go p.handleClose(closeChan)

	p.logger.Info("Connected to RabbitMQ",
		zap.String("exchange", p.exchange),
	)

	return nil
}

// handleClose handles connection close events and triggers reconnection.
func (p *RabbitMQPublisher) handleClose(closeChan chan *amqp.Error) {
	err := <-closeChan
	if err == nil {
		return // Graceful close
	}

	p.logger.Warn("RabbitMQ connection closed", zap.Error(err))
	p.reconnect()
}

// reconnect attempts to reconnect to RabbitMQ with exponential backoff.
func (p *RabbitMQPublisher) reconnect() {
	p.mu.Lock()
	if p.closed || p.reconnecting {
		p.mu.Unlock()
		return
	}
	p.reconnecting = true
	p.mu.Unlock()

	defer func() {
		p.mu.Lock()
		p.reconnecting = false
		p.mu.Unlock()
	}()

	// Parse reconnect delays
	reconnectDelay := 5 * time.Second
	maxReconnectWait := 30 * time.Second

	if d, err := time.ParseDuration(p.config.ReconnectDelay); err == nil {
		reconnectDelay = d
	}
	if d, err := time.ParseDuration(p.config.MaxReconnectWait); err == nil {
		maxReconnectWait = d
	}

	delay := reconnectDelay

	for {
		p.mu.RLock()
		if p.closed {
			p.mu.RUnlock()
			return
		}
		p.mu.RUnlock()

		p.logger.Info("Attempting to reconnect to RabbitMQ",
			zap.Duration("delay", delay),
		)

		time.Sleep(delay)

		if err := p.connect(); err != nil {
			p.logger.Warn("Reconnection failed",
				zap.Error(err),
				zap.Duration("next_attempt", delay*2),
			)
			delay *= 2
			if delay > maxReconnectWait {
				delay = maxReconnectWait
			}
			continue
		}

		p.logger.Info("Reconnected to RabbitMQ")
		return
	}
}

// Publish publishes an event with the given routing key.
func (p *RabbitMQPublisher) Publish(ctx context.Context, routingKey string, event interface{}) error {
	p.mu.RLock()
	if p.closed {
		p.mu.RUnlock()
		return fmt.Errorf("publisher is closed")
	}
	if p.channel == nil {
		p.mu.RUnlock()
		return fmt.Errorf("channel not available")
	}
	channel := p.channel
	p.mu.RUnlock()

	// Marshal event to JSON
	body, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	// Publish message
	err = channel.PublishWithContext(
		ctx,
		p.exchange, // exchange
		routingKey, // routing key
		false,      // mandatory
		false,      // immediate
		amqp.Publishing{
			ContentType:  "application/json",
			DeliveryMode: amqp.Persistent,
			Timestamp:    time.Now(),
			Body:         body,
		},
	)
	if err != nil {
		return fmt.Errorf("failed to publish event: %w", err)
	}

	p.logger.Debug("Published event",
		zap.String("routing_key", routingKey),
		zap.Int("body_size", len(body)),
	)

	return nil
}

// PublishTaskRunning publishes a task running event.
func (p *RabbitMQPublisher) PublishTaskRunning(job *domain.BacktestJob) error {
	event := NewTaskRunningEvent(job)
	return p.Publish(context.Background(), RoutingKeyTaskRunning, event)
}

// PublishTaskCompleted publishes a task completed event.
func (p *RabbitMQPublisher) PublishTaskCompleted(job *domain.BacktestJob, result *domain.BacktestResult) error {
	event := NewTaskCompletedEvent(job, result)
	return p.Publish(context.Background(), RoutingKeyTaskCompleted, event)
}

// PublishTaskFailed publishes a task failed event.
func (p *RabbitMQPublisher) PublishTaskFailed(job *domain.BacktestJob, errMsg string) error {
	event := NewTaskFailedEvent(job, errMsg)
	return p.Publish(context.Background(), RoutingKeyTaskFailed, event)
}

// PublishTaskCancelled publishes a task cancelled event.
func (p *RabbitMQPublisher) PublishTaskCancelled(job *domain.BacktestJob) error {
	event := NewTaskCancelledEvent(job)
	return p.Publish(context.Background(), RoutingKeyTaskCancelled, event)
}

// PublishTaskCreated publishes a task created event.
func (p *RabbitMQPublisher) PublishTaskCreated(job *domain.BacktestJob) error {
	event := NewTaskCreatedEvent(job)
	return p.Publish(context.Background(), RoutingKeyTaskCreated, event)
}

// PublishOptimizationStarted publishes an optimization started event.
func (p *RabbitMQPublisher) PublishOptimizationStarted(run *domain.OptimizationRun) error {
	event := NewOptimizationStartedEvent(run)
	err := p.Publish(context.Background(), RoutingKeyOptStarted, event)
	if err != nil {
		p.logger.Error("Failed to publish optimization.started event",
			zap.String("run_id", run.ID.String()),
			zap.Error(err))
	} else {
		p.logger.Info("Published optimization.started event",
			zap.String("run_id", run.ID.String()),
			zap.String("routing_key", RoutingKeyOptStarted))
	}
	return err
}

// PublishOptimizationIteration publishes an optimization iteration event.
func (p *RabbitMQPublisher) PublishOptimizationIteration(event *OptimizationIterationEvent) error {
	return p.Publish(context.Background(), RoutingKeyOptIteration, event)
}

// PublishOptimizationCompleted publishes an optimization completed event.
func (p *RabbitMQPublisher) PublishOptimizationCompleted(run *domain.OptimizationRun) error {
	event := NewOptimizationCompletedEvent(run)
	return p.Publish(context.Background(), RoutingKeyOptCompleted, event)
}

// PublishOptimizationFailed publishes an optimization failed event.
func (p *RabbitMQPublisher) PublishOptimizationFailed(run *domain.OptimizationRun, reason string) error {
	event := NewOptimizationFailedEvent(run, reason)
	return p.Publish(context.Background(), RoutingKeyOptFailed, event)
}

// PublishOptimizationStatusChanged publishes an optimization status changed event.
func (p *RabbitMQPublisher) PublishOptimizationStatusChanged(run *domain.OptimizationRun, oldStatus, newStatus string) error {
	event := NewOptimizationStatusChangedEvent(run, oldStatus, newStatus)
	return p.Publish(context.Background(), RoutingKeyOptStatusChanged, event)
}

// PublishScoutTrigger publishes a scout trigger event.
func (p *RabbitMQPublisher) PublishScoutTrigger(event *ScoutTriggerEvent) error {
	return p.Publish(context.Background(), RoutingKeyScoutTrigger, event)
}

// PublishScoutCancelled publishes a scout cancelled event.
func (p *RabbitMQPublisher) PublishScoutCancelled(runID uuid.UUID) error {
	event := NewScoutCancelledEvent(runID)
	return p.Publish(context.Background(), RoutingKeyScoutCancelled, event)
}

// Close closes the publisher connection.
func (p *RabbitMQPublisher) Close() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	if p.closed {
		return nil
	}
	p.closed = true

	var errs []error

	if p.channel != nil {
		if err := p.channel.Close(); err != nil {
			errs = append(errs, err)
		}
	}

	if p.conn != nil {
		if err := p.conn.Close(); err != nil {
			errs = append(errs, err)
		}
	}

	p.logger.Info("RabbitMQ publisher closed")

	if len(errs) > 0 {
		return fmt.Errorf("errors closing publisher: %v", errs)
	}
	return nil
}

// NoOpPublisher is a publisher that does nothing (for testing or when events disabled).
type NoOpPublisher struct{}

// NewNoOpPublisher creates a new no-op publisher.
func NewNoOpPublisher() *NoOpPublisher {
	return &NoOpPublisher{}
}

func (p *NoOpPublisher) Publish(ctx context.Context, routingKey string, event interface{}) error {
	return nil
}

func (p *NoOpPublisher) PublishTaskCreated(job *domain.BacktestJob) error {
	return nil
}

func (p *NoOpPublisher) PublishTaskRunning(job *domain.BacktestJob) error {
	return nil
}

func (p *NoOpPublisher) PublishTaskCompleted(job *domain.BacktestJob, result *domain.BacktestResult) error {
	return nil
}

func (p *NoOpPublisher) PublishTaskFailed(job *domain.BacktestJob, errMsg string) error {
	return nil
}

func (p *NoOpPublisher) PublishTaskCancelled(job *domain.BacktestJob) error {
	return nil
}

func (p *NoOpPublisher) PublishOptimizationStarted(run *domain.OptimizationRun) error {
	return nil
}

func (p *NoOpPublisher) PublishOptimizationIteration(event *OptimizationIterationEvent) error {
	return nil
}

func (p *NoOpPublisher) PublishOptimizationCompleted(run *domain.OptimizationRun) error {
	return nil
}

func (p *NoOpPublisher) PublishOptimizationFailed(run *domain.OptimizationRun, reason string) error {
	return nil
}

func (p *NoOpPublisher) PublishOptimizationStatusChanged(run *domain.OptimizationRun, oldStatus, newStatus string) error {
	return nil
}

func (p *NoOpPublisher) PublishScoutTrigger(event *ScoutTriggerEvent) error {
	return nil
}

func (p *NoOpPublisher) PublishScoutCancelled(runID uuid.UUID) error {
	return nil
}

func (p *NoOpPublisher) Close() error {
	return nil
}

// Ensure interface compliance
var _ Publisher = (*RabbitMQPublisher)(nil)
var _ Publisher = (*NoOpPublisher)(nil)
