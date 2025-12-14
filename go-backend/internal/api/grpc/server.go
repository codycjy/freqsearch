// Package grpc provides the gRPC server implementation for FreqSearch.
package grpc

import (
	"context"
	"errors"
	"net"

	"github.com/google/uuid"
	"go.uber.org/zap"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"github.com/saltfish/freqsearch/go-backend/internal/db/repository"
	"github.com/saltfish/freqsearch/go-backend/internal/domain"
	"github.com/saltfish/freqsearch/go-backend/internal/scheduler"
	pb "github.com/saltfish/freqsearch/go-backend/pkg/pb/freqsearch/v1"
)

// Server implements the FreqSearchService gRPC server.
type Server struct {
	pb.UnimplementedFreqSearchServiceServer

	repos     *repository.Repositories
	scheduler *scheduler.Scheduler
	logger    *zap.Logger

	grpcServer *grpc.Server
}

// NewServer creates a new gRPC server.
func NewServer(
	repos *repository.Repositories,
	sched *scheduler.Scheduler,
	logger *zap.Logger,
) *Server {
	return &Server{
		repos:     repos,
		scheduler: sched,
		logger:    logger,
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
	strategy := &domain.Strategy{
		ID:          uuid.New(),
		Name:        req.Name,
		Code:        req.Code,
		Description: req.Description,
	}

	if req.ParentId != nil && *req.ParentId != "" {
		parentID, err := uuid.Parse(*req.ParentId)
		if err != nil {
			return nil, status.Errorf(codes.InvalidArgument, "invalid parent_id: %v", err)
		}
		strategy.ParentID = &parentID
	}

	if err := s.repos.Strategy.Create(ctx, strategy); err != nil {
		if errors.Is(err, domain.ErrDuplicate) {
			return nil, status.Errorf(codes.AlreadyExists, "strategy with same code already exists")
		}
		s.logger.Error("Failed to create strategy", zap.Error(err))
		return nil, status.Errorf(codes.Internal, "failed to create strategy")
	}

	return &pb.CreateStrategyResponse{
		Strategy: domainStrategyToProto(strategy),
	}, nil
}

// GetStrategy gets a strategy by ID.
func (s *Server) GetStrategy(ctx context.Context, req *pb.GetStrategyRequest) (*pb.GetStrategyResponse, error) {
	id, err := uuid.Parse(req.Id)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid id: %v", err)
	}

	strategy, err := s.repos.Strategy.GetByID(ctx, id)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			return nil, status.Errorf(codes.NotFound, "strategy not found")
		}
		return nil, status.Errorf(codes.Internal, "failed to get strategy")
	}

	return &pb.GetStrategyResponse{
		Strategy: domainStrategyToProto(strategy),
	}, nil
}

// DeleteStrategy deletes a strategy by ID.
func (s *Server) DeleteStrategy(ctx context.Context, req *pb.DeleteStrategyRequest) (*pb.DeleteStrategyResponse, error) {
	id, err := uuid.Parse(req.Id)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid id: %v", err)
	}

	if err := s.repos.Strategy.Delete(ctx, id); err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			return nil, status.Errorf(codes.NotFound, "strategy not found")
		}
		if errors.Is(err, domain.ErrStrategyInUse) {
			return nil, status.Errorf(codes.FailedPrecondition, "strategy is in use")
		}
		return nil, status.Errorf(codes.Internal, "failed to delete strategy")
	}

	return &pb.DeleteStrategyResponse{}, nil
}

// SubmitBacktest submits a backtest job.
func (s *Server) SubmitBacktest(ctx context.Context, req *pb.SubmitBacktestRequest) (*pb.SubmitBacktestResponse, error) {
	strategyID, err := uuid.Parse(req.StrategyId)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid strategy_id: %v", err)
	}

	config := protoConfigToDomain(req.Config)
	job := domain.NewBacktestJob(strategyID, config, int(req.Priority), nil)

	if err := s.repos.BacktestJob.Create(ctx, job); err != nil {
		s.logger.Error("Failed to create backtest job", zap.Error(err))
		return nil, status.Errorf(codes.Internal, "failed to create job")
	}

	return &pb.SubmitBacktestResponse{
		Job: domainJobToProto(job),
	}, nil
}

// GetBacktestJob gets a backtest job by ID.
func (s *Server) GetBacktestJob(ctx context.Context, req *pb.GetBacktestJobRequest) (*pb.GetBacktestJobResponse, error) {
	id, err := uuid.Parse(req.JobId)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid job_id: %v", err)
	}

	job, err := s.repos.BacktestJob.GetByID(ctx, id)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			return nil, status.Errorf(codes.NotFound, "job not found")
		}
		return nil, status.Errorf(codes.Internal, "failed to get job")
	}

	return &pb.GetBacktestJobResponse{
		Job: domainJobToProto(job),
	}, nil
}

// GetBacktestResult gets a backtest result.
func (s *Server) GetBacktestResult(ctx context.Context, req *pb.GetBacktestResultRequest) (*pb.GetBacktestResultResponse, error) {
	jobID, err := uuid.Parse(req.JobId)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid job_id: %v", err)
	}

	result, err := s.repos.Result.GetByJobID(ctx, jobID)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			return nil, status.Errorf(codes.NotFound, "result not found")
		}
		return nil, status.Errorf(codes.Internal, "failed to get result")
	}

	return &pb.GetBacktestResultResponse{
		Result: domainResultToProto(result),
	}, nil
}

// CancelBacktest cancels a backtest job.
func (s *Server) CancelBacktest(ctx context.Context, req *pb.CancelBacktestRequest) (*pb.CancelBacktestResponse, error) {
	id, err := uuid.Parse(req.JobId)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid job_id: %v", err)
	}

	if err := s.repos.BacktestJob.Cancel(ctx, id); err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			return nil, status.Errorf(codes.NotFound, "job not found")
		}
		if errors.Is(err, domain.ErrJobNotCancellable) {
			return nil, status.Errorf(codes.FailedPrecondition, "job cannot be cancelled")
		}
		return nil, status.Errorf(codes.Internal, "failed to cancel job")
	}

	return &pb.CancelBacktestResponse{}, nil
}

// GetQueueStats gets queue statistics.
func (s *Server) GetQueueStats(ctx context.Context, req *pb.GetQueueStatsRequest) (*pb.GetQueueStatsResponse, error) {
	stats, err := s.repos.BacktestJob.GetQueueStats(ctx)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to get queue stats")
	}

	return &pb.GetQueueStatsResponse{
		PendingJobs:    int32(stats.PendingJobs),
		RunningJobs:    int32(stats.RunningJobs),
		CompletedToday: int32(stats.CompletedToday),
		FailedToday:    int32(stats.FailedToday),
	}, nil
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
