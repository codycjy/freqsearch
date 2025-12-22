// Package http provides HTTP server for health checks, metrics, REST API, and WebSocket.
package http

import (
	"sync"
	"time"
)

// AgentStore manages in-memory agent status from heartbeats.
type AgentStore struct {
	mu      sync.RWMutex
	agents  map[string]*AgentInfo // key: agent type (e.g., "orchestrator")
	timeout time.Duration         // duration after which an agent is considered offline
}

// NewAgentStore creates a new AgentStore with the specified timeout.
func NewAgentStore(timeout time.Duration) *AgentStore {
	store := &AgentStore{
		agents:  make(map[string]*AgentInfo),
		timeout: timeout,
	}
	// Start cleanup routine
	go store.startCleanupRoutine()
	return store
}

// UpdateHeartbeat updates the agent status from a heartbeat event.
func (s *AgentStore) UpdateHeartbeat(agentType, status, currentTask string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	now := time.Now()
	var taskPtr *string
	if currentTask != "" {
		taskPtr = &currentTask
	}

	s.agents[agentType] = &AgentInfo{
		Type:        AgentType(agentType),
		Status:      AgentStatusValue(status),
		LastSeen:    &now,
		CurrentTask: taskPtr,
	}
}

// GetAll returns the status of all known agents.
// Agents that haven't sent a heartbeat within the timeout are marked as offline.
func (s *AgentStore) GetAll() []AgentInfo {
	s.mu.RLock()
	defer s.mu.RUnlock()

	result := make([]AgentInfo, 0, len(s.agents))
	now := time.Now()

	for _, agent := range s.agents {
		info := *agent
		// Check if agent has timed out
		if info.LastSeen != nil && now.Sub(*info.LastSeen) > s.timeout {
			info.Status = AgentStatusOffline
		}
		result = append(result, info)
	}

	return result
}

// GetByType returns the status of a specific agent type.
func (s *AgentStore) GetByType(agentType string) *AgentInfo {
	s.mu.RLock()
	defer s.mu.RUnlock()

	agent, exists := s.agents[agentType]
	if !exists {
		return nil
	}

	info := *agent
	now := time.Now()
	if info.LastSeen != nil && now.Sub(*info.LastSeen) > s.timeout {
		info.Status = AgentStatusOffline
	}

	return &info
}

// startCleanupRoutine periodically cleans up stale agent entries.
func (s *AgentStore) startCleanupRoutine() {
	ticker := time.NewTicker(s.timeout / 2)
	defer ticker.Stop()

	for range ticker.C {
		s.cleanup()
	}
}

// cleanup removes agents that have been offline for too long (2x timeout).
func (s *AgentStore) cleanup() {
	s.mu.Lock()
	defer s.mu.Unlock()

	now := time.Now()
	staleThreshold := s.timeout * 2

	for agentType, agent := range s.agents {
		if agent.LastSeen != nil && now.Sub(*agent.LastSeen) > staleThreshold {
			delete(s.agents, agentType)
		}
	}
}

// AgentHeartbeatPayload represents the JSON payload of a heartbeat event.
type AgentHeartbeatPayload struct {
	AgentType   string `json:"agent_type"`
	Status      string `json:"status"`
	CurrentTask string `json:"current_task,omitempty"`
}
