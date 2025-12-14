"""Engineer Agent - LangGraph definition.

The Engineer Agent is responsible for:
1. Processing new strategies (fixing syntax, adapting to latest API)
2. Generating hyperparameter search spaces
3. Evolving strategies based on Analyst feedback

Modes:
- "new": Process a newly discovered strategy
- "fix": Fix validation errors in a strategy
- "evolve": Modify strategy based on DiagnosisReport
"""

from typing import Any, Literal

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

import structlog

from ...core.state import EngineerState
from .nodes import (
    analyze_input_node,
    rag_lookup_node,
    generate_code_node,
    validate_code_node,
    generate_metadata_node,
    generate_hyperopt_node,
    submit_node,
)

logger = structlog.get_logger(__name__)


def should_retry(state: EngineerState) -> Literal["retry", "continue", "fail"]:
    """Determine if code generation should be retried.

    Args:
        state: Current agent state

    Returns:
        "retry" if should retry, "continue" if valid, "fail" if max retries reached
    """
    if state["validation_passed"]:
        return "continue"

    if state["retry_count"] >= state["max_retries"]:
        logger.warning(
            "Max retries reached",
            strategy=state["strategy_name"],
            errors=state["validation_errors"],
        )
        return "fail"

    return "retry"


def create_engineer_agent() -> StateGraph:
    """Create the Engineer Agent LangGraph.

    The Engineer Agent workflow:
    1. analyze_input: Determine processing mode and extract info
    2. rag_lookup: Query knowledge base for relevant documentation
    3. generate_code: Generate/modify strategy code using LLM
    4. validate_code: Validate the generated code
    5. If invalid, retry up to max_retries
    6. generate_metadata: Generate description and tags using LLM
    7. generate_hyperopt: Generate hyperparameter configuration
    8. submit: Submit to message queue

    Returns:
        Compiled LangGraph
    """
    workflow = StateGraph(EngineerState)

    # Add nodes
    workflow.add_node("analyze", analyze_input_node)
    workflow.add_node("rag_lookup", rag_lookup_node)
    workflow.add_node("generate", generate_code_node)
    workflow.add_node("validate", validate_code_node)
    workflow.add_node("metadata", generate_metadata_node)
    workflow.add_node("hyperopt", generate_hyperopt_node)
    workflow.add_node("submit", submit_node)

    # Entry point
    workflow.set_entry_point("analyze")

    # Linear flow until validation
    workflow.add_edge("analyze", "rag_lookup")
    workflow.add_edge("rag_lookup", "generate")
    workflow.add_edge("generate", "validate")

    # Conditional edge based on validation result
    workflow.add_conditional_edges(
        "validate",
        should_retry,
        {
            "retry": "generate",  # Retry code generation
            "continue": "metadata",  # Proceed to metadata generation
            "fail": END,  # Give up after max retries
        },
    )

    workflow.add_edge("metadata", "hyperopt")
    workflow.add_edge("hyperopt", "submit")
    workflow.add_edge("submit", END)

    # Use memory checkpointer for retry state
    return workflow.compile(checkpointer=MemorySaver())


async def run_engineer(
    input_data: dict[str, Any],
    mode: str = "new",
    max_retries: int = 3,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Run the Engineer Agent to process a strategy.

    Args:
        input_data: Strategy data or DiagnosisReport
        mode: Processing mode ("new", "fix", "evolve")
        max_retries: Maximum retry attempts for code generation
        thread_id: Optional thread ID for checkpointing

    Returns:
        Final state with generated code and hyperopt config
    """
    logger.info(
        "Starting Engineer Agent",
        mode=mode,
        strategy=input_data.get("name", "unknown"),
    )

    agent = create_engineer_agent()

    # Initialize state
    initial_state: EngineerState = {
        "messages": [],
        "input_data": input_data,
        "mode": mode,
        "strategy_id": input_data.get("id"),
        "strategy_name": input_data.get("name", "unknown"),
        "original_code": input_data.get("code", ""),
        "rag_context": "",
        "generated_code": "",
        "validation_errors": [],
        "validation_passed": False,
        "hyperopt_config": {},
        "description": "",
        "tags": {},
        "retry_count": 0,
        "max_retries": max_retries,
    }

    # Configuration
    config = {
        "configurable": {
            "thread_id": thread_id or f"engineer-{input_data.get('name', 'unknown')}",
        }
    }

    # Run the agent
    final_state = await agent.ainvoke(initial_state, config=config)

    logger.info(
        "Engineer Agent completed",
        strategy=final_state["strategy_name"],
        validation_passed=final_state["validation_passed"],
        retry_count=final_state["retry_count"],
    )

    return final_state
