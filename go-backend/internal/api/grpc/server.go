// Package grpc provides the gRPC server implementation for FreqSearch.
package grpc

import (
	"context"
	"errors"
	"net"
	"strings"

	"github.com/google/uuid"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
	"go.uber.org/zap"
	"google.golang.org/grpc"
	grpccodes "google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/emptypb"

	"github.com/saltfish/freqsearch/go-backend/internal/db/repository"
	"github.com/saltfish/freqsearch/go-backend/internal/domain"
	"github.com/saltfish/freqsearch/go-backend/internal/events"
	"github.com/saltfish/freqsearch/go-backend/internal/scheduler"
	pb "github.com/saltfish/freqsearch/go-backend/pkg/pb/freqsearch/v1"
)

// Server implements the FreqSearchService gRPC server.
type Server struct {
	pb.UnimplementedFreqSearchServiceServer

	repos          *repository.Repositories
	scheduler      *scheduler.Scheduler
	eventPublisher events.Publisher
	logger         *zap.Logger
	tracer         trace.Tracer

	grpcServer *grpc.Server
}

// NewServer creates a new gRPC server.
func NewServer(
	repos *repository.Repositories,
	sched *scheduler.Scheduler,
	eventPublisher events.Publisher,
	logger *zap.Logger,
) *Server {
	return &Server{
		repos:          repos,
		scheduler:      sched,
		eventPublisher: eventPublisher,
		logger:         logger,
		tracer:         otel.Tracer("freqsearch.grpc"),
	}
}

// Start starts the gRPC server.
func (s *Server) Start(address string) error {
	lis, err := net.Listen("tcp", address)
	if err != nil {
		return err
	}

	s.grpcServer = grpc.NewServer()
	pb.RegisterFreqSearchServiceServer(s.grpcServer, s)

	s.logger.Info("gRPC server starting", zap.String("address", address))
	return s.grpcServer.Serve(lis)
}

// Stop gracefully stops the gRPC server.
func (s *Server) Stop() {
	if s.grpcServer != nil {
		s.grpcServer.GracefulStop()
	}
}

// CreateStrategy creates a new strategy.
func (s *Server) CreateStrategy(ctx context.Context, req *pb.CreateStrategyRequest) (*pb.CreateStrategyResponse, error) {
	// Sanitize strategy name to ensure valid Python class name
	sanitizedName := domain.SanitizeStrategyName(req.Name)

	// Also fix class name in code if it doesn't match
	code := req.Code
	if sanitizedName != req.Name {
		// Replace class definition with sanitized name
		code = strings.Replace(code, "class "+req.Name+"(", "class "+sanitizedName+"(", 1)
		s.logger.Info("Sanitized strategy name",
			zap.String("original", req.Name),
			zap.String("sanitized", sanitizedName),
		)
	}

	strategy := &domain.Strategy{
		ID:          uuid.New(),
		Name:        sanitizedName,
		Code:        code,
		Description: req.Description,
	}

	if req.ParentId != nil && *req.ParentId != "" {
		parentID, err := uuid.Parse(*req.ParentId)
		if err != nil {
			return nil, status.Errorf(grpccodes.InvalidArgument, "invalid parent_id: %v", err)
		}
		strategy.ParentID = &parentID
	}

	if err := s.repos.Strategy.Create(ctx, strategy); err != nil {
		if errors.Is(err, domain.ErrDuplicate) {
			return nil, status.Errorf(grpccodes.AlreadyExists, "strategy with same code already exists")
		}
		s.logger.Error("Failed to create strategy", zap.Error(err))
		return nil, status.Errorf(grpccodes.Internal, "failed to create strategy")
	}

	return &pb.CreateStrategyResponse{
		Strategy: domainStrategyToProto(strategy),
	}, nil
}

// GetStrategy gets a strategy by ID.
func (s *Server) GetStrategy(ctx context.Context, req *pb.GetStrategyRequest) (*pb.GetStrategyResponse, error) {
	id, err := uuid.Parse(req.Id)
	if err != nil {
		return nil, status.Errorf(grpccodes.InvalidArgument, "invalid id: %v", err)
	}

	strategy, err := s.repos.Strategy.GetByID(ctx, id)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			return nil, status.Errorf(grpccodes.NotFound, "strategy not found")
		}
		return nil, status.Errorf(grpccodes.Internal, "failed to get strategy")
	}

	return &pb.GetStrategyResponse{
		Strategy: domainStrategyToProto(strategy),
	}, nil
}

// DeleteStrategy deletes a strategy by ID.
func (s *Server) DeleteStrategy(ctx context.Context, req *pb.DeleteStrategyRequest) (*pb.DeleteStrategyResponse, error) {
	id, err := uuid.Parse(req.Id)
	if err != nil {
		return nil, status.Errorf(grpccodes.InvalidArgument, "invalid id: %v", err)
	}

	if err := s.repos.Strategy.Delete(ctx, id); err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			return nil, status.Errorf(grpccodes.NotFound, "strategy not found")
		}
		if errors.Is(err, domain.ErrStrategyInUse) {
			return nil, status.Errorf(grpccodes.FailedPrecondition, "strategy is in use")
		}
		return nil, status.Errorf(grpccodes.Internal, "failed to delete strategy")
	}

	return &pb.DeleteStrategyResponse{}, nil
}

// SubmitBacktest submits a backtest job.
func (s *Server) SubmitBacktest(ctx context.Context, req *pb.SubmitBacktestRequest) (*pb.SubmitBacktestResponse, error) {
	strategyID, err := uuid.Parse(req.StrategyId)
	if err != nil {
		return nil, status.Errorf(grpccodes.InvalidArgument, "invalid strategy_id: %v", err)
	}

	config := protoConfigToDomain(req.Config)
	job := domain.NewBacktestJob(strategyID, config, int(req.Priority), nil)

	if err := s.repos.BacktestJob.Create(ctx, job); err != nil {
		s.logger.Error("Failed to create backtest job", zap.Error(err))
		return nil, status.Errorf(grpccodes.Internal, "failed to create job")
	}

	// Publish task created event
	if err := s.eventPublisher.PublishTaskCreated(job); err != nil {
		s.logger.Warn("Failed to publish task created event", zap.Error(err), zap.String("job_id", job.ID.String()))
	}

	return &pb.SubmitBacktestResponse{
		Job: domainJobToProto(job),
	}, nil
}

// GetBacktestJob gets a backtest job by ID.
func (s *Server) GetBacktestJob(ctx context.Context, req *pb.GetBacktestJobRequest) (*pb.GetBacktestJobResponse, error) {
	id, err := uuid.Parse(req.JobId)
	if err != nil {
		return nil, status.Errorf(grpccodes.InvalidArgument, "invalid job_id: %v", err)
	}

	job, err := s.repos.BacktestJob.GetByID(ctx, id)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			return nil, status.Errorf(grpccodes.NotFound, "job not found")
		}
		return nil, status.Errorf(grpccodes.Internal, "failed to get job")
	}

	return &pb.GetBacktestJobResponse{
		Job: domainJobToProto(job),
	}, nil
}

// GetBacktestResult gets a backtest result.
func (s *Server) GetBacktestResult(ctx context.Context, req *pb.GetBacktestResultRequest) (*pb.GetBacktestResultResponse, error) {
	jobID, err := uuid.Parse(req.JobId)
	if err != nil {
		return nil, status.Errorf(grpccodes.InvalidArgument, "invalid job_id: %v", err)
	}

	result, err := s.repos.Result.GetByJobID(ctx, jobID)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			return nil, status.Errorf(grpccodes.NotFound, "result not found")
		}
		return nil, status.Errorf(grpccodes.Internal, "failed to get result")
	}

	return &pb.GetBacktestResultResponse{
		Result: domainResultToProto(result),
	}, nil
}

// CancelBacktest cancels a backtest job.
func (s *Server) CancelBacktest(ctx context.Context, req *pb.CancelBacktestRequest) (*pb.CancelBacktestResponse, error) {
	id, err := uuid.Parse(req.JobId)
	if err != nil {
		return nil, status.Errorf(grpccodes.InvalidArgument, "invalid job_id: %v", err)
	}

	if err := s.repos.BacktestJob.Cancel(ctx, id); err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			return nil, status.Errorf(grpccodes.NotFound, "job not found")
		}
		if errors.Is(err, domain.ErrJobNotCancellable) {
			return nil, status.Errorf(grpccodes.FailedPrecondition, "job cannot be cancelled")
		}
		return nil, status.Errorf(grpccodes.Internal, "failed to cancel job")
	}

	// Fetch the cancelled job and publish event
	job, err := s.repos.BacktestJob.GetByID(ctx, id)
	if err == nil {
		if err := s.eventPublisher.PublishTaskCancelled(job); err != nil {
			s.logger.Warn("Failed to publish task cancelled event", zap.Error(err), zap.String("job_id", id.String()))
		}
	}

	return &pb.CancelBacktestResponse{}, nil
}

// GetQueueStats gets queue statistics.
func (s *Server) GetQueueStats(ctx context.Context, req *pb.GetQueueStatsRequest) (*pb.GetQueueStatsResponse, error) {
	stats, err := s.repos.BacktestJob.GetQueueStats(ctx)
	if err != nil {
		return nil, status.Errorf(grpccodes.Internal, "failed to get queue stats")
	}

	return &pb.GetQueueStatsResponse{
		PendingJobs:    int32(stats.PendingJobs),
		RunningJobs:    int32(stats.RunningJobs),
		CompletedToday: int32(stats.CompletedToday),
		FailedToday:    int32(stats.FailedToday),
	}, nil
}

// SearchStrategies searches for strategies with filters.
func (s *Server) SearchStrategies(ctx context.Context, req *pb.SearchStrategiesRequest) (*pb.SearchStrategiesResponse, error) {
	ctx, span := s.tracer.Start(ctx, "FreqSearchService.SearchStrategies")
	defer span.End()

	query := protoSearchQueryToDomain(req)
	strategies, totalCount, err := s.repos.Strategy.Search(ctx, query)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "failed to search strategies")
		s.logger.Error("Failed to search strategies", zap.Error(err))
		return nil, status.Errorf(grpccodes.Internal, "failed to search strategies")
	}

	span.SetAttributes(attribute.Int("total_count", totalCount))

	protoStrategies := make([]*pb.StrategyWithMetrics, len(strategies))
	for i, swm := range strategies {
		protoStrategies[i] = domainStrategyWithMetricsToProto(swm)
	}

	pagination := &pb.PaginationResponse{
		TotalCount: int32(totalCount),
		Page:       int32(query.Page),
		PageSize:   int32(query.PageSize),
		TotalPages: int32((totalCount + query.PageSize - 1) / query.PageSize),
	}

	return &pb.SearchStrategiesResponse{
		Strategies: protoStrategies,
		Pagination: pagination,
	}, nil
}

// GetStrategyLineage gets the strategy lineage tree.
func (s *Server) GetStrategyLineage(ctx context.Context, req *pb.GetStrategyLineageRequest) (*pb.GetStrategyLineageResponse, error) {
	ctx, span := s.tracer.Start(ctx, "FreqSearchService.GetStrategyLineage")
	defer span.End()

	strategyID, err := uuid.Parse(req.StrategyId)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "invalid strategy_id")
		return nil, status.Errorf(grpccodes.InvalidArgument, "invalid strategy_id: %v", err)
	}

	span.SetAttributes(
		attribute.String("strategy_id", strategyID.String()),
		attribute.Int("depth", int(req.Depth)),
	)

	lineageNode, err := s.repos.Strategy.GetLineage(ctx, strategyID, int(req.Depth))
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			span.SetStatus(codes.Error, "strategy not found")
			return nil, status.Errorf(grpccodes.NotFound, "strategy not found")
		}
		span.RecordError(err)
		span.SetStatus(codes.Error, "failed to get lineage")
		s.logger.Error("Failed to get strategy lineage", zap.Error(err))
		return nil, status.Errorf(grpccodes.Internal, "failed to get lineage")
	}

	protoLineage := domainLineageNodeToProto(lineageNode)

	return &pb.GetStrategyLineageResponse{
		Lineage: []*pb.StrategyLineageNode{protoLineage},
	}, nil
}

// SubmitBatchBacktest submits multiple backtest jobs.
func (s *Server) SubmitBatchBacktest(ctx context.Context, req *pb.SubmitBatchBacktestRequest) (*pb.SubmitBatchBacktestResponse, error) {
	ctx, span := s.tracer.Start(ctx, "FreqSearchService.SubmitBatchBacktest")
	defer span.End()

	span.SetAttributes(attribute.Int("batch_size", len(req.Backtests)))

	jobs := make([]*domain.BacktestJob, 0, len(req.Backtests))
	for _, btReq := range req.Backtests {
		strategyID, err := uuid.Parse(btReq.StrategyId)
		if err != nil {
			span.RecordError(err)
			span.SetStatus(codes.Error, "invalid strategy_id in batch")
			return nil, status.Errorf(grpccodes.InvalidArgument, "invalid strategy_id: %v", err)
		}

		var optRunID *uuid.UUID
		if btReq.OptimizationRunId != nil && *btReq.OptimizationRunId != "" {
			parsed, err := uuid.Parse(*btReq.OptimizationRunId)
			if err != nil {
				span.RecordError(err)
				span.SetStatus(codes.Error, "invalid optimization_run_id in batch")
				return nil, status.Errorf(grpccodes.InvalidArgument, "invalid optimization_run_id: %v", err)
			}
			optRunID = &parsed
		}

		config := protoConfigToDomain(btReq.Config)
		job := domain.NewBacktestJob(strategyID, config, int(btReq.Priority), optRunID)
		jobs = append(jobs, job)
	}

	if err := s.repos.BacktestJob.CreateBatch(ctx, jobs); err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "failed to create batch")
		s.logger.Error("Failed to create batch backtest jobs", zap.Error(err))
		return nil, status.Errorf(grpccodes.Internal, "failed to create batch jobs")
	}

	// Publish task created events for each job
	for _, job := range jobs {
		if err := s.eventPublisher.PublishTaskCreated(job); err != nil {
			s.logger.Warn("Failed to publish task created event", zap.Error(err), zap.String("job_id", job.ID.String()))
		}
	}

	protoJobs := make([]*pb.BacktestJob, len(jobs))
	for i, job := range jobs {
		protoJobs[i] = domainJobToProto(job)
	}

	return &pb.SubmitBatchBacktestResponse{
		Jobs: protoJobs,
	}, nil
}

// QueryBacktestResults queries backtest results with filters.
func (s *Server) QueryBacktestResults(ctx context.Context, req *pb.QueryBacktestResultsRequest) (*pb.QueryBacktestResultsResponse, error) {
	ctx, span := s.tracer.Start(ctx, "FreqSearchService.QueryBacktestResults")
	defer span.End()

	query := protoBacktestQueryToDomain(req)
	results, totalCount, err := s.repos.Result.Query(ctx, query)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "failed to query results")
		s.logger.Error("Failed to query backtest results", zap.Error(err))
		return nil, status.Errorf(grpccodes.Internal, "failed to query results")
	}

	span.SetAttributes(attribute.Int("total_count", totalCount))

	protoResults := make([]*pb.BacktestResultSummary, len(results))
	for i, result := range results {
		protoResults[i] = domainResultSummaryToProto(result)
	}

	pagination := &pb.PaginationResponse{
		TotalCount: int32(totalCount),
		Page:       int32(query.Page),
		PageSize:   int32(query.PageSize),
		TotalPages: int32((totalCount + query.PageSize - 1) / query.PageSize),
	}

	return &pb.QueryBacktestResultsResponse{
		Results:    protoResults,
		Pagination: pagination,
	}, nil
}

// StartOptimization starts a new optimization run.
func (s *Server) StartOptimization(ctx context.Context, req *pb.StartOptimizationRequest) (*pb.StartOptimizationResponse, error) {
	ctx, span := s.tracer.Start(ctx, "FreqSearchService.StartOptimization")
	defer span.End()

	baseStrategyID, err := uuid.Parse(req.BaseStrategyId)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "invalid base_strategy_id")
		return nil, status.Errorf(grpccodes.InvalidArgument, "invalid base_strategy_id: %v", err)
	}

	span.SetAttributes(
		attribute.String("name", req.Name),
		attribute.String("base_strategy_id", baseStrategyID.String()),
	)

	config := protoOptConfigToDomain(req.Config)
	run := domain.NewOptimizationRun(req.Name, baseStrategyID, config)

	if err := s.repos.Optimization.Create(ctx, run); err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "failed to create optimization run")
		s.logger.Error("Failed to create optimization run", zap.Error(err))
		return nil, status.Errorf(grpccodes.Internal, "failed to create optimization run")
	}

	// Publish optimization started event
	if err := s.eventPublisher.PublishOptimizationStarted(run); err != nil {
		s.logger.Warn("Failed to publish optimization started event", zap.Error(err), zap.String("run_id", run.ID.String()))
	}

	return &pb.StartOptimizationResponse{
		Run: domainOptRunToProto(run),
	}, nil
}

// GetOptimizationRun gets an optimization run with its iterations.
func (s *Server) GetOptimizationRun(ctx context.Context, req *pb.GetOptimizationRunRequest) (*pb.GetOptimizationRunResponse, error) {
	ctx, span := s.tracer.Start(ctx, "FreqSearchService.GetOptimizationRun")
	defer span.End()

	runID, err := uuid.Parse(req.RunId)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "invalid run_id")
		return nil, status.Errorf(grpccodes.InvalidArgument, "invalid run_id: %v", err)
	}

	span.SetAttributes(attribute.String("run_id", runID.String()))

	run, err := s.repos.Optimization.GetByID(ctx, runID)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			span.SetStatus(codes.Error, "optimization run not found")
			return nil, status.Errorf(grpccodes.NotFound, "optimization run not found")
		}
		span.RecordError(err)
		span.SetStatus(codes.Error, "failed to get optimization run")
		s.logger.Error("Failed to get optimization run", zap.Error(err))
		return nil, status.Errorf(grpccodes.Internal, "failed to get optimization run")
	}

	iterations, err := s.repos.Optimization.GetIterations(ctx, runID)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "failed to get iterations")
		s.logger.Error("Failed to get optimization iterations", zap.Error(err))
		return nil, status.Errorf(grpccodes.Internal, "failed to get iterations")
	}

	protoIterations := make([]*pb.OptimizationIteration, len(iterations))
	for i, iter := range iterations {
		protoIterations[i] = domainIterationToProto(iter)

		// Populate result if available
		if iter.ResultID != nil {
			result, err := s.repos.Result.GetByID(ctx, *iter.ResultID)
			if err != nil {
				s.logger.Warn("Failed to load result for iteration",
					zap.Error(err),
					zap.String("iteration_id", iter.ID.String()),
					zap.String("result_id", iter.ResultID.String()))
			} else {
				protoIterations[i].Result = domainResultToProto(result)
			}
		}
	}

	return &pb.GetOptimizationRunResponse{
		Run:        domainOptRunToProto(run),
		Iterations: protoIterations,
	}, nil
}

// ControlOptimization controls an optimization run (pause/resume/cancel).
func (s *Server) ControlOptimization(ctx context.Context, req *pb.ControlOptimizationRequest) (*pb.ControlOptimizationResponse, error) {
	ctx, span := s.tracer.Start(ctx, "FreqSearchService.ControlOptimization")
	defer span.End()

	runID, err := uuid.Parse(req.RunId)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "invalid run_id")
		return nil, status.Errorf(grpccodes.InvalidArgument, "invalid run_id: %v", err)
	}

	span.SetAttributes(
		attribute.String("run_id", runID.String()),
		attribute.String("action", req.Action.String()),
	)

	// Get current status before updating
	oldRun, err := s.repos.Optimization.GetByID(ctx, runID)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			span.SetStatus(codes.Error, "optimization run not found")
			return nil, status.Errorf(grpccodes.NotFound, "optimization run not found")
		}
		span.RecordError(err)
		span.SetStatus(codes.Error, "failed to get optimization run")
		s.logger.Error("Failed to get optimization run", zap.Error(err))
		return nil, status.Errorf(grpccodes.Internal, "failed to get optimization run")
	}
	oldStatus := oldRun.Status.String()

	var newStatus domain.OptimizationStatus
	switch req.Action {
	case pb.OptimizationAction_OPTIMIZATION_ACTION_PAUSE:
		newStatus = domain.OptimizationStatusPaused
	case pb.OptimizationAction_OPTIMIZATION_ACTION_RESUME:
		newStatus = domain.OptimizationStatusRunning
	case pb.OptimizationAction_OPTIMIZATION_ACTION_CANCEL:
		newStatus = domain.OptimizationStatusCancelled
	case pb.OptimizationAction_OPTIMIZATION_ACTION_COMPLETE:
		newStatus = domain.OptimizationStatusCompleted
	case pb.OptimizationAction_OPTIMIZATION_ACTION_FAIL:
		newStatus = domain.OptimizationStatusFailed
	default:
		span.SetStatus(codes.Error, "invalid action")
		return nil, status.Errorf(grpccodes.InvalidArgument, "invalid action")
	}

	if err := s.repos.Optimization.UpdateStatus(ctx, runID, newStatus); err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			span.SetStatus(codes.Error, "optimization run not found")
			return nil, status.Errorf(grpccodes.NotFound, "optimization run not found")
		}
		span.RecordError(err)
		span.SetStatus(codes.Error, "failed to update status")
		s.logger.Error("Failed to control optimization run", zap.Error(err))
		return nil, status.Errorf(grpccodes.Internal, "failed to control optimization")
	}

	run, err := s.repos.Optimization.GetByID(ctx, runID)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "failed to get updated run")
		s.logger.Error("Failed to get optimization run after control", zap.Error(err))
		return nil, status.Errorf(grpccodes.Internal, "failed to get optimization run")
	}

	// Publish optimization status changed event
	if err := s.eventPublisher.PublishOptimizationStatusChanged(run, oldStatus, newStatus.String()); err != nil {
		s.logger.Warn("Failed to publish optimization status changed event",
			zap.Error(err),
			zap.String("run_id", run.ID.String()),
			zap.String("old_status", oldStatus),
			zap.String("new_status", newStatus.String()))
	}

	return &pb.ControlOptimizationResponse{
		Success: true,
		Run:     domainOptRunToProto(run),
	}, nil
}

// ListOptimizationRuns lists optimization runs with filters.
func (s *Server) ListOptimizationRuns(ctx context.Context, req *pb.ListOptimizationRunsRequest) (*pb.ListOptimizationRunsResponse, error) {
	ctx, span := s.tracer.Start(ctx, "FreqSearchService.ListOptimizationRuns")
	defer span.End()

	query := domain.OptimizationListQuery{
		Page:     1,
		PageSize: 20,
	}

	if req.Pagination != nil {
		query.Page = int(req.Pagination.Page)
		query.PageSize = int(req.Pagination.PageSize)
	}
	query.SetDefaults()

	if req.Status != nil {
		status := protoOptStatusToDomain(*req.Status)
		query.Status = &status
	}

	if req.TimeRange != nil {
		query.TimeRange = &domain.TimeRange{
			Start: req.TimeRange.Start.AsTime(),
			End:   req.TimeRange.End.AsTime(),
		}
	}

	runs, totalCount, err := s.repos.Optimization.List(ctx, query)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "failed to list optimization runs")
		s.logger.Error("Failed to list optimization runs", zap.Error(err))
		return nil, status.Errorf(grpccodes.Internal, "failed to list optimization runs")
	}

	span.SetAttributes(attribute.Int("total_count", totalCount))

	protoRuns := make([]*pb.OptimizationRun, len(runs))
	for i, run := range runs {
		protoRuns[i] = domainOptRunToProto(run)
	}

	pagination := &pb.PaginationResponse{
		TotalCount: int32(totalCount),
		Page:       int32(query.Page),
		PageSize:   int32(query.PageSize),
		TotalPages: int32((totalCount + query.PageSize - 1) / query.PageSize),
	}

	return &pb.ListOptimizationRunsResponse{
		Runs:       protoRuns,
		Pagination: pagination,
	}, nil
}

// UpdateIterationResult updates the result ID for an optimization iteration.
func (s *Server) UpdateIterationResult(ctx context.Context, req *pb.UpdateIterationResultRequest) (*emptypb.Empty, error) {
	ctx, span := s.tracer.Start(ctx, "FreqSearchService.UpdateIterationResult")
	defer span.End()

	iterID, err := uuid.Parse(req.IterationId)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "invalid iteration_id")
		return nil, status.Errorf(grpccodes.InvalidArgument, "invalid iteration_id: %v", err)
	}

	resultID, err := uuid.Parse(req.ResultId)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "invalid result_id")
		return nil, status.Errorf(grpccodes.InvalidArgument, "invalid result_id: %v", err)
	}

	span.SetAttributes(
		attribute.String("iteration_id", iterID.String()),
		attribute.String("result_id", resultID.String()),
	)

	if err := s.repos.Optimization.UpdateIterationResult(ctx, iterID, resultID); err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			span.SetStatus(codes.Error, "iteration not found")
			return nil, status.Errorf(grpccodes.NotFound, "iteration not found")
		}
		span.RecordError(err)
		span.SetStatus(codes.Error, "failed to update iteration result")
		s.logger.Error("Failed to update iteration result", zap.Error(err), zap.String("iteration_id", iterID.String()))
		return nil, status.Errorf(grpccodes.Internal, "failed to update iteration result")
	}

	return &emptypb.Empty{}, nil
}

// UpdateIterationFeedback updates the engineer changes and analyst feedback for an optimization iteration.
func (s *Server) UpdateIterationFeedback(ctx context.Context, req *pb.UpdateIterationFeedbackRequest) (*emptypb.Empty, error) {
	ctx, span := s.tracer.Start(ctx, "FreqSearchService.UpdateIterationFeedback")
	defer span.End()

	iterID, err := uuid.Parse(req.IterationId)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "invalid iteration_id")
		return nil, status.Errorf(grpccodes.InvalidArgument, "invalid iteration_id: %v", err)
	}

	span.SetAttributes(
		attribute.String("iteration_id", iterID.String()),
		attribute.String("approval", req.Approval.String()),
	)

	approval := domain.ApprovalStatus(req.Approval.String())

	if err := s.repos.Optimization.UpdateIterationFeedback(ctx, iterID, req.EngineerChanges, req.AnalystFeedback, approval); err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			span.SetStatus(codes.Error, "iteration not found")
			return nil, status.Errorf(grpccodes.NotFound, "iteration not found")
		}
		span.RecordError(err)
		span.SetStatus(codes.Error, "failed to update iteration feedback")
		s.logger.Error("Failed to update iteration feedback", zap.Error(err), zap.String("iteration_id", iterID.String()))
		return nil, status.Errorf(grpccodes.Internal, "failed to update iteration feedback")
	}

	return &emptypb.Empty{}, nil
}

// HealthCheck performs a health check.
func (s *Server) HealthCheck(ctx context.Context, req *pb.HealthCheckRequest) (*pb.HealthCheckResponse, error) {
	// TODO: Add actual health checks for DB, RabbitMQ, Docker
	return &pb.HealthCheckResponse{
		Healthy: true,
		Version: "1.0.0",
		Services: map[string]bool{
			"postgres": true,
			"rabbitmq": true,
			"docker":   true,
		},
	}, nil
}
