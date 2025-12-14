#!/bin/bash
set -e

# FreqSearch Proto Generation Script
# Generates Go and Python code from protobuf definitions

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PROTO_DIR="$ROOT_DIR/proto"
GO_OUT_DIR="$ROOT_DIR/go-backend/pkg/pb"
PYTHON_OUT_DIR="$ROOT_DIR/python-agents/src/freqsearch_agents/grpc_client/pb"

echo "=== FreqSearch Proto Generation ==="
echo "Proto dir: $PROTO_DIR"
echo "Go output: $GO_OUT_DIR"
echo "Python output: $PYTHON_OUT_DIR"

# Check for required tools
check_tool() {
    if ! command -v "$1" &> /dev/null; then
        echo "Error: $1 is not installed"
        echo "Install instructions:"
        case "$1" in
            protoc)
                echo "  brew install protobuf"
                ;;
            protoc-gen-go)
                echo "  go install google.golang.org/protobuf/cmd/protoc-gen-go@latest"
                ;;
            protoc-gen-go-grpc)
                echo "  go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest"
                ;;
        esac
        exit 1
    fi
}

check_tool protoc
check_tool protoc-gen-go
check_tool protoc-gen-go-grpc

# Create output directories
mkdir -p "$GO_OUT_DIR/freqsearch/v1"
mkdir -p "$PYTHON_OUT_DIR"

# Generate Go code
echo ""
echo "Generating Go code..."
protoc \
    --proto_path="$PROTO_DIR" \
    --go_out="$GO_OUT_DIR" \
    --go_opt=paths=source_relative \
    --go-grpc_out="$GO_OUT_DIR" \
    --go-grpc_opt=paths=source_relative \
    "$PROTO_DIR/freqsearch/v1/common.proto" \
    "$PROTO_DIR/freqsearch/v1/strategy.proto" \
    "$PROTO_DIR/freqsearch/v1/backtest.proto" \
    "$PROTO_DIR/freqsearch/v1/freqsearch.proto"

echo "Go code generated at: $GO_OUT_DIR"

# Generate Python code
echo ""
echo "Generating Python code..."

# Check for Python gRPC tools
if ! python3 -c "import grpc_tools.protoc" &> /dev/null; then
    echo "Warning: grpcio-tools not installed. Install with:"
    echo "  pip install grpcio-tools"
    echo "Skipping Python generation..."
else
    python3 -m grpc_tools.protoc \
        --proto_path="$PROTO_DIR" \
        --python_out="$PYTHON_OUT_DIR" \
        --pyi_out="$PYTHON_OUT_DIR" \
        --grpc_python_out="$PYTHON_OUT_DIR" \
        "$PROTO_DIR/freqsearch/v1/common.proto" \
        "$PROTO_DIR/freqsearch/v1/strategy.proto" \
        "$PROTO_DIR/freqsearch/v1/backtest.proto" \
        "$PROTO_DIR/freqsearch/v1/freqsearch.proto"

    # Fix Python imports (protoc generates absolute imports, we need relative)
    echo "Fixing Python imports..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS sed
        find "$PYTHON_OUT_DIR" -name "*.py" -exec sed -i '' \
            -e 's/^from freqsearch\.v1 import/from . import/g' \
            -e 's/^import freqsearch\.v1\./from . import /g' \
            {} +
    else
        # Linux sed
        find "$PYTHON_OUT_DIR" -name "*.py" -exec sed -i \
            -e 's/^from freqsearch\.v1 import/from . import/g' \
            -e 's/^import freqsearch\.v1\./from . import /g' \
            {} +
    fi

    # Create __init__.py files for package structure
    touch "$PYTHON_OUT_DIR/freqsearch/__init__.py"
    touch "$PYTHON_OUT_DIR/freqsearch/v1/__init__.py"

    cat > "$PYTHON_OUT_DIR/__init__.py" << 'EOF'
"""Generated protobuf and gRPC code for FreqSearch."""

from .freqsearch.v1.common_pb2 import (
    PaginationRequest,
    PaginationResponse,
    TimeRange,
    JobStatus,
    ApprovalStatus,
    HealthCheckRequest,
    HealthCheckResponse,
)
from .freqsearch.v1.strategy_pb2 import (
    Strategy,
    StrategyMetadata,
    StrategyWithMetrics,
    StrategyPerformanceMetrics,
    CreateStrategyRequest,
    CreateStrategyResponse,
    GetStrategyRequest,
    GetStrategyResponse,
    SearchStrategiesRequest,
    SearchStrategiesResponse,
)
from .freqsearch.v1.backtest_pb2 import (
    BacktestConfig,
    BacktestJob,
    BacktestResult,
    PairResult,
    SubmitBacktestRequest,
    SubmitBacktestResponse,
    GetBacktestJobRequest,
    GetBacktestJobResponse,
    GetBacktestResultRequest,
    GetBacktestResultResponse,
    QueryBacktestResultsRequest,
    QueryBacktestResultsResponse,
)
from .freqsearch.v1.freqsearch_pb2 import (
    OptimizationRun,
    OptimizationConfig,
    OptimizationCriteria,
    OptimizationMode,
    OptimizationStatus,
    OptimizationIteration,
    StartOptimizationRequest,
    StartOptimizationResponse,
    GetOptimizationRunRequest,
    GetOptimizationRunResponse,
)
from .freqsearch.v1.freqsearch_pb2_grpc import (
    FreqSearchServiceStub,
    FreqSearchServiceServicer,
    add_FreqSearchServiceServicer_to_server,
)

__all__ = [
    # Common
    "PaginationRequest",
    "PaginationResponse",
    "TimeRange",
    "JobStatus",
    "ApprovalStatus",
    "HealthCheckRequest",
    "HealthCheckResponse",
    # Strategy
    "Strategy",
    "StrategyMetadata",
    "StrategyWithMetrics",
    "StrategyPerformanceMetrics",
    "CreateStrategyRequest",
    "CreateStrategyResponse",
    "GetStrategyRequest",
    "GetStrategyResponse",
    "SearchStrategiesRequest",
    "SearchStrategiesResponse",
    # Backtest
    "BacktestConfig",
    "BacktestJob",
    "BacktestResult",
    "PairResult",
    "SubmitBacktestRequest",
    "SubmitBacktestResponse",
    "GetBacktestJobRequest",
    "GetBacktestJobResponse",
    "GetBacktestResultRequest",
    "GetBacktestResultResponse",
    "QueryBacktestResultsRequest",
    "QueryBacktestResultsResponse",
    # Optimization
    "OptimizationRun",
    "OptimizationConfig",
    "OptimizationCriteria",
    "OptimizationMode",
    "OptimizationStatus",
    "OptimizationIteration",
    "StartOptimizationRequest",
    "StartOptimizationResponse",
    "GetOptimizationRunRequest",
    "GetOptimizationRunResponse",
    # gRPC
    "FreqSearchServiceStub",
    "FreqSearchServiceServicer",
    "add_FreqSearchServiceServicer_to_server",
]
EOF

    echo "Python code generated at: $PYTHON_OUT_DIR"
fi

echo ""
echo "=== Proto generation complete ==="
