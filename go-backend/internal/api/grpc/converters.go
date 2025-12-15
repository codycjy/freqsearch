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

// protoSearchQueryToDomain converts a pb.SearchStrategiesRequest to a domain.StrategySearchQuery.
func protoSearchQueryToDomain(req *pb.SearchStrategiesRequest) domain.StrategySearchQuery {
	query := domain.StrategySearchQuery{
		OrderBy:   req.OrderBy,
		Ascending: req.Ascending,
	}

	if req.NamePattern != nil {
		query.NamePattern = req.NamePattern
	}
	if req.MinSharpe != nil {
		query.MinSharpe = req.MinSharpe
	}
	if req.MinProfitPct != nil {
		query.MinProfitPct = req.MinProfitPct
	}
	if req.MaxDrawdownPct != nil {
		query.MaxDrawdownPct = req.MaxDrawdownPct
	}
	if req.MinTrades != nil {
		minTrades := int(*req.MinTrades)
		query.MinTrades = &minTrades
	}

	if req.Pagination != nil {
		query.Page = int(req.Pagination.Page)
		query.PageSize = int(req.Pagination.PageSize)
	}

	query.SetDefaults()
	return query
}

// domainStrategyWithMetricsToProto converts a domain.StrategyWithMetrics to a pb.StrategyWithMetrics.
func domainStrategyWithMetricsToProto(swm domain.StrategyWithMetrics) *pb.StrategyWithMetrics {
	proto := &pb.StrategyWithMetrics{
		Strategy: domainStrategyToProto(swm.Strategy),
	}

	if swm.BestResult != nil {
		proto.BestResult = &pb.StrategyPerformanceMetrics{
			ProfitPct:      swm.BestResult.ProfitPct,
			MaxDrawdownPct: swm.BestResult.MaxDrawdownPct,
			TotalTrades:    int32(swm.BestResult.TotalTrades),
			WinRate:        swm.BestResult.WinRate,
		}

		if swm.BestResult.SharpeRatio != nil {
			proto.BestResult.SharpeRatio = *swm.BestResult.SharpeRatio
		}
		if swm.BestResult.SortinoRatio != nil {
			proto.BestResult.SortinoRatio = *swm.BestResult.SortinoRatio
		}
		if swm.BestResult.SharpeRatio != nil {
			proto.BestResult.ProfitFactor = *swm.BestResult.SharpeRatio
		}
	}

	proto.BacktestCount = int32(swm.BestResult.BacktestCount)

	return proto
}

// domainLineageNodeToProto converts a domain.StrategyLineageNode to a pb.StrategyLineageNode.
func domainLineageNodeToProto(node *domain.StrategyLineageNode) *pb.StrategyLineageNode {
	if node == nil {
		return nil
	}

	proto := &pb.StrategyLineageNode{
		Strategy: &pb.Strategy{
			Id:         node.ID.String(),
			Name:       node.Name,
			Generation: int32(node.Generation),
		},
	}

	if node.ParentID != nil {
		parentID := node.ParentID.String()
		proto.Strategy.ParentId = &parentID
	}

	if len(node.Children) > 0 {
		proto.Children = make([]*pb.StrategyLineageNode, len(node.Children))
		for i, child := range node.Children {
			proto.Children[i] = domainLineageNodeToProto(child)
		}
	}

	return proto
}

// protoBacktestQueryToDomain converts a pb.QueryBacktestResultsRequest to a domain.BacktestResultQuery.
func protoBacktestQueryToDomain(req *pb.QueryBacktestResultsRequest) domain.BacktestResultQuery {
	query := domain.BacktestResultQuery{
		OrderBy:   req.OrderBy,
		Ascending: req.Ascending,
	}

	if req.StrategyId != nil && *req.StrategyId != "" {
		strategyID := parseUUID(*req.StrategyId)
		query.StrategyID = &strategyID
	}

	if req.OptimizationRunId != nil && *req.OptimizationRunId != "" {
		optRunID := parseUUID(*req.OptimizationRunId)
		query.OptimizationRunID = &optRunID
	}

	if req.MinSharpe != nil {
		query.MinSharpe = req.MinSharpe
	}
	if req.MinProfitPct != nil {
		query.MinProfitPct = req.MinProfitPct
	}
	if req.MaxDrawdownPct != nil {
		query.MaxDrawdownPct = req.MaxDrawdownPct
	}
	if req.MinTrades != nil {
		minTrades := int(*req.MinTrades)
		query.MinTrades = &minTrades
	}

	if req.TimeRange != nil {
		query.TimeRange = &domain.TimeRange{
			Start: req.TimeRange.Start.AsTime(),
			End:   req.TimeRange.End.AsTime(),
		}
	}

	if req.Pagination != nil {
		query.Page = int(req.Pagination.Page)
		query.PageSize = int(req.Pagination.PageSize)
	}

	query.SetDefaults()
	return query
}

// domainResultSummaryToProto converts a domain.BacktestResult to a pb.BacktestResultSummary.
func domainResultSummaryToProto(r *domain.BacktestResult) *pb.BacktestResultSummary {
	if r == nil {
		return nil
	}

	summary := &pb.BacktestResultSummary{
		Id:             r.ID.String(),
		JobId:          r.JobID.String(),
		StrategyId:     r.StrategyID.String(),
		StrategyName:   "",
		ProfitPct:      r.ProfitPct,
		MaxDrawdownPct: r.MaxDrawdownPct,
		TotalTrades:    int32(r.TotalTrades),
		WinRate:        r.WinRate,
		CreatedAt:      timestamppb.New(r.CreatedAt),
	}

	if r.SharpeRatio != nil {
		summary.SharpeRatio = *r.SharpeRatio
	}

	return summary
}

// protoOptConfigToDomain converts a pb.OptimizationConfig to a domain.OptimizationConfig.
func protoOptConfigToDomain(cfg *pb.OptimizationConfig) domain.OptimizationConfig {
	if cfg == nil {
		return domain.OptimizationConfig{}
	}

	config := domain.OptimizationConfig{
		BacktestConfig: protoConfigToDomain(cfg.BacktestConfig),
		MaxIterations:  int(cfg.MaxIterations),
		Mode:           protoOptModeToDomain(cfg.Mode),
	}

	if cfg.Criteria != nil {
		config.Criteria = domain.OptimizationCriteria{
			MinSharpe:      cfg.Criteria.MinSharpe,
			MinProfitPct:   cfg.Criteria.MinProfitPct,
			MaxDrawdownPct: cfg.Criteria.MaxDrawdownPct,
			MinTrades:      int(cfg.Criteria.MinTrades),
			MinWinRate:     cfg.Criteria.MinWinRate,
		}
	}

	return config
}

// domainOptRunToProto converts a domain.OptimizationRun to a pb.OptimizationRun.
func domainOptRunToProto(run *domain.OptimizationRun) *pb.OptimizationRun {
	if run == nil {
		return nil
	}

	proto := &pb.OptimizationRun{
		Id:               run.ID.String(),
		Name:             run.Name,
		BaseStrategyId:   run.BaseStrategyID.String(),
		Config:           domainOptConfigToProto(run.Config),
		Status:           domainOptStatusToProto(run.Status),
		CurrentIteration: int32(run.CurrentIteration),
		MaxIterations:    int32(run.MaxIterations),
		TerminationReason: run.TerminationReason,
		CreatedAt:        timestamppb.New(run.CreatedAt),
		UpdatedAt:        timestamppb.New(run.UpdatedAt),
	}

	if run.BestStrategyID != nil {
		bestStrategyID := run.BestStrategyID.String()
		proto.BestStrategyId = &bestStrategyID
	}

	if run.CompletedAt != nil {
		proto.CompletedAt = timestamppb.New(*run.CompletedAt)
	}

	return proto
}

// domainOptConfigToProto converts a domain.OptimizationConfig to a pb.OptimizationConfig.
func domainOptConfigToProto(cfg domain.OptimizationConfig) *pb.OptimizationConfig {
	return &pb.OptimizationConfig{
		BacktestConfig: domainConfigToProto(cfg.BacktestConfig),
		MaxIterations:  int32(cfg.MaxIterations),
		Criteria: &pb.OptimizationCriteria{
			MinSharpe:      cfg.Criteria.MinSharpe,
			MinProfitPct:   cfg.Criteria.MinProfitPct,
			MaxDrawdownPct: cfg.Criteria.MaxDrawdownPct,
			MinTrades:      int32(cfg.Criteria.MinTrades),
			MinWinRate:     cfg.Criteria.MinWinRate,
		},
		Mode: domainOptModeToProto(cfg.Mode),
	}
}

// domainIterationToProto converts a domain.OptimizationIteration to a pb.OptimizationIteration.
func domainIterationToProto(iter *domain.OptimizationIteration) *pb.OptimizationIteration {
	if iter == nil {
		return nil
	}

	proto := &pb.OptimizationIteration{
		IterationNumber: int32(iter.IterationNumber),
		StrategyId:      iter.StrategyID.String(),
		BacktestJobId:   iter.BacktestJobID.String(),
		EngineerChanges: iter.EngineerChanges,
		AnalystFeedback: iter.AnalystFeedback,
		Approval:        domainApprovalStatusToProto(iter.Approval),
		Timestamp:       timestamppb.New(iter.CreatedAt),
	}

	return proto
}

// domainOptStatusToProto converts a domain.OptimizationStatus to a pb.OptimizationStatus.
func domainOptStatusToProto(status domain.OptimizationStatus) pb.OptimizationStatus {
	switch status {
	case domain.OptimizationStatusPending:
		return pb.OptimizationStatus_OPTIMIZATION_STATUS_PENDING
	case domain.OptimizationStatusRunning:
		return pb.OptimizationStatus_OPTIMIZATION_STATUS_RUNNING
	case domain.OptimizationStatusPaused:
		return pb.OptimizationStatus_OPTIMIZATION_STATUS_PAUSED
	case domain.OptimizationStatusCompleted:
		return pb.OptimizationStatus_OPTIMIZATION_STATUS_COMPLETED
	case domain.OptimizationStatusFailed:
		return pb.OptimizationStatus_OPTIMIZATION_STATUS_FAILED
	case domain.OptimizationStatusCancelled:
		return pb.OptimizationStatus_OPTIMIZATION_STATUS_CANCELLED
	default:
		return pb.OptimizationStatus_OPTIMIZATION_STATUS_UNSPECIFIED
	}
}

// protoOptStatusToDomain converts a pb.OptimizationStatus to a domain.OptimizationStatus.
func protoOptStatusToDomain(status pb.OptimizationStatus) domain.OptimizationStatus {
	switch status {
	case pb.OptimizationStatus_OPTIMIZATION_STATUS_PENDING:
		return domain.OptimizationStatusPending
	case pb.OptimizationStatus_OPTIMIZATION_STATUS_RUNNING:
		return domain.OptimizationStatusRunning
	case pb.OptimizationStatus_OPTIMIZATION_STATUS_PAUSED:
		return domain.OptimizationStatusPaused
	case pb.OptimizationStatus_OPTIMIZATION_STATUS_COMPLETED:
		return domain.OptimizationStatusCompleted
	case pb.OptimizationStatus_OPTIMIZATION_STATUS_FAILED:
		return domain.OptimizationStatusFailed
	case pb.OptimizationStatus_OPTIMIZATION_STATUS_CANCELLED:
		return domain.OptimizationStatusCancelled
	default:
		return domain.OptimizationStatusPending
	}
}

// domainOptModeToProto converts a domain.OptimizationMode to a pb.OptimizationMode.
func domainOptModeToProto(mode domain.OptimizationMode) pb.OptimizationMode {
	switch mode {
	case domain.OptimizationModeMaximizeSharpe:
		return pb.OptimizationMode_OPTIMIZATION_MODE_MAXIMIZE_SHARPE
	case domain.OptimizationModeMaximizeProfit:
		return pb.OptimizationMode_OPTIMIZATION_MODE_MAXIMIZE_PROFIT
	case domain.OptimizationModeMinimizeDrawdown:
		return pb.OptimizationMode_OPTIMIZATION_MODE_MINIMIZE_DRAWDOWN
	case domain.OptimizationModeBalanced:
		return pb.OptimizationMode_OPTIMIZATION_MODE_BALANCED
	default:
		return pb.OptimizationMode_OPTIMIZATION_MODE_UNSPECIFIED
	}
}

// protoOptModeToDomain converts a pb.OptimizationMode to a domain.OptimizationMode.
func protoOptModeToDomain(mode pb.OptimizationMode) domain.OptimizationMode {
	switch mode {
	case pb.OptimizationMode_OPTIMIZATION_MODE_MAXIMIZE_SHARPE:
		return domain.OptimizationModeMaximizeSharpe
	case pb.OptimizationMode_OPTIMIZATION_MODE_MAXIMIZE_PROFIT:
		return domain.OptimizationModeMaximizeProfit
	case pb.OptimizationMode_OPTIMIZATION_MODE_MINIMIZE_DRAWDOWN:
		return domain.OptimizationModeMinimizeDrawdown
	case pb.OptimizationMode_OPTIMIZATION_MODE_BALANCED:
		return domain.OptimizationModeBalanced
	default:
		return domain.OptimizationModeBalanced
	}
}

// domainApprovalStatusToProto converts a domain.ApprovalStatus to a pb.ApprovalStatus.
func domainApprovalStatusToProto(status domain.ApprovalStatus) pb.ApprovalStatus {
	switch status {
	case domain.ApprovalStatusPending:
		return pb.ApprovalStatus_APPROVAL_STATUS_PENDING
	case domain.ApprovalStatusApproved:
		return pb.ApprovalStatus_APPROVAL_STATUS_APPROVED
	case domain.ApprovalStatusRejected:
		return pb.ApprovalStatus_APPROVAL_STATUS_REJECTED
	case domain.ApprovalStatusNeedsIteration:
		return pb.ApprovalStatus_APPROVAL_STATUS_NEEDS_ITERATION
	default:
		return pb.ApprovalStatus_APPROVAL_STATUS_UNSPECIFIED
	}
}
