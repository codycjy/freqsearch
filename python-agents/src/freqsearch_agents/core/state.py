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


class SingleIterationState(TypedDict):
    """Minimal state for a single optimization iteration.

    支持两种模式:
    - "baseline": 第0次迭代，运行原始代码获取基准
    - "improve": 第1+次迭代，Analyst-First + Pre-Backtest循环
    """

    # Context (loaded from DB at start)
    optimization_run_id: str
    current_iteration: int
    base_strategy_id: str
    current_strategy_id: str
    backtest_config: dict[str, Any]

    # Input for this iteration
    input_code: str  # Strategy code to process/evolve
    mode: str  # "baseline" | "improve"

    # === Baseline 相关 ===
    baseline_result: dict[str, Any] | None  # baseline backtest 结果
    baseline_strategy_id: str | None  # baseline 使用的策略ID

    # === Analyst-First 相关 ===
    previous_backtest_result: dict[str, Any] | None  # 上次迭代的 backtest 结果
    diagnosis_report: dict[str, Any] | None  # Analyst 的结构化诊断报告

    # === Pre-Backtest 循环相关 ===
    code_iteration_count: int  # 当前代码迭代次数 (内部循环)
    max_code_iterations: int  # 最大代码迭代次数 (默认3)
    code_review_passed: bool  # Analyst 代码审核是否通过
    code_review_feedback: str | None  # Analyst 代码审核反馈

    # Best tracking (for comparison)
    best_sharpe: float
    best_strategy_id: str | None

    # === 改进度量 ===
    improvement_vs_baseline: dict[str, float] | None  # vs baseline 的改进
    improvement_vs_previous: dict[str, float] | None  # vs 上次迭代的改进

    # === 生成的代码 ===
    generated_code: str | None  # Engineer 生成的代码

    # Iteration outputs
    engineer_result: dict[str, Any] | None
    generated_strategy_id: str | None
    backtest_job_id: str | None
    backtest_result: dict[str, Any] | None
    analyst_decision: str | None  # "READY_FOR_LIVE", "NEEDS_MODIFICATION", "ARCHIVE"
    analyst_feedback: str | None

    # Validation tracking (internal retries don't consume iterations)
    validation_passed: bool
    validation_retry_count: int

    # Control outputs (read by external loop)
    should_terminate: bool
    termination_reason: str | None  # "approved", "max_iterations", "archived", "validation_failed"
    is_new_best: bool  # True if this iteration found a better strategy
    new_best_sharpe: float | None


class OrchestratorState(TypedDict):
    """State for Orchestrator Agent (legacy looping design).

    Coordinates the full optimization loop: Engineer → Backtest → Analyst → Decision.
    Note: Being replaced by SingleIterationState + external runner.
    """

    # Conversation messages
    messages: Annotated[list, add_messages]

    # Optimization run tracking
    optimization_run_id: str
    base_strategy_id: str
    current_strategy_id: str
    optimization_config: dict[str, Any]  # Full config including backtest_config

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
    engineer_result: dict[str, Any] | None  # Result from Engineer agent
    analyst_decision: str | None  # "approve", "modify", "archive"
    analyst_feedback: dict[str, Any] | None

    # Termination
    terminated: bool
    termination_reason: str | None

    # Error tracking
    errors: list[str]
