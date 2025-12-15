"""LangGraph state definitions for each agent."""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class ScoutState(TypedDict):
    """State for Scout Agent.

    Tracks the discovery and validation of raw strategies from various sources.
    """

    # Conversation messages (for LLM interactions)
    messages: Annotated[list, add_messages]

    # Current data source being processed
    current_source: str

    # Raw strategies fetched from source
    raw_strategies: list[dict[str, Any]]

    # Strategies after validation
    validated_strategies: list[dict[str, Any]]

    # Strategies after deduplication
    unique_strategies: list[dict[str, Any]]

    # Statistics
    total_fetched: int
    validation_failed: int
    duplicates_removed: int
    submitted_count: int

    # Error tracking
    errors: list[str]


class EngineerState(TypedDict):
    """State for Engineer Agent.

    Tracks the code generation and modification process.
    """

    # Conversation messages
    messages: Annotated[list, add_messages]

    # Input: either RawStrategy or DiagnosisReport
    input_data: dict[str, Any]

    # Processing mode
    mode: str  # "new" | "fix" | "evolve"

    # Strategy being processed
    strategy_id: str | None
    strategy_name: str

    # Original code (for reference)
    original_code: str

    # RAG context retrieved
    rag_context: str

    # Generated/modified code
    generated_code: str

    # Validation results
    validation_errors: list[str]
    validation_passed: bool

    # Hyperopt configuration
    hyperopt_config: dict[str, Any]

    # Generated metadata (description and tags)
    description: str
    tags: dict[str, Any]

    # Retry tracking
    retry_count: int
    max_retries: int


class AnalystState(TypedDict):
    """State for Analyst Agent.

    Tracks the analysis and diagnosis process for backtest results.
    """

    # Conversation messages
    messages: Annotated[list, add_messages]

    # Input: backtest result
    job_id: str
    strategy_id: str
    backtest_result: dict[str, Any]

    # Optimization iteration tracking
    optimization_run_id: str | None  # If part of an optimization run
    current_iteration: int  # Current iteration number (0-indexed)
    max_iterations: int  # Maximum allowed iterations (default: 10)

    # Computed metrics
    metrics: dict[str, float]

    # Trade analysis
    winning_trades: list[dict[str, Any]]
    losing_trades: list[dict[str, Any]]
    trade_context: str  # Market context during trades

    # Diagnosis
    issues: list[str]
    root_causes: list[str]

    # Decision
    decision: str  # "approve" | "modify" | "archive"
    confidence: float

    # Modification suggestions (if decision == "modify")
    suggestion_type: str | None
    suggestion_description: str | None
    target_metrics: list[str]

    # Termination reason (set when iteration limit reached or criteria met)
    termination_reason: str | None


class OrchestratorState(TypedDict):
    """State for Orchestrator Agent.

    Coordinates the full optimization loop: Engineer → Backtest → Analyst → Decision.
    """

    # Conversation messages
    messages: Annotated[list, add_messages]

    # Optimization run tracking
    optimization_run_id: str
    base_strategy_id: str
    current_strategy_id: str

    # Iteration tracking
    current_iteration: int
    max_iterations: int

    # Results tracking
    best_strategy_id: str | None
    best_result: dict[str, Any] | None
    best_sharpe: float

    # Current iteration state
    current_backtest_job_id: str | None
    current_result: dict[str, Any] | None
    analyst_decision: str | None  # "approve", "modify", "archive"
    analyst_feedback: dict[str, Any] | None

    # Termination
    terminated: bool
    termination_reason: str | None

    # Error tracking
    errors: list[str]
