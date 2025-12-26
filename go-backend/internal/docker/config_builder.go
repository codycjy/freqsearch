package docker

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/domain"
)

// ConfigBuilder builds runtime configuration files for Freqtrade containers.
type ConfigBuilder struct {
	baseConfigPath string
	logger         *zap.Logger
}

// NewConfigBuilder creates a new ConfigBuilder.
func NewConfigBuilder(baseConfigPath string, logger *zap.Logger) *ConfigBuilder {
	return &ConfigBuilder{
		baseConfigPath: baseConfigPath,
		logger:         logger,
	}
}

// BuildResult contains the result of building a runtime config.
type BuildResult struct {
	// ConfigPath is the path to the generated config file.
	ConfigPath string

	// Cleanup removes the temporary config file.
	Cleanup func()
}

// BuildRuntimeConfig creates a runtime configuration by merging base config with overrides.
// Returns the path to the temporary config file and a cleanup function.
func (b *ConfigBuilder) BuildRuntimeConfig(config domain.BacktestConfig) (*BuildResult, error) {
	// 1. Load base config
	baseConfig, err := b.loadBaseConfig()
	if err != nil {
		return nil, fmt.Errorf("failed to load base config: %w", err)
	}

	// 2. Apply backtest config settings
	b.applyBacktestConfig(baseConfig, config)

	// 3. Apply hyperopt overrides if present
	if config.HyperoptOverrides != nil {
		b.applyOverrides(baseConfig, config.HyperoptOverrides)
	}

	// 4. Write to temporary file
	tmpFile, err := os.CreateTemp("", "freqtrade-config-*.json")
	if err != nil {
		return nil, fmt.Errorf("failed to create temp config file: %w", err)
	}

	encoder := json.NewEncoder(tmpFile)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(baseConfig); err != nil {
		tmpFile.Close()
		os.Remove(tmpFile.Name())
		return nil, fmt.Errorf("failed to write config: %w", err)
	}
	tmpFile.Close()

	b.logger.Debug("Built runtime config",
		zap.String("path", tmpFile.Name()),
		zap.Int("override_count", len(config.HyperoptOverrides)),
	)

	return &BuildResult{
		ConfigPath: tmpFile.Name(),
		Cleanup:    func() { os.Remove(tmpFile.Name()) },
	}, nil
}

// loadBaseConfig loads the base Freqtrade configuration file.
func (b *ConfigBuilder) loadBaseConfig() (map[string]interface{}, error) {
	data, err := os.ReadFile(b.baseConfigPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read base config: %w", err)
	}

	var config map[string]interface{}
	if err := json.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("failed to parse base config: %w", err)
	}

	// Deep copy to avoid modifying cached config
	return deepCopyMap(config), nil
}

// applyBacktestConfig applies the backtest configuration to the runtime config.
func (b *ConfigBuilder) applyBacktestConfig(config map[string]interface{}, btConfig domain.BacktestConfig) {
	// Exchange settings
	if exchange, ok := config["exchange"].(map[string]interface{}); ok {
		exchange["name"] = btConfig.Exchange
	} else {
		config["exchange"] = map[string]interface{}{
			"name": btConfig.Exchange,
		}
	}

	// Transform pairs for futures trading mode
	// Futures pairs need format: "BTC/USDT:USDT" instead of "BTC/USDT"
	pairs := btConfig.Pairs
	if tradingMode, ok := config["trading_mode"].(string); ok && tradingMode == "futures" {
		// Get stake currency from config (defaults to USDT)
		stakeCurrency := "USDT"
		if sc, ok := config["stake_currency"].(string); ok {
			stakeCurrency = sc
		}
		pairs = transformPairsForFutures(btConfig.Pairs, stakeCurrency)
	}

	// Pairs whitelist
	config["exchange"].(map[string]interface{})["pair_whitelist"] = pairs

	// Timeframe
	config["timeframe"] = btConfig.Timeframe

	// Trading settings
	config["max_open_trades"] = btConfig.MaxOpenTrades

	// Set stake_amount with default if empty
	stakeAmount := btConfig.StakeAmount
	if stakeAmount == "" {
		stakeAmount = "unlimited"
	}
	config["stake_amount"] = stakeAmount
	config["dry_run_wallet"] = btConfig.DryRunWallet

	// Disable API server with required fields (Freqtrade requires all fields even when disabled)
	config["api_server"] = map[string]interface{}{
		"enabled":           false,
		"listen_ip_address": "127.0.0.1",
		"listen_port":       8080,
		"username":          "freqtrade",
		"password":          "freqtrade",
	}

	// Timerange is passed via CLI, not config
}

// transformPairsForFutures converts spot pair format to futures format.
// "BTC/USDT" -> "BTC/USDT:USDT"
func transformPairsForFutures(pairs []string, stakeCurrency string) []string {
	result := make([]string, len(pairs))
	suffix := ":" + stakeCurrency

	for i, pair := range pairs {
		// Only add suffix if not already present
		if !strings.Contains(pair, ":") {
			result[i] = pair + suffix
		} else {
			result[i] = pair
		}
	}

	return result
}

// applyOverrides merges hyperopt overrides into the config.
func (b *ConfigBuilder) applyOverrides(config map[string]interface{}, overrides map[string]interface{}) {
	for key, value := range overrides {
		// Handle nested keys like "ask_strategy.use_sell_signal"
		applyNestedValue(config, key, value)
	}
}

// applyNestedValue sets a value in a nested map structure.
// Supports dot notation for nested keys (e.g., "ask_strategy.use_sell_signal").
func applyNestedValue(config map[string]interface{}, key string, value interface{}) {
	parts := splitKey(key)
	current := config

	for i, part := range parts {
		if i == len(parts)-1 {
			// Last part - set the value
			current[part] = value
		} else {
			// Intermediate part - navigate or create nested map
			if next, ok := current[part].(map[string]interface{}); ok {
				current = next
			} else {
				// Create new nested map
				newMap := make(map[string]interface{})
				current[part] = newMap
				current = newMap
			}
		}
	}
}

// splitKey splits a dot-separated key into parts.
func splitKey(key string) []string {
	var parts []string
	current := ""
	for _, c := range key {
		if c == '.' {
			if current != "" {
				parts = append(parts, current)
				current = ""
			}
		} else {
			current += string(c)
		}
	}
	if current != "" {
		parts = append(parts, current)
	}
	return parts
}

// deepCopyMap creates a deep copy of a map.
func deepCopyMap(src map[string]interface{}) map[string]interface{} {
	dst := make(map[string]interface{}, len(src))
	for k, v := range src {
		switch vv := v.(type) {
		case map[string]interface{}:
			dst[k] = deepCopyMap(vv)
		case []interface{}:
			dst[k] = deepCopySlice(vv)
		default:
			dst[k] = v
		}
	}
	return dst
}

// deepCopySlice creates a deep copy of a slice.
func deepCopySlice(src []interface{}) []interface{} {
	dst := make([]interface{}, len(src))
	for i, v := range src {
		switch vv := v.(type) {
		case map[string]interface{}:
			dst[i] = deepCopyMap(vv)
		case []interface{}:
			dst[i] = deepCopySlice(vv)
		default:
			dst[i] = v
		}
	}
	return dst
}

// StrategyInjector handles strategy file preparation.
type StrategyInjector struct {
	logger *zap.Logger
}

// NewStrategyInjector creates a new StrategyInjector.
func NewStrategyInjector(logger *zap.Logger) *StrategyInjector {
	return &StrategyInjector{logger: logger}
}

// InjectResult contains the result of injecting a strategy.
type InjectResult struct {
	// StrategyPath is the path to the strategy file.
	StrategyPath string

	// Cleanup removes the temporary strategy file.
	Cleanup func()
}

// InjectStrategy writes the strategy code to a temporary file.
func (s *StrategyInjector) InjectStrategy(code string, name string) (*InjectResult, error) {
	// Create temporary directory for strategy
	tmpDir, err := os.MkdirTemp("", "freqtrade-strategy-")
	if err != nil {
		return nil, fmt.Errorf("failed to create temp dir: %w", err)
	}

	// Write strategy file
	strategyPath := filepath.Join(tmpDir, name+".py")
	if err := os.WriteFile(strategyPath, []byte(code), 0644); err != nil {
		os.RemoveAll(tmpDir)
		return nil, fmt.Errorf("failed to write strategy file: %w", err)
	}

	s.logger.Debug("Injected strategy",
		zap.String("path", strategyPath),
		zap.String("name", name),
	)

	return &InjectResult{
		StrategyPath: strategyPath,
		Cleanup:      func() { os.RemoveAll(tmpDir) },
	}, nil
}
