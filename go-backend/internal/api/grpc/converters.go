package grpc

import (
	"bytes"
	"compress/gzip"
	"io"
	"strconv"

	"github.com/google/uuid"
	"google.golang.org/protobuf/types/known/timestamppb"

	"github.com/saltfish/freqsearch/go-backend/internal/domain"
	pb "github.com/saltfish/freqsearch/go-backend/pkg/pb/freqsearch/v1"
)

// domainStrategyToProto converts a domain.Strategy to a pb.Strategy.
func domainStrategyToProto(s *domain.Strategy) *pb.Strategy {
	if s == nil {
		return nil
	}

	proto := &pb.Strategy{
		Id:          s.ID.String(),
		Name:        s.Name,
		Code:        s.Code,
		CodeHash:    s.CodeHash,
		Generation:  int32(s.Generation),
		Description: s.Description,
		CreatedAt:   timestamppb.New(s.CreatedAt),
		UpdatedAt:   timestamppb.New(s.UpdatedAt),
	}

	if s.ParentID != nil {
		parentID := s.ParentID.String()
		proto.ParentId = &parentID
	}

	// Build metadata
	metadata := &pb.StrategyMetadata{
		Timeframe:      s.Timeframe,
		Indicators:     s.Indicators,
		TrailingStop:   s.TrailingStop,
		MinimalRoi:     s.MinimalROI,
	}

	if s.Stoploss != nil {
		metadata.Stoploss = *s.Stoploss
	}
	if s.TrailingStopPositive != nil {
		metadata.TrailingStopPositive = *s.TrailingStopPositive
	}
	if s.TrailingStopPositiveOffset != nil {
		metadata.TrailingStopPositiveOffset = *s.TrailingStopPositiveOffset
	}
	if s.StartupCandleCount != nil {
		metadata.StartupCandleCount = int32(*s.StartupCandleCount)
	}

	proto.Metadata = metadata

	return proto
}

// domainJobToProto converts a domain.BacktestJob to a pb.BacktestJob.
func domainJobToProto(job *domain.BacktestJob) *pb.BacktestJob {
	if job == nil {
		return nil
	}

	proto := &pb.BacktestJob{
		Id:         job.ID.String(),
		StrategyId: job.StrategyID.String(),
		Config:     domainConfigToProto(job.Config),
		Status:     domainJobStatusToProto(job.Status),
		Priority:   int32(job.Priority),
		CreatedAt:  timestamppb.New(job.CreatedAt),
	}

	if job.OptimizationRunID != nil {
		optRunID := job.OptimizationRunID.String()
		proto.OptimizationRunId = &optRunID
	}

	if job.ContainerID != nil {
		proto.ContainerId = job.ContainerID
	}

	if job.ErrorMessage != nil {
		proto.ErrorMessage = job.ErrorMessage
	}

	if job.StartedAt != nil {
		proto.StartedAt = timestamppb.New(*job.StartedAt)
	}

	if job.CompletedAt != nil {
		proto.CompletedAt = timestamppb.New(*job.CompletedAt)
	}

	return proto
}

// domainConfigToProto converts a domain.BacktestConfig to a pb.BacktestConfig.
func domainConfigToProto(config domain.BacktestConfig) *pb.BacktestConfig {
	return &pb.BacktestConfig{
		Exchange:       config.Exchange,
		Pairs:          config.Pairs,
		Timeframe:      config.Timeframe,
		TimerangeStart: config.TimerangeStart,
		TimerangeEnd:   config.TimerangeEnd,
		DryRunWallet:   config.DryRunWallet,
		MaxOpenTrades:  int32(config.MaxOpenTrades),
		StakeAmount:    config.StakeAmount,
	}
}

// domainJobStatusToProto converts a domain.JobStatus to a pb.JobStatus.
func domainJobStatusToProto(status domain.JobStatus) pb.JobStatus {
	switch status {
	case domain.JobStatusPending:
		return pb.JobStatus_JOB_STATUS_PENDING
	case domain.JobStatusRunning:
		return pb.JobStatus_JOB_STATUS_RUNNING
	case domain.JobStatusCompleted:
		return pb.JobStatus_JOB_STATUS_COMPLETED
	case domain.JobStatusFailed:
		return pb.JobStatus_JOB_STATUS_FAILED
	case domain.JobStatusCancelled:
		return pb.JobStatus_JOB_STATUS_CANCELLED
	default:
		return pb.JobStatus_JOB_STATUS_UNSPECIFIED
	}
}

// domainResultToProto converts a domain.BacktestResult to a pb.BacktestResult.
func domainResultToProto(result *domain.BacktestResult) *pb.BacktestResult {
	if result == nil {
		return nil
	}

	proto := &pb.BacktestResult{
		Id:             result.ID.String(),
		JobId:          result.JobID.String(),
		StrategyId:     result.StrategyID.String(),
		TotalTrades:    int32(result.TotalTrades),
		WinningTrades:  int32(result.WinningTrades),
		LosingTrades:   int32(result.LosingTrades),
		WinRate:        result.WinRate,
		ProfitTotal:    result.ProfitTotal,
		ProfitPct:      result.ProfitPct,
		MaxDrawdown:    result.MaxDrawdown,
		MaxDrawdownPct: result.MaxDrawdownPct,
		CreatedAt:      timestamppb.New(result.CreatedAt),
	}

	if result.ProfitFactor != nil {
		proto.ProfitFactor = *result.ProfitFactor
	}
	if result.SharpeRatio != nil {
		proto.SharpeRatio = *result.SharpeRatio
	}
	if result.SortinoRatio != nil {
		proto.SortinoRatio = *result.SortinoRatio
	}
	if result.CalmarRatio != nil {
		proto.CalmarRatio = *result.CalmarRatio
	}
	if result.AvgTradeDurationMinutes != nil {
		proto.AvgTradeDurationMinutes = *result.AvgTradeDurationMinutes
	}
	if result.AvgProfitPerTrade != nil {
		proto.AvgProfitPerTrade = *result.AvgProfitPerTrade
	}
	if result.BestTradePct != nil {
		proto.BestTradePct = *result.BestTradePct
	}
	if result.WorstTradePct != nil {
		proto.WorstTradePct = *result.WorstTradePct
	}

	// Convert pair results
	proto.PairResults = make([]*pb.PairResult, len(result.PairResults))
	for i, pr := range result.PairResults {
		proto.PairResults[i] = &pb.PairResult{
			Pair:               pr.Pair,
			Trades:             int32(pr.Trades),
			ProfitPct:          pr.ProfitPct,
			WinRate:            pr.WinRate,
			AvgDurationMinutes: pr.AvgDurationMinutes,
		}
	}

	// Decompress raw log if present
	if len(result.RawLog) > 0 {
		if decompressed, err := decompressGzip(result.RawLog); err == nil {
			proto.RawLog = string(decompressed)
		}
	}

	return proto
}

// protoConfigToDomain converts a pb.BacktestConfig to a domain.BacktestConfig.
func protoConfigToDomain(config *pb.BacktestConfig) domain.BacktestConfig {
	if config == nil {
		return domain.BacktestConfig{}
	}

	return domain.BacktestConfig{
		Exchange:       config.Exchange,
		Pairs:          config.Pairs,
		Timeframe:      config.Timeframe,
		TimerangeStart: config.TimerangeStart,
		TimerangeEnd:   config.TimerangeEnd,
		DryRunWallet:   config.DryRunWallet,
		MaxOpenTrades:  int(config.MaxOpenTrades),
		StakeAmount:    config.StakeAmount,
	}
}

// protoJobStatusToDomain converts a pb.JobStatus to a domain.JobStatus.
func protoJobStatusToDomain(status pb.JobStatus) domain.JobStatus {
	switch status {
	case pb.JobStatus_JOB_STATUS_PENDING:
		return domain.JobStatusPending
	case pb.JobStatus_JOB_STATUS_RUNNING:
		return domain.JobStatusRunning
	case pb.JobStatus_JOB_STATUS_COMPLETED:
		return domain.JobStatusCompleted
	case pb.JobStatus_JOB_STATUS_FAILED:
		return domain.JobStatusFailed
	case pb.JobStatus_JOB_STATUS_CANCELLED:
		return domain.JobStatusCancelled
	default:
		return domain.JobStatusPending
	}
}

// Helper functions

// decompressGzip decompresses gzip-compressed data.
func decompressGzip(data []byte) ([]byte, error) {
	reader, err := gzip.NewReader(bytes.NewReader(data))
	if err != nil {
		return nil, err
	}
	defer reader.Close()

	return io.ReadAll(reader)
}

// stringPtr returns a pointer to the string.
func stringPtr(s string) *string {
	return &s
}

// float64Ptr returns a pointer to the float64.
func float64Ptr(f float64) *float64 {
	return &f
}

// parseInt32 safely parses a string to int32.
func parseInt32(s string) int32 {
	v, _ := strconv.ParseInt(s, 10, 32)
	return int32(v)
}

// parseUUID parses a string to uuid.UUID, returning uuid.Nil on error.
func parseUUID(s string) uuid.UUID {
	id, err := uuid.Parse(s)
	if err != nil {
		return uuid.Nil
	}
	return id
}
