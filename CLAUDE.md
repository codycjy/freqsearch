# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FreqSearch is an AI-powered trading strategy optimization system for Freqtrade. It discovers, engineers, backtests, and evolves trading strategies using LLM-powered agents coordinated through message queues.

## Important: Agent-First Development

**When modifying or analyzing code, always use specialized subagents via the Task tool:**
- Use `python-pro` or `backend-architect` for Python agent code changes
- Use `golang-pro` or `backend-architect` for Go backend changes
- Use `frontend-developer` for React/Refine frontend changes
- Use `debugger` or `error-detective` for investigating issues
- Use `code-reviewer` after significant changes
- Use `Explore` agent for codebase exploration and understanding

**Do NOT directly edit complex code yourself. Delegate to appropriate subagents for:**
- Multi-file refactoring
- Bug fixes requiring deep analysis
- New feature implementation
- Architecture decisions

## Python Environment

**All Python commands MUST use the `freq` conda environment:**

```bash
# Install packages
conda run -n freq pip install -e ".[dev]"
conda run -n freq pip install <package>

# Run agent commands
conda run -n freq python -m freqsearch_agents.main scout
conda run -n freq python -m freqsearch_agents.main engineer <file>
conda run -n freq python -m freqsearch_agents.main analyze <results>
conda run -n freq python -m freqsearch_agents.main serve
conda run -n freq python -m freqsearch_agents.main config

# Run tests
conda run -n freq pytest tests/
conda run -n freq pytest tests/unit/
conda run -n freq ruff check src/
```

## Debug Mode: Background Services

For debugging, start both services in background and monitor logs:

### Start Go Backend (Terminal 1 or background)
```bash
make build && ./go-backend/bin/freqsearch-backend
# Or run in background:
make build && ./go-backend/bin/freqsearch-backend > go-backend.log 2>&1 &
backend listen http://localhost:8083
```

### Start Python Agents (Terminal 2 or background)
```bash
cd python-agents
conda run -n freq python -m src.freqsearch_agents.main serve
# Or run in background:
conda run -n freq python -m src.freqsearch_agents.main serve > agents.log 2>&1 &
```

### Monitor Logs
```bash
tail -f go-backend.log      # Watch Go backend logs
tail -f agents.log          # Watch Python agent logs
```

## Frontend Debugging with MCP Tools

**Always use MCP browser tools (playwright) for frontend inspection:**

```bash
# Use mcp__playwright__browser_navigate to open frontend
# Use mcp__playwright__browser_snapshot to capture page state
# Use mcp__playwright__browser_console_messages to check errors
# Use mcp__playwright__browser_network_requests to inspect API calls
```

**Frontend debugging workflow:**
1. Start frontend: `cd frontend && npm run dev`
2. Use `mcp__playwright__browser_navigate` to open `http://localhost:5173`
3. Use `mcp__playwright__browser_snapshot` to see current page structure
4. Use `mcp__playwright__browser_console_messages` for JavaScript errors
5. Use `mcp__playwright__browser_network_requests` for API debugging
6. Delegate actual code fixes to `frontend-developer` subagent

## Common Commands

### Root Level (Makefile)
```bash
make build              # Build frontend + backend with embedded files
make dev-frontend       # Start Vite dev server
make dev-backend        # Run Go backend
make test               # Run all Go tests
make lint               # Lint frontend + backend
make proto              # Regenerate protobuf code
```

### Go Backend (`go-backend/`)
```bash
cd go-backend
make run                # Run backend server
make build              # Build binary to bin/
make test               # Run all tests with race detector
make lint               # Run golangci-lint
make proto              # Generate protobuf stubs
make migrate-up         # Run database migrations
```

### Frontend (`frontend/`)
```bash
cd frontend
npm run dev       # Start Vite dev server (http://localhost:5173)
npm run build     # Build for production
npm run lint      # ESLint check
```

### Docker (Infrastructure)
```bash
cd docker
docker compose up postgres rabbitmq     # Start infrastructure only
docker compose --profile backend up     # Include Go backend
docker compose --profile agents up      # Include Python agents
```

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│                   (Refine + Ant Design)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST/WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│                        GO BACKEND                                │
│   ┌──────────┐  ┌───────────┐  ┌────────────┐  ┌─────────────┐  │
│   │ HTTP API │  │ gRPC API  │  │ Scheduler  │  │ Docker Mgr  │  │
│   └──────────┘  └───────────┘  └────────────┘  └─────────────┘  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                    Repositories                           │  │
│   └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │ gRPC              │ RabbitMQ          │ PostgreSQL
         ▼                   ▼                   ▼
┌────────────────────────────────────────────────────────────────┐
│                      PYTHON AGENTS                              │
│   ┌────────────┐  ┌─────────────┐  ┌──────────────┐            │
│   │   Scout    │  │  Engineer   │  │   Analyst    │            │
│   │ (discover) │  │  (codegen)  │  │  (analyze)   │            │
│   └────────────┘  └─────────────┘  └──────────────┘            │
│                        LangGraph State Machines                 │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Communication Flow

1. **Scout** discovers strategies from sources → publishes `strategy.discovered`
2. **Go Backend** creates strategy record → publishes `strategy.needs_processing`
3. **Engineer** generates/fixes code → publishes `strategy.ready_for_backtest`
4. **Go Backend** schedules Docker backtest → publishes `backtest.completed`
5. **Analyst** evaluates results → decides: `READY_FOR_LIVE`, `NEEDS_MODIFICATION`, or `ARCHIVE`
6. If `NEEDS_MODIFICATION` → Engineer evolves strategy (loop continues)

### Key Message Queue Events
- `strategy.discovered` - Scout found new strategy
- `strategy.needs_processing` - Strategy needs Engineer processing
- `strategy.ready_for_backtest` - Ready for backtest execution
- `backtest.completed` - Backtest finished
- `strategy.approved` / `strategy.evolve` - Analyst decisions
- `scout.trigger` - Trigger scout run
- `agent.heartbeat` - Agent health status

### gRPC Service (FreqSearchService)

18 RPC methods in `proto/freqsearch/v1/freqsearch.proto`:

**Strategy**: CreateStrategy, GetStrategy, SearchStrategies, GetStrategyLineage, DeleteStrategy
**Backtest**: SubmitBacktest, SubmitBatchBacktest, GetBacktestJob, GetBacktestResult, QueryBacktestResults, CancelBacktest, GetQueueStats
**Optimization**: StartOptimization, GetOptimizationRun, ControlOptimization, ListOptimizationRuns
**Health**: HealthCheck

### Proto Generation

```bash
./scripts/generate_proto.sh   # or: make proto
```
- Go stubs: `go-backend/pkg/pb/freqsearch/v1/`
- Python stubs: `python-agents/src/freqsearch_agents/grpc_client/pb/`

## Directory Structure

```
freqsearch/
├── go-backend/           # Go backend service
│   ├── cmd/server/       # Entry point
│   ├── internal/         # api, config, db, docker, domain, events, scheduler
│   └── pkg/pb/           # Generated protobuf code
├── python-agents/        # Python AI agents
│   └── src/freqsearch_agents/
│       ├── agents/       # Scout, Engineer, Analyst
│       ├── core/         # LLM, messaging, gRPC client
│       ├── grpc_client/  # Generated + wrapper
│       ├── schemas/      # Pydantic models
│       └── tools/        # Code parsing, sources
├── frontend/             # Refine admin dashboard
├── proto/                # Protobuf definitions
├── docker/               # Docker Compose configs
└── configs/              # YAML configuration files
```

## Configuration

Copy `.env.example` to `.env`. Key variables:
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` - LLM provider credentials
- `DATABASE_URL` - PostgreSQL connection
- `RABBITMQ_URL` - Message queue connection
- `GRPC_SERVER` - Go backend gRPC address

## Testing

### Go Backend
```bash
cd go-backend
go test -v ./...                           # All tests
go test -v -run TestStrategyCreate ./...   # Single test
```

### Python Agents
```bash
conda run -n freq pytest tests/
conda run -n freq pytest tests/unit/
conda run -n freq pytest -k "test_code_parser"
```

## Quick Start Development

1. Start infrastructure: `cd docker && docker compose up postgres rabbitmq`
2. Start backend (background): `make build && ./go-backend/bin/freqsearch-backend &`
3. Start agents (background): `cd python-agents && conda run -n freq python -m src.freqsearch_agents.main serve &`
4. Start frontend: `cd frontend && npm run dev`
5. Open browser: Use `mcp__playwright__browser_navigate` to `http://localhost:5173`
