// Package parser provides result parsing for Freqtrade backtest output.
package parser

import (
	"bytes"
	"compress/gzip"
	"fmt"
	"regexp"
	"strconv"
	"strings"

	"github.com/google/uuid"
	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/domain"
)

// MaxLogSize is the maximum size of compressed logs to store (1MB).
const MaxLogSize = 1024 * 1024

// Parser parses Freqtrade backtest output into structured results.
type Parser struct {
	logger *zap.Logger
}

// NewParser creates a new Parser.
func NewParser(logger *zap.Logger) *Parser {
	return &Parser{logger: logger}
}

// ParseResult parses Freqtrade backtest output and creates a BacktestResult.
func (p *Parser) ParseResult(logs string, job *domain.BacktestJob) (*domain.BacktestResult, error) {
	// Check for errors in output
	if err := p.checkForErrors(logs); err != nil {
		return nil, err
	}

	// Parse summary statistics
	summary, err := p.parseSummary(logs)
	if err != nil {
		p.logger.Warn("Failed to parse summary, using defaults",
			zap.Error(err),
			zap.String("job_id", job.ID.String()),
		)
		summary = &SummaryStats{}
	}

	// Parse per-pair results
	pairResults := p.parsePairResults(logs)

	// Create result
	result := domain.NewBacktestResult(job.ID, job.StrategyID)

	// Fill in trade statistics
	result.TotalTrades = summary.TotalTrades
	result.WinningTrades = summary.WinningTrades
	result.LosingTrades = summary.LosingTrades
	result.WinRate = summary.WinRate

	// Fill in profit metrics
	result.ProfitTotal = summary.ProfitTotal
	result.ProfitPct = summary.ProfitPct
	if summary.ProfitFactor > 0 {
		result.ProfitFactor = &summary.ProfitFactor
	}

	// Fill in risk metrics
	result.MaxDrawdown = summary.MaxDrawdown
	result.MaxDrawdownPct = summary.MaxDrawdownPct
	if summary.SharpeRatio != 0 {
		result.SharpeRatio = &summary.SharpeRatio
	}
	if summary.SortinoRatio != 0 {
		result.SortinoRatio = &summary.SortinoRatio
	}
	if summary.CalmarRatio != 0 {
		result.CalmarRatio = &summary.CalmarRatio
	}

	// Fill in duration metrics
	if summary.AvgTradeDuration > 0 {
		result.AvgTradeDurationMinutes = &summary.AvgTradeDuration
	}
	if summary.AvgProfitPerTrade != 0 {
		result.AvgProfitPerTrade = &summary.AvgProfitPerTrade
	}
	if summary.BestTradePct != 0 {
		result.BestTradePct = &summary.BestTradePct
	}
	if summary.WorstTradePct != 0 {
		result.WorstTradePct = &summary.WorstTradePct
	}

	// Fill in pair results
	result.PairResults = pairResults

	// Compress and store raw log
	compressed, err := p.compressLog(logs)
	if err != nil {
		p.logger.Warn("Failed to compress log",
			zap.Error(err),
			zap.String("job_id", job.ID.String()),
		)
	} else {
		result.RawLog = compressed
	}

	p.logger.Info("Parsed backtest result",
		zap.String("job_id", job.ID.String()),
		zap.Int("total_trades", result.TotalTrades),
		zap.Float64("profit_pct", result.ProfitPct),
	)

	return result, nil
}

// SummaryStats holds parsed summary statistics.
type SummaryStats struct {
	TotalTrades       int
	WinningTrades     int
	LosingTrades      int
	WinRate           float64
	ProfitTotal       float64
	ProfitPct         float64
	ProfitFactor      float64
	MaxDrawdown       float64
	MaxDrawdownPct    float64
	SharpeRatio       float64
	SortinoRatio      float64
	CalmarRatio       float64
	AvgTradeDuration  float64
	AvgProfitPerTrade float64
	BestTradePct      float64
	WorstTradePct     float64
}

// checkForErrors checks the log output for error indicators.
func (p *Parser) checkForErrors(logs string) error {
	// Check for common error patterns
	errorPatterns := []string{
		"Error:",
		"CRITICAL:",
		"Exception:",
		"Traceback (most recent call last):",
		"Strategy file not found",
		"No data found",
		"ImportError:",
		"ModuleNotFoundError:",
		"SyntaxError:",
	}

	logsLower := strings.ToLower(logs)
	for _, pattern := range errorPatterns {
		if strings.Contains(logsLower, strings.ToLower(pattern)) {
			// Extract error context
			errorMsg := extractErrorMessage(logs, pattern)
			return fmt.Errorf("backtest error: %s", errorMsg)
		}
	}

	return nil
}

// extractErrorMessage extracts the error message from logs.
func extractErrorMessage(logs, pattern string) string {
	idx := strings.Index(strings.ToLower(logs), strings.ToLower(pattern))
	if idx == -1 {
		return "unknown error"
	}

	// Get up to 500 characters starting from the pattern
	end := idx + len(pattern) + 500
	if end > len(logs) {
		end = len(logs)
	}

	snippet := logs[idx:end]

	// Find end of line or message
	if newlineIdx := strings.Index(snippet, "\n"); newlineIdx != -1 {
		snippet = snippet[:newlineIdx]
	}

	return strings.TrimSpace(snippet)
}

// compressLog compresses the log using gzip.
func (p *Parser) compressLog(logs string) ([]byte, error) {
	var buf bytes.Buffer
	gz := gzip.NewWriter(&buf)

	if _, err := gz.Write([]byte(logs)); err != nil {
		return nil, err
	}

	if err := gz.Close(); err != nil {
		return nil, err
	}

	compressed := buf.Bytes()

	// Check size limit
	if len(compressed) > MaxLogSize {
		p.logger.Warn("Compressed log exceeds size limit, truncating",
			zap.Int("size", len(compressed)),
			zap.Int("limit", MaxLogSize),
		)
		// Truncate the original log and re-compress
		truncated := logs
		if len(logs) > 100000 {
			truncated = logs[:50000] + "\n... [truncated] ...\n" + logs[len(logs)-50000:]
		}
		return p.compressLog(truncated)
	}

	return compressed, nil
}

// DecompressLog decompresses a gzip-compressed log.
func DecompressLog(compressed []byte) (string, error) {
	if len(compressed) == 0 {
		return "", nil
	}

	gz, err := gzip.NewReader(bytes.NewReader(compressed))
	if err != nil {
		return "", err
	}
	defer gz.Close()

	var buf bytes.Buffer
	if _, err := buf.ReadFrom(gz); err != nil {
		return "", err
	}

	return buf.String(), nil
}

// Regular expressions for parsing Freqtrade output
var (
	// Summary patterns
	totalTradesRe    = regexp.MustCompile(`(?i)Total[/\s].*Trades?\s*[│|]\s*(\d+)`)
	profitPctRe      = regexp.MustCompile(`(?i)Total profit\s*%?\s*[│|]\s*([-\d.]+)\s*%?`)
	profitAbsRe      = regexp.MustCompile(`(?i)Abs\. profit\s*[│|]\s*([-\d.]+)`)
	sharpeRe         = regexp.MustCompile(`(?i)Sharpe\s*[│|]\s*([-\d.]+)`)
	sortinoRe        = regexp.MustCompile(`(?i)Sortino\s*[│|]\s*([-\d.]+)`)
	calmarRe         = regexp.MustCompile(`(?i)Calmar\s*[│|]\s*([-\d.]+)`)
	maxDrawdownRe    = regexp.MustCompile(`(?i)Max\s*[dD]rawdown\s*[│|]\s*([-\d.]+)\s*%?`)
	maxDrawdownAbsRe = regexp.MustCompile(`(?i)Max\s*[dD]rawdown\s*\([Aa]bs\)\s*[│|]\s*([-\d.]+)`)
	winRateRe        = regexp.MustCompile(`(?i)Win\s*[rR]ate\s*[│|]?\s*([\d.]+)\s*%?\s*\[?(\d+)[/](\d+)\]?`)
	avgDurationRe    = regexp.MustCompile(`(?i)Avg\.\s*[dD]uration\s*[│|]\s*(\d+:\d+:\d+|[\d.]+\s*min)`)
	profitFactorRe   = regexp.MustCompile(`(?i)Profit\s*[fF]actor\s*[│|]\s*([-\d.]+)`)
	bestTradeRe      = regexp.MustCompile(`(?i)Best\s*[tT]rade\s*[│|]\s*([-\d.]+)\s*%?`)
	worstTradeRe     = regexp.MustCompile(`(?i)Worst\s*[tT]rade\s*[│|]\s*([-\d.]+)\s*%?`)
)

// parseSummary extracts summary statistics from Freqtrade output.
func (p *Parser) parseSummary(logs string) (*SummaryStats, error) {
	stats := &SummaryStats{}

	// Parse total trades
	if matches := totalTradesRe.FindStringSubmatch(logs); len(matches) > 1 {
		stats.TotalTrades, _ = strconv.Atoi(matches[1])
	}

	// Parse profit percentage
	if matches := profitPctRe.FindStringSubmatch(logs); len(matches) > 1 {
		stats.ProfitPct, _ = strconv.ParseFloat(matches[1], 64)
	}

	// Parse absolute profit
	if matches := profitAbsRe.FindStringSubmatch(logs); len(matches) > 1 {
		stats.ProfitTotal, _ = strconv.ParseFloat(matches[1], 64)
	}

	// Parse Sharpe ratio
	if matches := sharpeRe.FindStringSubmatch(logs); len(matches) > 1 {
		stats.SharpeRatio, _ = strconv.ParseFloat(matches[1], 64)
	}

	// Parse Sortino ratio
	if matches := sortinoRe.FindStringSubmatch(logs); len(matches) > 1 {
		stats.SortinoRatio, _ = strconv.ParseFloat(matches[1], 64)
	}

	// Parse Calmar ratio
	if matches := calmarRe.FindStringSubmatch(logs); len(matches) > 1 {
		stats.CalmarRatio, _ = strconv.ParseFloat(matches[1], 64)
	}

	// Parse max drawdown percentage
	if matches := maxDrawdownRe.FindStringSubmatch(logs); len(matches) > 1 {
		stats.MaxDrawdownPct, _ = strconv.ParseFloat(matches[1], 64)
	}

	// Parse max drawdown absolute
	if matches := maxDrawdownAbsRe.FindStringSubmatch(logs); len(matches) > 1 {
		stats.MaxDrawdown, _ = strconv.ParseFloat(matches[1], 64)
	}

	// Parse win rate
	if matches := winRateRe.FindStringSubmatch(logs); len(matches) > 3 {
		stats.WinRate, _ = strconv.ParseFloat(matches[1], 64)
		if stats.WinRate > 1 {
			stats.WinRate /= 100 // Convert percentage to decimal
		}
		stats.WinningTrades, _ = strconv.Atoi(matches[2])
		totalFromWinRate, _ := strconv.Atoi(matches[3])
		stats.LosingTrades = totalFromWinRate - stats.WinningTrades
	} else {
		// Calculate winning/losing from total and win rate if available
		if stats.TotalTrades > 0 && stats.WinRate > 0 {
			stats.WinningTrades = int(float64(stats.TotalTrades) * stats.WinRate)
			stats.LosingTrades = stats.TotalTrades - stats.WinningTrades
		}
	}

	// Parse profit factor
	if matches := profitFactorRe.FindStringSubmatch(logs); len(matches) > 1 {
		stats.ProfitFactor, _ = strconv.ParseFloat(matches[1], 64)
	}

	// Parse best trade
	if matches := bestTradeRe.FindStringSubmatch(logs); len(matches) > 1 {
		stats.BestTradePct, _ = strconv.ParseFloat(matches[1], 64)
	}

	// Parse worst trade
	if matches := worstTradeRe.FindStringSubmatch(logs); len(matches) > 1 {
		stats.WorstTradePct, _ = strconv.ParseFloat(matches[1], 64)
	}

	// Parse average duration
	if matches := avgDurationRe.FindStringSubmatch(logs); len(matches) > 1 {
		stats.AvgTradeDuration = parseDuration(matches[1])
	}

	// Calculate average profit per trade
	if stats.TotalTrades > 0 {
		stats.AvgProfitPerTrade = stats.ProfitTotal / float64(stats.TotalTrades)
	}

	return stats, nil
}

// parseDuration parses duration string to minutes.
func parseDuration(s string) float64 {
	s = strings.TrimSpace(s)

	// Try HH:MM:SS format
	if strings.Contains(s, ":") {
		parts := strings.Split(s, ":")
		if len(parts) == 3 {
			hours, _ := strconv.Atoi(parts[0])
			mins, _ := strconv.Atoi(parts[1])
			return float64(hours*60 + mins)
		}
	}

	// Try "X min" format
	if strings.Contains(strings.ToLower(s), "min") {
		s = strings.TrimSuffix(strings.ToLower(s), "min")
		s = strings.TrimSpace(s)
		val, _ := strconv.ParseFloat(s, 64)
		return val
	}

	return 0
}

// Per-pair result parsing patterns
var pairResultRe = regexp.MustCompile(`(?i)([\w/]+:[\w]+)\s+[│|]\s+(\d+)\s+[│|]\s+([-\d.]+)\s*%?\s+[│|]\s+([-\d.]+)\s*%?\s+[│|]`)

// parsePairResults extracts per-pair results from Freqtrade output.
func (p *Parser) parsePairResults(logs string) []domain.PairResult {
	var results []domain.PairResult

	matches := pairResultRe.FindAllStringSubmatch(logs, -1)
	for _, match := range matches {
		if len(match) < 5 {
			continue
		}

		trades, _ := strconv.Atoi(match[2])
		profitPct, _ := strconv.ParseFloat(match[3], 64)
		winRate, _ := strconv.ParseFloat(match[4], 64)
		if winRate > 1 {
			winRate /= 100
		}

		results = append(results, domain.PairResult{
			Pair:      match[1],
			Trades:    trades,
			ProfitPct: profitPct,
			WinRate:   winRate,
		})
	}

	return results
}

// ValidateResult performs basic validation on a parsed result.
func ValidateResult(result *domain.BacktestResult) error {
	if result.ID == uuid.Nil {
		return fmt.Errorf("result ID is empty")
	}
	if result.JobID == uuid.Nil {
		return fmt.Errorf("job ID is empty")
	}
	if result.StrategyID == uuid.Nil {
		return fmt.Errorf("strategy ID is empty")
	}

	// Allow zero trades (strategy may not have triggered any)
	// but warn if other metrics seem inconsistent
	if result.TotalTrades == 0 && result.ProfitPct != 0 {
		return fmt.Errorf("inconsistent: zero trades but non-zero profit")
	}

	return nil
}
